"""Study units, invalid-answer behavior, and explicit blocked reporting."""

import copy
import json

import pytest

from tracebench.investigator_utility.reporting import render_report, write_report
from tracebench.investigator_utility.scoring import (
    METRICS,
    STATUSES,
    constant_response,
    sanity_scores,
    score_response,
    select_examples,
    summarize_scores,
)


def case_and_gold(case_id="case-1", *, cluster=None, subset="synthetic"):
    case = {
        "schema_version": 1, "case_id": case_id, "cluster_id": cluster or case_id,
        "subset": subset, "split": "evaluation",
        "records": [{"id": "r1", "kind": "context", "text": "retained evidence"}],
        "assumptions": [{"id": "a1", "text": "Incomplete logging."}],
        "claims": [{"id": f"q{i}", "text": f"claim {i}"} for i in range(3)],
    }
    gold = {"case_id": case_id, "claims": [
        {"id": f"q{i}", "status": status, "certificate": {"check": "test fixture"}}
        for i, status in enumerate(STATUSES)
    ], "validation": {"valid": True}}
    return case, gold


def response(case, statuses=STATUSES):
    return {"case_id": case["case_id"], "answers": [
        {"claim_id": claim["id"], "status": status, "evidence_ids": ["r1", "a1"],
         "reason": "Brief evidence-grounded justification."}
        for claim, status in zip(case["claims"], statuses, strict=True)
    ]}


def scored_row(case_id="case-1", *, cluster=None, subset="synthetic", model="model-1",
               arm="C", statuses=STATUSES):
    case, gold = case_and_gold(case_id, cluster=cluster, subset=subset)
    return {**score_response(case, gold, response(case, statuses)), "model_id": model, "arm": arm}


def test_perfect_statuses_resolve_fixed_denominators_and_assumption_citations():
    case, gold = case_and_gold()
    score = score_response(case, gold, json.dumps(response(case)))
    assert score["metrics"]["warranted_answer_accuracy"] == {
        "numerator": 2, "denominator": 2, "value": 1,
    }
    assert score["metrics"]["unjustified_certainty"]["denominator"] == 1
    assert score["metrics"]["three_class_accuracy"]["value"] == 1
    assert score["metrics"]["correct_unresolved"]["value"] == 1
    assert score["metrics"]["invalid_missing_answer_rate"]["value"] == 0
    assert score["metrics"]["evidence_citation_error_rate"]["value"] == 0


def test_always_unknown_is_not_success_on_answerable_claims():
    case, gold = case_and_gold()
    scored = score_response(case, gold, constant_response(case, "unresolved"))
    assert scored["metrics"]["unjustified_certainty"]["value"] == 0
    assert scored["metrics"]["warranted_answer_accuracy"]["value"] == 0
    assert scored["metrics"]["three_class_accuracy"]["value"] == pytest.approx(1 / 3)


@pytest.mark.parametrize("bad", [None, "not JSON", "```json\n{}\n```", [], 1, {"answers": []}])
def test_malformed_or_missing_responses_do_not_earn_abstention(bad):
    case, gold = case_and_gold()
    scored = score_response(case, gold, bad)
    assert scored["metrics"]["invalid_missing_answer_rate"]["value"] == 1
    assert scored["metrics"]["correct_unresolved"]["value"] == 0
    assert scored["metrics"]["warranted_answer_accuracy"]["denominator"] == 2
    assert scored["metrics"]["warranted_answer_accuracy"]["value"] == 0
    assert scored["metrics"]["unjustified_certainty_or_invalid"]["value"] == 1


@pytest.mark.parametrize("field,value", [
    ("status", "unknown"), ("status", ["unresolved"]), ("reason", ""),
    ("reason", 1), ("evidence_ids", "r1"), ("evidence_ids", [1]),
])
def test_invalid_answer_schema_does_not_receive_status_credit(field, value):
    case, gold = case_and_gold()
    output = response(case)
    output["answers"][2][field] = value
    scored = score_response(case, gold, output)
    assert scored["metrics"]["three_class_accuracy"]["value"] == 2 / 3
    assert scored["metrics"]["invalid_missing_answer_rate"]["value"] == 1 / 3
    assert scored["metrics"]["correct_unresolved"]["value"] == 0
    assert scored["metrics"]["unjustified_certainty_or_invalid"]["value"] == 1


