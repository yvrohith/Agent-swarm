"""Frozen exact audit frontier calculation on preserved finite archives."""
from __future__ import annotations

import argparse
import json
import resource
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from time import perf_counter, process_time

from studies.acquisition_prior_robustness.aggregation import weights_for
from studies.archive_model_misspecification.expanded import ExpandedModel
from studies.audit_aware_acquisition.analysis import (
    BUDGETS,
    KS,
    METRICS,
    POPULATIONS,
    CertificateCache,
    _weighted_metric,
    aggregate_cell,
    digest,
    number,
    qualify_run,
    read,
    write_new,
)
from tracebench.evidence_acquisition.model import Model, canonical

from .execution import ARMS, ORIGINAL_ARMS, execute_audit, hindsight, verify_roots
from .frontier import FrontierPlanner

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/exact_audit_frontier"
EXACT = "exact_frontier"
AFFORDABLE = "closure_informed_affordable"
GAP_FIELDS = ("full_conflicts", "hindsight_feasible", "hindsight_impossible", "exact_detection",
              "search_gap", "policy_selection_gap", "affordability_gain")


def _failure(error):
    return {"type": type(error).__name__, "message": str(error)}


def design_measurements(root, runs):
    """Derive points from paid executions, then check against saved optima."""
    frontiers = {row["budget"]: row for row in root["solver"]["budget_frontiers"]}
    minima = {tuple(row["full_signature"]): row["minimum_cost"] for row in root["hindsight"]}
    index = defaultdict(list)
    for row in runs:
        index[row["integer_budget"], row["arm"]].append(row)
    points, budgets = [], []
    for budget in range(root["residual_cost"] + 1):
        budget_points = {}
        for arm in ARMS:
            selected = index[budget, arm]
            complete = len(selected) == root["signature_count"] and all(
                row["execution_status"] == "completed" for row in selected)
            d = sum(row["status"] == "nominal_model_conflict" for row in selected) if complete else None
            cost = sum(row["added_cost"] for row in selected) if complete else None
            dominator = None
            if complete and budget in frontiers:
                eligible = [p for p in frontiers[budget]["frontier"] if p["d"] >= d and p["l"] <= cost]
                if not eligible:
                    raise ValueError("Exact frontier does not weakly dominate a feasible comparator")
                dominator = min(eligible, key=lambda p: (p["l"], -p["d"], canonical(p)))
            point = {"integer_budget": budget, "arm": arm,
                     "status": "completed" if complete else "unavailable",
                     "signature_count": root["signature_count"], "d": d, "l": cost,
                     "nominal_compatible_cost_sum": sum(r["added_cost"] for r in selected
                                                        if r["population"] == "original") if complete else None,
                     "detected_cost_sum": sum(r["added_cost"] for r in selected
                                              if r["status"] == "nominal_model_conflict") if complete else None,
                     "frontier_dominator": dominator,
                     "strictly_dominated": (dominator["d"] > d or dominator["l"] < cost)
                     if dominator is not None else None}
            if arm == EXACT and complete:
                primary = frontiers[budget]["canonical_point"]
                if (d, cost) != (primary["d"], primary["l"]):
                    raise ValueError("Executed canonical policy differs from its exact design value")
            if complete:
                for row in selected:
                    if row["status"] == "nominal_model_conflict":
                        minimum = minima[tuple(row["outcomes"])]
                        if minimum is None or minimum > row["added_cost"]:
                            raise ValueError("Detected paid path violates hindsight certificate lower bound")
            points.append(point)
            budget_points[arm] = point
        h = sum(value is not None and value <= budget for value in minima.values())
        e, a, d = (budget_points[arm]["d"] for arm in (EXACT, AFFORDABLE, "closure_informed"))
        gap = {"integer_budget": budget, "full_conflicts": root["new_signature_count"],
               "hindsight_feasible": h, "hindsight_impossible": root["new_signature_count"] - h,
               "exact_detection": e, "search_gap": h - e if e is not None else None,
               "policy_selection_gap": e - a if e is not None and a is not None else None,
               "affordability_gain": a - d if a is not None and d is not None else None}
        if any(gap[name] is not None and gap[name] < 0 for name in
               ("hindsight_impossible", "search_gap", "policy_selection_gap")):
            raise ValueError("Negative theoretical miss component")
        budgets.append(gap)
    return points, budgets


