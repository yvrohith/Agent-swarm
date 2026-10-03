"""One offline diagnostic audit. Never call a provider or modify frozen inputs.

Only final content/refusal and model/termination metadata are projected from saved
responses. Provider-private reasoning and credentials are never inspected.
"""

import hashlib
import json
import re
import socket
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from tracebench.evidence_responsiveness.__main__ import inputs, requests, verify_frozen
from tracebench.evidence_responsiveness.common import digest, file_hash, read
from tracebench.evidence_responsiveness.prompts import public_case
from tracebench.evidence_responsiveness.scoring import (
    score_families,
    score_variant,
    select_examples,
    summarize,
)
from tracebench.evidence_responsiveness.wiki import certify_wiki
from tracebench.investigator_utility.execution import _completion, request_payload
from tracebench.investigator_utility.scoring import _unique_object

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "studies/evidence_responsiveness"
OUT = Path(__file__).resolve().parent
RAW = ROOT / "artifacts/evidence-responsiveness"
LOCAL = RAW / "offline-failure-audit"
TERRA_FAMILY = "f_9695d2661a05a12eced27723"
SONNET = "anthropic/claude-sonnet-5.5"
TERRA = "openai/gpt-5.6-terra"
ROLES = ("base", "irrelevant", "decisive")


def strict_json(text):
    return json.loads(text, object_pairs_hook=_unique_object)


def json_candidates(text):
    """Locate disjoint response objects, without mistaking prose time intervals for answers.

    This fixed audit only diagnoses object responses identified by case_id or
    answers. Whole-response root arrays are handled by strict_json first. No
    candidate is chosen among multiple responses or used for primary scoring.
    """
    # A surrounded value is described only if there is a unique outermost
    # decodable object/array. Nested values do not become alternative answers.
    decoder = json.JSONDecoder(object_pairs_hook=_unique_object)
    found = []
    for match in re.finditer(r"[\[{]", text):
        if any(start <= match.start() < end for start, end, _ in found):
            continue
        try:
            value, size = decoder.raw_decode(text[match.start():])
            found.append((match.start(), match.start() + size, value))
        except ValueError:
            pass
    return [(a, b, value) for a, b, value in found if isinstance(value, dict)
            and ({"case_id", "answers"} & value.keys())]


def diagnostic_json(text):
    """Describe encoding/shape only; never substitute a payload into scoring."""
    try:
        return "whole_json", strict_json(text)
    except ValueError as exc:
        if "duplicate JSON key:" in str(exc):
            return "duplicate_json_keys", None
    fence = re.fullmatch(r"\s*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```\s*", text)
    if fence:
        try:
            return "sole_markdown_fence_single_json_value", strict_json(fence[1])
        except ValueError:
            return "malformed_json_inside_fence", None
    found = json_candidates(text)
    if len(found) == 1:
        return "surrounding_prose_single_json_value", found[0][2]
    return ("multiple_or_ambiguous_json_values" if len(found) > 1 else "malformed_json"), None


def container_kind(parsed):
    if not isinstance(parsed, dict):
        return "non_object_root"
    answers = parsed.get("answers")
    if isinstance(answers, dict):
        return "object_valued_answers"
    if not isinstance(answers, list):
        return "other_non_array_answers"
    if set(parsed) != {"case_id", "answers"}:
        return "missing_or_extra_root_fields"
    if any(not isinstance(answer, dict) for answer in answers):
        return "non_object_array_member"
    return "array"


