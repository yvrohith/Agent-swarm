"""Isolated utility-study CLI; existing tracebench commands remain unchanged."""

import argparse
import csv
import hashlib
from pathlib import Path

from .execution import _account, inspect_access, run_requests
from .prompts import ARMS, build_prompt, digest, ordered_requests
from .reporting import render_report
from .scoring import sanity_scores, score_response, select_examples, summarize_scores
from .study import (
    file_hash,
    freeze,
    ignored_output,
    prepare,
    read_json,
    validate_prepared,
    verify_freeze,
    verify_preservation,
    write_json,
)

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "studies/investigator_utility"


def execution_limits(config):
    return {"budget_usd": config["budget_usd"],
            "development_calls": config["development_request_limit"],
            "evaluation_calls": config["evaluation_request_limit"],
            "retry_attempts": config["transport_retry_limit"]}


def public_requests(prepared, config, split):
    # This boundary reads only the public case file. No evaluator status or
    # certificate is an argument to the actual investigator execution function.
    cases = read_json(prepared / "public_cases.json")
    return ordered_requests(cases, [m["model_id"] for m in config["models"]], split,
                            config["order_seed"])


def _bound_prepared(prepared, record):
    for name in ("public_cases.json", "gold.json", "selection.json"):
        relative = str((prepared / name).resolve().relative_to(ROOT))
        if relative not in record["input_sha256"]:
            raise ValueError("Prepared inputs do not belong to this freeze")


def _ledger_path(config):
    path = ROOT / config["raw_execution_directory"]
    ignored_output(ROOT, path)
    # One study-wide ledger. A fresh folder must not reset the task's budget.
    if path.resolve() != (ROOT / "artifacts/investigator-utility/calls").resolve():
        raise ValueError("The study-wide development/evaluation ledger path is fixed")
    return path


def develop(prepared, config, output):
    validation = validate_prepared(prepared, config)
    ignored_output(ROOT, output)
    if output.exists():
        raise ValueError("Development output already exists; do not overwrite")
    output.mkdir(parents=True)
    cases = read_json(prepared / "public_cases.json")
    for case in cases:
        if case["split"] == "development":
            for arm in ARMS:
                write_json(output / f"{case['case_id']}-{arm}.json", build_prompt(case, arm))
    result = run_requests(public_requests(prepared, config, "development"), config["models"],
                          _ledger_path(config), execution_limits(config))
    write_json(output / "execution.json", result)
    return {"validation": {k: v for k, v in validation.items() if k != "prompt_manifests"},
            "execution": result}


def evaluate(prepared, frozen):
    record = verify_freeze(ROOT, frozen)
    _bound_prepared(prepared, record)
    config = read_json(frozen / "config.json")
    requests = public_requests(prepared, config, "evaluation")
    manifest = read_json(frozen / "prompt_manifest.json")
    if [digest(request) for request in requests] != [r["request_sha256"] for r in manifest]:
        raise ValueError("Serialized requests differ from the frozen schedule")
    result = run_requests(requests, config["models"], _ledger_path(config), execution_limits(config))
    ledger = _ledger_path(config) / "attempts.jsonl"
    result["ledger_sha256"] = file_hash(ledger) if ledger.exists() else None
    result["freeze_sha256"] = file_hash(frozen / "freeze.json")
    if not config["models"]:
        result["blockers"] = record["execution_blockers"] + result["blockers"]
    return result


