import pytest

from tracebench.evaluate import METRICS, bootstrap_mean, paired_differences, score_edges, summarize


def test_event_and_target_errors_distinguish_wrong_source():
    scored = score_edges(frozenset({("wrong", "copied"), ("s", "independent")}),
                         frozenset({("right", "copied")}),
                         frozenset({"copied", "independent", "unused"}))
    assert scored["precision"] == 0
    assert scored["recall"] == 0
    assert scored["false_positive_edges_per_target"] == 2 / 3
    assert scored["false_attributed_target_fraction"] == 1 / 3
    assert scored["theta"] == 1 / 3
    assert scored["theta_hat"] == 2 / 3
    assert scored["false_positive_targets"] == 1
    assert scored["false_negative_targets"] == 0
    assert scored["signed_error"] == scored["target_disagreement"] == 1 / 3


def test_undefined_metrics_are_not_fabricated_zeroes():
    scored = score_edges(frozenset(), frozenset(), frozenset({"a"}))
    assert scored["precision"] is None
    assert scored["recall"] is None
    assert scored["f1"] is None
    assert scored["absolute_error"] == 0
    assert scored["false_positive_targets"] == scored["false_negative_targets"] == 0
    assert scored["signed_error"] == scored["target_disagreement"] == 0
    result = bootstrap_mean([None, None], seed=1, samples=100)
    assert result == {"mean": None, "ci_low": None, "ci_high": None, "n": 0}


def test_perfect_oracle_scoring():
    edges = frozenset({("a", "b")})
    score = score_edges(edges, edges, frozenset({"a", "b", "c"}))
    assert score["precision"] == score["recall"] == score["f1"] == 1
    assert score["absolute_error"] == 0
    assert score["false_positive_edges_per_target"] == 0
    assert score["false_positive_targets"] == score["false_negative_targets"] == 0
    assert score["signed_error"] == score["target_disagreement"] == 0


def test_undefined_seeds_are_counted_and_single_seed_has_no_ci():
    result = bootstrap_mean([None, 0.5], seed=1, samples=100)
    assert result == {"mean": 0.5, "ci_low": None, "ci_high": None, "n": 1}


def test_bootstrap_reproducible_and_nontrivial():
    a = bootstrap_mean([0, 0.2, 0.8, 1], seed=24, samples=1000)
    assert a == bootstrap_mean([0, 0.2, 0.8, 1], seed=24, samples=1000)
    assert a["ci_low"] < a["mean"] < a["ci_high"]


def test_rejects_invalid_scoring_universe_and_duplicate_seeds():
    with pytest.raises(ValueError):
        score_edges(frozenset(), frozenset(), frozenset())
    with pytest.raises(ValueError):
        score_edges(frozenset({("a", "b")}), frozenset(), frozenset({"c"}))
    row = {"seed": 0, "transmission_probability": 0, "shock_strength": 0,
           "regime": "writes", "method": "temporal"}
    with pytest.raises(ValueError, match="distinct"):
        summarize([row, row])


def test_wrong_source_has_edge_errors_without_target_errors():
    score = score_edges(frozenset({("wrong", "target")}),
                        frozenset({("right", "target")}), frozenset({"target", "unused"}))
    assert score["false_positive_edges"] == score["false_negative_edges"] == 1
    assert score["false_positive_targets"] == score["false_negative_targets"] == 0
    assert score["signed_error"] == score["target_disagreement"] == 0


def test_target_errors_can_cancel_in_theta_but_not_disagreement():
    score = score_edges(frozenset({("source", "independent")}),
                        frozenset({("source", "copied")}),
                        frozenset({"independent", "copied", "unused"}))
    assert score["false_positive_targets"] == score["false_negative_targets"] == 1
    assert score["signed_error"] == 0
    assert score["target_disagreement"] == 2 / 3


@pytest.mark.parametrize("predicted,actual", [(0, 0), (0, 7), (7, 0), (4, 5), (5, 4), (7, 7)])
def test_signed_theta_identity_and_target_disagreement(predicted, actual):
    eligible = frozenset(str(index) for index in range(9))
    predictions = frozenset(("prediction", str(index)) for index in range(predicted))
    truth = frozenset(("truth", str(index)) for index in range(2, actual + 2))
    score = score_edges(predictions, truth, eligible)
    assert score["theta_hat"] - score["theta"] == pytest.approx(
        (score["false_positive_targets"] - score["false_negative_targets"]) / len(eligible)
    )
    assert score["signed_error"] == score["theta_hat"] - score["theta"]
    assert score["target_disagreement"] == (
        score["false_positive_targets"] + score["false_negative_targets"]
    ) / len(eligible)