def classify(final, scored, *, finish=None, refusal=False, extraction_defect=False):
    """Apply the saved precedence once, keeping cascades out of primary counts."""
    empty = final is None or final == "" or (isinstance(final, str) and not final.strip())
    representation, parsed = diagnostic_json(final) if isinstance(final, str) and not empty else (
        "empty" if empty else "non_string_final", None)
    shape = container_kind(parsed) if parsed is not None else None
    secondary = []
    candidates = json_candidates(final) if isinstance(final, str) else []
    payload_shapes = [{"start": start, "end": end, "container": container_kind(value),
                       "root_keys": sorted(value) if isinstance(value, dict) else None,
                       "answer_keys": [sorted(a) if isinstance(a, dict) else None
                                       for a in value.get("answers", [])]
                       if isinstance(value, dict) and isinstance(value.get("answers"), list) else None}
                      for start, end, value in candidates]
    if isinstance(final, str) and "```" in final:
        secondary.append("markdown_fence_present")
    if len(candidates) > 1:
        secondary.append("multiple_json_candidates_not_selected")
    if shape and shape != "array":
        secondary.append(shape)
    if finish in {"length", "max_tokens"}:
        secondary.append("provider_truncation")
    if refusal or finish in {"content_filter", "refusal"}:
        primary, subtype, attribution = "provider_refusal_or_filter", "declared_refusal_or_filter", "provider_outcome"
        explanation = "Provider refusal/filter metadata is present; downstream parser failures are not separate causes."
    elif extraction_defect:
        primary, subtype, attribution = "acceptance_affecting_extraction_mismatch", "verified_difference", "implementation_defect"
        explanation = "A demonstrated extraction difference changes acceptance or the final answer."
    elif empty:
        primary, subtype, attribution = "empty_final_without_refusal", "empty_or_absent", "undetermined"
        explanation = "The actual final-content field is absent/empty; no provider refusal was recorded."
    elif representation != "whole_json":
        primary, subtype, attribution = "serialization_violation", representation, "explicit_instruction_violation"
        explanation = "Nonempty final content is not the requested single JSON object; the frozen parser consumes the whole string."
        if representation == "surrounding_prose_single_json_value":
            explanation = "Leading/surrounding prose accompanies one identifiable JSON response object; the whole final output is not JSON."
        elif representation == "multiple_or_ambiguous_json_values":
            explanation = "The final output contains multiple identifiable JSON response objects; no candidate is selected or repaired for scoring."
    elif shape != "array":
        primary, subtype = "root_or_answers_container_violation", shape
        attribution = "prompt_underspecification" if shape == "object_valued_answers" else "explicit_instruction_violation"
        explanation = "Decoded final JSON violates the frozen root/answers container contract."
    else:
        identity = {"wrong_case_id", "unknown_claim_id", "missing_claim", "duplicate_claim"}
        errors = set(scored["schema_errors"]) | set(scored["response_errors"])
        if identity & errors:
            primary = "case_or_claim_identity_violation"
            subtype = "+".join(sorted(identity & errors))
            attribution = "explicit_instruction_violation"
            explanation = "Whole-response JSON parsed, but its case/claim identities do not match the supplied opaque IDs."
            if any("id" in a and "claim_id" not in a for a in parsed["answers"]):
                secondary.append("id_instead_of_claim_id")
                explanation = "The answer uses id instead of the explicitly required claim_id; the expected claim is therefore missing."
        elif not scored["completion_valid"]:
            primary = "answer_field_or_value_violation"
            subtype = "+".join(sorted(errors)) or "termination_violation"
            attribution = "explicit_instruction_violation"
            explanation = "IDs and containers pass; required answer fields, values, lengths, or termination do not."
            if any("id" in a and "claim_id" in a for a in parsed["answers"]):
                secondary.append("extra_id_alongside_claim_id")
                explanation = "The answer includes both id and claim_id; id is an extra field forbidden by the exact four-field instruction."
        else:
            primary, subtype, attribution = "accepted", "frozen_contract_valid", "none"
            explanation = "The exact original final output passes the frozen contract; semantic correctness is separately recorded."
    return {"primary_cause": primary, "subtype": subtype, "attribution": attribution,
            "explanation": explanation, "secondary_flags": secondary,
            "diagnostic_representation": representation, "diagnostic_answers_shape": shape,
            "diagnostic_payload_shapes": payload_shapes,
            "actual_final_empty": empty,
            "annotation_method": "deterministic final-output inspection plus AI-assisted source/output audit; no human validation"}


def final_projection(path):
    """No raw envelope export: only explicitly allowed final-output fields."""
    saved = read(path)
    response = saved["raw_response"]
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    final = message.get("content")
    refusal = message.get("refusal")
    safe = {"choices": [{"message": {"content": final}}]}
    return {"final_content": final, "saved_completion_text": saved.get("completion_text"),
            "adapter_extracted": _completion(safe, "openrouter"),
            "finish_reason": choice.get("finish_reason"), "refusal": refusal,
            "response_model": response.get("model"), "provider": response.get("provider")}


