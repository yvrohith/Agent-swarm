"""Offline runner gates and retained evidence, using temporary mock studies only."""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from studies.chronology_consistency import runner
from studies.chronology_consistency.reference import verify_retiming
from studies.chronology_consistency.retime import RetimingError, retime_world
from studies.chronology_consistency.trace import trace_world
from tracebench.estimators import estimate
from tracebench.evaluate import score_edges
from tracebench.model import SimulationConfig
from tracebench.observe import Telemetry, observe

ROOT = Path(__file__).resolve().parents[1]


def put_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def diagnostic_trace():
    saved = json.loads((ROOT / "studies/review_remediation/chronology.json").read_text())
    config = next(row["config"] for row in saved["worlds"]
                  if row["published_cohort"] == "minimal_diagnostic")
    return trace_world(SimulationConfig(**config))


@pytest.fixture
def mock_study(tmp_path, monkeypatch):
    study = tmp_path / "studies/chronology_consistency"
    study.mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "STUDY", study)
    return tmp_path, study


def frozen_fixture(mock_study, monkeypatch):
    root, study = mock_study
    put_json(study / "inputs.json", {"artifacts": [], "dependencies": []})
    for name in ("config.json", "preservation.json", "ISOLATION.json",
                 "development_checks.json", "pre_freeze_checks.json"):
        put_json(study / name, {})
    for name in ("ANALYSIS.md", "METHOD.md", "instrumentation.py"):
        (study / name).write_text("temporary fixture\n")
    (root / "tests/test_chronology_fixture.py").write_text("# temporary fixture\n")
    monkeypatch.setattr(runner, "settings", lambda: {})
    monkeypatch.setattr(runner, "verify_input_manifest", lambda root, value: None)
    put_json(study / "freeze.json", {
        "files_sha256": {name: runner.digest(root / name) for name in runner.dependencies()}})
    return root, study


@pytest.mark.parametrize("suffix", [".json", ".json.gz"])
def test_write_new_refuses_overwrite_and_leaves_bytes_intact(tmp_path, suffix):
    target = tmp_path / ("evidence" + suffix)
    runner.write_new(target, {"record": [1, 2, None]})
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        runner.write_new(target, {"replacement": True})
    assert target.read_bytes() == before
    assert runner.read(target) == {"record": [1, 2, None]}


def test_compressed_retained_evidence_has_deterministic_bytes(tmp_path):
    first, second = (tmp_path / name for name in ("one.json.gz", "two.json.gz"))
    value = {"z": [3, 2, 1], "a": None}
    runner.write_new(first, value)
    runner.write_new(second, value)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("existing", ["inputs.json", "freeze.json"])
def test_prepare_refuses_retained_inputs_before_discovery(mock_study, monkeypatch, existing):
    _, study = mock_study
    target = study / existing
    target.write_text("retained fixture\n")

    def forbidden(*args, **kwargs):
        raise AssertionError("Input discovery must not run after the refusal gate")

    monkeypatch.setattr(runner, "build_input_manifest", forbidden)
    with pytest.raises(ValueError, match="Refusing to replace"):
        runner.prepare_inputs()
    assert target.read_text() == "retained fixture\n"


def test_freeze_verification_rejects_tampered_dependency(mock_study, monkeypatch):
    _, study = frozen_fixture(mock_study, monkeypatch)
    expected_count = len(runner.dependencies())
    assert runner.verify_freeze() == expected_count
    (study / "instrumentation.py").write_text("changed fixture\n")
    with pytest.raises(ValueError, match="Frozen dependency changed"):
        runner.verify_freeze()


@pytest.mark.parametrize("addition", ["source", "test"])
def test_freeze_verification_rejects_silent_source_closure_expansion(
        mock_study, monkeypatch, addition):
    root, study = frozen_fixture(mock_study, monkeypatch)
    target = study / "new_helper.py" if addition == "source" else (
        root / "tests/test_chronology_new_helper.py")
    target.write_text("# additional dependency\n")
    with pytest.raises(ValueError, match="Frozen dependency set differs"):
        runner.verify_freeze()