def test_unknown_citation_separate_from_mechanical_status_accuracy_but_not_abstention():
    case, gold = case_and_gold()
    output = response(case)
    output["answers"][0]["evidence_ids"] = ["hidden-truth"]
    output["answers"][2]["evidence_ids"] = ["invented-record"]
    scored = score_response(case, gold, output)
    assert scored["metrics"]["warranted_answer_accuracy"]["value"] == 1
    assert scored["metrics"]["three_class_accuracy"]["value"] == 1
    assert scored["metrics"]["invalid_missing_answer_rate"]["value"] == 0
    assert scored["metrics"]["evidence_citation_error_rate"]["value"] == 2 / 3
    assert scored["metrics"]["correct_unresolved"]["value"] == 0
    assert scored["metrics"]["unjustified_certainty_or_invalid"]["value"] == 1
    assert "unknown_evidence_id:hidden-truth" in scored["claims"][0]["citation_errors"]


@pytest.mark.parametrize("length,valid", [(400, True), (401, False)])
def test_frozen_reason_character_limit(length, valid):
    case, gold = case_and_gold()
    output = response(case)
    output["answers"][2]["reason"] = "x" * length
    scored = score_response(case, gold, output)
    assert scored["claims"][2]["schema_valid"] is valid
    assert ("invalid_reason_length" in scored["claims"][2]["schema_errors"]) is not valid


@pytest.mark.parametrize("alteration", ["missing", "duplicate"])
def test_missing_duplicate_answers_fail_only_the_expected_claim(alteration):
    case, gold = case_and_gold()
    output = response(case)
    if alteration == "missing":
        output["answers"].pop(0)
    else:
        output["answers"].append(copy.deepcopy(output["answers"][0]))
    scored = score_response(case, gold, output)
    assert scored["metrics"]["three_class_accuracy"]["value"] == 2 / 3
    assert scored["metrics"]["warranted_answer_accuracy"]["value"] == 1 / 2
    assert scored["metrics"]["correct_unresolved"]["value"] == 1
    assert scored["metrics"]["invalid_missing_answer_rate"]["value"] == 1 / 3


@pytest.mark.parametrize("alteration", ["unknown_claim", "wrong_case", "extra_root", "not_object"])
def test_root_schema_failures_are_explicit_and_keep_denominators(alteration):
    case, gold = case_and_gold()
    output = response(case)
    if alteration == "unknown_claim":
        output["answers"].append({**output["answers"][0], "claim_id": "extra"})
    elif alteration == "wrong_case":
        output["case_id"] = "other"
    elif alteration == "extra_root":
        output["confidence"] = 1
    else:
        output["answers"].append(None)
    scored = score_response(case, gold, output)
    assert scored["response_errors"]
    assert scored["metrics"]["invalid_missing_answer_rate"] == {
        "value": 1, "numerator": 3, "denominator": 3,
    }


def test_duplicate_json_keys_not_silently_overwritten():
    case, gold = case_and_gold()
    scored = score_response(case, gold, '{"case_id":"case-1","case_id":"case-1","answers":[]}')
    assert "malformed_json" in scored["response_errors"]
    assert scored["metrics"]["invalid_missing_answer_rate"]["value"] == 1


