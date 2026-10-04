"""One bounded offline sensitivity calculation over unchanged acquisition inputs."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from tracebench.evidence_acquisition.policies import POLICIES

from .aggregation import summarize
from .sensitivity import evaluate_problem
from .timing import run_timing

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/acquisition_prior_robustness"
ORIGINAL = ROOT / "studies/evidence_acquisition"


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    with path.open("x") as stream:
        stream.write(content + "\n")


def write_compressed(path, value):
    content = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode()
    with Path(path).open("xb") as stream:
        stream.write(gzip.compress(content, mtime=0))


def config():
    value = read(STUDY / "config.json")
    expected = {
        "evaluation_problems": 40, "development_problems": 4,
        "deployments": ["q0", "qS", "qT", "qMinus", "qPlus"],
        "planning_modes": ["frozen_p0", "matched_q"],
        "policies": list(POLICIES), "aggregation_rules": ["equal_problem", "structure_balanced"],
        "exact_state_cap": 100000, "timing_repetitions": 3, "timing_prior": "q0",
        "timing_policy_order": list(POLICIES), "model_calls": 0, "network_requests": 0,
        "additional_spend_usd": "0",
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise ValueError("Configuration differs from the bounded authorized design")
    return value


def verify_preservation():
    saved = read(STUDY / "preservation.json")
    for relative, expected in saved["tracked_sha256"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Historical preservation mismatch: {relative}")
    local = read(ROOT / saved["local_preservation_manifest"])
    for relative, expected in local["sha256"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Historical local-byte preservation mismatch: {relative}")
    return {"historical_tracked_files": len(saved["tracked_sha256"]),
            "historical_local_files": len(local["sha256"])}


def dependencies():
    # Explicit closure: changing an unrelated README does not invalidate this verifier.
    names = [
        "src/tracebench/__init__.py",
        *[f"src/tracebench/evidence_acquisition/{name}.py" for name in
          ("__init__", "model", "certificates", "policies", "study")],
        *[f"studies/evidence_acquisition/{name}" for name in
          ("evaluation_problems.json", "development_problems.json", "development_results.json",
           "freeze.json", "input_manifest.json")],
        *[f"studies/evidence_acquisition/results/{name}" for name in
          ("manifest.json", "per_problem_policy_budget.json", "summary.json", "runtime.json",
           "signature_runs.json.gz", "certificates.json.gz", "independent_verification.json")],
        *[f"studies/acquisition_prior_robustness/{name}" for name in
          ("analysis.py", "sensitivity.py", "aggregation.py", "timing.py", "config.json",
           "ANALYSIS.md", "METHOD.md", "baseline_reproduction.json", "structure_groups.json",
           "development_checks.json", "pre_freeze_checks.json")],
        *[f"tests/{name}.py" for name in
          ("test_acquisition_prior_robustness", "test_acquisition_prior_timing",
           "test_acquisition_prior_aggregation", "test_acquisition_prior_driver",
           "test_acquisition_policies")],
    ]
    return [ROOT / name for name in names]


def verify_freeze():
    frozen = read(STUDY / "freeze.json")
    expected = {str(path.relative_to(ROOT)) for path in dependencies()}
    if set(frozen["files_sha256"]) != expected:
        raise ValueError("Incomplete or extra frozen dependency closure")
    for relative, expected_hash in frozen["files_sha256"].items():
        if digest(ROOT / relative) != expected_hash:
            raise ValueError(f"Freeze mismatch: {relative}")
    config()
    return len(expected)


def freeze():
    config()
    preservation = verify_preservation()
    checks = read(STUDY / "pre_freeze_checks.json")
    if not checks["passed"] or checks["evaluation_comparisons_observed"] != 0:
        raise ValueError("Pre-freeze correctness checks incomplete or evaluation already observed")
    if read(STUDY / "baseline_reproduction.json")["status"] != "passed":
        raise ValueError("Historical full-budget reproduction has not passed")
    groups = read(STUDY / "structure_groups.json")
    if (groups["status"] != "verified_no_material_collisions_in_existing_inputs"
            or groups["problem_count"] != 40 or groups["group_count"] != 30):
        raise ValueError("Original structural grouping has not been verified")
    value = {"schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
             "label": "Review-informed post-baseline sensitivity; original outcomes already known",
             "new_evaluation_comparisons_observed": False, "python_version": sys.version,
             "files_sha256": {str(p.relative_to(ROOT)): digest(p) for p in dependencies()},
             "preservation": preservation}
    write_new(STUDY / "freeze.json", value)
    return {"status": "frozen", "dependencies": verify_freeze()}


def saved_baseline(development=False):
    if development:
        # The old development file retained expectations but omitted signature histories.
        # Recompute only its four existing finite inputs, using the unchanged driver.
        from tracebench.evidence_acquisition.study import evaluate
        problems = read(ORIGINAL / "development_problems.json")
        result = evaluate(problems, {"policies": list(POLICIES), "budget_percentages": [100]})
        old = {(r["problem_id"], r["policy"]): r for r in
               read(ORIGINAL / "development_results.json")["per_problem_policy_budget"]
               if r["budget_percent"] == 100}
        for row in result["per_problem_policy_budget"]:
            saved = old[row["problem_id"], row["policy"]]
            if row["expected"] != saved["expected"] or row["worst"] != saved["worst"]:
                raise ValueError("Original development expectations do not reproduce")
        return problems, result["runs"], result["certificates"]
    problems = read(ORIGINAL / "evaluation_problems.json")
    runs = json.loads(gzip.decompress((ORIGINAL / "results/signature_runs.json.gz").read_bytes()))
    certificates = json.loads(gzip.decompress((ORIGINAL / "results/certificates.json.gz").read_bytes()))
    return problems, [r for r in runs if r["budget_percent"] == 100], certificates


def execute(output, development=False):
    settings = config()
    if not development:
        verify_freeze()
    verify_preservation()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    results = []
    try:
        problems, baseline_runs, baseline_certificates = saved_baseline(development)
        if len(problems) != (4 if development else 40):
            raise ValueError("Frozen problem count differs")
        for problem in problems:
            selected_runs = [r for r in baseline_runs if r["problem_id"] == problem["problem_id"]]
            result = evaluate_problem(problem, selected_runs, baseline_certificates,
                                      state_cap=settings["exact_state_cap"])
            results.append(result)
            print(json.dumps({"problem": problem["problem_id"], "completed": len(results),
                              "total": len(problems)}), flush=True)
        rows = [row for result in results for row in result["rows"]]
        groups = ({p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems}
                  if development else read(STUDY / "structure_groups.json")["problem_to_group"])
        write_new(output / "per_problem.json", rows)
        write_new(output / "summary.json", summarize(rows, groups))
        # Full new trajectories/certificates are a compact synthetic audit record.
        write_compressed(output / "details.json.gz", results)
        timing = run_timing(problems)
        write_new(output / "runtime.json", timing)
        preservation = verify_preservation()
        validation = {"completed_at_utc": datetime.now(timezone.utc).isoformat(),
                      "split": "development" if development else "evaluation",
                      "problems": len(problems), "rows": len(rows),
                      "pipeline_seconds": perf_counter() - started,
                      "preservation": preservation,
                      "frozen_dependencies": None if development else verify_freeze(),
                      "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
        write_new(output / "validation.json", validation)
        write_new(output / "manifest.json", {
            "freeze_sha256": None if development else digest(STUDY / "freeze.json"),
            "files_sha256": {path.name: digest(path) for path in sorted(output.iterdir())},
            "completed_at_utc": validation["completed_at_utc"],
            "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"})
        return validation
    except Exception as error:
        # Preserve partial evidence; never silently overwrite or refreeze a failed evaluation.
        write_new(output / "failure.json", {"error_type": type(error).__name__, "message": str(error),
                                          "completed_problems": len(results),
                                          "elapsed_seconds": perf_counter() - started})
        write_compressed(output / "partial_details.json.gz", results)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("develop", "freeze", "verify", "run"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze()
    elif args.command == "verify":
        result = {"dependencies": verify_freeze(), "preservation": verify_preservation()}
    elif args.command == "develop":
        if args.output is None:
            parser.error("development requires a fresh ignored --output directory")
        result = execute(args.output, development=True)
    else:
        result = execute(args.output or STUDY / "results")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
