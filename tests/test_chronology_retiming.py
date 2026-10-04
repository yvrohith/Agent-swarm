"""Development-only checks: the saved six-write diagnostic and direct fixtures."""

import json
import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from studies.chronology_consistency.retime import (
    RetimingError,
    quarter_interval,
    retime_world,
)
from studies.chronology_consistency.trace import (
    CapturedTrace,
    ChainInstallation,
    DecisionSnapshot,
    trace_world,
    world_sha256,
)
from tracebench.model import ContextEntry, Delivery, Request, SimulationConfig, World, Write
from tracebench.simulate import simulate

ROOT = Path(__file__).resolve().parents[1]


def diagnostic():
    saved = json.loads((ROOT / "studies/review_remediation/chronology.json").read_text())
    row = next(item for item in saved["worlds"]
               if item["published_cohort"] == "minimal_diagnostic")
    return row, trace_world(SimulationConfig(**row["config"]))


def snapshot(write, index, available=(), requests=(), contexts=()):
    return DecisionSnapshot(write.event_id, write.run_id, write.timestamp, index,
                            available, requests, contexts, "fixture", None, "fixture")


def repeated_fixture():
    source = Write("source", 0.0, "task", "source-handle", ("concept",), (), "source-run")
    writes = (source,) + tuple(
        Write(f"write-{index}", timestamp, "task", "recipient-handle", (), (), "recipient")
        for index, timestamp in enumerate((0.75, 2.0, 4.0, 6.0)))
    first = ContextEntry("first", 1.0, "recipient", "source", source.concepts, ())
    repeat = ContextEntry("repeat", 0.5, "recipient", "source", source.concepts, ())
    world = World(
        SimulationConfig(n_runs=2, writes_per_run=2), writes,
        (Request("repeat", 0.1, "recipient", "task"),
         Request("first", 0.8, "recipient", "task")),
        (Delivery("repeat", 0.2, "recipient", "source"),
         Delivery("first", 0.9, "recipient", "source")),
        (repeat, first), frozenset(), frozenset(write.event_id for write in writes),
    )
    states = tuple(snapshot(write, index, ("source",) if index >= 2 else ())
                   for index, write in enumerate(writes))
    chains = (
        ChainInstallation("first", "write-1", 2, "source", "recipient", True, True, True),
        ChainInstallation("repeat", "write-3", 4, "source", "recipient", True, True, False),
    )
    return CapturedTrace(world, states, chains, True, {})


def test_saved_six_write_counterexample_and_complete_world_rng_identity():
    saved, trace = diagnostic()
    assert world_sha256(trace.world) == saved["world_sha256"]
    assert trace.world == simulate(SimulationConfig(**saved["config"]))
    assert trace.instrumented_equals_uninstrumented
    assert len(trace.snapshots) == 6
    assert trace.rng_evidence["profile_only_reference"] == trace.rng_evidence["detailed_trace"]
    counts = trace.rng_evidence["detailed_trace"]["primitive_rng_call_counts"]
    assert counts["random"] > 0 and counts["getrandbits"] > 0
    earlier, owner = trace.snapshots[3:5]
    assert earlier.write_event_id == "e000003" and earlier.available_source_ids == ()
    assert owner.available_source_ids == ("e000002",)
    assert owner.context_request_ids_created == ("q000001",)
    assert earlier.context_request_ids_created == ()
    # The complete log includes a receipt appended in a later iteration.
    receipt = trace.world.contexts[0]
    assert receipt.timestamp < earlier.timestamp < owner.timestamp
    chain = next(item for item in trace.chains if item.request_id == receipt.request_id)
    assert chain.owner_write_id == owner.write_event_id and chain.first_installation


def test_repair_moves_only_offending_chain_and_preserves_state_truth_and_values():
    _, trace = diagnostic()
    repaired = retime_world(trace)
    assert repaired.corrected_request_ids == ("q000001",)
    assert repaired.world.writes == trace.world.writes
    assert repaired.world.truth_edges == trace.world.truth_edges
    assert repaired.world.eligible_target_ids == trace.world.eligible_target_ids
    assert repaired.world.config == trace.world.config
    for name in ("requests", "deliveries", "contexts"):
        old = {item.request_id: item for item in getattr(trace.world, name)}
        new = {item.request_id: item for item in getattr(repaired.world, name)}
        assert old.keys() == new.keys()
        for key in old:
            assert replace(old[key], timestamp=new[key].timestamp) == new[key]
            if key != "q000001":
                assert old[key] == new[key]
    change = repaired.changes[0]
    assert change.contradicted_write_ids == ("e000003",)
    assert change.previous_recipient_write_id == "e000003"
    assert change.lower_bound < change.new_timestamps[0]
    assert change.new_timestamps[0] < change.new_timestamps[1] < change.new_timestamps[2]
    assert change.new_timestamps[2] < change.owner_timestamp


def test_repeated_receipt_only_retimes_if_it_causes_actual_earlier_absence():
    trace = repeated_fixture()
    result = retime_world(trace)
    assert result.corrected_request_ids == ("repeat",)
    assert result.changes[0].contradicted_write_ids == ("write-0",)
    assert result.changes[0].new_timestamps == (4.5, 5.0, 5.5)
    assert next(item for item in result.world.contexts if item.request_id == "first") == (
        next(item for item in trace.world.contexts if item.request_id == "first"))
    # Duplicates after first installation are repeated evidence, not new sources.
    safe_repeat = replace(trace.world.contexts[0], timestamp=3.0)
    safe_world = replace(trace.world, contexts=(trace.world.contexts[1], safe_repeat))
    untouched = retime_world(replace(trace, world=safe_world))
    assert untouched.world is safe_world and untouched.corrected_request_ids == ()


def test_no_context_fixture_world_is_identical_and_selection_trace_complete():
    config = SimulationConfig(n_runs=1, writes_per_run=3, n_task_families=1)
    trace = trace_world(config)
    assert not trace.world.contexts and not trace.chains
    assert len(trace.snapshots) == 3
    assert retime_world(trace).world is trace.world


@pytest.mark.parametrize("source,owner,previous", [
    (1.0, math.nextafter(1.0, math.inf), None),
    (0.0, 1.0, 1.0),
    (2.0, 1.0, None),
    (0.0, math.inf, None),
    (math.nan, 1.0, None),
    (0.0, 1.0, math.nan),
])
def test_strict_interpolation_explicitly_rejects_unrepresentable_intervals(source, owner, previous):
    with pytest.raises(RetimingError, match="representable strict quarter interval"):
        quarter_interval(source, owner, previous)


def test_strict_interpolation_uses_source_or_previous_write_without_epsilon():
    assert quarter_interval(2.0, 10.0, None) == (4.0, 6.0, 8.0)
    assert quarter_interval(2.0, 10.0, 6.0) == (7.0, 8.0, 9.0)
    assert quarter_interval(6.0, 10.0, 2.0) == (7.0, 8.0, 9.0)


def test_context_chain_missing_upstream_stage_fails_without_creation():
    _, trace = diagnostic()
    malformed = replace(trace.world, deliveries=())
    with pytest.raises(RetimingError, match="upstream stages"):
        retime_world(replace(trace, world=malformed))


def test_refuses_to_replace_existing_trace_hook():
    previous = sys.gettrace()
    try:
        sys.settrace(lambda frame, event, arg: None)
        with pytest.raises(RuntimeError, match="existing trace or profile"):
            trace_world(SimulationConfig(n_runs=1, writes_per_run=1))
    finally:
        sys.settrace(previous)