def test_undefined_metrics_stay_none_in_case_group_and_paired_results():
    case, gold = case_and_gold()
    gold["claims"] = [{**claim, "status": "unresolved"} for claim in gold["claims"]]
    rows = [{**score_response(case, gold, constant_response(case, "unresolved")),
             "model_id": "m", "arm": arm} for arm in "ABC"]
    summary = summarize_scores(rows, resamples=50)
    for row in rows:
        assert row["metrics"]["warranted_answer_accuracy"]["value"] is None
    for group in summary["groups"]:
        assert group["metrics"]["warranted_answer_accuracy"]["mean"] is None
    for pair in summary["paired"]:
        assert pair["metrics"]["warranted_answer_accuracy"]["mean"] is None
        assert pair["metrics"]["warranted_answer_accuracy"]["n_cases"] == 0


def test_paired_difference_first_averages_claims_then_cases():
    first, first_gold = case_and_gold("first")
    second, second_gold = case_and_gold("second")
    # One answerable claim in the first case versus two in the second.
    first["claims"] = first["claims"][1:]
    first_gold["claims"] = first_gold["claims"][1:]
    rows = []
    for case, gold in ((first, first_gold), (second, second_gold)):
        for arm in ("B", "C"):
            output = constant_response(case, "unresolved")
            if arm == "C":
                output["answers"][0]["status"] = gold["claims"][0]["status"]
            rows.append({**score_response(case, gold, output), "model_id": "m", "arm": arm})
    summary = summarize_scores(rows, resamples=200)
    paired = next(p for p in summary["paired"] if p["comparison"] == "C-B")
    assert paired["metrics"]["warranted_answer_accuracy"]["mean"] == 0.75
    treatment = next(g for g in summary["groups"] if g["arm"] == "C")
    assert treatment["metrics"]["warranted_answer_accuracy"]["numerator"] == 2
    assert treatment["metrics"]["warranted_answer_accuracy"]["denominator"] == 3
    assert treatment["metrics"]["warranted_answer_accuracy"]["mean"] != 2 / 3


def test_shared_history_cases_are_one_bootstrap_cluster_not_independent_observations():
    rows = [scored_row(case_id, cluster="same-history", arm=arm)
            for case_id in ("one", "two", "three") for arm in "BC"]
    summary = summarize_scores(rows, resamples=50)
    paired = next(p for p in summary["paired"] if p["comparison"] == "C-B")
    for metric in paired["metrics"].values():
        assert metric["n_cases"] == 3
        assert metric["n_clusters"] == 1
        assert metric["ci_low"] is None


def test_cluster_pairing_bootstrap_is_reproducible_and_input_order_independent():
    rows = [scored_row(f"case-{i}", cluster=f"history-{i // 2}", arm=arm,
                       statuses=STATUSES if (i < 2) == (arm == "C") else ("unresolved",) * 3)
            for i in range(4) for arm in "ABC"]
    summary = summarize_scores(rows, bootstrap_seed=13, resamples=300)
    assert summary == summarize_scores(list(reversed(rows)), bootstrap_seed=13, resamples=300)
    paired = next(p for p in summary["paired"] if p["comparison"] == "C-B")
    metric = paired["metrics"]["warranted_answer_accuracy"]
    assert metric == {"mean": 0, "ci_low": -1, "ci_high": 1, "n_cases": 4, "n_clusters": 2}


def test_models_and_subsets_never_pooled():
    rows = [scored_row(subset=subset, model=model, arm=arm)
            for model in ("one", "two") for subset in ("wiki", "synthetic") for arm in "ABC"]
    summary = summarize_scores(rows, resamples=50)
    assert len(summary["groups"]) == 12
    assert len(summary["paired"]) == 12
    assert all(g["case_count"] == 1 for g in summary["groups"])