def test_freeze_verification_rejects_source_closure_contraction(mock_study, monkeypatch):
    _, study = frozen_fixture(mock_study, monkeypatch)
    (study / "instrumentation.py").unlink()
    with pytest.raises(ValueError, match="Frozen dependency set differs"):
        runner.verify_freeze()


def qualification_fixture(mock_study, monkeypatch):
    root, study = frozen_fixture(mock_study, monkeypatch)
    omitted = {"studies/chronology_consistency/" + name for name in (
        "development_checks.json", "pre_freeze_checks.json")}
    evidence = {"status": "passed", "new_published_sensitivity_outcomes_observed": 0,
                "source_sha256": {name: runner.digest(root / name)
                                  for name in runner.dependencies() if name not in omitted}}
    put_json(study / "development_checks.json", evidence)
    put_json(study / "pre_freeze_checks.json", {
        "status": "passed", "new_published_sensitivity_outcomes_observed": 0})
    monkeypatch.setattr(runner, "verify_preservation", lambda: {"fixture": True})
    return root, study, evidence


def test_freeze_refuses_to_replace_existing_execution_freeze(mock_study, monkeypatch):
    _, study, _ = qualification_fixture(mock_study, monkeypatch)
    original = (study / "freeze.json").read_bytes()
    with pytest.raises(FileExistsError):
        runner.freeze()
    assert (study / "freeze.json").read_bytes() == original


def test_freeze_rejects_source_change_after_development_qualification(mock_study, monkeypatch):
    _, study, _ = qualification_fixture(mock_study, monkeypatch)
    (study / "freeze.json").unlink()
    (study / "instrumentation.py").write_text("changed after qualification\n")
    with pytest.raises(ValueError, match="Sources changed after development qualification"):
        runner.freeze()
    assert not (study / "freeze.json").exists()


def test_freeze_rejects_incomplete_development_dependency_scope(mock_study, monkeypatch):
    _, study, evidence = qualification_fixture(mock_study, monkeypatch)
    (study / "freeze.json").unlink()
    evidence["source_sha256"].pop("studies/chronology_consistency/instrumentation.py")
    put_json(study / "development_checks.json", evidence)
    with pytest.raises(ValueError, match="Development source scope differs from freeze"):
        runner.freeze()
    assert not (study / "freeze.json").exists()


def test_tampered_frozen_dependency_prevents_output_creation_or_generation(mock_study, monkeypatch):
    root, study = frozen_fixture(mock_study, monkeypatch)
    (study / "instrumentation.py").write_text("tampered\n")

    def forbidden(*args, **kwargs):
        raise AssertionError("Generation must follow successful frozen dependency verification")

    monkeypatch.setattr(runner, "trace_world", forbidden)
    output = root / "forbidden-output"
    with pytest.raises(ValueError, match="Frozen dependency changed"):
        runner.execute(output)
    assert not output.exists()


def test_preservation_verifies_tracked_and_existing_local_bytes(mock_study):
    root, study = mock_study
    tracked, local = root / "historical.py", root / "retained.json"
    tracked.write_text("original scientific implementation\n")
    local.write_text("existing local artifact\n")
    put_json(study / "preservation.json", {
        "tracked_sha256": {tracked.name: runner.digest(tracked)},
        "local_sha256": {local.name: runner.digest(local)},
    })
    assert runner.verify_preservation() == {"tracked_files": 1, "historical_local_files": 1}
    local.write_text("changed existing local artifact\n")
    with pytest.raises(ValueError, match="Historical preservation mismatch: retained.json"):
        runner.verify_preservation()
    assert tracked.read_text() == "original scientific implementation\n"


def test_existing_output_is_rejected_before_world_generation(mock_study, monkeypatch):
    root, _ = mock_study
    output = root / "already-retained"
    output.mkdir()
    retained = output / "evidence.json"
    retained.write_text("original\n")
    monkeypatch.setattr(runner, "verify_freeze", lambda: 1)
    monkeypatch.setattr(runner, "verify_preservation", lambda: {})

    def forbidden(*args, **kwargs):
        raise AssertionError("World generation must not occur after overwrite refusal")

    monkeypatch.setattr(runner, "trace_world", forbidden)
    with pytest.raises(FileExistsError):
        runner.execute(output)
    assert retained.read_text() == "original\n"


