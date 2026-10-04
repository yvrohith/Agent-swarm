"""Exact aggregation of the fixed prior-sensitivity grid; no policy execution.

Repeated price/configuration variants retain their original problem rows. A
structure-balanced mean first averages variants inside each supplied group,
then gives each group equal weight. Neither grouping is an incident sample.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from itertools import product

DEPLOYMENTS = ("q0", "qS", "qT", "qMinus", "qPlus")
MODES = ("frozen_p0", "matched_q")
POLICIES = ("read_all", "schema_aware", "world_entropy", "pair_cut", "exact_optimal")
RULES = ("equal_problem", "structure_balanced")
METRICS = ("cost", "query_count", "returned_bytes", "established", "ruled_out",
           "archive_irreducible")
STATUSES = ("established", "ruled_out", "archive_irreducible")


def number(value):
    return None if value is None else {"exact": str(value), "value": float(value)}


def fraction(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"exact", "value"}:
        raise ValueError("Expected an exact/value rational or explicit null")
    if not isinstance(value["exact"], str):
        raise ValueError("Exact rational must be a string")
    parsed = Fraction(value["exact"])
    if not isinstance(value["value"], (int, float)) or isinstance(value["value"], bool):
        raise ValueError("Readable value must be numeric")
    if float(parsed) != value["value"]:
        raise ValueError("Readable value differs from exact rational")
    return parsed


def weights_for(ids, groupmap, rule):
    """Return exact problem weights for one declared population/eligible set."""
    ids = list(ids)
    if not ids or len(ids) != len(set(ids)) or any(pid not in groupmap for pid in ids):
        raise ValueError("Weights require distinct, nonempty, mapped problem IDs")
    if any(not isinstance(groupmap[pid], str) or not groupmap[pid] for pid in ids):
        raise ValueError("Each problem needs a nonempty structure-group identifier")
    if rule == "equal_problem":
        return {pid: Fraction(1, len(ids)) for pid in ids}
    if rule != "structure_balanced":
        raise ValueError("Unknown aggregation rule")
    groups = defaultdict(list)
    for pid in ids:
        groups[groupmap[pid]].append(pid)
    return {pid: Fraction(1, len(groups) * len(groups[groupmap[pid]])) for pid in ids}


def average(values, ids, groupmap, rule):
    """Never renormalize around failed computations in the fixed population."""
    weights = weights_for(ids, groupmap, rule)
    missing = [pid for pid in ids if values[pid] is None]
    observed_sum = sum((weights[pid] * value for pid, value in values.items()
                        if pid in weights and value is not None), Fraction())
    available_weight = sum((weights[pid] for pid in ids if values[pid] is not None), Fraction())
    return {
        "mean": number(observed_sum) if not missing else None,
        "expected_problems": len(ids), "available_problems": len(ids) - len(missing),
        "missing_problems": missing, "available_weight": number(available_weight),
        "observed_weighted_sum": number(observed_sum),
    }


def _counts(values):
    return {"lower": sum(v is not None and v < 0 for v in values),
            "tied": sum(v == 0 for v in values),
            "higher": sum(v is not None and v > 0 for v in values),
            "missing": sum(v is None for v in values), "expected": len(values)}


def _paired_summary(values, ids, groupmap, rule):
    groups = defaultdict(list)
    for pid in ids:
        groups[groupmap[pid]].append(values[pid])
    group_means = [sum(v, Fraction()) / len(v) if all(x is not None for x in v) else None
                   for v in groups.values()]
    return {**average(values, ids, groupmap, rule),
            "problem_counts": _counts(list(values.values())),
            "group_mean_counts": _counts(group_means)}


def _ratio_summary(costs, optima, ids, groupmap, rule):
    unknown = [pid for pid in ids if optima[pid] is None]
    zero = [pid for pid in ids if optima[pid] == 0]
    positive = [pid for pid in ids if optima[pid] is not None and optima[pid] > 0]
    ratios = {pid: costs[pid] / optima[pid] if costs[pid] is not None else None
              for pid in positive}
    missing_cost = [pid for pid in positive if costs[pid] is None]
    result = {
        "mean": None, "worst": None, "expected_problems": len(ids),
        "positive_optimum_problems": positive, "zero_optimum_problems": zero,
        "unknown_optimum_problems": unknown, "missing_positive_optimum_costs": missing_cost,
        "available_positive_optimum_ratios": len(positive) - len(missing_cost),
        "positive_optimum_groups": len({groupmap[pid] for pid in positive}),
        "zero_optimum_positive_cost_problems": [pid for pid in zero
                                                if costs[pid] is not None and costs[pid] > 0],
        "zero_optimum_zero_cost_problems": [pid for pid in zero if costs[pid] == 0],
        "zero_optimum_missing_cost_problems": [pid for pid in zero if costs[pid] is None],
        "denominator_complete": not unknown and not missing_cost,
    }
    # The ratio population explicitly excludes zero optima. Reapply the declared
    # weighting within that eligible population, not a ratio of aggregate costs.
    if positive and not unknown and not missing_cost:
        result["mean"] = average(ratios, positive, groupmap, rule)["mean"]
        result["worst"] = number(max(ratios.values()))
    return result


def summarize(rows, group_for_problem):
    """Summarize the complete fixed grid, retaining explicit unavailable rows.

    A missing grid row is an error. An existing row with expected=None is an
    unavailable computation: all requested means keep its original denominator
    and become unavailable, rather than silently averaging the successful subset.
    """
    ids = sorted(group_for_problem)
    weights_for(ids, group_for_problem, "equal_problem")
    indexed, strata = {}, {}
    for row in rows:
        pid = row["problem_id"]
        key = (pid, row["deployment"], row["planning_mode"], row["policy"])
        if pid not in group_for_problem or key in indexed:
            raise ValueError("Unknown problem or duplicate condition row")
        if key[1] not in DEPLOYMENTS or key[2] not in MODES or key[3] not in POLICIES:
            raise ValueError("Unexpected prior, planning mode or policy")
        stratum = row["stratum"]
        if not isinstance(stratum, str) or not stratum or stratum == "all":
            raise ValueError("A named nonpooled stratum is required")
        if pid in strata and strata[pid] != stratum:
            raise ValueError("Problem stratum changes across conditions")
        strata[pid] = stratum
        expected = row["expected"]
        if expected is None:
            if row.get("availability") != "unavailable" or not row.get("failure"):
                raise ValueError("Unavailable computation needs an explicit failure record")
            metrics = dict.fromkeys(METRICS)
        else:
            if row.get("availability") != "complete":
                raise ValueError("Expected metrics need a complete computation label")
            if any(name not in expected for name in METRICS):
                raise ValueError("Required expected metric absent; use explicit null for unavailable")
            metrics = {name: fraction(expected[name]) for name in METRICS}
            if any(value is None for value in metrics.values()):
                raise ValueError("Complete computation has an unavailable metric")
            if any(value is not None and value < 0 for value in metrics.values()):
                raise ValueError("Expected costs, quantities and masses must be nonnegative")
            if all(metrics[s] is not None for s in STATUSES):
                if sum((metrics[s] for s in STATUSES), Fraction()) != 1:
                    raise ValueError("Full-budget terminal masses must sum to one")
            elif any(metrics[s] is not None and metrics[s] > 1 for s in STATUSES):
                raise ValueError("Terminal probability mass exceeds one")
        indexed[key] = metrics
    expected_keys = set(product(ids, DEPLOYMENTS, MODES, POLICIES))
    if set(indexed) != expected_keys:
        raise ValueError(f"Incomplete fixed grid: {len(expected_keys - set(indexed))} missing rows")
    members = defaultdict(list)
    for pid in ids:
        members[group_for_problem[pid]].append(pid)
    if any(len({strata[pid] for pid in group}) != 1 for group in members.values()):
        raise ValueError("A structure group mixes strata; grouping needs explicit scientific review")
    populations = {"all": ids, **{s: [pid for pid in ids if strata[pid] == s]
                                  for s in sorted(set(strata.values()))}}
    policy_summaries, comparisons, penalties, weight_tables = [], [], [], []
    for rule, (stratum, selected) in product(RULES, populations.items()):
        weight_tables.append({"weighting": rule, "stratum": stratum,
                              "problem_weights": {pid: number(w) for pid, w in
                                                  weights_for(selected, group_for_problem, rule).items()}})
        for deployment in DEPLOYMENTS:
            optima = {pid: indexed[pid, deployment, "matched_q", "exact_optimal"]["cost"]
                      for pid in selected}
            frozen_exact = {pid: indexed[pid, deployment, "frozen_p0", "exact_optimal"]["cost"]
                            for pid in selected}
            penalty = {pid: frozen_exact[pid] - optima[pid]
                       if frozen_exact[pid] is not None and optima[pid] is not None else None
                       for pid in selected}
            if any(value is not None and value < 0 for value in penalty.values()):
                raise ValueError("Frozen exact policy beats matched optimum")
            penalties.append({"deployment": deployment, "weighting": rule, "stratum": stratum,
                              "exact_p0_deployment_prior_penalty": _paired_summary(
                                  penalty, selected, group_for_problem, rule)})
            for mode in MODES:
                common = {"deployment": deployment, "planning_mode": mode,
                          "weighting": rule, "stratum": stratum}
                for policy in POLICIES:
                    costs = {pid: indexed[pid, deployment, mode, policy]["cost"] for pid in selected}
                    gap = {pid: costs[pid] - optima[pid]
                           if costs[pid] is not None and optima[pid] is not None else None
                           for pid in selected}
                    if any(value is not None and value < 0 for value in gap.values()):
                        raise ValueError("Feasible policy beats matched optimum")
                    policy_summaries.append({**common, "policy": policy,
                        "expected_problems": len(selected),
                        "structure_groups": len({group_for_problem[pid] for pid in selected}),
                        "expected": {metric: average(
                            {pid: indexed[pid, deployment, mode, policy][metric] for pid in selected},
                            selected, group_for_problem, rule) for metric in METRICS},
                        "matched_optimum_excess": average(gap, selected, group_for_problem, rule),
                        "mean_per_problem_optimum_ratio": _ratio_summary(
                            costs, optima, selected, group_for_problem, rule)})
                for comparator in ("schema_aware", "world_entropy"):
                    differences = {}
                    for pid in selected:
                        pair_cut = indexed[pid, deployment, mode, "pair_cut"]["cost"]
                        other = indexed[pid, deployment, mode, comparator]["cost"]
                        differences[pid] = pair_cut - other if pair_cut is not None and other is not None else None
                    comparisons.append({**common, "comparison": "pair_cut_minus_" + comparator,
                                        **_paired_summary(differences, selected, group_for_problem, rule)})
    return {
        "problem_count": len(ids), "original_rows": len(rows), "structure_group_count": len(members),
        "aggregation_definitions": {
            "equal_problem": "Each declared problem in the stated population has equal weight.",
            "structure_balanced": "Mean within each supplied structure group, then equal mean across groups in the stated population.",
            "unavailable": "Missing grid rows fail closed. Explicit unavailable computations retain their problem weights; affected full means are null with missing IDs and observed weight shown.",
            "ratios": "Mean of per-problem cost/matched-optimum ratios, never ratio of means. Zero optima excluded explicitly; apply the declared weighting again within the positive-optimum population. Unknown optimum or missing eligible cost makes the mean unavailable.",
            "interpretation": "Exact finite-model expectations; structural groups and repeated prior/policy conditions are not independent sampled incidents."},
        "structure_groups": [{"group_id": group, "members": pids, "size": len(pids),
                              "stratum": strata[pids[0]]} for group, pids in sorted(members.items())],
        "weight_tables": weight_tables, "policy_summaries": policy_summaries,
        "pairwise_comparisons": comparisons, "exact_p0_prior_penalty": penalties,
    }
