"""Nested telemetry projections with no access to source-use labels."""

from dataclasses import dataclass, replace
from enum import Enum

from .model import ContextEntry, Delivery, Request, World, Write


class Telemetry(str, Enum):
    WRITES = "writes"
    IDENTITY = "identity"
    REQUESTS = "requests"
    DELIVERY = "delivery"
    CONTEXT = "context"


@dataclass(frozen=True)
class Observation:
    regime: Telemetry
    writes: tuple[Write, ...]
    requests: tuple[Request, ...] = ()
    deliveries: tuple[Delivery, ...] = ()
    contexts: tuple[ContextEntry, ...] = ()
    temporal_window: float = 12.0


def observe(world: World, regime: Telemetry) -> Observation:
    """Reveal additional real telemetry, never hidden simulator configuration."""
    regime = Telemetry(regime)
    level = list(Telemetry).index(regime)
    writes = world.writes if level >= 1 else tuple(replace(w, run_id=None) for w in world.writes)
    return Observation(
        regime=regime, writes=writes,
        requests=world.requests if level >= 2 else (),
        deliveries=world.deliveries if level >= 3 else (),
        contexts=world.contexts if level >= 4 else (),
        temporal_window=world.config.temporal_window,
    )