def test_six_write_trace_and_retiming_roundtrip_from_retained_values(tmp_path, diagnostic_trace):
    trace = diagnostic_trace
    corrected = retime_world(trace)
    path = tmp_path / "world.json.gz"
    runner.write_new(path, {"trace": trace, "changes": corrected.changes})
    value = runner.read(path)
    decoded = runner.decode_trace(value["trace"])
    reconstructed = runner.reconstruct_corrected(decoded, value["changes"])
    assert decoded == trace
    assert reconstructed == corrected.world
    assert verify_retiming(decoded.world, reconstructed, decoded)["status"] == "verified"


def execution_fixture(mock_study, monkeypatch, trace):
    """A saved tiny benchmark fixture; no published configuration is generated."""
    root, study = mock_study
    config = asdict(trace.world.config)
    rows, summary = [], []
    for regime in ("writes", "identity", "requests", "delivery", "context"):
        for method in ("temporal", "witness"):
            keys = {"transmission_probability": config["transmission_probability"],
                    "shock_strength": config["shock_strength"], "regime": regime,
                    "method": method}
            observation = observe(trace.world, Telemetry(regime))
            scores = score_edges(estimate(observation, method), trace.world.truth_edges,
                                 trace.world.eligible_target_ids)
            rows.append(keys | {"seed": config["seed"]} | scores)
            summary.append(keys | {"n_seeds": 1, "metrics": {
                name: {"mean": value, "n": int(value is not None)}
                for name, value in scores.items()}})
    manifest = {
        "distinct_configuration_count": 1,
        "cohorts": {"benchmark": {"configuration_count": 1},
                    "missing_receipts": {"configuration_count": 0}},
        "configurations": [{"configuration_id": "diagnostic-fixture", "config": config,
                            "origins": [{"cohort": "benchmark", "run_indices": list(range(10))}]}],
    }
    put_json(study / "inputs.json", {"configuration_manifest": manifest})
    put_json(study / "freeze.json", {"fixture": True})
    put_json(root / "results/benchmark.json", {"runs": rows, "summary": summary})
    put_json(root / "studies/missing_receipts/results/study.json", {
        "runs": [], "worlds": [], "summary": [], "paired_runs": [],
        "paired_summary": [], "retention_audit": []})
    put_json(root / "studies/review_remediation/chronology.json", {"worlds": []})
    monkeypatch.setattr(runner, "verify_freeze", lambda: 1)
    monkeypatch.setattr(runner, "verify_preservation", lambda: {"fixture": True})
    monkeypatch.setattr(runner, "trace_world", lambda config: trace)
    return root / "new-output"


def test_saved_output_verification_reuses_retained_trace_without_generation(
        mock_study, monkeypatch, diagnostic_trace):
    output = execution_fixture(mock_study, monkeypatch, diagnostic_trace)
    result = runner.execute(output)
    assert result["status"] == "passed"

    def forbidden(*args, **kwargs):
        raise AssertionError("Retained verification must not generate another World")

    monkeypatch.setattr(runner, "trace_world", forbidden)
    verified = runner.verify_outputs(output)
    assert verified["status"] == "passed"
    assert verified["writes_checked"] == 6
    assert verified["configurations_checked"] == 1
    assert verified["unavailable_configurations"] == 0


def test_failed_correction_preserves_legacy_evaluations_and_unavailable_denominators(
        mock_study, monkeypatch, diagnostic_trace):
    output = execution_fixture(mock_study, monkeypatch, diagnostic_trace)

    def fail_correction(trace):
        raise RetimingError("fixture unrepresentable interval")

    monkeypatch.setattr(runner, "retime_world", fail_correction)
    result = runner.execute(output)
    assert result["status"] == "unavailable_or_failed_results_retained"
    impact = runner.read(output / "impact.json.gz")
    assert impact["counts"]["benchmark_evaluations"] == 10
    assert impact["counts"]["unavailable_evaluations"] == 10
    for row in impact["per_world_impact"]:
        assert row["legacy"]["eligible_targets"] == 6
        assert row["corrected"] is None
        assert set(row["corrected_minus_legacy"].values()) == {None}
        assert row["status"] == "unavailable_due_to_correction_failure"
        assert row["unavailable_reasons"][0]["correction"]["message"] == (
            "fixture unrepresentable interval")
    for group in impact["per_scenario_impact"]:
        assert group["n_worlds"] == 1 and group["n_unavailable_worlds"] == 1
        assert group["metrics"]["absolute_error"]["corrected"]["mean"] is None
    assert runner.verify_outputs(output)["unavailable_configurations"] == 1


