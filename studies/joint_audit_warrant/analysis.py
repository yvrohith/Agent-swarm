"""Bounded joint detection/support frontiers on retained acquisition roots."""
from __future__ import annotations

import argparse
import copy
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
    POPULATIONS,
    CertificateCache,
    _weighted_metric,
    digest,
    number,
    qualify_run,
    read,
    write_new,
)
from studies.audit_aware_acquisition.analysis import METRICS as BASE_METRICS
from studies.audit_aware_acquisition.analysis import (
    aggregate_cell as original_aggregate_cell,
)
from tracebench.evidence_acquisition.model import Model, canonical, pin

from .execution import SavedEPolicy, execute_audit
from .frontier import JointFrontierPlanner
from .support import SupportContract

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/joint_audit_warrant"
E, SEQUENTIAL, JOINT = "exact_frontier", "E_then_support", "joint_frontier"
ARMS = (E, SEQUENTIAL, JOINT)
PHASE_FIELDS = tuple(f"{phase}_phase_{measure}" for phase in ("detection", "support", "joint")
                     for measure in ("cost", "query_count", "returned_bytes"))
DESIGN_FLAGS = ("design_supported_original", "design_initially_supported_original", "design_newly_supported_original")
STATUS_FLAGS = ("claim_established", "claim_ruled_out", "claim_unresolved", "operational_pending", "operational_irreducible")
METRICS = (*BASE_METRICS, *PHASE_FIELDS, *DESIGN_FLAGS, *STATUS_FLAGS)
ROOT_FIELDS = ("nominal_model_pin", "design_signature_set_pin", "base_history", "root_pin", "root_id",
               "baseline", "signatures", "root_signature_set_pin", "signature_count", "original_signature_count",
               "new_signature_count", "unqueried_query_ids", "residual_cost", "original_path_verified",
               "problem_id", "stratum", "subtype")


def _failure(error):
    return {"type": type(error).__name__, "message": str(error)}


def aggregate_cell(problem, k, arm, budget, runs, expected_count, failure=None):
    result = original_aggregate_cell(problem, k, arm, budget, runs, expected_count, failure)
    for population in POPULATIONS:
        selected = [r for r in runs if population == "all" or r["population"] == population]
        part = result["populations"][population]
        size = len(selected)
        for field in PHASE_FIELDS:
            total = sum(r[field] for r in selected)
            part["totals"][field] = total
            part["metrics"][field] = number(Fraction(total, size)) if size else None
            part["worst"][field] = max((r[field] for r in selected), default=None)
        for field in (*DESIGN_FLAGS, *STATUS_FLAGS):
            count = sum(r[field] for r in selected)
            part["counts"][field] = count
            part["metrics"][field] = number(Fraction(count, size)) if size else None
    return result


def _support_baseline(support, root):
    definite = root["baseline"]["status"] in ("established", "ruled_out")
    initial = support.reward(support.mask(root["base_history"]))
    ceiling = sum(support.supported(1 << i) for i, signature in enumerate(support.design_signatures)
                  if list(signature) in root["signatures"] and signature in support.nominal.signature_cells)
    original_definite = root["original_signature_count"] if definite else 0
    return {"original_definite_count": original_definite, "initial_supported": initial,
            "initially_unsupported": original_definite - initial,
            "full_archive_support_ceiling": ceiling,
            "full_archive_unsupported_floor": original_definite - ceiling}