def analyze_problem(problem, saved_conditions, *, cache=None, state_cap=100000,
                    combination_cap=10000000, retained=None):
    """Compute one complete bounded schedule; actual-k support is evaluator-only."""
    cache = cache if cache is not None else CertificateCache()
    retained = {} if retained is None else retained
    saved = {c["k"]: c for c in saved_conditions}
    if set(saved) != set(KS) or len(saved) != len(saved_conditions) or any(
            c["status"] != "completed" or c["problem_id"] != problem["problem_id"] for c in saved.values()):
        raise ValueError("Exactly the three completed saved closure conditions are required")
    nominal = Model(problem)
    design = tuple(sorted(tuple(row["outcomes"]) for row in saved[2]["signature_rows"]))
    expanded_models = {}
    # Before planners see even the compact retained identifier, bind it to the
    # actual unchanged certificate body and reconstruct each declared support.
    for k in KS:
        expanded = ExpandedModel(problem, k)
        if canonical(expanded.to_dict()) != canonical(saved[k]["expansion"]):
            raise ValueError("Saved expanded closure did not reproduce exactly")
        expanded_models[k] = expanded
        for source in saved[k]["signature_rows"]:
            baseline = source["policy"]
            for model, name in ((nominal, "certificate"), (expanded, "expanded_certificate")):
                reference = baseline[name]
                actual = cache.get(model, baseline["history"], saved[k]["certificates"][reference])
                if actual != reference:
                    raise ValueError("Saved stopping certificate reference is not its actual body pin")
    roots = verify_roots(nominal, design, saved[2]["signature_rows"], certificate_cache=cache)
    roots.sort(key=lambda r: r["root_id"])
    design_runs, anchor_runs, cells = [], [], []
    retained.update({"roots": roots, "design_runs": design_runs, "runs": anchor_runs, "cells": cells})
    for root in roots:
        root.update({"problem_id": problem["problem_id"], "stratum": problem["stratum"],
                     "subtype": problem.get("subtype", problem["stratum"])})
        planner = FrontierPlanner(nominal, design, root["base_history"],
                                  state_cap=state_cap, combination_cap=combination_cap)
        root["solver"] = planner.solve()
        root["exact_status"] = "completed" if root["solver"]["status"] == "complete" else "unavailable"
        root["failure"] = root["solver"].get("cap")
        root["hindsight"] = []
        for signature in root["signatures"]:
            minimum = hindsight(nominal, root, signature, certificate_cache=cache)
            if minimum["certificate"] is not None:
                observed = root["base_history"] + minimum["additional_history"]
                reference = cache.get(nominal, observed, minimum["certificate"])
                if reference != minimum["certificate_pin"]:
                    raise ValueError("Hindsight certificate binding differs")
            root["hindsight"].append(minimum)
        wall, cpu = perf_counter(), process_time()
        current = []
        for budget in range(root["residual_cost"] + 1):
            for arm in ARMS:
                for signature in root["signatures"]:
                    metadata = {"problem_id": problem["problem_id"], "root_id": root["root_id"],
                                "integer_budget": budget, "budget_percent": None, "arm": arm,
                                "outcomes": signature,
                                "population": "original" if tuple(signature) in nominal.signature_cells else "new"}
                    if arm == EXACT and root["exact_status"] != "completed":
                        current.append({**metadata, "execution_status": "unavailable", "failure": root["failure"]})
                        continue
                    try:
                        result = execute_audit(nominal, root["baseline"], signature, arm, budget,
                                               design_signatures=design if arm in
                                               ("closure_informed", AFFORDABLE, EXACT) else None,
                                               planner=planner if arm == EXACT else None,
                                               certificate_cache=cache)
                        references = {"base_nominal": cache.get(nominal, root["base_history"]),
                                      "final_nominal": cache.get(nominal, result["history"])}
                        current.append({**result, **metadata, "execution_status": "completed",
                                        "certificates": references})
                    except Exception as error:
                        current.append({**metadata, "execution_status": "unavailable", "failure": _failure(error)})
        root["execution_resources"] = {"all_integer_reconstruction_wall_seconds": perf_counter() - wall,
                                       "all_integer_reconstruction_cpu_seconds": process_time() - cpu}
        root["solver"] = planner.export()
        design_runs.extend(current)
        root["design_points"], root["budget_summary"] = design_measurements(root, current)
        del planner
    by_signature = {tuple(signature): root for root in roots for signature in root["signatures"]}
    design_index = {(r["root_id"], r["integer_budget"], r["arm"], tuple(r["outcomes"])): r for r in design_runs}
    for k in KS:
        for arm in ARMS:
            for percent in BUDGETS:
                current, missing = [], []
                for source in saved[k]["signature_rows"]:
                    signature = tuple(source["outcomes"])
                    root = by_signature[signature]
                    budget = root["residual_cost"] * percent // 100
                    executed = design_index[root["root_id"], budget, arm, signature]
                    if executed["execution_status"] != "completed":
                        row = {**executed, "k": k, "signature_id": source["signature_id"],
                               "budget_percent": percent, "stratum": problem["stratum"],
                               "subtype": problem.get("subtype", problem["stratum"])}
                        missing.append(row["failure"])
                    else:
                        result = {**executed, "budget_percent": percent}
                        row = qualify_run(problem, nominal, expanded_models[k], source, result,
                                          cache, saved[k]["certificates"])
                        current.append(row)
                    anchor_runs.append(row)
                cells.append(aggregate_cell(problem, k, arm, percent, current,
                                            len(saved[k]["signature_rows"]),
                                            {"unavailable_runs": len(missing), "causes": missing} if missing else None))
    return retained