def test_failed_reproduction_retains_configuration_census_and_explicit_reason(
        mock_study, monkeypatch, diagnostic_trace):
    output = execution_fixture(mock_study, monkeypatch, diagnostic_trace)

    def fail_trace(config):
        raise ValueError("fixture baseline hash mismatch")

    monkeypatch.setattr(runner, "trace_world", fail_trace)
    result = runner.execute(output)
    assert result["status"] == "unavailable_or_failed_results_retained"
    assert result["configurations"] == 1
    chronology = runner.read(output / "chronology.json")
    all_unique = next(row for row in chronology["summary"] if row["cohort"] == "all_unique")
    assert all_unique["configurations"] == 1 and all_unique["expected_configurations"] == 1
    assert all_unique["audited_configurations"] == 0 and all_unique["unavailable_configurations"] == 1
    assert chronology["worlds"][0]["failure"]["message"] == "fixture baseline hash mismatch"
    worlds = runner.read(output / "worlds.json.gz")
    assert len(worlds) == 1 and worlds[0]["trace"] is None
    assert worlds[0]["failure"]["message"] == "fixture baseline hash mismatch"
    impact = runner.read(output / "impact.json.gz")
    assert impact["counts"]["benchmark_evaluations"] == 10
    assert impact["counts"]["unavailable_evaluations"] == 10
    assert not impact["counts"]["reproduction_all_matched"]
    assert len(impact["per_world_impact"]) == 10
    saved_rows = runner.read(runner.ROOT / "results/benchmark.json")["runs"]
    saved_by_key = {(row["regime"], row["method"]): row for row in saved_rows}
    for row in impact["per_world_impact"]:
        assert row["status"] == "unavailable_due_to_failed_reproduction"
        assert not row["legacy_available"]
        assert set(row["legacy"].values()) == {None}
        assert row["corrected"] is None
        assert set(row["corrected_minus_legacy"].values()) == {None}
        assert row["saved_eligible_targets"] == 6
        assert row["saved_legacy"] == saved_by_key[(row["regime"], row["method"])]
    assert len(impact["per_scenario_impact"]) == 10
    for group in impact["per_scenario_impact"]:
        assert group["n_worlds"] == 1 and group["n_unavailable_worlds"] == 1
        assert group["n_unreproduced_worlds"] == 1
        assert group["status"].startswith("unavailable_due_to_failed_reproduction")
        for metric in group["metrics"].values():
            for version in ("legacy", "corrected", "corrected_minus_legacy"):
                assert metric[version]["mean"] is None
                assert metric[version]["n_defined_worlds"] == 0
    claim_rows = runner.read(output / "claims.json")
    assert len(claim_rows) == 5
    for claim in claim_rows:
        assert claim["status"] == "unavailable_due_to_failed_reproduction_or_correction"
        assert claim["n_configurations"] == 1
        assert set(claim["values"]["legacy"].values()) == {None}
        assert set(claim["values"]["corrected"].values()) == {None}
    verified = runner.verify_outputs(output)
    assert verified["status"] == "unavailable_rows_retained"
    assert verified["writes_checked"] == 0 and verified["configurations_checked"] == 1
    assert verified["unavailable_configurations"] == 1


def test_retained_output_hash_change_is_rejected_before_recomputation(
        mock_study, monkeypatch, diagnostic_trace):
    output = execution_fixture(mock_study, monkeypatch, diagnostic_trace)
    runner.execute(output)
    (output / "claims.json").write_text("[]\n")

    def forbidden(*args, **kwargs):
        raise AssertionError("Retained integrity gate must precede investigator replay")

    monkeypatch.setattr(runner, "evaluate_origins", forbidden)
    with pytest.raises(ValueError, match="Saved result hash differs"):
        runner.verify_outputs(output)