def design_measurements(root, runs, old_root):
    """Actual charged rewards, full projection equality, and support prices."""
    new_frontiers = {f["budget"]: f for f in root["solver"]["budget_frontiers"]}
    old_frontiers = {f["budget"]: f for f in old_root["solver"]["budget_frontiers"]}
    index = defaultdict(list)
    for row in runs:
        index[row["integer_budget"], row["arm"]].append(row)
    points, budgets = [], []
    for budget in root["integer_budgets"]:
        available = budget in new_frontiers
        old = old_frontiers[budget]
        old_projection = sorted({(p["d"], p["l"]) for p in old["frontier"]})
        projection = None
        if available:
            triples = new_frontiers[budget]["frontier"]
            pairs = {(p["d"], p["l"]) for p in triples}
            projection = sorted((d, cost) for d, cost in pairs if not any(
                od >= d and ocost <= cost and (od, ocost) != (d, cost) for od, ocost in pairs))
            if projection != old_projection:
                raise ValueError("Joint frontier projection differs from the saved detection-cost frontier")
        current = {}
        for arm in ARMS:
            rows = index[budget, arm]
            complete = len(rows) == root["signature_count"] and all(r["execution_status"] == "completed" for r in rows)
            point = {"integer_budget": budget, "arm": arm, "status": "completed" if complete else "unavailable",
                     "signature_count": root["signature_count"],
                     "d": sum(r["status"] == "nominal_model_conflict" for r in rows) if complete else None,
                     "w": sum(r["design_supported_original"] for r in rows) if complete else None,
                     "l": sum(r["added_cost"] for r in rows) if complete else None,
                     "newly_supported_original": sum(r["design_newly_supported_original"] for r in rows) if complete else None,
                     "original_cost": sum(r["added_cost"] for r in rows if r["population"] == "original") if complete else None,
                     "new_cost": sum(r["added_cost"] for r in rows if r["population"] == "new") if complete else None,
                     "phase_costs": {phase: sum(r[f"{phase}_phase_cost"] for r in rows) if complete else None
                                     for phase in ("detection", "support", "joint")},
                     "dominating_joint_point": None}
            if complete:
                if point["d"] != old["canonical_point"]["d"]:
                    raise ValueError("A study arm lost or exceeded the preserved maximum detection")
                if arm == E and point["l"] != old["canonical_point"]["l"]:
                    raise ValueError("Historical E paths do not reproduce their saved minimum-cost value")
                if available:
                    eligible = [p for p in triples if p["d"] >= point["d"] and p["w"] >= point["w"] and p["l"] <= point["l"]]
                    if not eligible:
                        raise ValueError("Feasible policy triple lacks an attainable weakly dominating frontier point")
                    point["dominating_joint_point"] = min(eligible, key=lambda p: (p["l"], -p["d"], -p["w"], canonical(p)))
                    if arm == JOINT:
                        expected = new_frontiers[budget]["canonical_point"]
                        if tuple(point[k] for k in ("d", "w", "l")) != tuple(expected[k] for k in ("d", "w", "l")):
                            raise ValueError("Executed joint policy does not attain its exact triple")
            points.append(point)
            current[arm] = point
        e, sequential, joint = (current[arm] for arm in ARMS)
        max_d = old["canonical_point"]["d"]
        levels = sorted((p for p in new_frontiers[budget]["frontier"] if p["d"] == max_d),
                        key=lambda p: (p["w"], p["l"], canonical(p))) if available else None
        threshold_curve = []
        if levels is not None:
            for threshold in range(root["support_baseline"]["full_archive_support_ceiling"] + 1):
                eligible = [p for p in levels if p["w"] >= threshold]
                selected = min(eligible, key=lambda p: (p["l"], -p["w"], canonical(p))) if eligible else None
                threshold_curve.append({"minimum_supported_original": threshold,
                                        "minimum_cost": selected["l"] if selected else None, "attaining_point": selected})
        free_points = [p for p in levels or () if e["l"] is not None and p["l"] <= e["l"]]
        free = min(free_points, key=lambda p: (-p["w"], p["l"], canonical(p))) if free_points else None
        summary = {"integer_budget": budget, "detection_ceiling": max_d,
                   "saved_detection_cost_frontier": [{"d": d, "l": cost} for d, cost in old_projection],
                   "joint_projection": [{"d": d, "l": cost} for d, cost in projection] if projection is not None else None,
                   "projection_equal": True if available else None,
                   "maximum_detection_nondominated_support_levels": levels,
                   "support_threshold_price_curve": threshold_curve if available else None,
                   "zero_extra_e_cost_point": free,
                   "zero_extra_cost_support_gain": free["w"] - e["w"] if free is not None else None,
                   "joint_support_gain_vs_e": joint["w"] - e["w"] if joint["w"] is not None and e["w"] is not None else None,
                   "joint_support_gain_vs_sequential": joint["w"] - sequential["w"]
                   if joint["w"] is not None and sequential["w"] is not None else None,
                   "joint_added_cost_vs_e": joint["l"] - e["l"] if joint["l"] is not None and e["l"] is not None else None,
                   "joint_added_cost_vs_sequential": joint["l"] - sequential["l"]
                   if joint["l"] is not None and sequential["l"] is not None else None,
                   "sequential_support_gain_vs_e": sequential["w"] - e["w"]
                   if sequential["w"] is not None and e["w"] is not None else None,
                   "sequential_added_cost_vs_e": sequential["l"] - e["l"]
                   if sequential["l"] is not None and e["l"] is not None else None,
                   "sequential_matched_support_point": sequential["dominating_joint_point"],
                   "sequential_matched_support_cost_saving":
                   sequential["l"] - sequential["dominating_joint_point"]["l"]
                   if sequential["dominating_joint_point"] is not None else None}
        if available and budget == root["residual_cost"]:
            if joint["d"] != root["new_signature_count"] or joint["w"] != root["support_baseline"]["full_archive_support_ceiling"]:
                raise ValueError("Full-budget joint policy missed an achievable detection/support endpoint")
        budgets.append(summary)
    return points, budgets


