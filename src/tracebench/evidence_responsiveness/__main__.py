"""Prepare, validate, freeze and execute the bounded responsiveness study."""

import argparse
import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .common import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, ROLES, digest, file_hash, read, write
from .execution import cumulative_preflight, run_requests
from .prompts import build_prompt, manifests, ordered_requests, public_case
from .receipts import build_receipt_families, certify_receipt
from .scoring import constant_baselines, score_families, score_variant, select_examples, summarize
from .wiki import build_wiki_families, certify_wiki

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "studies/evidence_responsiveness"
RAW = ROOT / "artifacts/evidence-responsiveness"
PREPARED = RAW / "prepared"
FROZEN = STUDY / "frozen"


def preservation():
    saved = read(STUDY / "preservation.json")
    presentation = set(saved.get("presentation_only_paths", []))
    if not presentation <= {"README.md", "docs/SUBMISSION.md"}:
        raise ValueError("Unrecognized presentation preservation exception")
    failed = [name for group in ("tracked_sha256", "historical_raw_sha256")
              for name, expected in saved[group].items()
              if not (ROOT / name).is_file() or file_hash(ROOT / name) != expected]
    if set(failed) - presentation:
        raise ValueError(f"Preserved files differ: {failed}")
    if failed and not (STUDY / "results/REPORT.md").is_file():
        raise ValueError("Presentation updates require actual study results first")
    return {"baseline_commit": saved["baseline_commit"], "all_match": not failed,
            "scientific_all_match": True, "historical_raw_all_match": True,
            "scientific_tracked_files": len(saved["tracked_sha256"]) - len(presentation),
            "changed_presentation_paths": sorted(failed),
            "tracked_files": len(saved["tracked_sha256"]),
            "historical_raw_files": len(saved["historical_raw_sha256"])}


def inputs():
    return read(PREPARED / "cases.json"), read(PREPARED / "gold.json"), read(PREPARED / "families.json")


def requests(cases, families, config):
    return [r for split in ("development", "evaluation") for r in
            ordered_requests(cases, families, config["models"], split)]


def validate(cases, golds, families):
    indexed = {case["case_id"]: case for case in cases}
    by_gold = {gold["case_id"]: gold for gold in golds}
    if len(indexed) != len(cases) or set(indexed) != set(by_gold) or len(golds) != len(cases):
        raise ValueError("Duplicate or missing cases/certificates")
    counts = Counter((f["split"], f["subset"]) for f in families)
    if counts != {("development", "receipt"): 1, ("development", "wiki_derived"): 1,
                  ("evaluation", "receipt"): 8, ("evaluation", "wiki_derived"): 4}:
        raise ValueError("The fixed family strata were changed")
    assigned = []
    for family in families:
        if set(family["variants"]) != set(ROLES):
            raise ValueError("Missing variant in family")
        statuses = {}
        for role, identifier in family["variants"].items():
            assigned.append(identifier)
            case = indexed[identifier]
            if any(case[key] != family[key] for key in ("subset", "split", "cluster_id")):
                raise ValueError("Family metadata does not match case")
            recomputed = (certify_receipt if case["subset"] == "receipt" else certify_wiki)(case)
            if recomputed != by_gold[identifier]:
                raise ValueError("Certificate differs from actual variant")
            statuses[role] = by_gold[identifier]["claims"][0]["status"]
            original = build_prompt(case)
            changed = copy.deepcopy(case)
            changed.update(gold="replaced", variant_role="replaced", family_id="replaced",
                           cluster_id="replaced", split="replaced", provenance={"replaced": True})
            if original != build_prompt(changed):
                raise ValueError("Evaluator metadata affected the public request")
            public_case(case)
        if statuses["base"] != statuses["irrelevant"] or statuses["base"] == statuses["decisive"]:
            raise ValueError("Uncertified invariant/decisive relationship")
    if len(assigned) != len(set(assigned)) or set(assigned) != set(indexed):
        raise ValueError("Families overlap or omit cases")
    dev_clusters = {f["cluster_id"] for f in families if f["split"] == "development"}
    eval_clusters = {f["cluster_id"] for f in families if f["split"] == "evaluation"}
    if dev_clusters & eval_clusters:
        raise ValueError("Development and evaluation share histories")
    baselines = constant_baselines(cases, golds, families)
    unresolved = [f for f in baselines["family_rows"] if f["model_id"] == "always_unresolved"]
    if any(f["metrics"]["decisive_pair_correct"] or f["metrics"]["whole_family_correct"]
           for f in unresolved):
        raise ValueError("Always-unresolved incorrectly earns decisive/family success")
    return {"cases": len(cases), "families": len(families),
            "family_counts": {f"{split}/{subset}": n for (split, subset), n in sorted(counts.items())},
            "certificates_reproduced": len(golds), "relationship_checks": len(families),
            "metadata_invariance_checks": len(cases), "constant_baselines_pass": True,
            "review_type": "mechanical and AI-assisted; no human validation claimed"}