def legacy_parity(runs, historical):
    """Compare retained fields exactly, excluding only measured runtime."""
    def key(row):
        return row["problem_id"], row["k"], row["arm"], row["budget_percent"], row["signature_id"]
    index = {key(r): r for r in runs if r["arm"] in ORIGINAL_ARMS}
    if len(index) != len(historical) or set(index) != {key(r) for r in historical}:
        raise ValueError("Original four-arm anchor schedule differs")
    for old in historical:
        new = index[key(old)]
        if new["execution_status"] != "completed":
            raise ValueError("Historical comparator path is unavailable")
        for name, value in old.items():
            if name not in ("selection_seconds", "checking_seconds") and canonical(new.get(name)) != canonical(value):
                raise ValueError(f"Original arm did not reproduce retained {name}: {key(old)}")
    return {"status": "passed", "historical_anchor_runs": len(historical),
            "excluded_fields": ["selection_seconds", "checking_seconds"]}


def summarize(cells, groups):
    index = {(c["problem_id"], c["k"], c["arm"], c["budget_percent"]): c for c in cells}
    expected = {(pid, k, arm, budget) for pid in groups for k in KS for arm in ARMS for budget in BUDGETS}
    if len(index) != len(cells) or set(index) != expected:
        raise ValueError("All fixed problem/condition/arm/budget cells must remain present")
    buckets = defaultdict(list)
    for cell in cells:
        for stratum, subtype in {("all", "all"), (cell["stratum"], "all"),
                                 (cell["stratum"], cell["subtype"])}:
            buckets[cell["k"], cell["arm"], cell["budget_percent"], stratum, subtype].append(cell)
    result = []
    for (k, arm, budget, stratum, subtype), selected in sorted(buckets.items()):
        for population in POPULATIONS:
            pooled_counts, pooled_totals, joint = Counter(), Counter(), Counter()
            for cell in selected:
                part = cell["populations"][population]
                pooled_counts.update(part["counts"])
                pooled_totals.update(part["totals"])
                for item in part["joint_counts"]:
                    joint[canonical({key: value for key, value in item.items() if key != "count"}).decode()] += item["count"]
            for weighting in ("equal_problem", "structure_balanced"):
                result.append({
                    "k": k, "arm": arm, "budget_percent": budget, "stratum": stratum, "subtype": subtype,
                    "population": population, "weighting": weighting,
                    "comparison_scope": "fixed_k2_envelope" if arm in ("closure_informed", AFFORDABLE, EXACT) else "nominal_only",
                    "problem_count": len(selected), "structure_count": len({groups[c["problem_id"]] for c in selected}),
                    "unavailable_problems": [c["problem_id"] for c in selected if c["status"] != "completed"],
                    "pooled_counts": dict(pooled_counts), "pooled_totals": dict(pooled_totals),
                    "pooled_counts_complete": all(c["status"] == "completed" for c in selected),
                    "joint_counts": [{**json.loads(key), "count": value} for key, value in sorted(joint.items())],
                    "metrics": {name: _weighted_metric(selected, population, name, groups, weighting) for name in METRICS},
                })
    return {"interpretation": "Descriptive signature census, not a deployment prior; actual k populations remain separate",
            "problem_to_group": groups, "conditions": result}


