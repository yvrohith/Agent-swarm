import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from tracebench import receipt_study
from tracebench.cli import main
from tracebench.receipt_study import evaluate_study, run_study, validate_config


def small_config():
    # Correctness fixtures are deliberately outside the frozen study's seed range.
    return {
        "study_id": "receipt-loss-test-fixture", "reviewed_baseline_commit": "test-only",
        "study_type": "follow-up stress test informed by review; not preregistered",
        "world_seeds": [71, 72], "n_runs": 8, "writes_per_run": 3,
        "transmission_probabilities": [0, 0.3], "shock_strengths": [0.9],
        "retentions": [1, 0.5, 0], "profiles": ["drop_delivery", "drop_context"],
        "methods": ["temporal", "witness"], "policies": ["conjunction", "evidence_aware"],
        "mask_seed_base": 900000, "bootstrap_samples": 100, "regime": "context",
        "policy_assumptions": "trusted retained synthetic receipts; declared channel completeness",
        "freeze": "test fixture, not the reported experiment",
    }


def test_world_generated_once_and_shared_observation_pairing(monkeypatch):
    worlds, observations = [], defaultdict(list)
    original_simulate, original_infer = receipt_study.simulate, receipt_study.infer

    def simulate_once(config):
        worlds.append(config)
        return original_simulate(config)

    def audit_infer(observation, method, policy):
        observations[id(observation)].append((observation, method, policy))
        return original_infer(observation, method, policy)

    monkeypatch.setattr(receipt_study, "simulate", simulate_once)
    monkeypatch.setattr(receipt_study, "infer", audit_infer)
    result = evaluate_study(small_config())
    assert len(worlds) == 4
    assert len(observations) == 24
    assert all(len(calls) == 4 for calls in observations.values())
    assert len(result["runs"]) == 96
    assert len(result["paired_runs"]) == 48
    assert len(result["summary"]) == 48
    assert all(s["n_seeds"] == 2 for s in result["summary"])
    assert len(result["paired_summary"]) == 24
    for row in result["runs"]:
        assert row["eligible_targets"] == 24
        assert row["mask_seed"] == 900000 + row["seed"]
        assert row["signed_error"] == pytest.approx(
            (row["false_positive_targets"] - row["false_negative_targets"]) / 24
        )
        if row["transmission_probability"] == 0:
            assert row["recall"] is None
        if row["profile"] == "drop_context" and row["retention"] == 0:
            assert row["predicted_edges"] == 0
    for row in result["retention_audit"]:
        assert row["request_records_retained"] == row["request_records_original"]
        affected = "delivery" if row["profile"] == "drop_delivery" else "context"
        other = "context" if affected == "delivery" else "delivery"
        assert row[f"{other}_records_retained"] == row[f"{other}_records_original"]
        if row["retention"] == 0:
            assert row[f"{affected}_records_retained"] == 0


def test_fresh_study_outputs_are_reproducible_and_protected(tmp_path):
    config_file = tmp_path / "configuration.json"
    config_file.write_text(json.dumps(small_config()))
    first, second = tmp_path / "one", tmp_path / "two"
    run_study(config_file, first)
    main(["receipt-study", "--config", str(config_file), "--output", str(second)])
    assert (first / "study.json").read_bytes() == (second / "study.json").read_bytes()
    data = json.loads((first / "study.json").read_text())
    manifest = json.loads((first / "manifest.json").read_text())
    assert data["metadata"]["config_sha256"] == manifest["config_sha256"]
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
    assert (first / "recall_retention.png").stat().st_size > 1000
    with pytest.raises(ValueError, match="empty"):
        run_study(config_file, first)
    baseline = Path(receipt_study.__file__).resolve().parents[2] / "results"
    for forbidden in (baseline, baseline / "followup"):
        with pytest.raises(ValueError, match="baseline"):
            run_study(config_file, forbidden)
    assert "not a preregistered discovery" in (first / "REPORT.md").read_text()


@pytest.mark.parametrize("key,value", [
    ("world_seeds", [200, 200]), ("retentions", [1, float("nan")]),
    ("regime", "delivery"), ("profiles", ["drop_context"]),
    ("policies", ["conjunction", "conjunction"]), ("n_runs", 0),
    ("bootstrap_samples", 1), ("mask_seed_base", True),
    ("shock_strengths", [0.5, 0.9]),
])
def test_invalid_study_settings_rejected(key, value):
    config = small_config() | {key: value}
    with pytest.raises(ValueError):
        validate_config(config)


def test_logging_study_cannot_override_world_failure_probabilities():
    with pytest.raises(ValueError, match="exactly"):
        validate_config(small_config() | {"delivery_probability": 0})