def prepare(wiki_cache=None):
    preservation()
    if PREPARED.exists():
        raise ValueError("Prepared cases already exist; never replace a selected study")
    receipt = build_receipt_families()
    if wiki_cache:
        cache = Path(wiki_cache).resolve()
        if not cache.is_relative_to(RAW):
            raise ValueError("Only this study's checked local wiki cache may be reused")
        provenance = read(cache.with_name(cache.stem + "-provenance.json"))
        if file_hash(cache) != provenance["cache_sha256"]:
            raise ValueError("Wiki cache bytes differ from their checked provenance")
        for section in ("code_sha256", "source_sha256"):
            for name, expected in provenance[section].items():
                if file_hash(ROOT / name) != expected:
                    raise ValueError(f"Cached wiki selection dependency changed: {name}")
        wiki = read(cache)
    else:
        wiki = build_wiki_families(ROOT)
    cases = receipt["cases"] + wiki["cases"]
    gold = receipt["gold"] + wiki["gold"]
    families = receipt["families"] + wiki["families"]
    checked = validate(cases, gold, families)
    for name, value in (("cases", cases), ("gold", gold), ("families", families),
                        ("selection", {"receipt": receipt["selection"], "wiki_derived": wiki["selection"]})):
        write(PREPARED / f"{name}.json", value)
    write(STUDY / "validation.json", checked)
    return checked


def verify_frozen():
    preservation()
    record = read(FROZEN / "freeze.json")
    for section in ("code_sha256", "input_sha256"):
        for name, expected in record[section].items():
            if file_hash(ROOT / name) != expected:
                raise ValueError(f"Frozen {section} dependency changed: {name}")
    for name, expected in record["artifacts_sha256"].items():
        if file_hash(FROZEN / name) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")
    return record


def verify_development_snapshot(config, development):
    ledger = RAW / "calls/attempts.jsonl"
    if development["ledger_sha256"] != file_hash(ledger):
        raise ValueError("Development snapshot does not match the live ledger")
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    if any(e["event"] == "attempt_reserved" and e.get("split") == "evaluation" for e in events):
        raise ValueError("Evaluation was attempted before its freeze")
    if development["development_completed"] != 6 * len(config["models"]):
        raise ValueError("The two development triplets are not complete")
    if development["evaluation_completed"]:
        raise ValueError("Evaluation began before its freeze")


def freeze(config):
    preservation()
    if FROZEN.exists():
        raise ValueError("Evaluation freeze already exists")
    cases, golds, families = inputs()
    checked = validate(cases, golds, families)
    schedule = requests(cases, families, config)
    budget = cumulative_preflight(schedule, config["models"], ROOT)
    development = read(RAW / "development.json")
    verify_development_snapshot(config, development)
    if not read(STUDY / "development_checks.json")["complete_requests_and_certificates_inspected"]:
        raise ValueError("Complete development evidence has not been inspected")
    artifacts = {"config.json": config, "validation.json": checked,
                 "public_manifest.json": manifests(cases, schedule),
                 "family_manifest.json": [{k: f[k] for k in
                     ("family_id", "subset", "split", "cluster_id", "motif", "variants")}
                     | {"full_family_sha256": digest(f)} for f in families],
                 "gold_manifest.json": [{"case_id": g["case_id"], "gold_sha256": digest(g),
                     "status": g["claims"][0]["status"]} for g in golds],
                 "preflight.json": budget}
    for name, value in artifacts.items():
        write(FROZEN / name, value)
    source = sorted((ROOT / "src").rglob("*.py"))
    input_paths = [STUDY / n for n in ("ANALYSIS.md", "config.json", "preservation.json",
                   "metadata_manifest.json", "development_checks.json")]
    input_paths += [PREPARED / f"{n}.json" for n in ("cases", "gold", "families", "selection")]
    input_paths.append(ROOT / "uv.lock")
    record = {"status": "ready", "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
              "models": [m["model_id"] for m in config["models"]],
              "code_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in source},
              "input_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in input_paths},
              "artifacts_sha256": {n: file_hash(FROZEN / n) for n in artifacts},
              "request_count": len(schedule), "evaluation_requests": 36 * len(config["models"]),
              "public_schedule_sha256": digest(schedule), "preservation": preservation()}
    write(FROZEN / "freeze.json", record)
    return record