def paired_differences(cells, groups):
    index = {(c["problem_id"], c["k"], c["arm"], c["budget_percent"]): c for c in cells}
    per_problem = []
    comparisons = ((EXACT, AFFORDABLE, "primary_matched_information_and_budget"),
                   (EXACT, "closure_informed", "secondary_budget_awareness_and_planning"),
                   (AFFORDABLE, "closure_informed", "secondary_affordable_candidate_filter"))
    for pid in sorted(groups):
        for k in KS:
            for budget in BUDGETS:
                for left, right, scope in comparisons:
                    a, b = index[pid, k, left, budget], index[pid, k, right, budget]
                    for population in POPULATIONS:
                        values = {}
                        for name in METRICS:
                            av = a["populations"][population]["metrics"][name]
                            bv = b["populations"][population]["metrics"][name]
                            values[name] = number(Fraction(av["exact"]) - Fraction(bv["exact"])) \
                                if av is not None and bv is not None and a["status"] == b["status"] == "completed" else None
                        per_problem.append({"problem_id": pid, "structure_group": groups[pid],
                                            "stratum": a["stratum"], "subtype": a["subtype"], "k": k,
                                            "budget_percent": budget, "left": left, "right": right,
                                            "comparison_scope": scope, "population": population,
                                            "available": a["status"] == b["status"] == "completed", "differences": values})
    buckets = defaultdict(list)
    for row in per_problem:
        for stratum in {"all", row["stratum"]}:
            buckets[row["k"], row["budget_percent"], row["left"], row["right"], row["population"], stratum].append(row)
    summaries = []
    for (k, budget, left, right, population, stratum), rows in sorted(buckets.items()):
        for weighting in ("equal_problem", "structure_balanced"):
            metrics = {}
            for name in METRICS:
                failed = [r["problem_id"] for r in rows if not r["available"]]
                defined = {r["problem_id"]: Fraction(r["differences"][name]["exact"])
                           for r in rows if r["differences"][name] is not None and r["available"]}
                mean = None
                if defined and not failed:
                    weights = weights_for(defined, groups, weighting)
                    mean = sum((weights[pid] * value for pid, value in defined.items()), Fraction())
                metrics[name] = {"mean": number(mean), "expected_problems": len(rows),
                                 "defined_problems": len(defined), "failed_problems": failed,
                                 "undefined_problems": [r["problem_id"] for r in rows
                                                        if r["problem_id"] not in defined and r["problem_id"] not in failed],
                                 "lower": sum(v < 0 for v in defined.values()),
                                 "tied": sum(v == 0 for v in defined.values()),
                                 "higher": sum(v > 0 for v in defined.values())}
            summaries.append({"k": k, "budget_percent": budget, "left": left, "right": right,
                              "comparison_scope": rows[0]["comparison_scope"], "population": population,
                              "stratum": stratum, "weighting": weighting, "metrics": metrics})
    return {"direction": "left minus right; lower retrieval cost is not a matched-detection improvement unless detection is comparable; warrant remains a separate objective",
            "per_problem": per_problem, "summary": summaries}


