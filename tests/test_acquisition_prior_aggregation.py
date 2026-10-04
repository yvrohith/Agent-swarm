"""Only toy grids: the follow-up evaluation must remain frozen before outcomes."""

import copy
import importlib.util
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "prior_aggregation", Path(__file__).resolve().parents[1]
    / "studies/acquisition_prior_robustness/aggregation.py")
aggregation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aggregation)

GROUPS = {"p1": "g1", "p2": "g1", "p3": "g2", "zero": "g3"}
COSTS = {"read_all": [9, 9, 9, 8], "schema_aware": [4, 4, 6, 0],
         "world_entropy": [2, 6, 5, 0], "pair_cut": [2, 5, 6, 0],
         "exact_optimal": [1, 3, 2, 0]}


def toy_rows():
    rows = []
    for (index, pid), deployment, mode, policy in product(
            enumerate(GROUPS), aggregation.DEPLOYMENTS, aggregation.MODES, aggregation.POLICIES):
        cost = COSTS[policy][index]
        if deployment == "qPlus" and mode == "frozen_p0" and policy == "exact_optimal" and pid == "p1":
            cost += 2
        rows.append({"problem_id": pid, "stratum": "second" if pid == "zero" else "first",
                     "deployment": deployment, "planning_mode": mode, "policy": policy,
                     "availability": "complete", "failure": None,
                     "expected": {k: aggregation.number(Fraction(v)) for k, v in {
                         "cost": cost, "query_count": 0 if pid == "zero" else 2,
                         "returned_bytes": 100, "established": Fraction(1, 4),
                         "ruled_out": Fraction(1, 4), "archive_irreducible": Fraction(1, 2)}.items()}})
    return rows


def select(summary, collection="policy_summaries", **overrides):
    target = {"deployment": "q0", "planning_mode": "frozen_p0", "weighting": "structure_balanced",
              "stratum": "all", "policy": "pair_cut"}
    if collection != "policy_summaries":
        target.pop("policy")
    if collection == "exact_p0_prior_penalty":
        target.pop("planning_mode")
    target.update(overrides)
    return next(row for row in summary[collection] if all(row[k] == v for k, v in target.items()))


def test_weights_average_inside_groups_then_across_groups():
    weights = aggregation.weights_for(GROUPS, GROUPS, "structure_balanced")
    assert weights == {"p1": Fraction(1, 6), "p2": Fraction(1, 6),
                       "p3": Fraction(1, 3), "zero": Fraction(1, 3)}
    assert sum(weights.values()) == 1
    assert aggregation.weights_for(["p1", "p2", "p3"], GROUPS, "structure_balanced")["p3"] == Fraction(1, 2)


@pytest.mark.parametrize("ids,rule", [([], "equal_problem"), (["p1", "p1"], "equal_problem"),
                                    (["unknown"], "equal_problem"), (["p1"], "unknown")])
def test_invalid_weight_denominators_fail_closed(ids, rule):
    with pytest.raises(ValueError):
        aggregation.weights_for(ids, GROUPS, rule)


def test_stratified_weighting_uses_its_own_group_population():
    summary = aggregation.summarize(toy_rows(), GROUPS)
    balanced = select(summary)
    equal = select(summary, weighting="equal_problem")
    stratum = select(summary, stratum="first")
    assert balanced["expected"]["cost"]["mean"]["exact"] == "19/6"
    assert equal["expected"]["cost"]["mean"]["exact"] == "13/4"
    assert stratum["expected"]["cost"]["mean"]["exact"] == "19/4"
    assert balanced["expected_problems"] == 4 and stratum["expected_problems"] == 3
    assert summary["original_rows"] == len(GROUPS) * 50


def test_pair_counts_keep_problem_and_group_units_distinct():
    summary = aggregation.summarize(toy_rows(), GROUPS)
    row = select(summary, "pairwise_comparisons", comparison="pair_cut_minus_schema_aware")
    assert row["mean"]["exact"] == "-1/6"
    assert row["problem_counts"] == {"lower": 1, "tied": 2, "higher": 1, "missing": 0, "expected": 4}
    assert row["group_mean_counts"] == {"lower": 1, "tied": 2, "higher": 0, "missing": 0, "expected": 3}


def test_ratios_are_means_of_ratios_and_exclude_zero_optima_explicitly():
    summary = aggregation.summarize(toy_rows(), GROUPS)
    ratio = select(summary)["mean_per_problem_optimum_ratio"]
    assert ratio["mean"]["exact"] == "29/12"
    assert ratio["mean"]["exact"] != "19/8"  # Ratio of the positive-population cost means.
    assert ratio["zero_optimum_problems"] == ["zero"]
    assert ratio["positive_optimum_problems"] == ["p1", "p2", "p3"]
    assert ratio["available_positive_optimum_ratios"] == 3
    read_all = select(summary, policy="read_all")["mean_per_problem_optimum_ratio"]
    assert read_all["zero_optimum_positive_cost_problems"] == ["zero"]