def test_unmatched_arms_are_exposed_and_duplicate_retries_rejected():
    row = scored_row()
    summary = summarize_scores([row], resamples=50)
    paired = next(p for p in summary["paired"] if p["comparison"] == "C-B")
    assert paired["missing_control_case_ids"] == ["case-1"]
    assert paired["paired_case_count"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        summarize_scores([row, row])


@pytest.mark.parametrize("mismatch", ["cluster", "denominator"])
def test_mismatched_case_metadata_cannot_be_paired(mismatch):
    control, treatment = scored_row(arm="B"), scored_row(arm="C")
    if mismatch == "cluster":
        treatment["cluster_id"] = "new-history"
    else:
        treatment["metrics"]["warranted_answer_accuracy"]["denominator"] += 1
    with pytest.raises(ValueError, match="must match"):
        summarize_scores([control, treatment])


def test_sanity_baselines_are_separate_from_model_observations():
    case, gold = case_and_gold()
    rows = sanity_scores([case], [gold])
    assert len(rows) == 3
    assert all("model_id" not in row and "arm" not in row for row in rows)
    scores = {row["baseline"]: row for row in rows}
    assert scores["always_unresolved"]["metrics"]["warranted_answer_accuracy"]["value"] == 0
    assert scores["always_established"]["metrics"]["unjustified_certainty"]["value"] == 1
    assert scores["always_ruled_out"]["metrics"]["unjustified_certainty"]["value"] == 1


def test_gold_must_exactly_match_case_and_valid_statuses():
    case, gold = case_and_gold()
    gold["claims"].pop()
    with pytest.raises(ValueError, match="match exactly"):
        score_response(case, gold, None)


def test_examples_include_failure_and_are_deterministic_with_explicit_absence():
    rows = []
    for case_id, improving in (("better", True), ("worse", False)):
        for arm in "BC":
            statuses = STATUSES if (arm == "C") == improving else ("established",) * 3
            rows.append(scored_row(case_id, arm=arm, statuses=statuses))
    examples = select_examples(rows)
    assert examples == select_examples(list(reversed(rows)))
    assert {e["selection"]["case_id"] for e in examples} == {"better", "worse"}
    flat = select_examples([scored_row(arm=arm) for arm in "BC"])
    assert all(e["selection"] is None and e["absence"] for e in flat)


def test_less_certainty_with_worse_warranted_accuracy_not_selected_as_improvement():
    rows = [scored_row(arm="B", statuses=("established", "ruled_out", "established")),
            scored_row(arm="C", statuses=("unresolved",) * 3)]
    examples = {e["category"]: e for e in select_examples(rows)}
    assert examples["improvement"]["selection"] is None
    assert examples["unsuccessful_or_disagreeing"]["selection"]["case_id"] == "case-1"


def test_report_blocked_has_empty_model_results_and_analytic_baselines(tmp_path):
    summary = summarize_scores([])
    case, gold = case_and_gold()
    baseline = sanity_scores([case], [gold])
    execution = {"status": "blocked", "blockers": ["No authorized model execution path."],
                 "evaluation_calls_completed": 0, "development_calls_completed": 0,
                 "actual_cost_usd": 0, "preservation_status": "all hashes match"}
    output = render_report(summary, execution=execution, sanity_baselines=baseline)
    assert "No investigator evaluation results exist" in output
    assert "No C-minus-B effect is estimated" in output
    assert "No authorized model execution path." in output
    assert "always_unresolved" in output
    assert "Actual model cost (USD): 0." in output
    assert "No evaluated examples exist" in output
    assert output == render_report(summary, execution=execution, sanity_baselines=baseline)
    path = tmp_path / "REPORT.md"
    write_report(summary, path, execution=execution, sanity_baselines=baseline)
    assert path.read_text() == output


def test_report_real_rows_expose_primary_metrics_failures_cost_and_null_intervals():
    rows = [scored_row(arm=arm) for arm in "ABC"]
    report = render_report(summarize_scores(rows, resamples=50), execution={"status": "completed"},
                           examples=select_examples(rows))
    assert "C-B (primary)" in report
    assert "B-A" in report
    assert all(metric in report for metric in METRICS)
    assert "interval unavailable" in report
    assert "unavailable (not recorded)" in report
    assert "No qualifying paired case exists." in report


@pytest.mark.parametrize("resamples", [0, -1, True, 0.5])
def test_invalid_bootstrap_count_rejected(resamples):
    with pytest.raises(ValueError, match="positive integer"):
        summarize_scores([], resamples=resamples)
