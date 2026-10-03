#!/usr/bin/env python3
"""Rescore the public response evidence offline using only the standard library.

Run from any directory with Python 3.11+. No credentials, network, installed
package, raw artifacts, or provider reasoning are needed. This verifies released
visible answers against the unchanged scorer and gold; the minimal case metadata
does not reconstruct supplied evidence or independently validate gold semantics.
Published hashes establish consistency, not provider authenticity. The original
freeze/preservation checker is unchanged: only its two historical documentation
pins are explicitly reconciled with this release's updated documentation hashes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
REPO = BUNDLE.parents[3]
STUDY = BUNDLE.parent
SCORER = "src/tracebench/investigator_utility/scoring.py"
SOURCE_COMMIT = "0bb581e9b9debaf1160754931964ab90dc3b9702"
DOCUMENTATION = {"README.md", "docs/SUBMISSION.md"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON object key")
        result[key] = value
    return result


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hashes(base: Path, entries: dict) -> None:
    for name, expected in entries.items():
        path = (base / name).resolve()
        require(path.is_relative_to(base), "Hash manifest path escapes its directory")
        require(digest(path) == expected, f"File hash mismatch: {name}")


def identity(row: dict) -> tuple:
    return tuple(row[key] for key in ("model_id", "split", "case_id", "arm"))


def main() -> dict:
    manifest = read(BUNDLE / "manifest.json")
    require(manifest["schema_version"] == 1, "Unsupported manifest schema")
    require(manifest["source_commit"] == SOURCE_COMMIT, "Unexpected source commit")
    expected = {"development": 24, "evaluation": 144, "total": 168}
    require(manifest["expected_counts"] == expected, "Changed schedule counts")
    require((manifest["bootstrap_seed"], manifest["resamples"]) == (73021, 2000),
            "Changed bootstrap settings")
    require({"responses.jsonl", "scoring_cases.json"} <= manifest["files_sha256"].keys(),
            "Missing response evidence hashes")
    verify_hashes(BUNDLE, manifest["files_sha256"])
    repo_hashes = manifest["repository_files_sha256"]
    required = {SCORER, "studies/investigator_utility/preservation.json"}
    required.update(str((STUDY / name).relative_to(REPO)) for name in (
        "frozen/freeze.json", "results/response_manifest.json", "results/execution.json",
        "results/per_case_scores.json", "results/paired_summary.json", "results/sanity_baselines.json"))
    require(required <= repo_hashes.keys(), "Missing required repository hashes")
    verify_hashes(REPO, repo_hashes)
    freeze = read(STUDY / "frozen/freeze.json")
    for name, expected_hash in freeze["code_sha256"].items():
        require(repo_hashes.get(name) == expected_hash, "Frozen source hash mismatch")
    for name, expected_hash in freeze["artifacts_sha256"].items():
        relative = str((STUDY / "frozen" / name).relative_to(REPO))
        require(repo_hashes.get(relative) == expected_hash, "Frozen artifact hash mismatch")

    preservation = read(REPO / "studies/investigator_utility/preservation.json")["files"]
    historical = manifest["historical_documentation_pins"]
    current = manifest["current_documentation_sha256"]
    require(set(historical) == set(current) == DOCUMENTATION, "Unexpected documentation exceptions")
    require(historical == {name: preservation[name] for name in DOCUMENTATION},
            "Historical documentation pins do not match preserved manifest")
    verify_hashes(REPO, {name: value for name, value in preservation.items() if name not in current})
    verify_hashes(REPO, current)

    spec = importlib.util.spec_from_file_location("frozen_utility_scoring", REPO / SCORER)
    require(spec is not None and spec.loader is not None, "Scorer import unavailable")
    scorer = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(scorer)
    cases = read(BUNDLE / "scoring_cases.json")
    golds = read(STUDY / "frozen/gold_certificates.json")
    case_manifest = read(STUDY / "frozen/case_manifest.json")
    by_case = {case["case_id"]: case for case in cases}
    by_gold = {gold["case_id"]: gold for gold in golds}
    by_manifest = {case["case_id"]: case for case in case_manifest}
    require(len(by_case) == len(cases) == len(by_gold) == len(golds) == 28,
            "Missing or duplicate case/gold metadata")
    require(by_case.keys() == by_gold.keys() == by_manifest.keys(), "Case/gold universe differs")
    for case in cases:
        original = by_manifest[case["case_id"]]
        require(all(case[key] == original[key] for key in ("subset", "split", "cluster_id")),
                "Case metadata differs from freeze")
        require([c["id"] for c in case["claims"]] == original["claim_ids"], "Claim IDs differ")
        require([r["id"] for r in case["records"]] == original["record_ids"], "Record IDs differ")
        scorer._validate_case_gold(case, by_gold[case["case_id"]])

    rows = [json.loads(line, object_pairs_hook=unique_object)
            for line in (BUNDLE / "responses.jsonl").read_text(encoding="utf-8").splitlines()]
    response_manifest = read(STUDY / "results/response_manifest.json")
    originals = response_manifest["requests"]
    require(len(rows) == len(originals) == 168, "Wrong response count")
    require(len({identity(row) for row in rows}) == len({r["attempt_id"] for r in rows}) == 168,
            "Duplicate request or attempt")
    counts = Counter(row["split"] for row in rows)
    require(dict(counts) == {key: expected[key] for key in ("development", "evaluation")},
            "Split counts differ")
    extra = {"completion_text", "completion_json_sha256", "refusal_text", "refusal_json_sha256", "score"}
    for row, original in zip(rows, originals):
        require(set(row) == set(original) | extra, "Unexpected response fields")
        require({key: row[key] for key in original} == original, "Response metadata differs")
        for name in ("completion", "refusal"):
            value = row[f"{name}_text"]
            require(value is None or isinstance(value, str), "Visible response must be text or null")
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            require(hashlib.sha256(encoded).hexdigest() == row[f"{name}_json_sha256"],
                    f"{name.capitalize()} text hash mismatch")
        case = by_case[row["case_id"]]
        require((row["split"], row["subset"]) == (case["split"], case["subset"]),
                "Response case split/subset mismatch")
        score = {**scorer.score_response(case, by_gold[row["case_id"]], row["completion_text"]),
                 "model_id": row["model_id"], "arm": row["arm"]}
        require(score == row["score"], "Published response score does not reproduce")

    evaluation = [row for row in rows if row["split"] == "evaluation"]
    schedule = read(STUDY / "frozen/prompt_manifest.json")
    require(len(schedule) == 144, "Wrong frozen evaluation count")
    for row, planned in zip(evaluation, schedule):
        require(identity(row) == identity(planned), "Frozen evaluation schedule differs")
        require(row["public_request_sha256"] == planned["request_sha256"], "Public request hash differs")
    scores = [row["score"] for row in evaluation]
    require(scores == read(STUDY / "results/per_case_scores.json"), "Evaluation scores differ")
    summary = scorer.summarize_scores(scores, bootstrap_seed=manifest["bootstrap_seed"],
                                      resamples=manifest["resamples"])
    require(summary == read(STUDY / "results/paired_summary.json"), "Paired bootstrap results differ")
    eval_cases = [case for case in cases if case["split"] == "evaluation"]
    sanity = scorer.sanity_scores(eval_cases, [by_gold[case["case_id"]] for case in eval_cases])
    require(sanity == read(STUDY / "results/sanity_baselines.json"), "Sanity baseline scores differ")

    execution = read(STUDY / "results/execution.json")
    models = {model["model_id"]: model for model in read(STUDY / "frozen/config.json")["models"]}
    reported = sum((Decimal(row["provider_reported_cost_usd"]) for row in rows
                    if row["provider_reported_cost_usd"] is not None), Decimal(0))
    charged = sum((Decimal(row["charged_or_reserved_usd"]) for row in rows), Decimal(0))
    unknown_actual = sum(row["provider_reported_cost_usd"] is None for row in rows)
    known_usage, unknown_usage = Decimal(0), 0
    for row in rows:
        if row["input_tokens"] is None or row["output_tokens"] is None:
            unknown_usage += 1
            continue
        require(all(type(row[key]) is int and row[key] >= 0 for key in ("input_tokens", "output_tokens")),
                "Invalid token usage")
        model = models[row["model_id"]]
        known_usage += (Decimal(row["input_tokens"]) * Decimal(model["input_usd_per_million"])
                        + Decimal(row["output_tokens"]) * Decimal(model["output_usd_per_million"])) / 1000000
    for key, value in (("provider_reported_actual_cost_usd", reported),
                       ("charged_or_reserved_usd", charged), ("reserved_cost_usd", charged),
                       ("known_usage_cost_usd", known_usage)):
        require(Decimal(execution[key]) == value, "Cost accounting differs")
    require(execution["unknown_actual_cost_attempts"] == unknown_actual
            and execution["unknown_cost_attempts"] == unknown_usage, "Unknown cost counts differ")
    total = execution["actual_total_cost_usd"]
    require(total is None if unknown_actual else Decimal(total) == reported, "Actual total cost differs")
    require(execution["completed_calls"] == execution["attempts"] == 168
            and execution["development_completed"] == 24 and execution["evaluation_completed"] == 144
            and execution["additional_retry_attempts"] == 0, "Execution call counts differ")
    require(execution["status"] == "completed" and not execution["missing_requests"]
            and execution["freeze_sha256"] == response_manifest["freeze_sha256"]
            == digest(STUDY / "frozen/freeze.json"), "Execution/freeze linkage differs")
    require(charged <= Decimal("25"), "Whole-study budget exceeded")
    return {"status": "verified", "responses": len(rows), "development": counts["development"],
            "evaluation": counts["evaluation"], "cases": len(cases), "resamples": manifest["resamples"],
            "provider_reported_cost_usd": str(reported), "charged_or_reserved_usd": str(charged),
            "unknown_actual_cost_attempts": unknown_actual}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), sort_keys=True))
    except ValueError as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except (OSError, KeyError, TypeError, AttributeError) as error:
        print(f"Verification failed: missing or malformed evidence ({type(error).__name__})", file=sys.stderr)
        raise SystemExit(1) from None
