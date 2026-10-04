"""Retained-data diagnostics distinguish chronology, stage order, and metric error."""

import copy
from pathlib import Path

import pytest

from studies.comparative_validity.chronology_scope import (
    METRICS,
    check_pin,
    extrema,
    index_unique,
    inspect_trace,
    load,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def diagnostic():
    return load(ROOT / "studies/chronology_consistency/development_checks.json")


def test_retained_counterexample_distinguishes_order_from_availability(diagnostic):
    result = inspect_trace(diagnostic["trace"], diagnostic["retiming"])
    assert result["writes_checked"] == 6
    assert result["receipt_stage_order_violations"] == 0
    assert result["legacy_affected_writes"] == 1
    assert result["offending_first_contexts"] == 1
    assert result["corrected_availability_disagreements"] == 0


def test_readonly_check_preserves_primitive_input(diagnostic):
    saved = copy.deepcopy(diagnostic)
    inspect_trace(diagnostic["trace"], diagnostic["retiming"])
    assert diagnostic == saved


def test_invalid_stage_order_fails_even_with_saved_parity_flags(diagnostic):
    diagnostic["trace"]["world"]["requests"][0]["timestamp"] = -100
    with pytest.raises(ValueError, match="receipt-stage order"):
        inspect_trace(diagnostic["trace"], diagnostic["retiming"])


def test_changed_captured_availability_fails(diagnostic):
    diagnostic["trace"]["snapshots"][0]["available_source_ids"] = ["invented"]
    with pytest.raises(ValueError, match="Captured availability"):
        inspect_trace(diagnostic["trace"], diagnostic["retiming"])


def test_missing_correction_cannot_claim_availability_restored(diagnostic):
    with pytest.raises(ValueError, match="exactly the offending chains"):
        inspect_trace(diagnostic["trace"], [])


def test_changed_quarter_rule_fails(diagnostic):
    diagnostic["retiming"][0]["new_timestamps"][0] += 0.1
    with pytest.raises(ValueError, match="quarter rule"):
        inspect_trace(diagnostic["trace"], diagnostic["retiming"])


def test_duplicate_record_identity_fails():
    with pytest.raises(ValueError, match="Duplicate request_id"):
        index_unique([{"request_id": "q"}, {"request_id": "q"}], "request_id")


def test_duplicate_json_keys_fail(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"x": 1, "x": 2}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        load(path)


def test_extrema_retain_null_and_adverse_direction():
    rows = [{"world_id": name, "corrected_minus_legacy": {m: value for m in METRICS}}
            for name, value in (("a", -2), ("b", 5), ("c", None))]
    for value in extrema(rows).values():
        assert value["maximum_absolute_delta"] == 5
        assert value["minimum_delta"] == -2
        assert value["maximum_absolute_witness"] == {"world_id": "b"}
        assert value["undefined_rows"] == 1
        assert value["defined_rows"] == 2


def test_all_undefined_is_not_zero():
    row = {"corrected_minus_legacy": dict.fromkeys(METRICS)}
    for value in extrema([row]).values():
        assert value["maximum_absolute_delta"] is None
        assert value["defined_rows"] == 0


def test_original_authority_rejects_modified_dependency(tmp_path):
    path = tmp_path / "inputs.json"
    path.write_text('{"changed": true}')
    with pytest.raises(ValueError, match="Frozen computational dependency changed"):
        check_pin(tmp_path, "inputs.json", {"inputs.json": "0" * 64})


def test_original_authority_rejects_missing_pin(tmp_path):
    with pytest.raises(ValueError, match="Missing original dependency pin"):
        check_pin(tmp_path, "inputs.json", {})


def test_original_authority_rejects_path_escape(tmp_path):
    with pytest.raises(ValueError, match="path escape"):
        check_pin(tmp_path, "../outside.json", {"../outside.json": "0" * 64})
