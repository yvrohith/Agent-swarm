"""One targeted, state-preserving repair of legacy receipt chronology.

This wrapper does not replay decisions or draw randomness. The independent
reference verifier must additionally check full-log availability at every write.
"""

import math
from dataclasses import dataclass, replace

from tracebench.model import World

from .trace import CapturedTrace


class RetimingError(ValueError):
    """An explicit failed correction, never a revised scientific result."""


@dataclass(frozen=True)
class ChainRetiming:
    request_id: str
    owner_write_id: str
    source_event_id: str
    recipient_run_id: str
    previous_recipient_write_id: str | None
    lower_bound: float
    owner_timestamp: float
    old_timestamps: tuple[float, float, float]
    new_timestamps: tuple[float, float, float]
    contradicted_write_ids: tuple[str, ...]


@dataclass(frozen=True)
class RetimingResult:
    world: World
    corrected_request_ids: tuple[str, ...]
    changes: tuple[ChainRetiming, ...]


def quarter_interval(source_time: float, owner_time: float,
                     previous_recipient_time: float | None) -> tuple[float, float, float]:
    """Use precisely the frozen quarter interpolation; reject collapsed floats."""
    if previous_recipient_time is not None and not math.isfinite(previous_recipient_time):
        raise RetimingError("No representable strict quarter interval for offending chain")
    lo = source_time if previous_recipient_time is None else max(
        source_time, previous_recipient_time)
    gap = owner_time - lo
    request_time = lo + gap / 4
    delivery_time = lo + gap / 2
    context_time = lo + 3 * gap / 4
    if (not all(math.isfinite(value) for value in (
            source_time, lo, owner_time, request_time, delivery_time, context_time))
            or not source_time <= lo < request_time < delivery_time < context_time < owner_time):
        raise RetimingError("No representable strict quarter interval for offending chain")
    return request_time, delivery_time, context_time


def retime_world(trace: CapturedTrace) -> RetimingResult:
    """Move only chains that create actual extra source availability in final logs.

    The trigger includes repeated receipts if their timestamps also make a source
    appear before it existed in captured decision state. Receipt-before-owner by
    itself does not trigger retiming. Missing or inconsistent stages fail closed.
    """
    world = trace.world
    writes = {write.event_id: write for write in world.writes}
    owners = {chain.request_id: chain for chain in trace.chains}
    requests = {item.request_id: item for item in world.requests}
    deliveries = {item.request_id: item for item in world.deliveries}
    if (len(writes) != len(world.writes) or len(owners) != len(trace.chains)
            or len(requests) != len(world.requests) or len(deliveries) != len(world.deliveries)
            or len({item.request_id for item in world.contexts}) != len(world.contexts)):
        raise RetimingError("Duplicate physical record or chain identity")
    previous_writes = {}
    last_write = {}
    for snapshot in trace.snapshots:
        previous_writes[snapshot.write_event_id] = last_write.get(snapshot.run_id)
        last_write[snapshot.run_id] = writes[snapshot.write_event_id]
    replacements = {}
    changes = []
    for context in world.contexts:
        contradicted = tuple(snapshot.write_event_id for snapshot in trace.snapshots
                             if snapshot.run_id == context.run_id
                             and context.timestamp < snapshot.timestamp
                             and context.source_event_id not in snapshot.available_source_ids)
        if not contradicted:
            continue
        chain = owners.get(context.request_id)
        request = requests.get(context.request_id)
        delivery = deliveries.get(context.request_id)
        if chain is None or request is None or delivery is None:
            raise RetimingError("Offending context lacks owning chain or required upstream stages")
        if (not chain.has_delivery or not chain.has_context
                or context.source_event_id != chain.source_event_id
                or context.source_event_id != delivery.source_event_id
                or len({context.run_id, request.run_id, delivery.run_id,
                        chain.recipient_run_id}) != 1):
            raise RetimingError("Offending context has inconsistent chain metadata")
        source = writes[chain.source_event_id]
        owner = writes[chain.owner_write_id]
        if owner.run_id != context.run_id:
            raise RetimingError("Offending context owner has a different recipient")
        previous = previous_writes[owner.event_id]
        new_times = quarter_interval(source.timestamp, owner.timestamp,
                                     None if previous is None else previous.timestamp)
        replacements[context.request_id] = new_times
        changes.append(ChainRetiming(
            context.request_id, owner.event_id, source.event_id, context.run_id,
            None if previous is None else previous.event_id,
            source.timestamp if previous is None else max(source.timestamp, previous.timestamp),
            owner.timestamp, (request.timestamp, delivery.timestamp, context.timestamp),
            new_times, contradicted,
        ))
    if not replacements:
        return RetimingResult(world, (), ())
    stage_records = {}
    for index, name in enumerate(("requests", "deliveries", "contexts")):
        stage_records[name] = tuple(sorted((
            replace(item, timestamp=replacements[item.request_id][index])
            if item.request_id in replacements else item
            for item in getattr(world, name)
        ), key=lambda item: item.timestamp))
    corrected = replace(world, **stage_records)
    return RetimingResult(corrected, tuple(sorted(replacements)), tuple(changes))
