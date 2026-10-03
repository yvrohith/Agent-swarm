"""Behavioral checks for the simulator's evidence and truth boundaries."""

from dataclasses import asdict, fields, replace

import pytest

from tracebench.estimators import METHODS, estimate
from tracebench.model import SimulationConfig
from tracebench.observe import Observation, Telemetry, observe
from tracebench.simulate import observational_equivalence_pair, simulate


def rich_config(**overrides):
    values = dict(
        seed=31, n_runs=30, writes_per_run=4, n_task_families=1,
        request_probability=1, delivery_probability=1, context_probability=1,
        same_run_reuse_probability=0, witness_probability=1,
        witness_retention_probability=1, handle_rotation_probability=1,
        shared_witness_probability=0,
    )
    values.update(overrides)
    return SimulationConfig(**values)


@pytest.mark.parametrize("name,value", [
    ("n_runs", 0), ("n_runs", 1.5), ("writes_per_run", -1),
    ("n_task_families", 0), ("seed", True), ("seed", "1"),
    ("transmission_probability", 1.1), ("transmission_probability", -0.1),
    ("shock_strength", float("nan")), ("request_probability", float("inf")),
    ("delivery_probability", True), ("context_probability", "0.5"),
    ("temporal_window", 0), ("temporal_window", float("inf")),
])
def test_invalid_configs_rejected(name, value):
    with pytest.raises(ValueError, match=name):
        SimulationConfig(**{name: value})


def test_simulation_reproducible_and_seed_sensitive():
    config = SimulationConfig(seed=13, n_runs=10)
    assert simulate(config) == simulate(config)
    assert simulate(config).writes != simulate(replace(config, seed=14)).writes


def test_every_write_including_first_is_eligible():
    world = simulate(SimulationConfig(n_runs=7, writes_per_run=3))
    assert len(world.writes) == 21
    assert world.eligible_target_ids == frozenset(w.event_id for w in world.writes)
    assert world.writes[0].event_id in world.eligible_target_ids
    assert not any(target == world.writes[0].event_id for _, target in world.truth_edges)


def test_true_edges_require_preceding_cross_run_source_in_context():
    world = simulate(rich_config(transmission_probability=1))
    assert world.truth_edges
    writes = {w.event_id: w for w in world.writes}
    targets = []
    for source_id, target_id in world.truth_edges:
        source, target = writes[source_id], writes[target_id]
        assert source.timestamp < target.timestamp
        assert source.run_id != target.run_id
        assert source.concepts == target.concepts
        assert any(entry.source_event_id == source_id
                   and entry.run_id == target.run_id
                   and entry.timestamp < target.timestamp for entry in world.contexts)
        targets.append(target_id)
    assert len(targets) == len(set(targets))


def test_zero_transmission_has_rich_unused_exposure():
    world = simulate(rich_config(transmission_probability=0))
    assert not world.truth_edges
    assert world.requests and world.deliveries and world.contexts
    # The temporal investigator can still accuse exposed but unused sources.
    assert estimate(observe(world, Telemetry.CONTEXT), "temporal")


@pytest.mark.parametrize("missing_stage", ["request_probability", "delivery_probability", "context_probability"])
def test_no_cross_run_source_use_without_required_exposure(missing_stage):
    world = simulate(rich_config(transmission_probability=1, **{missing_stage: 0}))
    assert not world.truth_edges


def test_successful_delivery_does_not_require_context_insertion():
    world = simulate(rich_config(context_probability=0))
    assert world.deliveries
    assert not world.contexts
    assert not world.truth_edges


def test_single_run_replays_are_not_cross_run_truth():
    world = simulate(rich_config(n_runs=1, writes_per_run=6, same_run_reuse_probability=1))
    assert not world.truth_edges
    assert estimate(observe(world, Telemetry.WRITES), "witness")
    assert not estimate(observe(world, Telemetry.IDENTITY), "witness")


