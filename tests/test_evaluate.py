import pytest

from tracebench.evaluate import bootstrap_mean, score_edges, summarize


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


def test_undefined_metrics_are_not_fabricated_zeroes():
    scored = score_edges(frozenset(), frozenset(), frozenset({"a"}))
    assert scored["precision"] is None
    assert scored["recall"] is None
    assert scored["f1"] is None
    assert scored["absolute_error"] == 0
    result = bootstrap_mean([None, None], seed=1, samples=100)
    assert result == {"mean": None, "ci_low": None, "ci_high": None, "n": 0}


def test_perfect_oracle_scoring():
    edges = frozenset({("a", "b")})
    score = score_edges(edges, edges, frozenset({"a", "b", "c"}))
    assert score["precision"] == score["recall"] == score["f1"] == 1
    assert score["absolute_error"] == 0
    assert score["false_positive_edges_per_target"] == 0


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
