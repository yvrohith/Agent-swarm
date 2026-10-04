"""Read-only evidence from the untouched legacy simulation.

Line events capture the state after installation and before selection. A passive
profile counts calls to the seeded RNG's primitive drawing methods. The detailed
trace is compared with both an ordinary call with no hooks and a profile-only
reference call. No callback assigns to simulator locals or calls a drawing method.
"""

import hashlib
import inspect
import json
import random
import sys
from dataclasses import asdict, dataclass

from tracebench.model import SimulationConfig, World
from tracebench.simulate import simulate


@dataclass(frozen=True)
class DecisionSnapshot:
    write_event_id: str
    run_id: str
    timestamp: float
    generation_index: int
    available_source_ids: tuple[str, ...]
    request_ids_created: tuple[str, ...]
    context_request_ids_created: tuple[str, ...]
    rng_state_before_selection_sha256: str
    selected_source_id: str | None
    rng_state_after_selection_sha256: str


@dataclass(frozen=True)
class ChainInstallation:
    request_id: str
    owner_write_id: str
    generation_index: int
    source_event_id: str
    recipient_run_id: str
    has_delivery: bool
    has_context: bool
    first_installation: bool | None


@dataclass(frozen=True)
class CapturedTrace:
    world: World
    snapshots: tuple[DecisionSnapshot, ...]
    chains: tuple[ChainInstallation, ...]
    instrumented_equals_uninstrumented: bool
    rng_evidence: dict


def canonical_world(world: World) -> str:
    """Match the historical chronology audit's complete World serialization."""
    value = asdict(world)
    value["truth_edges"] = sorted(value["truth_edges"])
    value["eligible_target_ids"] = sorted(value["eligible_target_ids"])
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def world_sha256(world: World) -> str:
    return hashlib.sha256(canonical_world(world).encode()).hexdigest()


def _rng_sha256(rng: random.Random) -> str:
    return hashlib.sha256(repr(rng.getstate()).encode()).hexdigest()


def _selection_lines() -> tuple[int, int]:
    lines, first_line = inspect.getsourcelines(simulate)
    locations = []
    for target in ("selected = None", "witness_tokens = []"):
        matches = [first_line + offset for offset, line in enumerate(lines)
                   if line.strip() == target]
        if len(matches) != 1:
            raise ValueError(f"Legacy source changed: expected unique {target!r}")
        locations.append(matches[0])
    return tuple(locations)