STUDY_KEYS = ("transmission_probability", "shock_strength", "regime", "method",
              "profile", "retention", "policy")


def _study_row(seed=200, policy="conjunction", recall=0.5, **changes):
    return {
        "seed": seed, "transmission_probability": 0.3, "shock_strength": 0.9,
        "regime": "context", "method": "temporal", "profile": "delivery",
        "retention": 0.5, "policy": policy, "mask_seed": seed + 1000,
        "observation_sha256": f"world-{seed}", "recall": recall, **changes,
    }


@pytest.mark.parametrize("dimension", ["profile", "retention", "policy"])
def test_study_dimensions_cannot_be_silently_pooled(dimension):
    with pytest.raises(ValueError, match="study dimensions"):
        summarize([_study_row()], group_keys=tuple(key for key in STUDY_KEYS if key != dimension),
                  metric_names=("recall",))


def test_summary_separates_study_dimensions_and_accepts_additive_metrics():
    rows = [_study_row(), _study_row(profile="context"), _study_row(retention=0.9),
            _study_row(policy="evidence_aware")]
    results = summarize(rows, bootstrap_samples=100, group_keys=STUDY_KEYS,
                        metric_names=("recall",))
    assert len(results) == 4
    assert all(result["n_seeds"] == 1 for result in results)
    assert all(result["metrics"]["recall"]["mean"] == 0.5 for result in results)
    assert {"signed_error", "target_disagreement", "false_positive_targets",
            "false_negative_targets"} <= set(METRICS)


def test_summary_bootstrap_is_invariant_to_input_order():
    rows = [_study_row(seed=seed, recall=seed / 10) for seed in range(6)]
    assert summarize(rows, 100, group_keys=STUDY_KEYS, metric_names=("recall",)) == summarize(
        rows[::-1], 100, group_keys=STUDY_KEYS, metric_names=("recall",)
    )


def test_masks_are_not_independent_worlds():
    rows = [_study_row(), _study_row(mask_seed=999)]
    with pytest.raises(ValueError, match="distinct simulation seeds"):
        summarize(rows, 100, group_keys=STUDY_KEYS, metric_names=("recall",))
    with pytest.raises(ValueError, match="not summary groups"):
        summarize(rows, 100, group_keys=STUDY_KEYS + ("mask_seed",), metric_names=("recall",))


def test_paired_differences_match_worlds_preserve_nulls_and_bootstrap_worlds():
    rows = [
        _study_row(seed=201, policy="evidence_aware", recall=0.8),
        _study_row(seed=200, recall=0.1),
        _study_row(seed=202, policy="evidence_aware", recall=0.5),
        _study_row(seed=200, policy="evidence_aware", recall=0.3),
        _study_row(seed=202, recall=None),
        _study_row(seed=201, recall=0.6),
    ]
    deltas = paired_differences(rows, group_keys=STUDY_KEYS, metric_names=("recall",))
    assert [row["seed"] for row in deltas] == [200, 201, 202]
    assert [row["recall"] for row in deltas[:2]] == pytest.approx([0.2, 0.2])
    assert deltas[2]["recall"] is None
    assert deltas[0]["mask_seed"] == 1200
    assert deltas[0]["observation_sha256"] == "world-200"
    assert deltas[0]["reference_policy"] == "conjunction"
    assert deltas[0]["comparison_policy"] == "evidence_aware"
    summaries = summarize(deltas, 100, group_keys=STUDY_KEYS[:-1], metric_names=("recall",))
    metric = summaries[0]["metrics"]["recall"]
    assert summaries[0]["n_seeds"] == 3
    assert metric["n"] == 2
    assert metric["ci_low"] == pytest.approx(0.2)
    assert metric["ci_high"] == pytest.approx(0.2)


@pytest.mark.parametrize("field,value", [("mask_seed", 99), ("observation_sha256", "different")])
def test_pairing_rejects_mismatched_observations(field, value):
    rows = [_study_row(), _study_row(policy="evidence_aware", **{field: value})]
    with pytest.raises(ValueError, match=f"identical {field}"):
        paired_differences(rows, group_keys=STUDY_KEYS, metric_names=("recall",))


def test_pairing_rejects_duplicates_and_missing_policy_for_world():
    row = _study_row()
    with pytest.raises(ValueError, match="distinct simulation seeds"):
        paired_differences([row, row], group_keys=STUDY_KEYS, metric_names=("recall",))
    with pytest.raises(ValueError, match="both comparison policies"):
        paired_differences([row, _study_row(seed=201, policy="evidence_aware")],
                           group_keys=STUDY_KEYS, metric_names=("recall",))