def score_and_report(prepared, frozen, execution_path, output):
    record = verify_freeze(ROOT, frozen)
    _bound_prepared(prepared, record)
    config = read_json(frozen / "config.json")
    execution = read_json(execution_path)
    cases = [c for c in read_json(prepared / "public_cases.json") if c["split"] == "evaluation"]
    golds = read_json(prepared / "gold.json")
    by_gold = {gold["case_id"]: gold for gold in golds}
    ledger_dir = _ledger_path(config)
    events = []
    ledger = ledger_dir / "attempts.jsonl"
    if execution.get("freeze_sha256") != file_hash(frozen / "freeze.json"):
        raise ValueError("Execution status belongs to a different freeze")
    if execution.get("ledger_sha256") != (file_hash(ledger) if ledger.exists() else None):
        raise ValueError("Execution status describes a changed ledger; save a fresh status")
    if ledger.exists():
        import json
        events = [json.loads(line) for line in ledger.read_text().splitlines()]
        if events and events[0].get("models_hash") != digest(config["models"]):
            raise ValueError("Execution ledger belongs to different frozen models")
    execution = execution | _account(events)
    completed = {}
    for event in events:
        if event["event"] == "attempt_completed":
            completed.setdefault(event["attempt_key"], event)
    rows = []
    for request in public_requests(prepared, config, "evaluation"):
        case = next(c for c in cases if c["case_id"] == request["case_id"])
        event = completed.get(request["attempt_key"])
        completion = None
        if event:
            saved = read_json(ledger_dir / event["response_file"])
            if saved["attempt_key"] != request["attempt_key"]:
                raise ValueError("Response identity does not match frozen request")
            safe_key = hashlib.sha256(request["attempt_key"].encode()).hexdigest()
            sent = read_json(ledger_dir / "requests" / f"{safe_key}.json")
            if sent["public_request"] != request:
                raise ValueError("Response belongs to changed request")
            completion = saved["completion_text"]
        row = score_response(case, by_gold[case["case_id"]], completion)
        rows.append(row | {"model_id": request["model_id"], "arm": request["arm"]})
    summary = summarize_scores(rows, bootstrap_seed=config["bootstrap_seed"],
                               resamples=config["bootstrap_resamples"])
    sanity = sanity_scores(cases, [by_gold[case["case_id"]] for case in cases])
    if output.exists():
        raise ValueError("Results already exist; never overwrite or replace a run")
    if not (output.resolve().is_relative_to(STUDY.resolve())
            or output.resolve().is_relative_to((ROOT / "artifacts").resolve())):
        raise ValueError("Results must be inside this study or ignored artifacts/")
    output.mkdir(parents=True)
    write_json(output / "per_case_scores.json", rows)
    write_json(output / "paired_summary.json", summary)
    write_json(output / "sanity_baselines.json", sanity)
    preservation = verify_preservation(ROOT)
    execution = execution | {
                             "development_calls_completed": execution.get("development_completed", 0),
                             "evaluation_calls_completed": execution.get("evaluation_completed", 0),
                             "transport_retry_attempts": execution.get("additional_retry_attempts", 0),
                             "actual_cost_usd": execution.get("actual_total_cost_usd"),
                             "reserved_cost_usd": execution.get("charged_or_reserved_usd"),
                             "preservation_status": f"All {preservation['verified_files']} baseline "
                                                    "tracked-file hashes match.",
                             "preservation": preservation,
                             "case_counts": read_json(frozen / "validation.json")["case_counts"],
                             "frozen_at_utc": record["frozen_at_utc"]}
    write_json(output / "execution.json", execution)
    for metric in ("unjustified_certainty", "warranted_answer_accuracy"):
        with (output / f"{metric}.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["model", "subset", "arm", "case_mean", "ci_low", "ci_high",
                             "numerator", "denominator", "n_cases", "n_clusters"])
            for group in summary["groups"]:
                value = group["metrics"][metric]
                writer.writerow([group["model_id"], group["subset"], group["arm"],
                                 *[value[k] for k in ("mean", "ci_low", "ci_high", "numerator",
                                                     "denominator", "n_cases", "n_clusters")]])
    report = render_report(summary, execution=execution, examples=select_examples(rows),
                           sanity_baselines=sanity)
    report += ("\n## Frozen preparation\n\n"
               "Cases and evaluator certificates: [case manifest](../frozen/case_manifest.json), "
               "[gold certificates](../frozen/gold_certificates.json), "
               "[selection](../frozen/selection.json), "
               "[view hashes and size overhead](../frozen/view_manifest.json), and "
               "[freeze record](../frozen/freeze.json). Full selected texts, serialized requests, "
               "and provider responses stay in ignored artifacts.\n\n"
               "No model IDs or pricing were invented. This blocked preparation freezes cases, "
               "prompts and scoring, but permits no API calls; model access and a versioned "
               "execution freeze must be established before evaluation. The original three "
               "studies, README and submission remain unchanged.\n") if not config["models"] else ""
    (output / "REPORT.md").write_text(report, encoding="utf-8")
    return {"status": execution["status"], "model_score_rows": len(rows),
            "output": str(output), "preservation": execution["preservation"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "validate", "develop", "freeze", "run", "report", "access"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path, default=STUDY / "config.json")
        command.add_argument("--prepared", type=Path,
                             default=ROOT / "artifacts/investigator-utility/prepared")
        if name == "prepare":
            command.add_argument("--archive", type=Path, default=ROOT / "data/raw/wiki/full-wiki-logs.zip")
            command.add_argument("--other-wikis", type=Path, default=ROOT / "data/raw/wiki/other-wikis.json.gz")
        if name in ("freeze", "run", "report"):
            command.add_argument("--frozen", type=Path, default=STUDY / "frozen")
        if name == "freeze":
            command.add_argument("--protocol", type=Path, default=STUDY / "ANALYSIS.md")
        if name in ("develop", "run", "report"):
            default = ROOT / "artifacts/investigator-utility/development" if name == "develop" else (
                ROOT / "artifacts/investigator-utility/execution.json" if name == "run" else STUDY / "results")
            command.add_argument("--output", type=Path, default=default)
        if name == "report":
            command.add_argument("--execution", type=Path,
                                 default=ROOT / "artifacts/investigator-utility/execution.json")
    args = parser.parse_args()
    config = read_json(args.config)
    if args.command == "access":
        result = inspect_access(config["models"])
    elif args.command == "prepare":
        result = prepare(ROOT, args.archive, args.other_wikis, args.prepared, config)
        result.pop("prompt_manifests", None)
    elif args.command == "validate":
        result = validate_prepared(args.prepared, config)
        result.pop("prompt_manifests", None)
    elif args.command == "develop":
        result = develop(args.prepared, config, args.output)
    elif args.command == "freeze":
        result = freeze(ROOT, args.prepared, args.config, args.protocol, args.frozen)
    elif args.command == "run":
        ignored_output(ROOT, args.output)
        if args.output.exists():
            raise ValueError("Execution status exists; preserve it and use a new status filename")
        result = evaluate(args.prepared, args.frozen)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, result)
    else:
        result = score_and_report(args.prepared, args.frozen, args.execution, args.output)
    import json
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
