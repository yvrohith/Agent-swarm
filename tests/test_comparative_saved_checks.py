"""Focused failure checks for the additive released-results verifier."""
from fractions import Fraction

import pytest

from studies.comparative_validity.verify_comparisons import (
    average,
    conflict_impossible,
    index,
    verify_pins,
)


def test_complementary_queries_do_not_authorize_an_early_stop():
    # Neither first query can contradict this nominal support, but their joint
    # answer 01 can. A zero immediate alarm probability therefore cannot STOP.
    nominal = {(0, 0), (1, 1)}
    envelope = nominal | {(0, 1)}
    positions = {"left": 0, "right": 1}
    assert not conflict_impossible(nominal, envelope, positions, [])
    assert not conflict_impossible(nominal, envelope, positions,
                                   [{"query_id": "left", "outcome_id": 0}])
    assert conflict_impossible(nominal, envelope, positions,
                               [{"query_id": "left", "outcome_id": 1}])


def test_empty_hypothetical_support_is_not_a_vacuous_stop():
    with pytest.raises(ValueError, match="outside hypothetical"):
        conflict_impossible({(0,)}, {(0,)}, {"q": 0}, [{"query_id": "q", "outcome_id": 1}])


def test_structure_weighting_retains_price_variants():
    values = {"cheap": Fraction(1), "expensive": Fraction(9), "other": Fraction(2)}
    groups = {"cheap": "same_structure", "expensive": "same_structure", "other": "other"}
    ids = list(values)
    assert average(values, ids, groups, "equal_problem")[0] == 4
    mean, weights = average(values, ids, groups, "structure_balanced")
    assert mean == Fraction(7, 2)
    assert weights == {"cheap": Fraction(1, 4), "expensive": Fraction(1, 4), "other": Fraction(1, 2)}


def test_duplicate_result_identity_is_rejected():
    with pytest.raises(ValueError, match="Duplicate result identity"):
        index([{"problem": "a", "signature": [0]}, {"problem": "a", "signature": [0]}],
              ("problem", "signature"))


def test_public_manifest_cannot_escape_checkout(tmp_path):
    with pytest.raises(ValueError, match="Path escape"):
        verify_pins(tmp_path, {"../unrelated": "0" * 64})