def _instrumented(config: SimulationConfig, detailed: bool):
    selection_line, selected_line = _selection_lines()
    snapshots = []
    chains = []
    installed = set()
    counts = {"random": 0, "getrandbits": 0}
    result_evidence = {}
    request_count = 0
    delivery_count = 0
    context_count = 0
    pending = None
    simulator_rng = None

    def profile(frame, event, arg):
        nonlocal simulator_rng
        if frame.f_back is not None and frame.f_back.f_code is simulate.__code__:
            simulator_rng = frame.f_back.f_locals.get("rng", simulator_rng)
        if frame.f_code is simulate.__code__:
            simulator_rng = frame.f_locals.get("rng", simulator_rng)
            if event == "return":
                result_evidence["final_rng_state_sha256"] = _rng_sha256(simulator_rng)
        if event == "c_call" and getattr(arg, "__self__", None) is simulator_rng:
            name = getattr(arg, "__name__", "")
            if name in counts:
                counts[name] += 1

    def trace(frame, event, arg):
        nonlocal request_count, delivery_count, context_count, pending
        if frame.f_code is not simulate.__code__:
            return None
        if event != "line":
            return trace
        local = frame.f_locals
        if frame.f_lineno == selection_line:
            if pending is not None:
                raise AssertionError("Selection completion was not captured")
            run_id = local["run_id"]
            new_requests = local["requests"][request_count:]
            new_deliveries = local["deliveries"][delivery_count:]
            new_contexts = local["contexts"][context_count:]
            if len(new_requests) > 1 or len(new_deliveries) > 1 or len(new_contexts) > 1:
                raise AssertionError("Legacy one-chain-per-write premise changed")
            request_ids = {request.request_id for request in new_requests}
            if any(record.request_id not in request_ids
                   for record in (*new_deliveries, *new_contexts)):
                raise AssertionError("Receipt was appended outside its owning iteration")
            for request in new_requests:
                source = local["source"]
                delivery = next((item for item in new_deliveries
                                 if item.request_id == request.request_id), None)
                context = next((item for item in new_contexts
                                if item.request_id == request.request_id), None)
                pair = (run_id, source.event_id)
                first = None if context is None else pair not in installed
                if context is not None:
                    if delivery is None or context.source_event_id != source.event_id:
                        raise AssertionError("Context chain lacks matching delivery/source")
                    installed.add(pair)
                chains.append(ChainInstallation(
                    request.request_id, local["event_id"], local["index"], source.event_id,
                    run_id, delivery is not None, context is not None, first,
                ))
            pending = {
                "write_event_id": local["event_id"], "run_id": run_id,
                "timestamp": local["timestamp"], "generation_index": local["index"],
                "available_source_ids": tuple(sorted(local["available_context"].get(run_id, {}))),
                "request_ids_created": tuple(item.request_id for item in new_requests),
                "context_request_ids_created": tuple(item.request_id for item in new_contexts),
                "rng_state_before_selection_sha256": _rng_sha256(local["rng"]),
            }
            request_count = len(local["requests"])
            delivery_count = len(local["deliveries"])
            context_count = len(local["contexts"])
        elif frame.f_lineno == selected_line:
            if pending is None or pending["write_event_id"] != local["event_id"]:
                raise AssertionError("Selection entry was not captured")
            selected = local["selected"]
            snapshots.append(DecisionSnapshot(
                **pending, selected_source_id=None if selected is None else selected.event_id,
                rng_state_after_selection_sha256=_rng_sha256(local["rng"]),
            ))
            pending = None
        return trace

    if sys.gettrace() is not None or sys.getprofile() is not None:
        raise RuntimeError("Refusing to replace an existing trace or profile hook")
    try:
        sys.setprofile(profile)
        if detailed:
            sys.settrace(trace)
        world = simulate(config)
    finally:
        if detailed:
            sys.settrace(None)
        sys.setprofile(None)
    result_evidence["primitive_rng_call_counts"] = dict(counts)
    if detailed:
        if pending is not None or len(snapshots) != len(world.writes):
            raise AssertionError("Incomplete write trace")
        if {chain.request_id for chain in chains} != {item.request_id for item in world.requests}:
            raise AssertionError("Incomplete chain ownership trace")
        for write, snapshot in zip(world.writes, snapshots, strict=True):
            if (write.event_id, write.timestamp, write.run_id) != (
                    snapshot.write_event_id, snapshot.timestamp, snapshot.run_id):
                raise AssertionError("Trace/write identity mismatch")
        selected_edges = frozenset(
            (snapshot.selected_source_id, snapshot.write_event_id)
            for snapshot in snapshots
            if snapshot.selected_source_id in snapshot.available_source_ids
        )
        if selected_edges != world.truth_edges:
            raise AssertionError("Captured cross-run selections differ from truth edges")
    return world, tuple(snapshots), tuple(chains), result_evidence


def trace_world(config: SimulationConfig) -> CapturedTrace:
    """Return decision/installation evidence; fail on any observed interference.

    The first World is generated with no hooks. A separate profile-only replay
    supplies the primitive RNG-call and final-state reference, because ordinary
    returned Worlds do not expose their local RNG. The third replay adds line
    snapshots. All three outputs must compare exactly, including all randomness.
    """
    if sys.gettrace() is not None or sys.getprofile() is not None:
        raise RuntimeError("Refusing to replace an existing trace or profile hook")
    ordinary = simulate(config)
    reference, _, _, reference_rng = _instrumented(config, detailed=False)
    traced, snapshots, chains, traced_rng = _instrumented(config, detailed=True)
    if traced != ordinary or reference != ordinary:
        raise AssertionError("Instrumentation changed complete World outputs")
    if traced_rng != reference_rng:
        raise AssertionError("Line instrumentation changed RNG state or primitive draw counts")
    return CapturedTrace(
        traced, snapshots, chains, True,
        {"profile_only_reference": reference_rng, "detailed_trace": traced_rng,
         "final_rng_state_and_primitive_calls_match": True,
         "ordinary_world_has_no_hooks": True},
    )