def summarize_design(roots, groups):
    """Count each signature through one root; never average roots equally."""
    problems = defaultdict(list)
    for root in roots:
        problems[root["problem_id"]].append(root)
    if set(problems) != set(groups):
        raise ValueError("Design summary lost a fixed problem")
    per_problem = []
    for pid, selected in sorted(problems.items()):
        size = sum(r["signature_count"] for r in selected)
        new_count = sum(r["new_signature_count"] for r in selected)
        for percent in BUDGETS:
            gaps = [next(g for g in r["budget_summary"] if g["integer_budget"] ==
                         r["residual_cost"] * percent // 100) for r in selected]
            counts = {name: sum(g[name] for g in gaps) if all(g[name] is not None for g in gaps) else None
                      for name in GAP_FIELDS}
            metrics = {name + "_per_new_signature": number(Fraction(value, new_count))
                       if value is not None and new_count else None for name, value in counts.items()}
            unavailable = {name + "_per_new_signature": [r["root_id"] for r, g in zip(selected, gaps, strict=True)
                                                         if g[name] is None] for name in GAP_FIELDS}
            arms = {}
            for arm in ARMS:
                points = [next(p for p in r["design_points"] if p["arm"] == arm and
                               p["integer_budget"] == r["residual_cost"] * percent // 100) for r in selected]
                complete = all(p["status"] == "completed" for p in points)
                fields = ("d", "l", "nominal_compatible_cost_sum", "detected_cost_sum")
                totals = {name: sum(p[name] for p in points) if complete else None for name in fields}
                dominators = [p["frontier_dominator"] for p in points]
                available_frontier = complete and all(d is not None for d in dominators)
                arms[arm] = {"status": "completed" if complete else "unavailable", **totals,
                             "dominating_detection": sum(d["d"] for d in dominators) if available_frontier else None,
                             "dominating_cost": sum(d["l"] for d in dominators) if available_frontier else None,
                             "strictly_dominated_roots": sum(p["strictly_dominated"] for p in points)
                             if available_frontier else None,
                             "frontier_matched_detection_cost_saving":
                             totals["l"] - sum(d["l"] for d in dominators) if available_frontier else None}
                arm_metrics = {
                    "detection_fraction_new": (totals["d"], new_count),
                    "added_cost_per_all_signature": (totals["l"], size),
                    "added_cost_per_original_signature": (totals["nominal_compatible_cost_sum"], size - new_count),
                    "cost_conditional_on_detection": (totals["detected_cost_sum"], totals["d"]),
                    "frontier_matched_detection_saving_per_all_signature":
                    (arms[arm]["frontier_matched_detection_cost_saving"], size),
                }
                for name, (value, denominator) in arm_metrics.items():
                    key = arm + ":" + name
                    metrics[key] = number(Fraction(value, denominator)) if value is not None and denominator else None
                    unavailable[key] = [r["root_id"] for r, p in zip(selected, points, strict=True)
                                        if p["status"] != "completed" or
                                        (name.startswith("frontier_") and p["frontier_dominator"] is None)]
            per_problem.append({"problem_id": pid, "stratum": selected[0]["stratum"],
                                "structure_group": groups[pid], "budget_percent": percent,
                                "root_count": len(selected), "signature_count": size,
                                "new_signature_count": new_count,
                                "unavailable_exact_roots": [r["root_id"] for r in selected
                                                            if r["exact_status"] != "completed"],
                                "counts": counts, "arms": arms, "metrics": metrics,
                                "unavailable_metric_roots": unavailable})
    output = []
    for percent in BUDGETS:
        for stratum in ["all", *sorted({r["stratum"] for r in per_problem})]:
            selected = [r for r in per_problem if r["budget_percent"] == percent and
                        (stratum == "all" or r["stratum"] == stratum)]
            for rule in ("equal_problem", "structure_balanced"):
                metrics = {}
                for name in selected[0]["metrics"]:
                    failed = [r["problem_id"] for r in selected if r["unavailable_metric_roots"][name]]
                    defined = {r["problem_id"]: Fraction(r["metrics"][name]["exact"]) for r in selected
                               if r["metrics"][name] is not None and r["problem_id"] not in failed}
                    weights = weights_for(defined, groups, rule) if defined and not failed else {}
                    metrics[name] = {"mean": number(sum((weights[p] * v for p, v in defined.items()), Fraction()))
                                     if weights else None, "expected_problems": len(selected),
                                     "defined_problems": len(defined), "failed_problems": failed,
                                     "undefined_problems": [r["problem_id"] for r in selected
                                                            if r["problem_id"] not in defined and r["problem_id"] not in failed]}
                output.append({"budget_percent": percent, "stratum": stratum, "weighting": rule,
                               "problem_count": len(selected),
                               "signature_count": sum(r["signature_count"] for r in selected),
                               "new_signature_count": sum(r["new_signature_count"] for r in selected),
                               "unavailable_exact_roots": [x for r in selected for x in r["unavailable_exact_roots"]],
                               "pooled_counts": {name: sum(r["counts"][name] for r in selected)
                                                 if all(r["counts"][name] is not None for r in selected) else None
                                                 for name in GAP_FIELDS},
                               "pooled_arms": {arm: {name: sum(r["arms"][arm][name] for r in selected)
                                                      if all(r["arms"][arm][name] is not None for r in selected) else None
                                                      for name in ("d", "l", "nominal_compatible_cost_sum",
                                                                   "dominating_detection", "dominating_cost",
                                                                   "frontier_matched_detection_cost_saving")}
                                               for arm in ARMS}, "metrics": metrics})
    return {"interpretation": "Fixed k2 design census; root-conditioned anchors, not equal-root averages or actual-k optimization",
            "per_problem": per_problem, "summary": output}


def settings():
    config = read(STUDY / "config.json")
    expected = {"evaluation_problems": 40, "development_problems": 4, "evaluation_anchor_cells": 2880,
                "omission_budgets": list(KS), "arms": list(ARMS), "extra_budget_percentages": list(BUDGETS),
                "design_envelope_k": 2, "expanded_world_cap": 4096, "signature_cap": 256, "query_cap": 8,
                "outcomes_per_query_cap": 2,
                "caps": {"states_per_root": 100000, "child_combinations_per_root": 10000000},
                "evaluation_source": "studies/evidence_acquisition/evaluation_problems.json",
                "development_source": "studies/evidence_acquisition/development_problems.json",
                "evaluation_baseline_source": "studies/archive_model_misspecification/results/details.json.gz",
                "development_baseline_source": "studies/audit_aware_acquisition/development_baseline.json.gz",
                "evaluation_legacy_audit_source": "studies/audit_aware_acquisition/results/runs.json.gz",
                "development_legacy_audit_source": "studies/exact_audit_frontier/development_legacy_audit.json.gz",
                "group_source": "studies/acquisition_prior_robustness/structure_groups.json",
                "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("Configuration differs from the fixed authorized exact-frontier design")
    return config


def verify_preservation():
    saved = read(STUDY / "preservation.json")
    if digest(ROOT / saved["local_preservation_manifest"]) != saved["local_preservation_manifest_sha256"]:
        raise ValueError("Historical local preservation manifest changed")
    local = read(ROOT / saved["local_preservation_manifest"])
    for path, expected in {**saved["tracked_sha256"], **local["sha256"]}.items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Historical byte preservation mismatch: {path}")
    return {"tracked_files": len(saved["tracked_sha256"]), "local_files": len(local["sha256"])}


def verify_input_provenance():
    """Check the portable dev copy against the already reconciled old source."""
    provenance = read(STUDY / "input_provenance.json")["development_legacy_audit"]
    baseline = read(STUDY / "baseline_verification.json")
    recorded = baseline["portable_development_audit_provenance"]
    expected = "studies/exact_audit_frontier/development_legacy_audit.json.gz"
    if (provenance.get("copy") != expected or recorded.get("copy") != expected or
            provenance.get("byte_identical") is not True or recorded.get("byte_identical") is not True or
            provenance.get("sha256") != recorded.get("sha256") or
            provenance.get("source") != recorded.get("source") or
            digest(ROOT / expected) != recorded["sha256"]):
        raise ValueError("Portable legacy development provenance differs from reconciled historical bytes")
    for name in (expected, "studies/exact_audit_frontier/input_provenance.json"):
        if digest(ROOT / name) != baseline["input_sha256"][name]:
            raise ValueError("Baseline input pin differs from the declared portable development source")
    return {"status": "passed", "copy_sha256": recorded["sha256"]}


def dependencies():
    paths = ["src/tracebench/__init__.py",
             *[f"src/tracebench/evidence_acquisition/{name}.py" for name in ("__init__", "model", "policies", "certificates")],
             "studies/acquisition_prior_robustness/aggregation.py", "studies/acquisition_prior_robustness/structure_groups.json",
             "studies/acquisition_prior_robustness/sensitivity.py",
             *[f"studies/archive_model_misspecification/{name}" for name in
               ("expanded.py", "reference.py", "analysis.py", "results/details.json.gz")],
             "studies/evidence_acquisition/development_problems.json", "studies/evidence_acquisition/evaluation_problems.json",
             *[f"studies/audit_aware_acquisition/{name}" for name in
               ("analysis.py", "auditing.py", "reference.py", "development_baseline.json.gz", "results/runs.json.gz")],
             *[f"studies/exact_audit_frontier/{name}" for name in
               ("analysis.py", "execution.py", "frontier.py", "reference.py", "config.json", "ANALYSIS.md", "METHOD.md",
                "development_legacy_audit.json.gz", "input_provenance.json", "baseline_verification.json",
                "development_checks.json", "pre_freeze_checks.json")],
             "tests/test_audit_aware_acquisition.py", "tests/test_exact_audit_frontier.py",
             "tests/test_exact_audit_execution.py", "tests/test_exact_audit_planner_guards.py",
             "tests/test_exact_audit_driver.py"]
    return [ROOT / path for path in paths]


def verify_freeze():
    frozen = read(STUDY / "freeze.json")
    if set(frozen["files_sha256"]) != {str(path.relative_to(ROOT)) for path in dependencies()}:
        raise ValueError("Frozen computational dependency closure differs")
    for path, expected in frozen["files_sha256"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Frozen computational input changed: {path}")
    settings()
    return len(frozen["files_sha256"])


def freeze():
    settings()
    verify_input_provenance()
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        if read(STUDY / name).get("status") != "passed":
            raise ValueError(f"Pre-freeze check has not passed: {name}")
    if read(STUDY / "pre_freeze_checks.json").get("new_evaluation_policy_outcomes_observed") != 0:
        raise ValueError("New-policy evaluation chronology is not pre-outcome")
    development = read(STUDY / "development_checks.json")
    if development.get("new_evaluation_policy_outcomes_observed") != 0:
        raise ValueError("Development check chronology is not pre-outcome")
    expected_sources = {str(p.relative_to(ROOT)) for p in dependencies()
                        if p.name not in ("development_checks.json", "pre_freeze_checks.json")}
    if set(development.get("source_sha256", {})) != expected_sources:
        raise ValueError("Development checks did not pin the complete computational source closure")
    for name, expected in development["source_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Computational source changed after development qualification")
    write_new(STUDY / "freeze.json", {
        "schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "new_evaluation_policy_outcomes_observed": 0, "known_legacy_audit_outcomes": True,
        "python_version": sys.version,
        "files_sha256": {str(path.relative_to(ROOT)): digest(path) for path in dependencies()},
        "preservation": verify_preservation()})
    return {"status": "frozen", "dependencies": verify_freeze()}


def _inputs(development):
    config = settings()
    verify_input_provenance()
    prefix = "development" if development else "evaluation"
    problems = read(ROOT / config[prefix + "_source"])
    saved = read(ROOT / config[prefix + "_baseline_source"])
    historical = read(ROOT / config[prefix + "_legacy_audit_source"])
    expected = config[prefix + "_problems"]
    if len(problems) != expected or len(saved) != expected * 3:
        raise ValueError("Fixed problem/support counts differ")
    groups = ({p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems} if development else
              read(ROOT / config["group_source"])["problem_to_group"])
    if set(groups) != {p["problem_id"] for p in problems}:
        raise ValueError("Structural-group mapping differs from the fixed population")
    return problems, saved, historical, groups


def _check_schedule(roots, design_runs, runs, cells, development):
    actual = {"roots": len(roots), "root_integer_budget_cells": sum(r["residual_cost"] + 1 for r in roots),
              "integer_design_runs_six_arms": len(design_runs), "anchor_cells": len(cells), "anchor_runs": len(runs)}
    expected = settings()["expected_schedule"]["development" if development else "evaluation"]
    if actual != expected:
        raise ValueError(f"Retained fixed schedule differs: {actual}")
    return actual


def execute(output, *, development=False):
    from .reference import verify_all

    if not development:
        verify_freeze()
    verify_preservation()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    config = settings()
    problems, saved, historical, groups = _inputs(development)
    cache = CertificateCache()
    roots, design_runs, runs, cells, failures = [], [], [], [], []
    wall, cpu = perf_counter(), process_time()
    for problem in problems:
        selected = [c for c in saved if c["problem_id"] == problem["problem_id"]]
        attempted = {}
        # Unexpected construction failures stop this bounded run after saving
        # completed output; they never substitute a different problem or prefix.
        try:
            result = analyze_problem(problem, selected, cache=cache,
                                     state_cap=config["caps"]["states_per_root"],
                                     combination_cap=config["caps"]["child_combinations_per_root"], retained=attempted)
            roots.extend(result["roots"])
            design_runs.extend(result["design_runs"])
            runs.extend(result["runs"])
            cells.extend(result["cells"])
        except Exception as error:
            failures.append({"problem_id": problem["problem_id"], **_failure(error),
                             "attempted_problem": attempted})
            break
        print(json.dumps({"problem_id": problem["problem_id"], "roots_retained": len(roots),
                          "integer_paths_retained": len(design_runs), "anchor_paths_retained": len(runs)}), flush=True)
        if not development:
            verify_freeze()
    schedule = None
    parity = {"status": "unavailable"}
    check_wall, check_cpu = perf_counter(), process_time()
    try:
        schedule = _check_schedule(roots, design_runs, runs, cells, development)
        parity = legacy_parity(runs, historical)
        independent = verify_all(problems, saved, roots, design_runs, runs, cache.certificates)
    except Exception as error:
        independent = {"status": "failed", "failure": _failure(error)}
    checker = {"wall_seconds": perf_counter() - check_wall, "cpu_seconds": process_time() - check_cpu}
    if failures:
        summary = paired = design_summary = {"status": "unavailable", "failures": failures}
    else:
        summary, paired, design_summary = summarize(cells, groups), paired_differences(cells, groups), summarize_design(roots, groups)
    artifacts = {"roots.json.gz": roots, "design_runs.json.gz": design_runs, "runs.json.gz": runs,
                 "certificates.json.gz": cache.certificates, "per_condition.json.gz": cells,
                 "summary.json.gz": summary, "paired.json.gz": paired, "design_summary.json.gz": design_summary,
                 "independent_verification.json": independent, "legacy_parity.json": parity}
    serialize_wall, serialize_cpu = perf_counter(), process_time()
    for name, value in artifacts.items():
        write_new(output / name, value)
    serialization = {"wall_seconds": perf_counter() - serialize_wall, "cpu_seconds": process_time() - serialize_cpu}
    completed_cells = sum(c["status"] == "completed" for c in cells)
    complete = not failures and schedule is not None and completed_cells == len(cells) and independent.get("status") == "passed"
    expected_schedule = config["expected_schedule"]["development" if development else "evaluation"]
    retained_schedule = {"roots": len(roots), "root_integer_budget_cells": sum(r["residual_cost"] + 1 for r in roots),
                         "integer_design_runs_six_arms": len(design_runs),
                         "anchor_cells": len(cells), "anchor_runs": len(runs)}
    validation = {"status": "passed" if complete else "unavailable_or_failed_checks_retained",
                  "split": "development" if development else "evaluation", "problems": len(problems),
                  "schedule": schedule, "completed_roots": sum(r["exact_status"] == "completed" for r in roots),
                  "expected_schedule": expected_schedule, "retained_schedule": retained_schedule,
                  "missing_schedule_counts": {key: expected_schedule[key] - retained_schedule[key]
                                              for key in expected_schedule},
                  "missing_problem_ids": sorted(set(groups) - {r["problem_id"] for r in roots}),
                  "unavailable_roots": [r["root_id"] for r in roots if r["exact_status"] != "completed"],
                  "completed_cells": completed_cells, "aggregate_cells": len(cells),
                  "completed_design_runs": sum(r["execution_status"] == "completed" for r in design_runs),
                  "completed_anchor_runs": sum(r["execution_status"] == "completed" for r in runs),
                  "failures": failures, "certificate_checks": cache.stats(),
                  "resources": {"total_wall_seconds": perf_counter() - wall, "total_cpu_seconds": process_time() - cpu,
                                "independent_checker": checker, "serialization": serialization,
                                "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                "peak_scope": "Cumulative process peak, not an isolated per-policy measurement"},
                  "preservation": verify_preservation(), "frozen_dependencies": None if development else verify_freeze(),
                  "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
    write_new(output / "validation.json", validation)
    write_new(output / "manifest.json", {"freeze_sha256": None if development else digest(STUDY / "freeze.json"),
                                        "files_sha256": {p.name: digest(p) for p in sorted(output.iterdir())}})
    if development:
        write_new(STUDY / "development_checks.json", {**validation, "output": str(output.resolve().relative_to(ROOT)),
                  "manifest_sha256": digest(output / "manifest.json"), "new_evaluation_policy_outcomes_observed": 0,
                  "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in dependencies()
                                    if p.name not in ("development_checks.json", "pre_freeze_checks.json")}})
    return validation


def verify_outputs(output):
    from .reference import verify_all

    verify_freeze()
    output = Path(output)
    manifest = read(output / "manifest.json")
    if manifest["freeze_sha256"] != digest(STUDY / "freeze.json"):
        raise ValueError("Result freeze pin differs")
    for name, expected in manifest["files_sha256"].items():
        if Path(name).name != name or digest(output / name) != expected:
            raise ValueError("Result manifest bytes differ")
    problems, saved, historical, groups = _inputs(False)
    roots, design_runs, runs, certificates, cells = (read(output / name) for name in
        ("roots.json.gz", "design_runs.json.gz", "runs.json.gz", "certificates.json.gz", "per_condition.json.gz"))
    schedule = _check_schedule(roots, design_runs, runs, cells, False)
    parity = legacy_parity(runs, historical)
    checked = verify_all(problems, saved, roots, design_runs, runs, certificates)
    if checked.get("status") not in ("passed", "unavailable_exact_roots_verified"):
        raise ValueError("Independent verification returned a failed or unrecognized status")
    by_key, design_by_root = defaultdict(list), defaultdict(list)
    for row in runs:
        by_key[row["problem_id"], row["k"], row["arm"], row["budget_percent"]].append(row)
    for row in design_runs:
        design_by_root[row["root_id"]].append(row)
    for root in roots:
        points, budgets = design_measurements(root, design_by_root[root["root_id"]])
        if canonical(points) != canonical(root["design_points"]) or canonical(budgets) != canonical(root["budget_summary"]):
            raise ValueError("Root design points/gaps differ from paid execution reaggregation")
    problem_map = {p["problem_id"]: p for p in problems}
    source_map = {(c["problem_id"], c["k"]): c for c in saved}
    for cell in cells:
        key = cell["problem_id"], cell["k"], cell["arm"], cell["budget_percent"]
        completed = [r for r in by_key[key] if r["execution_status"] == "completed"]
        missing = [r["failure"] for r in by_key[key] if r["execution_status"] != "completed"]
        expected = aggregate_cell(problem_map[key[0]], *key[1:], completed,
                                  len(source_map[key[:2]]["signature_rows"]),
                                  {"unavailable_runs": len(missing), "causes": missing} if missing else None)
        if canonical(cell) != canonical(expected):
            raise ValueError("Anchor cell differs from exact reaggregation")
    for name, computed in (("summary.json.gz", summarize(cells, groups)),
                           ("paired.json.gz", paired_differences(cells, groups)),
                           ("design_summary.json.gz", summarize_design(roots, groups))):
        if canonical(computed) != canonical(read(output / name)):
            raise ValueError(f"Saved {name} differs from exact reaggregation")
    return {"status": "passed" if checked.get("status") == "passed" else "unavailable_exact_roots_verified",
            "schedule": schedule, "independent_verification": checked, "legacy_parity": parity,
            "scope": "Frozen scientific dependencies and retained outputs; historical preservation is checked separately"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("develop", "freeze", "run", "verify", "preservation"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze()
    elif args.command == "preservation":
        result = verify_preservation()
    elif args.command == "develop":
        if args.output is None:
            parser.error("development requires a fresh ignored --output directory")
        result = execute(args.output, development=True)
    elif args.command == "verify":
        result = verify_outputs(args.output or STUDY / "results")
    else:
        result = execute(args.output or STUDY / "results")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