def test_projections_are_nested_and_hide_truth_and_configuration():
    world = simulate(rich_config())
    levels = [observe(world, regime) for regime in Telemetry]
    assert all(w.run_id is None for w in levels[0].writes)
    assert all(w.run_id is not None for level in levels[1:] for w in level.writes)
    assert all(level.writes == world.writes for level in levels[1:])
    assert not levels[0].requests and not levels[1].requests
    assert levels[2].requests == levels[3].requests == levels[4].requests == world.requests
    assert not levels[2].deliveries
    assert levels[3].deliveries == levels[4].deliveries == world.deliveries
    assert not levels[3].contexts
    assert levels[4].contexts == world.contexts
    for level in levels:
        serialized = asdict(level)
        assert not {"truth_edges", "eligible_target_ids", "config", "seed"} & serialized.keys()
        assert not any("origin" in field.name or "selected" in field.name for field in fields(level))


@pytest.mark.parametrize("method", METHODS)
def test_filters_preserve_nested_candidate_sets(method):
    world = simulate(rich_config())
    predictions = [estimate(observe(world, regime), method) for regime in Telemetry]
    for before, after in zip(predictions, predictions[1:]):
        assert after <= before
    # Every prediction is a public event pair; truth is fixed, not regenerated.
    ids = world.eligible_target_ids
    assert all(source in ids and target in ids for edges in predictions for source, target in edges)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("shock_strength", [0, 0.9])
def test_complete_telemetry_filters_preserve_true_positive_edges(method, shock_strength):
    """Missing logs are not modeled: added evidence cannot discard a true edge.

    Recall therefore stays constant across regimes in this baseline. Any change
    would indicate inconsistent simulator receipts or incorrect candidate gates.
    """
    world = simulate(rich_config(transmission_probability=0.5,
                                 shock_strength=shock_strength))
    assert world.truth_edges
    detected = [estimate(observe(world, regime), method) & world.truth_edges
                for regime in Telemetry]
    assert detected[0], "The invariant must exercise at least one recovered true edge"
    assert all(edges == detected[0] for edges in detected[1:])


def test_witness_can_miss_actual_source_use():
    world = simulate(rich_config(transmission_probability=1, witness_retention_probability=0))
    assert world.truth_edges
    assert not estimate(observe(world, Telemetry.CONTEXT), "witness")


def test_common_scaffold_witnesses_can_falsely_suggest_transmission():
    world = simulate(rich_config(transmission_probability=0, witness_probability=0,
                                 shared_witness_probability=1))
    assert not world.truth_edges
    assert estimate(observe(world, Telemetry.CONTEXT), "witness")


def test_equivalence_survives_context_and_exposes_ambiguous_attribution():
    independent, source_use = observational_equivalence_pair()
    assert not independent.truth_edges
    assert source_use.truth_edges == frozenset({("e000000", "e000001")})
    assert independent.eligible_target_ids == source_use.eligible_target_ids
    for regime in Telemetry:
        left, right = observe(independent, regime), observe(source_use, regime)
        assert left == right
        for method in METHODS:
            assert estimate(left, method) == estimate(right, method) == source_use.truth_edges


def test_estimators_reject_truth_objects_and_unknown_methods():
    world = simulate(SimulationConfig(n_runs=1))
    with pytest.raises(TypeError, match="Observation"):
        estimate(world, "witness")
    with pytest.raises(ValueError, match="Unknown method"):
        estimate(observe(world, Telemetry.WRITES), "hawkes")
    with pytest.raises(ValueError):
        observe(world, "omniscient")


def test_same_time_writes_do_not_suggest_a_precedence_edge():
    world, _ = observational_equivalence_pair()
    first, second = world.writes
    observation = Observation(Telemetry.WRITES,
                              (replace(first, run_id=None),
                               replace(second, timestamp=first.timestamp, run_id=None)))
    assert not estimate(observation, "temporal")
    assert not estimate(observation, "witness")