def historical_hashes():
    baseline = read(OUT / "baseline.json")
    for name, expected in baseline["input_sha256"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError(f"Historical input changed: {name}")
    return len(baseline["input_sha256"])


def load_verified():
    historical_hashes()
    frozen = verify_frozen()
    cases, golds, families = inputs()
    config = read(STUDY / "frozen/config.json")
    schedule = requests(cases, families, config)
    assert digest(schedule) == frozen["public_schedule_sha256"]
    assert read(RAW / "calls/schedule.json")["requests"] == schedule
    ledger = RAW / "calls/attempts.jsonl"
    assert file_hash(ledger) == read(STUDY / "results/execution.json")["ledger_sha256"]
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    completed, registered = {}, {}
    for event in events:
        if event["event"] == "attempt_completed":
            completed.setdefault(event["attempt_key"], event)
        if event["event"] == "request":
            registered[event["attempt_key"]] = event
    by_case = {c["case_id"]: c for c in cases}
    by_gold = {g["case_id"]: g for g in golds}
    models = {m["model_id"]: m for m in config["models"]}
    manifests = {m["attempt_key"]: m for m in read(STUDY / "results/response_manifest.json")}
    saved_scores = {(r["model_id"], r["case_id"]): r
                    for r in read(STUDY / "results/per_variant.json")}
    items, rows = [], []
    for request in schedule:
        if request["split"] != "evaluation":
            continue
        key = request["attempt_key"]
        manifest = manifests[key]
        assert registered[key]["request_sha256"] == manifest["request_sha256"] == digest(request)
        req_path = RAW / "calls/requests" / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        req = read(req_path)
        assert set(req) == {"public_request", "provider_payload"}
        assert req["public_request"] == request
        assert req["provider_payload"] == request_payload(request, models[request["model_id"]])
        response_path = RAW / "calls" / completed[key]["response_file"]
        assert file_hash(response_path) == manifest["response_sha256"]
        final = final_projection(response_path)
        # All retained outputs must follow the adapter exactly; do not silently
        # replace any mismatched output with the visible source value.
        assert final["adapter_extracted"] == final["saved_completion_text"]
        assert final["response_model"] == manifest["response_model"] == request["model_id"]
        assert final["provider"] == manifest["provider"]
        assert final["finish_reason"] == manifest["finish_reason"]
        row = score_variant(by_case[request["case_id"]], by_gold[request["case_id"]],
                            final["saved_completion_text"], request["model_id"],
                            final["finish_reason"], refused=bool(final["refusal"]))
        assert row == saved_scores[(request["model_id"], request["case_id"])]
        rows.append(row)
        items.append({"request": request, "provider_payload": req["provider_payload"],
                      "request_file": str(req_path.relative_to(ROOT)),
                      "request_file_sha256": file_hash(req_path),
                      "response_file": str(response_path.relative_to(ROOT)),
                      "response_file_sha256": file_hash(response_path), "final": final, "score": row})
    eval_families = [f for f in families if f["split"] == "evaluation"]
    paired = score_families(rows, eval_families, model_ids=list(models))
    assert paired == read(STUDY / "results/per_family.json")
    assert summarize(paired) == read(STUDY / "results/summary.json")
    assert select_examples(paired) == read(STUDY / "results/examples.json")
    assert all(f["metrics"][m] == f["metrics"]["strict_" + m] for f in paired
               for m in ("decisive_pair_correct", "invariant_pair_correct", "whole_family_correct"))
    return cases, golds, families, items, rows, paired


def field_differences(left, right, path=""):
    """All changed leaf paths; full values stay in the ignored exact package."""
    if left == right:
        return []
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return [v for key in sorted(left) for v in field_differences(left[key], right[key], path + "/" + key)]
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [v for i, (a, b) in enumerate(zip(left, right, strict=True))
                for v in field_differences(a, b, path + "/" + str(i))]
    return [{"path": path, "before_sha256": digest(left), "after_sha256": digest(right)}]


def terra_audit(cases, golds, families, items):
    family = next(f for f in families if f["family_id"] == TERRA_FAMILY)
    assert family["motif"] == "inserted_versus_inherited"
    indexed = {c["case_id"]: c for c in cases}
    gold = {g["case_id"]: g for g in golds}
    calls = {i["request"]["case_id"]: i for i in items if i["request"]["model_id"] == TERRA}
    variants, summaries = {}, {}
    for role in ROLES:
        identifier = family["variants"][role]
        case, certificate, item = indexed[identifier], gold[identifier], calls[identifier]
        assert certify_wiki(case) == certificate
        public = public_case(case)
        request_evidence = item["request"]["user"].split("\nBEGIN_EVIDENCE\n", 1)[1].rsplit("\nEND_EVIDENCE\n", 1)[0]
        assert json.loads(request_evidence) == public
        assert item["final"]["final_content"] == item["final"]["saved_completion_text"]
        answer = strict_json(item["final"]["final_content"])["answers"][0]
        cert = certificate["claims"][0]["certificate"]
        variants[role] = {"case": case, "certificate": certificate, "execution": item,
                          "decoded_final_answer": answer}
        summaries[role] = {"case_id": identifier,
            "gold_status": certificate["claims"][0]["status"], "returned_status": answer["status"],
            "cited_ids": answer["evidence_ids"], "final_content_sha256": digest(item["final"]["final_content"]),
            "score": item["score"], "request_file": item["request_file"],
            "request_file_sha256": item["request_file_sha256"], "public_request_sha256": digest(item["request"]),
            "canonical_provider_payload_sha256": digest(item["provider_payload"]),
            "response_file": item["response_file"], "response_file_sha256": item["response_file_sha256"],
            "public_case_sha256": digest(public),
            "record_text_sha256": {r["id"]: r["text_sha256"] for r in case["records"]},
            **{key: cert[key] for key in ("predecessor_matches", "target_matches", "opcodes",
                                         "qualifying_spans", "classifications")}}
    differences = {}
    base = variants["base"]
    for role in ("irrelevant", "decisive"):
        variant = variants[role]
        edits = []
        for a, b in zip(base["case"]["records"], variant["case"]["records"], strict=True):
            assert len(a["text"]) == len(b["text"])
            edits += [{"record_id": a["id"], "offset": i, "before": x, "after": y}
                      for i, (x, y) in enumerate(zip(a["text"], b["text"], strict=True)) if x != y]
        assert edits == family["transformations"][role + "_from_base"]
        differences[role] = {"text_edits": edits,
            "public_case_changes": field_differences(public_case(base["case"]), public_case(variant["case"])),
            "public_request_changes": field_differences(base["execution"]["request"], variant["execution"]["request"]),
            "provider_payload_changes": field_differences(base["execution"]["provider_payload"], variant["execution"]["provider_payload"])}
    private = {"family": family, "variants": variants, "all_request_differences": differences,
               "note": "Full exact fixture/request/final-visible output package; no provider-private reasoning."}
    pairwise = {a + "_to_" + b: {
        "public_case": field_differences(public_case(variants[a]["case"]), public_case(variants[b]["case"])),
        "public_request": field_differences(variants[a]["execution"]["request"], variants[b]["execution"]["request"]),
        "provider_payload": field_differences(variants[a]["execution"]["provider_payload"], variants[b]["execution"]["provider_payload"])}
        for a, b in (("base", "irrelevant"), ("base", "decisive"), ("irrelevant", "decisive"))}
    private["pairwise_request_differences"] = pairwise
    summary = {"family_id": family["family_id"], "motif": family["motif"], "variants": summaries,
               "base_comparisons": differences, "certificates_reproduced": 3,
               "pairwise_request_differences": pairwise,
               "public_package_note": "Complete texts, final explanations and provenance remain in the ignored package.",
               "alignment_limit": "Both classifier checks share SequenceMatcher; not independent alignment or human validation.",
               "causal_limit": "One sample each; case IDs and derived hashes also change. The text edit alone is not causally isolated."}
    return summary, private


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    def blocked(*args, **kwargs):
        raise RuntimeError("Offline audit forbids socket/network access")
    socket.socket.connect = socket.socket.connect_ex = blocked
    socket.create_connection = socket.getaddrinfo = blocked
    cases, golds, families, items, rows, paired = load_verified()
    mapping = {identifier: {"family_id": f["family_id"], "role": role, "substrate": f["subset"]}
               for f in families for role, identifier in f["variants"].items()}
    causes, originals = [], []
    for item in items:
        req, final, score = item["request"], item["final"], item["score"]
        if req["model_id"] != SONNET:
            continue
        assert final["final_content"] == final["adapter_extracted"] == final["saved_completion_text"]
        diagnosis = classify(final["final_content"], score, finish=final["finish_reason"], refusal=bool(final["refusal"]))
        row = {"case_id": req["case_id"], "model_id": req["model_id"], **mapping[req["case_id"]],
               "request_file": item["request_file"], "request_file_sha256": item["request_file_sha256"],
               "public_request_sha256": digest(req), "provider_payload_sha256": digest(item["provider_payload"]),
               "response_file": item["response_file"], "response_file_sha256": item["response_file_sha256"],
               "final_content_sha256": digest(final["final_content"]),
               "saved_completion_sha256": digest(final["saved_completion_text"]),
               "adapter_matches_final": True, "finish_reason": final["finish_reason"],
               "provider_refusal_present": bool(final["refusal"]), "response_model": final["response_model"],
               "provider": final["provider"], "original_score": score, **diagnosis}
        causes.append(row)
        originals.append({"case_id": req["case_id"], "request": req,
                          "provider_payload": item["provider_payload"], "visible_final_projection": final})
    assert len(causes) == 36
    counts = Counter(r["primary_cause"] for r in causes)
    assert counts["accepted"] == sum(r["original_score"]["completion_valid"] for r in causes)
    terra, terra_private = terra_audit(cases, golds, families, items)
    verification = {"evaluation_variant_scores_reproduced": len(rows),
                    "model_family_rows_reproduced": len(paired), "paired_summary_and_examples_match": True,
                    "strict_companion_matches_primary": True,
                    "sonnet_primary_causes": dict(sorted(counts.items())),
                    "sonnet_subtypes": dict(sorted(Counter(r["subtype"] for r in causes).items())),
                    "sonnet_actual_empty": sum(r["actual_final_empty"] for r in causes),
                    "diagnostic_response_object_count": sum(len(r["diagnostic_payload_shapes"]) for r in causes),
                    "sonnet_cascading_missing_response": sum("missing_response" in r["original_score"]["response_errors"] for r in causes),
                    "object_valued_answers_across_all_diagnostic_payloads": sum(p["container"] == "object_valued_answers" for r in causes for p in r["diagnostic_payload_shapes"]),
                    "unchanged_historical_inputs": historical_hashes(),
                    "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0",
                    "provider_private_reasoning_inspected": False, "credential_access": False}
    outputs = {OUT / "response_causes.json": causes, OUT / "terra_summary.json": terra,
               OUT / "verification.json": verification,
               LOCAL / "sonnet_final_outputs.json": originals,
               LOCAL / "terra_evidence.json": terra_private,
               LOCAL / "reproduced_scores.json": {"evaluation_variants": rows, "model_families": paired}}
    assert not any(path.exists() for path in outputs), "Audit outputs already exist; do not replace them"
    for path, value in outputs.items():
        save(path, value)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "reviewed_head": read(OUT / "baseline.json")["head"],
                "baseline_sha256": file_hash(OUT / "baseline.json"),
                "audit_script_sha256": file_hash(Path(__file__)),
                "diagnostic_rules_sha256": file_hash(OUT / "diagnostic_rules.json"),
                "input_hashes": "baseline.json", "output_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in outputs},
                "verification": verification, "annotation": "mechanical and AI-assisted; no independent human review"}
    save(OUT / "manifest.json", manifest)
    print(json.dumps(verification, sort_keys=True))


if __name__ == "__main__":
    main()