def analyze_problem(problem, saved_conditions, old_roots, old_design_runs, *, cache=None,
                    state_cap=100000, combination_cap=10000000, retained=None):
    cache = cache if cache is not None else CertificateCache()
    retained = {} if retained is None else retained
    saved = {c["k"]: c for c in saved_conditions}
    if set(saved) != set(KS) or len(saved) != len(saved_conditions) or any(
            c["status"] != "completed" or c["problem_id"] != problem["problem_id"] for c in saved.values()):
        raise ValueError("Exactly three completed retained omission closures are required")
    nominal, models = Model(problem), {}
    for k in KS:
        expanded = ExpandedModel(problem, k)
        if canonical(expanded.to_dict()) != canonical(saved[k]["expansion"]):
            raise ValueError("Historical physical support does not reproduce exactly")
        models[k] = expanded
        for source in saved[k]["signature_rows"]:
            baseline = source["policy"]
            for model, field in ((nominal, "certificate"), (expanded, "expanded_certificate")):
                ref = baseline[field]
                if cache.get(model, baseline["history"], saved[k]["certificates"][ref]) != ref:
                    raise ValueError("Historical stopping certificate binding differs")
    roots = [copy.deepcopy({name: old[name] for name in ROOT_FIELDS}) for old in old_roots]
    roots.sort(key=lambda r: r["root_id"])
    old_by_id = {r["root_id"]: r for r in old_roots}
    if len(old_by_id) != len(old_roots) or any(r["problem_id"] != problem["problem_id"] for r in roots):
        raise ValueError("Duplicate or mismatched saved acquisition roots")
    saved_e = {(r["root_id"], r["integer_budget"], tuple(r["outcomes"])): r
               for r in old_design_runs if r["arm"] == E}
    design_runs, anchor_runs, cells = [], [], []
    retained.update({"roots": roots, "design_runs": design_runs, "runs": anchor_runs, "cells": cells})
    for root in roots:
        old = old_by_id[root["root_id"]]
        if old["exact_status"] != "completed":
            raise ValueError("Original detection frontier is unavailable; it cannot be regenerated")
        root["old_root_pin"] = pin(old)
        root["old_solver_pin"] = pin(old["solver"])
        root["anchor_budgets"] = [{"budget_percent": p, "integer_budget": root["residual_cost"] * p // 100} for p in BUDGETS]
        root["integer_budgets"] = sorted({r["integer_budget"] for r in root["anchor_budgets"]})
        support = SupportContract(nominal, models[2], root["base_history"], root["baseline"]["status"])
        root["physical_pin"] = support.physical_pin
        root["support_baseline"] = _support_baseline(support, root)
        policy = SavedEPolicy(nominal, support.design_signatures, old["solver"])
        planner = JointFrontierPlanner(nominal, support, root["base_history"],
                                       [row["integer_budget"] for row in root["anchor_budgets"]],
                                       state_cap=state_cap, combination_cap=combination_cap)
        root["solver"] = planner.solve()
        root["joint_status"] = "completed" if root["solver"]["status"] == "complete" else "unavailable"
        root["failure"] = root["solver"].get("cap")
        current = []
        wall, cpu = perf_counter(), process_time()
        for budget in root["integer_budgets"]:
            for arm in ARMS:
                for signature in root["signatures"]:
                    original = tuple(signature) in nominal.signature_cells
                    metadata = {"problem_id": problem["problem_id"], "root_id": root["root_id"], "arm": arm,
                                "integer_budget": budget, "budget_percent": None, "outcomes": signature,
                                "population": "original" if original else "new"}
                    if arm == JOINT and root["joint_status"] != "completed":
                        current.append({**metadata, "execution_status": "unavailable", "failure": root["failure"]})
                        continue
                    result = execute_audit(nominal, root["baseline"], signature, arm, budget, support=support,
                                           saved_e=policy, joint_planner=planner if arm == JOINT else None,
                                           certificate_cache=cache)
                    if arm == E:
                        historical = saved_e[root["root_id"], budget, tuple(signature)]
                        for field in ("history", "audit_history", "added_cost", "added_query_count", "added_returned_bytes",
                                      "status", "termination_reason", "next_query", "first_conflict", "coverage"):
                            if canonical(result[field]) != canonical(historical[field]):
                                raise ValueError(f"Preserved E path changed: {field}")
                    assessed = support.assess(result["history"])
                    initial = support.assess(root["base_history"])
                    supported = original and assessed["supported"] and result["status"] != "nominal_model_conflict"
                    refs = {"base_nominal": cache.get(nominal, root["base_history"]),
                            "final_nominal": cache.get(nominal, result["history"]),
                            "base_design": cache.get(models[2], root["base_history"]),
                            "final_design": cache.get(models[2], result["history"])}
                    current.append({**result, **metadata, "execution_status": "completed", "design_support": assessed,
                                    "design_supported_original": supported,
                                    "design_initially_supported_original": original and initial["supported"],
                                    "design_newly_supported_original": supported and not initial["supported"], "certificates": refs})
        root["execution_resources"] = {"anchor_reconstruction_wall_seconds": perf_counter() - wall,
                                       "anchor_reconstruction_cpu_seconds": process_time() - cpu}
        root["solver"] = planner.export()
        design_runs.extend(current)
        root["design_points"], root["budget_summary"] = design_measurements(root, current, old)
        del planner
    by_signature = {tuple(s): r for r in roots for s in r["signatures"]}
    expected_signatures = {tuple(r["outcomes"]) for r in saved[2]["signature_rows"]}
    if set(by_signature) != expected_signatures or sum(r["signature_count"] for r in roots) != len(expected_signatures):
        raise ValueError("Saved roots do not partition the fixed distinct-signature design population")
    index = {(r["root_id"], r["integer_budget"], r["arm"], tuple(r["outcomes"])): r for r in design_runs}
    for k in KS:
        for arm in ARMS:
            for percent in BUDGETS:
                current, missing = [], []
                for source in saved[k]["signature_rows"]:
                    signature = tuple(source["outcomes"])
                    root = by_signature[signature]
                    executed = index[root["root_id"], root["residual_cost"] * percent // 100, arm, signature]
                    if executed["execution_status"] != "completed":
                        row = {**executed, "k": k, "signature_id": source["signature_id"], "budget_percent": percent,
                               "stratum": problem["stratum"], "subtype": problem.get("subtype", problem["stratum"])}
                        missing.append(row["failure"])
                    else:
                        row = qualify_run(problem, nominal, models[k], source, {**executed, "budget_percent": percent},
                                          cache, saved[k]["certificates"])
                        row.update({"claim_established": row["final_expanded_claim_status"] == "established",
                                    "claim_ruled_out": row["final_expanded_claim_status"] == "ruled_out",
                                    "claim_unresolved": row["final_expanded_claim_status"] == "unresolved",
                                    "operational_pending": row["final_expanded_terminal_status"] == "unresolved_pending",
                                    "operational_irreducible": row["final_expanded_terminal_status"] == "archive_irreducible"})
                        current.append(row)
                    anchor_runs.append(row)
                cells.append(aggregate_cell(problem, k, arm, percent, current, len(saved[k]["signature_rows"]),
                                            {"unavailable_runs": len(missing), "causes": missing} if missing else None))
    return retained


def legacy_parity(runs, historical):
    def key(row):
        return row["problem_id"], row["k"], row["budget_percent"], row["signature_id"]
    index = {key(r): r for r in runs if r["arm"] == E}
    prior = [r for r in historical if r["arm"] == E]
    if len(index) != len(prior) or set(index) != {key(r) for r in prior}:
        raise ValueError("Original E anchor schedule differs")
    for old in prior:
        new = index[key(old)]
        for name, value in old.items():
            if name not in ("selection_seconds", "checking_seconds") and canonical(new.get(name)) != canonical(value):
                raise ValueError(f"Original E scientific anchor field changed: {name}")
    return {"status": "passed", "historical_e_anchor_runs": len(prior),
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
                    "comparison_scope": "full_hypothetical_physical_semantics" if arm in (SEQUENTIAL, JOINT) else "historical_observable_envelope_only",
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
    comparisons = ((JOINT, SEQUENTIAL, "primary_matched_full_hypothetical_knowledge"),
                   (JOINT, E, "secondary_additional_physical_support_knowledge_and_objective"),
                   (SEQUENTIAL, E, "diagnostic_additional_physical_support_knowledge"))
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
    """Sum disjoint root populations before problem/group aggregation."""
    problems = defaultdict(list)
    for root in roots:
        problems[root["problem_id"]].append(root)
    if set(problems) != set(groups):
        raise ValueError("Design summary lost a fixed problem")
    count_fields = ("detection_ceiling", "zero_extra_cost_support_gain", "joint_support_gain_vs_e",
                    "joint_support_gain_vs_sequential", "joint_added_cost_vs_e", "joint_added_cost_vs_sequential",
                    "sequential_support_gain_vs_e", "sequential_added_cost_vs_e", "sequential_matched_support_cost_saving")
    per_problem = []
    for pid, selected in sorted(problems.items()):
        size = sum(r["signature_count"] for r in selected)
        original = sum(r["original_signature_count"] for r in selected)
        new = size - original
        baseline = {key: sum(r["support_baseline"][key] for r in selected) for key in selected[0]["support_baseline"]}
        for percent in BUDGETS:
            summaries = [next(b for b in r["budget_summary"] if b["integer_budget"] == r["residual_cost"] * percent // 100)
                         for r in selected]
            counts = {key: sum(s[key] for s in summaries) if all(s[key] is not None for s in summaries) else None
                      for key in count_fields}
            metrics, missing = {}, {}
            for key in count_fields:
                denominator = size if "cost" in key and "support_gain" not in key else original
                if key == "detection_ceiling":
                    denominator = new
                metric_name = key + ("_per_all_signature" if denominator == size and "cost" in key
                                     and "support_gain" not in key else "_per_new_signature"
                                     if key == "detection_ceiling" else "_per_original_signature")
                value = counts[key]
                metrics[metric_name] = number(Fraction(value, denominator)) if value is not None and denominator else None
                missing[metric_name] = [r["root_id"] for r, s in zip(selected, summaries, strict=True) if s[key] is None]
            arms = {}
            for arm in ARMS:
                points = [next(p for p in r["design_points"] if p["arm"] == arm and
                               p["integer_budget"] == r["residual_cost"] * percent // 100) for r in selected]
                complete = all(p["status"] == "completed" for p in points)
                fields = ("d", "w", "l", "newly_supported_original", "original_cost", "new_cost")
                totals = {key: sum(p[key] for p in points) if complete else None for key in fields}
                arms[arm] = {"status": "completed" if complete else "unavailable", **totals,
                             "remaining_unsupported_original": baseline["original_definite_count"] - totals["w"]
                             if totals["w"] is not None else None,
                             "support_phase_cost": sum(p["phase_costs"]["support"] for p in points) if complete else None}
                arm_metrics = {"detection_per_new_signature": (totals["d"], new),
                               "supported_per_original_signature": (totals["w"], original),
                               "newly_supported_per_initially_unsupported": (totals["newly_supported_original"], baseline["initially_unsupported"]),
                               "added_cost_per_all_signature": (totals["l"], size),
                               "added_cost_per_original_signature": (totals["original_cost"], original),
                               "added_cost_per_new_signature": (totals["new_cost"], new)}
                for key, (value, denominator) in arm_metrics.items():
                    name = arm + ":" + key
                    metrics[name] = number(Fraction(value, denominator)) if value is not None and denominator else None
                    missing[name] = [r["root_id"] for r, p in zip(selected, points, strict=True) if p["status"] != "completed"]
            per_problem.append({"problem_id": pid, "structure_group": groups[pid], "stratum": selected[0]["stratum"],
                                "budget_percent": percent, "root_count": len(selected), "signature_count": size,
                                "original_signature_count": original, "new_signature_count": new, "support_baseline": baseline,
                                "unavailable_joint_roots": [r["root_id"] for r in selected if r["joint_status"] != "completed"],
                                "counts": counts, "arms": arms, "metrics": metrics, "unavailable_metric_roots": missing})
    summaries = []
    for percent in BUDGETS:
        for stratum in ["all", *sorted({r["stratum"] for r in per_problem})]:
            selected = [r for r in per_problem if r["budget_percent"] == percent and (stratum == "all" or r["stratum"] == stratum)]
            for weighting in ("equal_problem", "structure_balanced"):
                metrics = {}
                for name in selected[0]["metrics"]:
                    failed = [r["problem_id"] for r in selected if r["unavailable_metric_roots"][name]]
                    defined = {r["problem_id"]: Fraction(r["metrics"][name]["exact"]) for r in selected
                               if r["metrics"][name] is not None and r["problem_id"] not in failed}
                    weights = weights_for(defined, groups, weighting) if defined and not failed else {}
                    metrics[name] = {"mean": number(sum((weights[p] * v for p, v in defined.items()), Fraction())) if weights else None,
                                     "expected_problems": len(selected), "defined_problems": len(defined), "failed_problems": failed,
                                     "undefined_problems": [r["problem_id"] for r in selected if r["problem_id"] not in defined
                                                            and r["problem_id"] not in failed]}
                summaries.append({"budget_percent": percent, "stratum": stratum, "weighting": weighting,
                                  "problem_count": len(selected), "signature_count": sum(r["signature_count"] for r in selected),
                                  "original_signature_count": sum(r["original_signature_count"] for r in selected),
                                  "new_signature_count": sum(r["new_signature_count"] for r in selected),
                                  "support_baseline": {key: sum(r["support_baseline"][key] for r in selected)
                                                       for key in selected[0]["support_baseline"]},
                                  "unavailable_joint_roots": [rid for r in selected for rid in r["unavailable_joint_roots"]],
                                  "pooled_counts": {key: sum(r["counts"][key] for r in selected)
                                                    if all(r["counts"][key] is not None for r in selected) else None
                                                    for key in count_fields},
                                  "pooled_arms": {arm: {key: sum(r["arms"][arm][key] for r in selected)
                                                         if all(r["arms"][arm][key] is not None for r in selected) else None
                                                         for key in ("d", "w", "l", "newly_supported_original", "original_cost",
                                                                      "new_cost", "remaining_unsupported_original", "support_phase_cost")}
                                                  for arm in ARMS}, "metrics": metrics})
    return {"interpretation": "Fixed physical M2 design reward on original signatures; distinct signatures summed once through retained H0",
            "per_problem": per_problem, "summary": summaries}


def settings():
    config = read(STUDY / "config.json")
    expected = {"evaluation_problems": 40, "development_problems": 4, "evaluation_anchor_cells": 1440,
                "omission_budgets": list(KS), "arms": list(ARMS), "extra_budget_percentages": list(BUDGETS),
                "design_envelope_k": 2, "support_model_k": 2,
                "expanded_world_cap": 4096, "signature_cap": 256, "query_cap": 8, "outcomes_per_query_cap": 2,
                "caps": {"states_per_root": 100000, "child_combinations_per_root": 10000000},
                "evaluation_source": "studies/evidence_acquisition/evaluation_problems.json",
                "development_source": "studies/evidence_acquisition/development_problems.json",
                "evaluation_baseline_source": "studies/archive_model_misspecification/results/details.json.gz",
                "development_baseline_source": "studies/audit_aware_acquisition/development_baseline.json.gz",
                "group_source": "studies/acquisition_prior_robustness/structure_groups.json",
                "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
    for field, filename in (("roots", "roots"), ("design_runs", "design_runs"), ("anchor_runs", "runs")):
        expected["evaluation_old_" + field + "_source"] = f"studies/exact_audit_frontier/results/{filename}.json.gz"
        expected["development_old_" + field + "_source"] = f"studies/joint_audit_warrant/development_old_{field}.json.gz"
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("Configuration differs from the fixed authorized joint detection/support design")
    return config


def verify_preservation():
    saved = read(STUDY / "preservation.json")
    if digest(ROOT / saved["local_preservation_manifest"]) != saved["local_preservation_manifest_sha256"]:
        raise ValueError("Historical local preservation manifest changed")
    local = read(ROOT / saved["local_preservation_manifest"])
    for path, expected in {**saved["tracked_sha256"], **local["sha256"], **saved["additional_local_sha256"]}.items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Historical byte preservation mismatch: {path}")
    return {"tracked_files": len(saved["tracked_sha256"]), "local_files": len(local["sha256"]),
            "additional_local_files": len(saved["additional_local_sha256"])}


def verify_input_provenance():
    provenance = read(STUDY / "input_provenance.json")["development_exact_reference"]
    baseline = read(STUDY / "baseline_verification.json")
    if canonical(provenance) != canonical(baseline["portable_development_exact_reference"]):
        raise ValueError("Portable development references differ from reconciled historical provenance")
    expected_copies = {f"studies/joint_audit_warrant/development_old_{name}.json.gz" for name in ("roots", "design_runs", "anchor_runs")}
    if {row["copy"] for row in provenance["files"]} != expected_copies or len(provenance["files"]) != 3:
        raise ValueError("Portable development reference catalogue differs")
    for row in provenance["files"]:
        if row.get("byte_identical") is not True or digest(ROOT / row["copy"]) != row["sha256"]:
            raise ValueError("Portable development source differs from retained historical bytes")
    for name in (*expected_copies, "studies/joint_audit_warrant/input_provenance.json"):
        if digest(ROOT / name) != baseline["input_sha256"][name]:
            raise ValueError("Baseline input pin differs from portable development source")
    return {"status": "passed", "portable_files": 3}


def dependencies():
    paths = ["src/tracebench/__init__.py",
             *[f"src/tracebench/evidence_acquisition/{name}.py" for name in ("__init__", "model", "policies", "certificates")],
             "studies/acquisition_prior_robustness/aggregation.py", "studies/acquisition_prior_robustness/structure_groups.json",
             "studies/acquisition_prior_robustness/sensitivity.py",
             *[f"studies/archive_model_misspecification/{name}" for name in
               ("expanded.py", "reference.py", "results/details.json.gz")],
             "studies/evidence_acquisition/development_problems.json", "studies/evidence_acquisition/evaluation_problems.json",
             *[f"studies/audit_aware_acquisition/{name}" for name in ("analysis.py", "auditing.py", "reference.py", "development_baseline.json.gz")],
             *[f"studies/exact_audit_frontier/{name}" for name in
               ("execution.py", "frontier.py", "reference.py", "results/roots.json.gz",
                "results/design_runs.json.gz", "results/runs.json.gz")],
             *[f"studies/joint_audit_warrant/{name}" for name in
               ("analysis.py", "support.py", "execution.py", "frontier.py", "reference.py", "config.json", "ANALYSIS.md", "METHOD.md",
                "development_old_roots.json.gz", "development_old_design_runs.json.gz", "development_old_anchor_runs.json.gz",
                "input_provenance.json", "baseline_verification.json", "development_checks.json", "pre_freeze_checks.json")],
             "tests/test_joint_audit_warrant.py", "tests/test_joint_audit_support_execution.py",
             "tests/test_joint_audit_planner_guards.py", "tests/test_joint_audit_driver.py"]
    return [ROOT / path for path in paths]


def verify_freeze():
    frozen = read(STUDY / "freeze.json")
    if set(frozen["files_sha256"]) != {str(p.relative_to(ROOT)) for p in dependencies()}:
        raise ValueError("Frozen computational dependency closure differs")
    for name, expected in frozen["files_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Frozen scientific dependency changed: {name}")
    settings()
    return len(frozen["files_sha256"])


def freeze():
    settings()
    verify_input_provenance()
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        if read(STUDY / name).get("status") != "passed":
            raise ValueError(f"Pre-freeze check has not passed: {name}")
    for name in ("development_checks.json", "pre_freeze_checks.json"):
        if read(STUDY / name).get("new_evaluation_policy_outcomes_observed") != 0:
            raise ValueError("New-policy evaluation chronology is not pre-outcome")
    development = read(STUDY / "development_checks.json")
    expected = {str(p.relative_to(ROOT)) for p in dependencies() if p.name not in ("development_checks.json", "pre_freeze_checks.json")}
    if set(development.get("source_sha256", {})) != expected:
        raise ValueError("Development checks did not pin the complete computational source closure")
    for name, value in development["source_sha256"].items():
        if digest(ROOT / name) != value:
            raise ValueError("Computational source changed after development qualification")
    write_new(STUDY / "freeze.json", {"schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                                    "new_evaluation_policy_outcomes_observed": 0, "known_detection_only_outcomes": True,
                                    "python_version": sys.version,
                                    "files_sha256": {str(p.relative_to(ROOT)): digest(p) for p in dependencies()},
                                    "preservation": verify_preservation()})
    return {"status": "frozen", "dependencies": verify_freeze()}


def _inputs(development):
    config = settings()
    verify_input_provenance()
    prefix = "development" if development else "evaluation"
    problems = read(ROOT / config[prefix + "_source"])
    saved = read(ROOT / config[prefix + "_baseline_source"])
    old_roots, old_design, old_anchors = (read(ROOT / config[prefix + "_old_" + name + "_source"])
                                        for name in ("roots", "design_runs", "anchor_runs"))
    expected = config[prefix + "_problems"]
    if len(problems) != expected or len(saved) != expected * 3 or len(old_roots) != config["expected_schedule"][prefix]["roots"]:
        raise ValueError("Fixed problem/support/root census differs")
    groups = ({p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems} if development else
              read(ROOT / config["group_source"])["problem_to_group"])
    if set(groups) != {p["problem_id"] for p in problems}:
        raise ValueError("Structural groups differ from fixed problem population")
    return problems, saved, old_roots, old_design, old_anchors, groups


def schedule_counts(roots, design_runs, runs, cells):
    return {"roots": len(roots), "root_unique_budget_cells": sum(len(r["integer_budgets"]) for r in roots),
            "unique_design_runs_three_arms": len(design_runs), "anchor_cells": len(cells), "anchor_runs": len(runs)}


def _check_schedule(roots, design_runs, runs, cells, development):
    actual = schedule_counts(roots, design_runs, runs, cells)
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
    qualification_sources = ({str(p.relative_to(ROOT)): digest(p) for p in dependencies()
                              if p.name not in ("development_checks.json", "pre_freeze_checks.json")}
                             if development else None)
    problems, saved, old_roots, old_design, old_anchors, groups = _inputs(development)
    cache = CertificateCache()
    roots, design_runs, runs, cells, failures = [], [], [], [], []
    wall, cpu = perf_counter(), process_time()
    for problem in problems:
        pid = problem["problem_id"]
        attempted = {}
        try:
            result = analyze_problem(problem, [c for c in saved if c["problem_id"] == pid],
                                     [r for r in old_roots if r["problem_id"] == pid],
                                     [r for r in old_design if r["problem_id"] == pid], cache=cache,
                                     state_cap=config["caps"]["states_per_root"],
                                     combination_cap=config["caps"]["child_combinations_per_root"], retained=attempted)
            roots.extend(result["roots"])
            design_runs.extend(result["design_runs"])
            runs.extend(result["runs"])
            cells.extend(result["cells"])
        except Exception as error:
            failures.append({"problem_id": pid, **_failure(error), "attempted_problem": attempted})
            break
        print(json.dumps({"problem_id": pid, "roots_retained": len(roots), "unique_paths_retained": len(design_runs),
                          "anchor_views_retained": len(runs)}), flush=True)
        if not development:
            verify_freeze()
    schedule, parity = None, {"status": "unavailable"}
    check_wall, check_cpu = perf_counter(), process_time()
    try:
        schedule = _check_schedule(roots, design_runs, runs, cells, development)
        parity = legacy_parity(runs, old_anchors)
        independent = verify_all(problems, saved, old_roots, old_design, roots, design_runs, runs, cache.certificates)
    except Exception as error:
        independent = {"status": "failed", "failure": _failure(error)}
    checker = {"wall_seconds": perf_counter() - check_wall, "cpu_seconds": process_time() - check_cpu}
    if failures:
        summary = paired = design_summary = {"status": "unavailable", "failures": failures}
    else:
        summary, paired, design_summary = summarize(cells, groups), paired_differences(cells, groups), summarize_design(roots, groups)
    artifacts = {"roots.json.gz": roots, "design_runs.json.gz": design_runs, "runs.json.gz": runs,
                 "certificates.json.gz": cache.certificates, "per_condition.json.gz": cells, "summary.json.gz": summary,
                 "paired.json.gz": paired, "design_summary.json.gz": design_summary,
                 "independent_verification.json": independent, "legacy_parity.json": parity}
    serial_wall, serial_cpu = perf_counter(), process_time()
    for name, value in artifacts.items():
        write_new(output / name, value)
    serialization = {"wall_seconds": perf_counter() - serial_wall, "cpu_seconds": process_time() - serial_cpu}
    completed = sum(c["status"] == "completed" for c in cells)
    complete = not failures and schedule is not None and completed == len(cells) and independent.get("status") == "passed"
    expected = config["expected_schedule"]["development" if development else "evaluation"]
    actual = schedule_counts(roots, design_runs, runs, cells)
    validation = {"status": "passed" if complete else "unavailable_or_failed_checks_retained",
                  "split": "development" if development else "evaluation", "problems": len(problems), "schedule": schedule,
                  "expected_schedule": expected, "retained_schedule": actual,
                  "missing_schedule_counts": {key: expected[key] - actual[key] for key in expected},
                  "missing_problem_ids": sorted(set(groups) - {r["problem_id"] for r in roots}),
                  "completed_roots": sum(r["joint_status"] == "completed" for r in roots),
                  "unavailable_roots": [r["root_id"] for r in roots if r["joint_status"] != "completed"],
                  "aggregate_cells": len(cells), "completed_cells": completed,
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
        if any(digest(ROOT / name) != expected for name, expected in qualification_sources.items()):
            raise ValueError("Computational source changed during development qualification; outputs retained")
        write_new(STUDY / "development_checks.json", {**validation, "output": str(output.resolve().relative_to(ROOT)),
                  "manifest_sha256": digest(output / "manifest.json"), "new_evaluation_policy_outcomes_observed": 0,
                  "source_sha256": qualification_sources})
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
    problems, saved, old_roots, old_design, old_anchors, groups = _inputs(False)
    roots, design_runs, runs, certificates, cells = (read(output / name) for name in
        ("roots.json.gz", "design_runs.json.gz", "runs.json.gz", "certificates.json.gz", "per_condition.json.gz"))
    schedule = _check_schedule(roots, design_runs, runs, cells, False)
    parity = legacy_parity(runs, old_anchors)
    checked = verify_all(problems, saved, old_roots, old_design, roots, design_runs, runs, certificates)
    if checked.get("status") not in ("passed", "unavailable_joint_roots_verified"):
        raise ValueError("Independent verification returned a failed or unrecognized status")
    by_key, by_root = defaultdict(list), defaultdict(list)
    old_by_root = {r["root_id"]: r for r in old_roots}
    for row in runs:
        by_key[row["problem_id"], row["k"], row["arm"], row["budget_percent"]].append(row)
    for row in design_runs:
        by_root[row["root_id"]].append(row)
    for root in roots:
        points, budgets = design_measurements(root, by_root[root["root_id"]], old_by_root[root["root_id"]])
        if canonical(points) != canonical(root["design_points"]) or canonical(budgets) != canonical(root["budget_summary"]):
            raise ValueError("Joint design points/support prices differ from paid path reaggregation")
    problem_map = {p["problem_id"]: p for p in problems}
    source_map = {(c["problem_id"], c["k"]): c for c in saved}
    for cell in cells:
        key = cell["problem_id"], cell["k"], cell["arm"], cell["budget_percent"]
        completed = [r for r in by_key[key] if r["execution_status"] == "completed"]
        missing = [r["failure"] for r in by_key[key] if r["execution_status"] != "completed"]
        expected = aggregate_cell(problem_map[key[0]], *key[1:], completed, len(source_map[key[:2]]["signature_rows"]),
                                  {"unavailable_runs": len(missing), "causes": missing} if missing else None)
        if canonical(cell) != canonical(expected):
            raise ValueError("Anchor aggregate differs from exact reaggregation")
    for name, result in (("summary.json.gz", summarize(cells, groups)), ("paired.json.gz", paired_differences(cells, groups)),
                         ("design_summary.json.gz", summarize_design(roots, groups))):
        if canonical(result) != canonical(read(output / name)):
            raise ValueError(f"Saved {name} differs from exact reaggregation")
    return {"status": checked["status"], "schedule": schedule, "independent_verification": checked, "legacy_parity": parity,
            "scope": "Frozen scientific dependencies and retained outputs; historical checkout preservation is separate"}


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
