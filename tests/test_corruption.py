"""Receipt erasure changes observation coverage, never a generated world."""

from dataclasses import asdict, fields, replace

import pytest

from tracebench.corruption import PROFILES, LoggingCompleteness, ReceiptObservation, corrupt
from tracebench.model import SimulationConfig
from tracebench.observe import Observation, Telemetry, observe
from tracebench.simulate import simulate


@pytest.fixture
def world():
    return simulate(SimulationConfig(seed=43, n_runs=30, writes_per_run=3,
                                     shock_strength=0.9))


@pytest.mark.parametrize("profile", PROFILES)
def test_nested_masks_preserve_fixed_world_and_unmasked_channels(world, profile):
    original_world = asdict(world)
    observation = observe(world, Telemetry.CONTEXT)
    channel = "deliveries" if profile == "drop_delivery" else "contexts"
    unmasked = "contexts" if profile == "drop_delivery" else "deliveries"
    assert getattr(observation, channel), "Exercise nonempty receipt records"
    observations = [corrupt(observation, profile, level, 4102)
                    for level in (0, 0.5, 0.9, 1)]
    kept_sets = [set(getattr(result.observation, channel)) for result in observations]
    assert not kept_sets[0]
    assert kept_sets[-1] == set(getattr(observation, channel))
    for previous, following in zip(kept_sets, kept_sets[1:]):
        assert previous <= following
    for result in observations:
        assert result.observation.writes is observation.writes
        assert result.observation.requests is observation.requests
        assert getattr(result.observation, unmasked) is getattr(observation, unmasked)
        assert result.observation.temporal_window == observation.temporal_window
    assert asdict(world) == original_world
    assert world.truth_edges
    assert world.eligible_target_ids == frozenset(w.event_id for w in observation.writes)


@pytest.mark.parametrize("profile", PROFILES)
def test_masks_are_seed_reproducible_and_seed_sensitive(world, profile):
    observation = observe(world, Telemetry.CONTEXT)
    assert corrupt(observation, profile, 0.5, 821) == corrupt(observation, profile, 0.5, 821)
    assert corrupt(observation, profile, 0.5, 821) != corrupt(observation, profile, 0.5, 822)


@pytest.mark.parametrize("profile", PROFILES)
def test_completeness_is_declared_not_realized_and_no_loss_labels_leak(world, profile):
    empty = replace(observe(world, Telemetry.CONTEXT), deliveries=(), contexts=())
    channel = "deliveries" if profile == "drop_delivery" else "contexts"
    incomplete = corrupt(empty, profile, 0.9, 6)
    complete = corrupt(empty, profile, 1, 6)
    assert incomplete.observation == complete.observation
    assert getattr(incomplete.completeness, channel) is False
    assert complete.completeness == LoggingCompleteness(True, True, True)
    assert {field.name for field in fields(incomplete)} == {"observation", "completeness"}
    assert {field.name for field in fields(incomplete.completeness)} == {
        "requests", "deliveries", "contexts", "receipts_authenticated",
    }
    assert set(asdict(incomplete)["observation"]) == {
        "regime", "writes", "requests", "deliveries", "contexts", "temporal_window",
    }


@pytest.mark.parametrize("retention", [-0.1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_invalid_retention_rejected(world, retention):
    with pytest.raises(ValueError, match="retention"):
        corrupt(observe(world, Telemetry.CONTEXT), "drop_context", retention, 1)


@pytest.mark.parametrize("mask_seed", [True, 1.2, "seed"])
def test_invalid_mask_seed_rejected(world, mask_seed):
    with pytest.raises(ValueError, match="mask_seed"):
        corrupt(observe(world, Telemetry.CONTEXT), "drop_context", 0.5, mask_seed)


def test_corruption_rejects_truth_wrong_regime_missing_identity_and_unknown_profile(world):
    with pytest.raises(TypeError, match="Observation"):
        corrupt(world, "drop_context", 0.5, 1)
    with pytest.raises(ValueError, match="CONTEXT"):
        corrupt(observe(world, Telemetry.DELIVERY), "drop_context", 0.5, 1)
    missing_identity = Observation(Telemetry.CONTEXT,
                                   tuple(replace(w, run_id=None) for w in world.writes))
    with pytest.raises(ValueError, match="identities"):
        corrupt(missing_identity, "drop_context", 0.5, 1)
    with pytest.raises(ValueError, match="profile"):
        corrupt(observe(world, Telemetry.CONTEXT), "invented", 0.5, 1)
    with pytest.raises(TypeError, match="LoggingCompleteness"):
        ReceiptObservation(observe(world, Telemetry.CONTEXT), {"contexts": False})
    with pytest.raises(ValueError, match="boolean"):
        LoggingCompleteness(True, True, "unknown")
