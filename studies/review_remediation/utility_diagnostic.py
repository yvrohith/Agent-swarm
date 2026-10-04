"""Retrospective utility sensitivity check; never replace frozen primary scores.

Uses published final responses, an unchanged scorer and fixed gold-blind rules.
No network, model, provider-response or credential access. Run offline from any
directory; retained request files are needed only for schema-enforcement checks.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
STUDY = ROOT / "studies/investigator_utility/openrouter_v1"
BUNDLE = STUDY / "response_evidence"


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def read(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_object)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def normalize(text, expected_ids, *, refused=False, truncated=False):
    """Structural rules only: this function has no gold, model or arm input."""
    transformations, blockers, candidates = [], [], []
    if refused or truncated:
        return None, [], ["retained_refusal" if refused else "retained_truncation"], []
    if text is None or text == "":
        return text, [], ["empty_final"], []
    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except ValueError as exc:
        if "duplicate JSON key" in str(exc):
            return text, [], ["duplicate_json_keys"], []
        decoder = json.JSONDecoder(object_pairs_hook=unique_object)
        # Skip complete outer containers before considering later candidates;
        # nested answers and prose time-window arrays are not response objects.
        containers = []
        for match in re.finditer(r"[\[{]", text):
            if any(a <= match.start() < b for a, b in containers):
                continue
            try:
                candidate, length = decoder.raw_decode(text[match.start():])
            except ValueError as error:
                if "duplicate JSON key" in str(error):
                    return text, [], ["duplicate_json_keys"], []
                continue
            end = match.start() + length
            containers.append((match.start(), end))
            if isinstance(candidate, dict) and {"case_id", "answers"} & candidate.keys():
                candidates.append((match.start(), end, candidate))
        spans = [[a, b] for a, b, _ in candidates]
        if len(candidates) != 1:
            return text, [], ["multiple_candidates" if candidates else "no_candidate"], spans
        start, end, value = candidates[0]
        transformations.append({"operation": "extract_unique_response_object",
                                "unicode_span": [start, end]})
    value = copy.deepcopy(value)
    if isinstance(value, dict) and isinstance(value.get("answers"), list):
        for index, answer in enumerate(value["answers"]):
            if not isinstance(answer, dict) or "id" not in answer:
                continue
            old = answer["id"]
            if not isinstance(old, str) or old not in expected_ids:
                blockers.append(f"answers/{index}:id_not_expected_claim")
            elif "claim_id" not in answer:
                answer["claim_id"] = answer.pop("id")
                transformations.append({"operation": "rename_id_to_claim_id",
                                        "answer_index": index, "claim_id": old})
            elif answer["claim_id"] == old:
                del answer["id"]
                transformations.append({"operation": "remove_agreeing_extra_id",
                                        "answer_index": index, "claim_id": old})
            else:
                blockers.append(f"answers/{index}:conflicting_id_and_claim_id")
    return (value if transformations else text), transformations, blockers, [[a, b] for a, b, _ in candidates]


def primary_cause(row):
    score = row["score"]
    errors = {e for claim in score["claims"] for e in claim["schema_errors"]}
    if row["finish_reason"] in {"content_filter", "refusal"} or row["refusal_text"]:
        return "provider_refusal_or_filter"
    if row["completion_text"] in (None, ""):
        return "empty_final_without_refusal"
    if "malformed_json" in errors:
        return "whole_response_serialization_violation"
    if errors & {"answers_not_list", "response_not_object", "invalid_response_fields", "answer_not_object"}:
        return "root_or_answers_container_violation"
    if errors & {"wrong_case_id", "unknown_claim_id", "missing_claim", "duplicate_claim"}:
        return "claim_or_case_identity_violation"
    if errors:
        return "answer_fields_or_values"
    return "accepted"


def summarize(rows):
    """Fixed response/claim counts and separate means over applicable cases."""
    claims = [claim for row in rows for claim in row["claims"]]
    metrics = rows[0]["metrics"]
    return {
        "responses": len(rows),
        "schema_valid_responses": sum(all(c["schema_valid"] for c in r["claims"]) for r in rows),
        "all_status_correct_responses": sum(all(c["status_correct"] for c in r["claims"]) for r in rows),
        "responses_with_citation_errors": sum(any(c["citation_errors"] for c in r["claims"]) for r in rows),
        "claims": len(claims),
        "schema_valid_claims": sum(c["schema_valid"] for c in claims),
        "schema_invalid_claims": sum(not c["schema_valid"] for c in claims),
        "status_correct_claims": sum(c["status_correct"] for c in claims),
        "schema_valid_wrong_status_claims": sum(c["schema_valid"] and not c["status_correct"] for c in claims),
        "citation_error_claims": sum(not c["citation_valid"] for c in claims),
        "status_and_citation_correct_claims": sum(c["status_correct"] and c["citation_valid"] for c in claims),
        "pooled_claim_metrics": {name: {
            "numerator": sum(r["metrics"][name]["numerator"] for r in rows),
            "denominator": sum(r["metrics"][name]["denominator"] for r in rows)} for name in metrics},
        "case_means": {name: {
            "value": mean(values) if values else None, "applicable_cases": len(values),
            "all_cases": len(rows)} for name in metrics
            for values in [[r["metrics"][name]["value"] for r in rows if r["metrics"][name]["value"] is not None]]},
    }


def main():
    rules_path = OUT / "diagnostic_rules.json"
    rules = read(rules_path)
    baseline = read(OUT / "baseline.json")
    for name, expected in rules["input_sha256"].items():
        assert file_hash(ROOT / name) == expected == baseline["immutable_sha256"][name], name
    for name, expected in rules["local_request_sha256_before_inspection"].items():
        assert file_hash(ROOT / name) == expected, name
    release = read(BUNDLE / "manifest.json")
    for name in ("responses.jsonl", "scoring_cases.json"):
        assert file_hash(BUNDLE / name) == release["files_sha256"][name]
    spec = importlib.util.spec_from_file_location("unchanged_scorer", ROOT / "src/tracebench/investigator_utility/scoring.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    cases = {c["case_id"]: c for c in read(BUNDLE / "scoring_cases.json")}
    golds = {c["case_id"]: c for c in read(STUDY / "frozen/gold_certificates.json")}
    manifest = read(STUDY / "results/response_manifest.json")["requests"]
    rows = [(n, json.loads(line, object_pairs_hook=unique_object)) for n, line in
            enumerate((BUNDLE / "responses.jsonl").read_text().splitlines(), start=1)]
    assert len(rows) == len(manifest) == 168
    assert len({(r["model_id"], r["split"], r["case_id"], r["arm"]) for _, r in rows}) == 168
    evaluation = [(line, row) for line, row in rows if row["split"] == "evaluation"]
    schedule = read(STUDY / "frozen/prompt_manifest.json")
    assert len(evaluation) == len(schedule) == 144
    annotated, old_scores, new_scores, enforcement = [], [], [], []
    for (line, row), planned in zip(evaluation, schedule, strict=True):
        original = manifest[line - 1]
        assert all(row[k] == original[k] for k in original)
        for key in ("model_id", "split", "case_id", "arm"):
            assert row[key] == planned[key]
        assert row["public_request_sha256"] == planned["request_sha256"]
        assert value_hash(row["completion_text"]) == row["completion_json_sha256"]
        assert value_hash(row["refusal_text"]) == row["refusal_json_sha256"]
        case, gold = cases[row["case_id"]], golds[row["case_id"]]
        old = {**scorer.score_response(case, gold, row["completion_text"]),
               "model_id": row["model_id"], "arm": row["arm"]}
        assert old == row["score"]
        refused = row["finish_reason"] in {"content_filter", "refusal"} or bool(row["refusal_text"])
        normalized, transforms, blockers, spans = normalize(
            row["completion_text"], {c["id"] for c in case["claims"]},
            refused=refused, truncated=row["finish_reason"] in {"length", "max_tokens"})
        new = {**scorer.score_response(case, gold, normalized),
               "model_id": row["model_id"], "arm": row["arm"]}
        old_scores.append(old)
        new_scores.append(new)
        old_valid = all(c["schema_valid"] for c in old["claims"])
        new_valid = all(c["schema_valid"] for c in new["claims"])
        diagnostic_shapes = []
        for start, end in spans:
            candidate = json.loads(row["completion_text"][start:end], object_pairs_hook=unique_object)
            diagnostic_shapes.append({"unicode_span": [start, end],
                "root_fields": sorted(candidate), "case_id_matches": candidate.get("case_id") == case["case_id"],
                "answers_container": type(candidate.get("answers")).__name__,
                "answer_fields": [sorted(a) if isinstance(a, dict) else None
                                  for a in candidate.get("answers", [])]})
        annotated.append({
            "model_id": row["model_id"], "case_id": row["case_id"], "arm": row["arm"],
            "subset": row["subset"], "split": "evaluation", "bundle_line": line,
            "response_locator": str((BUNDLE / "responses.jsonl").relative_to(ROOT)) + f":{line}",
            "completion_json_sha256": row["completion_json_sha256"], "refusal_json_sha256": row["refusal_json_sha256"],
            "diagnostic_value_sha256": value_hash(normalized), "finish_reason": row["finish_reason"],
            "primary_cause": primary_cause(row), "transforms": transforms, "blockers": blockers,
            "candidate_unicode_spans": spans, "diagnostic_candidate_shapes": diagnostic_shapes,
            "markdown_fence_present": "```" in (row["completion_text"] or ""),
            "unchanged_response_value": normalized == row["completion_text"],
            "original_completion_preserved": True,
            "original_schema_valid": old_valid, "diagnostic_schema_valid": new_valid,
            "recovered_response": not old_valid and new_valid,
            "newly_decodable_claims": sum(not a["schema_valid"] and b["schema_valid"]
                                            for a, b in zip(old["claims"], new["claims"], strict=True)),
            "original_claims": old["claims"], "diagnostic_claims": new["claims"],
        })
        # Only serialized request files: no raw provider envelope is opened.
        path = (ROOT / row["request_file"]).resolve()
        assert path.is_relative_to(ROOT / "artifacts/investigator-utility/calls/requests")
        assert file_hash(path) == row["saved_request_sha256"] == rules["local_request_sha256_before_inspection"][row["request_file"]]
        request = read(path)
        assert value_hash(request["public_request"]) == row["public_request_sha256"]
        payload = request["provider_payload"]
        assert payload["model"] == row["model_id"]
        assert payload["messages"] == [{"role": "system", "content": request["public_request"]["system"]},
                                       {"role": "user", "content": request["public_request"]["user"]}]
        enforcement.append({"request_file": row["request_file"], "saved_request_sha256": row["saved_request_sha256"],
                            "model_id": row["model_id"], "arm": row["arm"], "case_id": row["case_id"],
                            "payload_fields": sorted(payload), "response_format_present": "response_format" in payload,
                            "schema_field_present": bool({"json_schema", "output_config", "output_format"} & payload.keys()),
                            "tools_present": "tools" in payload or "tool_choice" in payload})
    assert old_scores == read(STUDY / "results/per_case_scores.json")
    groups = defaultdict(list)
    for i, row in enumerate(annotated):
        groups[(row["model_id"], row["subset"], row["arm"])].append(i)
    summaries = [{"model_id": key[0], "subset": key[1], "arm": key[2],
                  "primary": summarize([old_scores[i] for i in indices]),
                  "diagnostic": summarize([new_scores[i] for i in indices]),
                  "transformed_responses": sum(bool(annotated[i]["transforms"]) for i in indices),
                  "recovered_responses": sum(annotated[i]["recovered_response"] for i in indices),
                  "primary_cause_counts": dict(Counter(annotated[i]["primary_cause"] for i in indices))}
                 for key, indices in sorted(groups.items())]
    model_summaries = [{"model_id": model,
                       "primary": summarize([r for r in old_scores if r["model_id"] == model]),
                       "diagnostic": summarize([r for r in new_scores if r["model_id"] == model])}
                      for model in sorted({r["model_id"] for r in annotated})]
    result = {"analysis_type": "Retrospective diagnostic sensitivity analysis; not a replacement primary score or causal mechanism",
              "rules_sha256": file_hash(rules_path), "script_sha256": file_hash(Path(__file__)),
              "baseline_head": baseline["head"], "input_sha256": rules["input_sha256"],
              "evaluation_responses": len(annotated), "development_excluded": 24,
              "primary_rows_reproduced": len(old_scores), "all_models_and_arms_processed": True,
              "recovered_responses": sum(r["recovered_response"] for r in annotated),
              "transformed_responses": sum(bool(r["transforms"]) for r in annotated),
              "unchanged_response_values": sum(r["unchanged_response_value"] for r in annotated),
              "ambiguous_responses": sum("multiple_candidates" in r["blockers"] for r in annotated),
              "newly_decodable_claims": sum(r["newly_decodable_claims"] for r in annotated),
              "summaries": summaries, "model_summaries": model_summaries, "responses": annotated,
              "native_schema_enforcement": {"requests_inspected": len(enforcement),
                  "request_fields": [list(fields) for fields in sorted({tuple(r["payload_fields"]) for r in enforcement})],
                  "native_schema_requested": any(r["response_format_present"] or r["schema_field_present"] or r["tools_present"] for r in enforcement),
                  "request_checks": enforcement,
                  "conclusion": "Native structured-output/schema enforcement was not requested; routing require_parameters does not create an output schema. No schema-enforced rerun was measured."},
              "limitations": ["Gold-blind transformation is retrospective; successful recovery does not establish faithful reasoning, causal assistance benefit or future schema-enforced performance.",
                              "Pooled claim counts and case means are different estimands; development never enters evaluation denominators.",
                              "Unknown citations remain errors; refusal failures are retained. Original prompts, responses and primary scores remain unchanged.",
                              "Public response evidence supplies scoring metadata, not independently validated full case semantics or provider authenticity."],
              "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0", "historical_inputs_unchanged": True}
    for name, expected in rules["input_sha256"].items():
        assert file_hash(ROOT / name) == expected
    for name, expected in rules["local_request_sha256_before_inspection"].items():
        assert file_hash(ROOT / name) == expected
    return result


if __name__ == "__main__":
    result = main()
    with (OUT / "utility_diagnostic.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("evaluation_responses", "recovered_responses",
                                                  "newly_decodable_claims", "ambiguous_responses")}))