def execute(config, split):
    preservation()
    cases, _, families = inputs()
    schedule = requests(cases, families, config)
    if split == "evaluation":
        frozen = verify_frozen()
        if frozen["public_schedule_sha256"] != digest(schedule):
            raise ValueError("Requests differ from frozen order or contents")
    output = RAW / f"{split}.json"
    if output.exists():
        raise ValueError("Execution status exists; do not duplicate or overwrite a completed phase")
    result = run_requests([r for r in schedule if r["split"] == split], config["models"], ROOT,
                          all_requests=schedule)
    result["ledger_sha256"] = file_hash(RAW / "calls/attempts.jsonl")
    if split == "evaluation":
        result["freeze_sha256"] = file_hash(FROZEN / "freeze.json")
    write(output, result)
    return result


def report():
    from .reporting import render_report

    frozen = verify_frozen()
    config = read(FROZEN / "config.json")
    execution = read(RAW / "evaluation.json")
    if execution["freeze_sha256"] != file_hash(FROZEN / "freeze.json"):
        raise ValueError("Evaluation belongs to a different freeze")
    if execution["ledger_sha256"] != file_hash(RAW / "calls/attempts.jsonl"):
        raise ValueError("Ledger changed after execution status was saved")
    output = STUDY / "results"
    if output.exists():
        raise ValueError("Study results already exist; never overwrite a run")
    cases, golds, families = inputs()
    by_case = {c["case_id"]: c for c in cases}
    by_gold = {g["case_id"]: g for g in golds}
    events = [json.loads(line) for line in (RAW / "calls/attempts.jsonl").read_text().splitlines()]
    completed = {}
    for event in events:
        if event["event"] == "attempt_completed":
            completed.setdefault(event["attempt_key"], event)
    rows, responses = [], []
    for request in requests(cases, families, config):
        event = completed.get(request["attempt_key"])
        saved = read(RAW / "calls" / event["response_file"]) if event else {}
        raw = saved.get("raw_response", {})
        choice = (raw.get("choices") or [{}])[0]
        finish = choice.get("finish_reason")
        row = score_variant(by_case[request["case_id"]], by_gold[request["case_id"]],
                            saved.get("completion_text"), request["model_id"], finish,
                            refused=bool(choice.get("message", {}).get("refusal")))
        rows.append(row)
        responses.append({k: request[k] for k in ("attempt_key", "case_id", "split", "model_id")}
                         | {"request_sha256": digest(request), "response_model": raw.get("model"),
                            "provider": raw.get("provider"), "finish_reason": finish,
                            "response_file": event["response_file"] if event else None,
                            "response_sha256": file_hash(RAW / "calls" / event["response_file"])
                            if event else None})
    evaluation_rows = [r for r in rows if r["split"] == "evaluation"]
    eval_families = [f for f in families if f["split"] == "evaluation"]
    paired = score_families(evaluation_rows, eval_families,
                            model_ids=[m["model_id"] for m in config["models"]])
    summary = summarize(paired, seed=BOOTSTRAP_SEED, resamples=BOOTSTRAP_RESAMPLES)
    eval_cases = [c for c in cases if c["split"] == "evaluation"]
    baseline = constant_baselines(eval_cases, [by_gold[c["case_id"]] for c in eval_cases], eval_families)
    examples = select_examples(paired)
    validation = read(FROZEN / "validation.json") | {"preservation": preservation(),
                  "frozen_at_utc": frozen["frozen_at_utc"]}
    for name, value in (("per_variant", rows), ("per_family", paired), ("summary", summary),
                        ("baselines", baseline), ("examples", examples), ("execution", execution),
                        ("response_manifest", responses), ("validation", validation)):
        write(output / f"{name}.json", value)
    (output / "REPORT.md").write_text(render_report(summary, execution, examples,
                                                   baseline["summary"], validation))
    return {"status": execution["status"], "variant_rows": len(rows),
            "evaluation_family_rows": len(paired), "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate", "preflight", "develop",
                                            "freeze", "run", "report"))
    parser.add_argument("--wiki-cache", type=Path)
    args = parser.parse_args()
    config = read(STUDY / "config.json")
    if args.command == "prepare":
        result = prepare(args.wiki_cache)
    elif args.command == "validate":
        result = validate(*inputs()) | {"preservation": preservation()}
    elif args.command == "preflight":
        cases, _, families = inputs()
        result = cumulative_preflight(requests(cases, families, config), config["models"], ROOT)
    elif args.command == "develop":
        result = execute(config, "development")
    elif args.command == "freeze":
        result = freeze(config)
    elif args.command == "run":
        result = execute(config, "evaluation")
    else:
        result = report()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
