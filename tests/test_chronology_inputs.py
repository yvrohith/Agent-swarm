"""Offline saved-input and freeze guards; never generate published worlds."""

import copy
import json
from pathlib import Path

import pytest

from studies.chronology_consistency.inputs import (
    build_input_manifest,
    configuration_id,
    digest,
    discover_configurations,
    file_digest,
    load_json_strict,
    source_pin_audit,
    validate_csv_rows,
    verify_input_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def test_complete_published_grid_and_every_original_denominator():
    manifest = discover_configurations(ROOT)
    assert manifest["reported_configuration_count"] == 184
    assert manifest["distinct_configuration_count"] == 184
    assert manifest["duplicate_configuration_count"] == 0
    benchmark = manifest["cohorts"]["benchmark"]
    receipts = manifest["cohorts"]["missing_receipts"]
    assert (benchmark["configuration_count"], benchmark["evaluation_count"],
            benchmark["summary_group_count"]) == (144, 1440, 120)
    assert (receipts["configuration_count"], receipts["evaluation_count"],
            receipts["masked_observation_count"], receipts["paired_evaluation_count"],
            receipts["summary_group_count"], receipts["paired_summary_group_count"]) == (
                40, 1280, 320, 640, 64, 32)
    originals = {"benchmark": [], "missing_receipts": []}
    saved = load_json_strict(ROOT / "studies/missing_receipts/results/study.json")
    for configuration in manifest["configurations"]:
        assert configuration_id(configuration["config"]) == configuration["configuration_id"]
        for origin in configuration["origins"]:
            originals[origin["cohort"]].extend(origin["run_indices"])
            assert origin["config_locator"].startswith(origin["result_locator"] + "#/")
            if origin["cohort"] == "missing_receipts":
                world = saved["worlds"][origin["saved_world_index"]]
                assert world["config"] == configuration["config"]
                assert world["world_id"] == configuration["configuration_id"]
    assert sorted(originals["benchmark"]) == list(range(1440))
    assert sorted(originals["missing_receipts"]) == list(range(1280))


def test_historical_pins_reconcile_without_refreshing():
    audit = source_pin_audit(ROOT)
    benchmark = audit["benchmark"]
    assert benchmark["historical_aggregate_reconstructed"] is True
    assert benchmark["aggregate_pin_matches_current"] is False
    assert benchmark["run_benchmark_ast_unchanged"] is True
    assert all(benchmark["score_compatibility"]
               ["old_score_field_ast_equal_after_local_factoring"].values())
    assert benchmark["score_compatibility"]["added_score_fields"] == [
        "false_negative_targets", "false_positive_targets", "signed_error", "target_disagreement"]
    assert audit["missing_receipts"]["cli_historical_pin_reconstructed"] is True
    assert audit["historical_pins_refreshed"] is False


def test_manifest_separates_presentation_and_scientific_dependencies():
    manifest = build_input_manifest(ROOT)
    roles = {entry["path"]: entry["role"] for entry in manifest["artifacts"]}
    assert roles["results/benchmark.json"] == "scientific_result_input"
    assert roles["results/trace_completeness.svg"] == "presentation_history"
    assert roles["results/REPORT.md"] == "presentation_history"
    assert all(entry.get("historical_pin_matches", True) for entry in manifest["artifacts"])
    verify_input_manifest(ROOT, manifest)


@pytest.mark.parametrize("source", ['{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}'])
def test_strict_json_rejects_ambiguous_or_nonfinite_inputs(tmp_path, source):
    path = tmp_path / "bad.json"
    path.write_text(source)
    with pytest.raises(ValueError):
        load_json_strict(path)


def test_configuration_requires_all_fields_and_no_hidden_parameters():
    config = discover_configurations(ROOT)["configurations"][0]["config"]
    incomplete = copy.deepcopy(config)
    del incomplete["temporal_window"]
    with pytest.raises(ValueError, match="complete"):
        configuration_id(incomplete)
    with pytest.raises(ValueError, match="complete"):
        configuration_id(config | {"new_hidden_condition": 1})
    with pytest.raises(ValueError, match="integer"):
        configuration_id(config | {"seed": True})


@pytest.mark.parametrize("contents", ["a,b\n1,changed\n", "a,b\n1,\n1,\n", "a,a\n1,1\n"])
def test_saved_csv_cell_count_and_duplicate_column_mismatches_fail(tmp_path, contents):
    path = tmp_path / "rows.csv"
    path.write_text(contents)
    with pytest.raises(ValueError):
        validate_csv_rows(path, [{"a": 1, "b": None}])


def test_frozen_input_mutation_fails_before_configuration_recovery(tmp_path):
    path = tmp_path / "frozen.json"
    path.write_text("{\"seed\": 0}\n")
    manifest = {"schema_version": 1, "artifacts": [],
                "dependencies": [{"path": path.name, "sha256": file_digest(path)}]}
    before = copy.deepcopy(manifest)
    path.write_text("{\"seed\": 1}\n")
    with pytest.raises(ValueError, match="Frozen input changed"):
        verify_input_manifest(tmp_path, manifest)
    assert manifest == before
    assert json.loads(path.read_text()) == {"seed": 1}


def test_frozen_input_path_traversal_is_rejected(tmp_path):
    manifest = {"schema_version": 1, "artifacts": [],
                "dependencies": [{"path": "../outside", "sha256": "0" * 64}]}
    with pytest.raises(ValueError, match="Unsafe frozen input path"):
        verify_input_manifest(tmp_path, manifest)


def test_historical_digest_retains_exact_saved_number_encoding():
    assert digest({"value": 0}) != digest({"value": 0.0})
