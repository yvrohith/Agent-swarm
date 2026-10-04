"""Public prior-sensitivity result replay, separately from local preservation.

This additive entry point does not modify the historical frozen verifier.
It reads only released synthetic evidence for public-results, and never runs
planners, generates problems, reads credentials or makes network requests.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIOR = "studies/acquisition_prior_robustness/"
ORIGINAL = "studies/evidence_acquisition/"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON object key")
        result[key] = value
    return result


def read(path):
    path = Path(path)
    data = path.read_bytes()
    if path.name.endswith(".gz"):
        data = gzip.decompress(data)
    return json.loads(data, object_pairs_hook=unique_object)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_path(root, name):
    """Reject lexical escapes, aliases, and symlinks outside the release root."""
    require(isinstance(name, str) and bool(name), "Invalid manifest path")
    pure = PurePosixPath(name)
    require(not pure.is_absolute() and ".." not in pure.parts
            and str(pure) == name and "\\" not in name, "Manifest path escape or alias")
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root), "Manifest path escapes release root")
    return path


def unique_rows(rows, keys, label):
    indexed = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        require(key not in indexed, f"Duplicate {label} identity")
        indexed[key] = row
    return indexed


def verify_dependencies(root=ROOT, manifest=None):
    manifest = manifest or read(HERE / "public_manifest_v1.json")
    require(manifest["schema_version"] == 1, "Unsupported public manifest")
    require(manifest["study"] == "acquisition_prior_robustness", "Wrong public study")
    anchors = manifest["authority_sha256"]
    required_anchors = {PRIOR + "freeze.json", PRIOR + "results/manifest.json",
                        ORIGINAL + "freeze.json", ORIGINAL + "results/manifest.json"}
    require(set(anchors) == required_anchors, "Public authority set differs")
    authorities = {}
    for name, expected in anchors.items():
        path = safe_path(root, name)
        require(digest(path) == expected, f"Historical authority bytes differ: {name}")
        authorities[name] = read(path)
    for prefix in (PRIOR, ORIGINAL):
        require(authorities[prefix + "results/manifest.json"]["freeze_sha256"]
                == anchors[prefix + "freeze.json"], "Historical result/freeze linkage differs")
    files = manifest["files"]
    unique_rows(files, ("path",), "public dependency")
    required = {
        "src/tracebench/__init__.py", "src/tracebench/evidence_acquisition/__init__.py",
        *{"src/tracebench/evidence_acquisition/" + name + ".py"
          for name in ("model", "certificates", "policies")},
        *{PRIOR + name for name in ("sensitivity.py", "aggregation.py", "config.json",
                                    "structure_groups.json")},
        ORIGINAL + "evaluation_problems.json",
        ORIGINAL + "results/signature_runs.json.gz", ORIGINAL + "results/certificates.json.gz",
        *{PRIOR + "results/" + name for name in
          ("details.json.gz", "per_problem.json", "summary.json", "runtime.json", "validation.json")},
    }
    require({entry["path"] for entry in files} == required,
            "Incomplete or extra public computational closure")
    for entry in files:
        origin = entry["origin"]
        require(origin["record"] in authorities and origin["section"] == "files_sha256",
                "Unsupported historical pin origin")
        pin = authorities[origin["record"]][origin["section"]][origin["key"]]
        require(entry["sha256"] == pin, "Public pin differs from historical authority")
        path = safe_path(root, entry["path"])
        require(digest(path) == pin, f"Public dependency bytes differ: {entry['path']}")
    return {"status": "passed", "historical_authorities": len(anchors),
            "computational_and_result_files": len(files),
            "local_history": "not checked", "unrelated_documentation": "not a dependency"}


def verify_public(root=ROOT):
    dependencies = verify_dependencies(root)
    require(Path(root).resolve() == ROOT.resolve(),
            "Run the verifier inside the release being checked; imports must use that release")
    verify_import_origins(root)
    # Imports occur only after their original frozen byte pins have passed.
    from studies.acquisition_prior_robustness.aggregation import summarize
    from studies.acquisition_prior_robustness.sensitivity import (
        POLICIES,
        _trajectory_check,
        deployment_priors,
        number,
        retained_action_counts,
        saved_trajectories,
        signature_masses,
        summarize_trajectories,
        with_prior,
    )
    from tracebench.evidence_acquisition.model import Model
    problems = read(root / (ORIGINAL + "evaluation_problems.json"))
    problem_map = unique_rows(problems, ("problem_id",), "problem")
    require(len(problem_map) == 40, "Wrong frozen problem count")
    details = read(root / (PRIOR + "results/details.json.gz"))
    detailed = unique_rows(details, ("problem_id",), "detailed problem")
    require(problem_map.keys() == detailed.keys(), "Missing or extra detailed problem")
    source_runs = read(root / (ORIGINAL + "results/signature_runs.json.gz"))
    source_certificates = read(root / (ORIGINAL + "results/certificates.json.gz"))
    rows = read(root / (PRIOR + "results/per_problem.json"))
    row_keys = ("problem_id", "deployment", "planning_mode", "policy")
    unique_rows(rows, row_keys, "metric row")
    require(rows == [row for item in details for row in item["rows"]],
            "Metric rows differ from detailed result")
    trajectory_count = distribution_count = metric_count = 0
    for key, problem in problem_map.items():
        detail = detailed[key]
        require(not detail["failures"], "Saved unavailable solves require separate review")
        base = Model(problem)
        baseline = saved_trajectories(base, source_runs, source_certificates)
        priors = deployment_priors(base)
        distributions = unique_rows(detail["distributions"], ("deployment",), "prior")
        require(set(distributions) == {(name,) for name in priors}, "Prior grid differs")
        paths = unique_rows(detail["trajectories"],
                            ("deployment", "policy", "signature_index"), "matched trajectory")
        expected_paths = {(name, policy, index) for name in priors
                          for policy in ("world_entropy", "pair_cut", "exact_optimal")
                          for index in range(len(base.signature_cells))}
        require(set(paths) == expected_paths, "Matched trajectory grid differs")
        metrics = unique_rows(detail["rows"], ("deployment", "planning_mode", "policy"),
                              "problem metric")
        require(set(metrics) == {(name, mode, policy) for name in priors
                                  for mode in ("frozen_p0", "matched_q") for policy in POLICIES},
                "Problem metric grid differs")
        for name, weights in priors.items():
            changed = with_prior(base, weights)
            saved = distributions[name,]
            require(saved["world_prior"] == list(map(str, weights)), "Prior values differ")
            require(saved["retained_action_counts"] == list(retained_action_counts(base)),
                    "Retained action counts differ")
            masses = signature_masses(base, weights)
            require(saved["signature_masses"] == [
                {"signature_index": index, "signature": list(signature), "mass": number(mass)}
                for index, (signature, mass) in enumerate(masses.items())],
                "Signature prior masses differ")
            distribution_count += 1
            for policy in POLICIES:
                matched = baseline[policy]
                if policy not in {"read_all", "schema_aware"}:
                    matched = []
                    for index, signature in enumerate(sorted(base.signature_cells)):
                        path = paths[name, policy, index]
                        cert = detail["certificates"][path["certificate"]]
                        history = _trajectory_check(changed, signature, path, cert)
                        require(path["history"] == history, "Saved paid history differs")
                        matched.append(path)
                        trajectory_count += 1
                    if name == "q0":
                        fields = ("signature_index", "history", "cost", "query_count",
                                  "returned_bytes", "status")
                        require([{k: p[k] for k in fields} for p in matched]
                                == [{k: p[k] for k in fields} for p in baseline[policy]],
                                "q0 retained paths differ from original policy")
                for mode, selected in (("frozen_p0", baseline[policy]), ("matched_q", matched)):
                    computed = summarize_trajectories(base, weights, selected)
                    saved_row = metrics[name, mode, policy]
                    require(saved_row["availability"] == "complete"
                            and all(saved_row[k] == value for k, value in computed.items()),
                            "Expected metrics differ from retained trajectories")
                    metric_count += 1
    groups = read(root / (PRIOR + "structure_groups.json"))["problem_to_group"]
    expected_summary = summarize(rows, groups)
    require(expected_summary == read(root / (PRIOR + "results/summary.json")),
            "Same-code exact reaggregation differs")
    return {"status": "passed_public_results_only", "dependencies": dependencies,
            "problems": len(problems), "deployment_distributions": distribution_count,
            "matched_trajectories": trajectory_count, "metric_rows": metric_count,
            "summary_policy_rows": len(expected_summary["policy_summaries"]),
            "summary_paired_rows": len(expected_summary["pairwise_comparisons"]),
            "scope": "Original byte pins, saved paths, shared-model certificates, prior masses and same-code exact reaggregation",
            "not_performed": ["local history preservation", "planner or optimum re-solve",
                              "timing measurement", "independent physical semantics",
                              "human or external validation"],
            "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0"}


def verify_import_origins(root=ROOT):
    """An installed second checkout cannot stand in for the pinned runtime."""
    modules = {
        "tracebench": "src/tracebench/__init__.py",
        "tracebench.evidence_acquisition": "src/tracebench/evidence_acquisition/__init__.py",
        **{"tracebench.evidence_acquisition." + name:
           "src/tracebench/evidence_acquisition/" + name + ".py"
           for name in ("model", "certificates", "policies")},
        **{"studies.acquisition_prior_robustness." + name: PRIOR + name + ".py"
           for name in ("aggregation", "sensitivity")},
    }
    for name, relative in modules.items():
        module = importlib.import_module(name)
        require(Path(module.__file__).resolve() == safe_path(root, relative),
                f"Imported computation comes from another checkout: {name}")


def local_history(root=ROOT, preservation=None):
    """Explicit opaque hashing; missing local evidence is an incomplete check."""
    saved = preservation or read(root / (PRIOR + "preservation.json"))
    missing, changed = [], []
    checked = 0
    manifest_path = safe_path(root, saved["local_preservation_manifest"])
    if not manifest_path.is_file():
        missing.append(saved["local_preservation_manifest"])
        local = {}
    else:
        require(digest(manifest_path) == saved["local_preservation_manifest_sha256"],
                "Historical local preservation manifest differs")
        local = read(manifest_path)["sha256"]
    for name, expected in {**saved["tracked_sha256"], **local}.items():
        path = safe_path(root, name)
        if not path.is_file():
            missing.append(name)
        elif digest(path) != expected:
            changed.append(name)
        else:
            checked += 1
    return {"status": "passed_local_history" if not missing and not changed else "incomplete_or_changed_local_history",
            "scope": "Historical preservation only; opaque bytes, never decoded provider responses",
            "matched_files": checked, "missing_files": missing, "changed_files": changed,
            "public_results": "not checked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("public-results", "local-history"))
    args = parser.parse_args()
    try:
        result = verify_public() if args.command == "public-results" else local_history()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"].startswith("passed_") else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
