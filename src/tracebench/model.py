"""Immutable synthetic records; only ``World`` contains evaluation truth."""

import math
from dataclasses import dataclass
from numbers import Real

Edge = tuple[str, str]


@dataclass(frozen=True)
class SimulationConfig:
    seed: int = 0
    n_runs: int = 120
    writes_per_run: int = 3
    transmission_probability: float = 0.3
    shock_strength: float = 0.5
    n_task_families: int = 4
    request_probability: float = 0.8
    delivery_probability: float = 0.8
    context_probability: float = 0.8
    same_run_reuse_probability: float = 0.2
    handle_rotation_probability: float = 0.75
    witness_probability: float = 0.65
    witness_retention_probability: float = 0.7
    shared_witness_probability: float = 0.12
    temporal_window: float = 12.0

    def __post_init__(self) -> None:
        for name in ("seed", "n_runs", "writes_per_run", "n_task_families"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
            if name != "seed" and value < 1:
                raise ValueError(f"{name} must be positive")
        probability_names = (
            "transmission_probability", "shock_strength", "request_probability",
            "delivery_probability", "context_probability", "same_run_reuse_probability",
            "handle_rotation_probability", "witness_probability",
            "witness_retention_probability", "shared_witness_probability",
        )
        for name in probability_names:
            value = getattr(self, name)
            if (not isinstance(value, Real) or isinstance(value, bool)
                    or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError(f"{name} must be a finite number between 0 and 1")
        if (not isinstance(self.temporal_window, Real)
                or isinstance(self.temporal_window, bool)
                or not math.isfinite(self.temporal_window)
                or self.temporal_window <= 0):
            raise ValueError("temporal_window must be a finite positive number")


@dataclass(frozen=True)
class Write:
    event_id: str
    timestamp: float
    page: str
    handle: str
    concepts: tuple[str, ...]
    witness_tokens: tuple[str, ...]
    # None in writes-only observations. Ground truth always has stable identity.
    run_id: str | None


@dataclass(frozen=True)
class Request:
    request_id: str
    timestamp: float
    run_id: str
    page: str


@dataclass(frozen=True)
class Delivery:
    request_id: str
    timestamp: float
    run_id: str
    source_event_id: str


@dataclass(frozen=True)
class ContextEntry:
    request_id: str
    timestamp: float
    run_id: str
    source_event_id: str
    # This records entry into context, not whether the output used the chunk.
    concepts: tuple[str, ...]
    witness_tokens: tuple[str, ...]


@dataclass(frozen=True)
class World:
    config: SimulationConfig
    writes: tuple[Write, ...]
    requests: tuple[Request, ...]
    deliveries: tuple[Delivery, ...]
    contexts: tuple[ContextEntry, ...]
    truth_edges: frozenset[Edge]
    eligible_target_ids: frozenset[str]