def test_frozen_prior_penalty_uses_matched_optimum_not_frozen_reference():
    summary = aggregation.summarize(toy_rows(), GROUPS)
    row = select(summary, "exact_p0_prior_penalty", deployment="qPlus")
    assert row["exact_p0_deployment_prior_penalty"]["mean"]["exact"] == "1/3"
    # A heuristic may beat a frozen exact policy under a changed workload.
    pair = select(summary, deployment="qPlus")
    assert pair["matched_optimum_excess"]["mean"]["exact"] == "11/6"


@pytest.mark.parametrize("defect", ["missing", "duplicate", "unmapped", "metric_absent",
                                   "bad_mass", "inconsistent_decimal", "negative_cost", "unlabelled_null"])
def test_missing_or_invalid_rows_cannot_silently_change_denominators(defect):
    rows = toy_rows()
    if defect == "missing":
        rows.pop()
    elif defect == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif defect == "unmapped":
        rows[0]["problem_id"] = "other"
    elif defect == "metric_absent":
        del rows[0]["expected"]["cost"]
    elif defect == "bad_mass":
        rows[0]["expected"]["established"] = aggregation.number(Fraction(1))
    elif defect == "inconsistent_decimal":
        rows[0]["expected"]["cost"]["value"] = 10.5
    elif defect == "negative_cost":
        rows[0]["expected"]["cost"] = aggregation.number(Fraction(-1))
    else:
        rows[0]["expected"] = None
    with pytest.raises(ValueError):
        aggregation.summarize(rows, GROUPS)


def test_explicit_cap_retains_weight_and_marks_only_affected_means_unavailable():
    rows = toy_rows()
    row = next(r for r in rows if r["problem_id"] == "p1" and r["deployment"] == "q0"
               and r["planning_mode"] == "frozen_p0" and r["policy"] == "pair_cut")
    row.update(expected=None, availability="unavailable", failure={"kind": "cap"})
    summary = aggregation.summarize(rows, GROUPS)
    cost = select(summary)["expected"]["cost"]
    assert cost["mean"] is None and cost["expected_problems"] == 4 and cost["available_problems"] == 3
    assert cost["missing_problems"] == ["p1"] and cost["available_weight"]["exact"] == "5/6"
    assert select(summary, stratum="second")["expected"]["cost"]["mean"]["exact"] == "0"
    contrast = select(summary, "pairwise_comparisons", comparison="pair_cut_minus_schema_aware")
    assert contrast["problem_counts"]["missing"] == 1 and contrast["mean"] is None


def test_missing_matched_optimum_keeps_unknown_ratio_denominator_visible():
    rows = toy_rows()
    row = next(r for r in rows if r["problem_id"] == "p1" and r["deployment"] == "q0"
               and r["planning_mode"] == "matched_q" and r["policy"] == "exact_optimal")
    row.update(expected=None, availability="unavailable", failure={"kind": "cap"})
    summary = aggregation.summarize(rows, GROUPS)
    selected = select(summary)
    assert selected["expected"]["cost"]["mean"] is not None
    assert selected["matched_optimum_excess"]["mean"] is None
    ratio = selected["mean_per_problem_optimum_ratio"]
    assert ratio["mean"] is None and ratio["unknown_optimum_problems"] == ["p1"]
    assert ratio["zero_optimum_problems"] == ["zero"] and not ratio["denominator_complete"]


def test_group_crossing_strata_requires_explicit_review():
    with pytest.raises(ValueError, match="mixes strata"):
        aggregation.summarize(toy_rows(), {**GROUPS, "zero": "g1"})


def test_policy_cannot_beat_matched_exact_optimum():
    rows = toy_rows()
    row = next(r for r in rows if r["problem_id"] == "p1" and r["policy"] == "pair_cut")
    row["expected"]["cost"] = aggregation.number(Fraction())
    with pytest.raises(ValueError, match="beats matched optimum"):
        aggregation.summarize(rows, GROUPS)


def test_all_zero_optima_have_no_ratio_mean():
    rows = [r for r in toy_rows() if r["problem_id"] == "zero"]
    summary = aggregation.summarize(rows, {"zero": "g3"})
    ratio = select(summary)["mean_per_problem_optimum_ratio"]
    assert ratio["mean"] is None and ratio["positive_optimum_problems"] == []
    assert ratio["zero_optimum_problems"] == ["zero"] and ratio["denominator_complete"]
