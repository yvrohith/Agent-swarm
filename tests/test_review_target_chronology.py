"""Focused checks for the additive target-error derivation and chronology trace."""

import csv
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGET = runpy.run_path(str(ROOT / "studies/review_remediation/target_errors.py"))
CHRONOLOGY = runpy.run_path(str(ROOT / "studies/review_remediation/chronology_audit.py"))


def original_rows():
    with (ROOT / "results/runs.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_original_paired_target_error_identities_and_mean_absolute_error():
    result = TARGET["derive"](original_rows())
    assert len(result["rows"]) == 24
    assert len(result["paired_context_minus_requests"]) == 12
    requests = result["means"]["requests"]
    assert requests["absolute_error"] != pytest.approx(abs(requests["signed_error"]))
    assert requests["absolute_error"] == pytest.approx(0.029629629629629634)
    assert result["means"]["context"]["target_disagreement"] == pytest.approx(0.11388888888888889)
    for row in result["rows"]:
        n = row["eligible_targets"]
        assert row["signed_error"] == pytest.approx(
            (row["false_positive_targets"] - row["false_negative_targets"]) / n)
        assert row["target_disagreement"] == pytest.approx(
            (row["false_positive_targets"] + row["false_negative_targets"]) / n)


def test_target_derivation_rejects_missing_paired_world():
    rows = original_rows()
    rows = [r for r in rows if not (r["seed"] == "0" and r["regime"] == "context")]
    with pytest.raises(ValueError, match="paired seeds"):
        TARGET["derive"](rows)


def test_target_derivation_rejects_impossible_target_counts():
    row = TARGET["derive"](original_rows())["rows"][0]
    original = next(r for r in original_rows() if r["seed"] == str(row["seed"])
                    and r["regime"] == row["regime"] and r["method"] == "witness"
                    and r["transmission_probability"] == "0.3" and r["shock_strength"] == "0.9")
    with pytest.raises(ValueError, match="integer target counts"):
        TARGET["derive_row"]({**original, "false_attributed_target_fraction": "0.0212345"})


def test_first_installation_backdates_before_an_actual_empty_selection_state():
    config = CHRONOLOGY["SimulationConfig"](
        seed=0, n_runs=2, n_task_families=1, writes_per_run=3, shock_strength=0.0)
    result = CHRONOLOGY["audit_world"](config)
    assert result["instrumented_equals_uninstrumented"]
    assert result["writes_checked"] == 6
    assert result["ordinary_chain_order_violations"] == []
    assert result["violating_first_installations"] == 1
    v = result["violations"][0]
    assert v["source_event_id"] == "e000002"
    assert v["earlier_recipient_write"]["event_id"] == "e000003"
    assert v["installed_during_write_id"] == "e000004"
    assert v["earlier_selection_available_sources"] == []
    assert len(v["all_contexts_for_source_run"]) == 1
    assert v["source_timestamp"] < v["request_timestamp"] < v["delivery_timestamp"]
    assert (v["delivery_timestamp"] < v["context_timestamp"]
            < v["earlier_recipient_write"]["timestamp"] < v["installed_during_write_timestamp"])


def test_ordinary_earlier_context_receipts_are_not_automatically_defects():
    config = CHRONOLOGY["SimulationConfig"](seed=0, shock_strength=0.9)
    result = CHRONOLOGY["audit_world"](config)
    assert result["context_records"] > 0
    assert result["instrumented_equals_uninstrumented"]
    assert result["ordinary_chain_order_violations"] == []
    assert result["violations"] == []
