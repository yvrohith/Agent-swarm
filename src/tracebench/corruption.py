"""Erase observed receipts after simulation, without consulting source-use truth.

The two logging profiles describe record loss, not event non-occurrence. Their
coarse completeness declarations apply to entire channels. Investigators do not
receive a per-record loss mask, the original counts, or the masking seed.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from numbers import Real

from .model import ContextEntry, Delivery
from .observe import Observation, Telemetry

PROFILES = ("drop_delivery", "drop_context")


@dataclass(frozen=True)
class LoggingCompleteness:
    """Declared channel completeness and trusted receipt provenance.

    Authentication is an assumption of this loss-only synthetic study, not a
    cryptographic check implemented here. A False completeness flag means that
    absence cannot by itself establish non-occurrence, even when a particular
    sample happened to lose no records.
    """

    requests: bool
    deliveries: bool
    contexts: bool
    receipts_authenticated: bool = True

    def __post_init__(self) -> None:
        for name in ("requests", "deliveries", "contexts", "receipts_authenticated"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")


def _require_context_observation(observation: Observation) -> None:
    if not isinstance(observation, Observation):
        raise TypeError("requires an Observation, not simulator truth")
    if observation.regime != Telemetry.CONTEXT:
        raise ValueError("missing-receipt policies require a CONTEXT observation")
    if any(not write.run_id for write in observation.writes):
        raise ValueError("missing-receipt policies require stable run identities")


@dataclass(frozen=True)
class ReceiptObservation:
    """The investigator's entire input: surviving records and coarse metadata."""

    observation: Observation
    completeness: LoggingCompleteness

    def __post_init__(self) -> None:
        _require_context_observation(self.observation)
        if not isinstance(self.completeness, LoggingCompleteness):
            raise TypeError("completeness must be LoggingCompleteness")


def _retained(record: Delivery | ContextEntry, channel: str,
              retention: float, mask_seed: int) -> bool:
    # Public record identity only; no truth, hidden selection label, or retention
    # in the hash. Reusing a mask seed therefore produces nested retention sets.
    key = [mask_seed, channel, record.request_id, record.timestamp,
           record.run_id, record.source_event_id]
    digest = hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).digest()
    rank = int.from_bytes(digest, "big") / (1 << 256)
    return rank < retention


def corrupt(observation: Observation, profile: str, retention: float,
            mask_seed: int) -> ReceiptObservation:
    """Mask one observable receipt channel, preserving the fixed world's writes.

    The input contract is a complete authentic CONTEXT projection. This function
    cannot establish that contract by inspecting absence; do not repeatedly mask
    its output as though it were a fresh complete projection.

    Unaffected tuples are reused unchanged. ``retention`` is a nominal independent
    per-record probability; realized fractions must be measured externally for
    audit and never passed to the investigator as per-record loss information.
    """
    _require_context_observation(observation)
    if profile not in PROFILES:
        raise ValueError(f"Unknown logging profile {profile!r}; choose from {PROFILES}")
    if (not isinstance(retention, Real) or isinstance(retention, bool)
            or not math.isfinite(retention) or not 0 <= retention <= 1):
        raise ValueError("retention must be a finite number between 0 and 1")
    if not isinstance(mask_seed, int) or isinstance(mask_seed, bool):
        raise ValueError("mask_seed must be an integer")

    channel = "deliveries" if profile == "drop_delivery" else "contexts"
    original = getattr(observation, channel)
    kept = original if retention == 1 else tuple(
        record for record in original if _retained(record, channel, retention, mask_seed)
    )
    completeness = LoggingCompleteness(
        requests=True,
        deliveries=profile != "drop_delivery" or retention == 1,
        contexts=profile != "drop_context" or retention == 1,
    )
    return ReceiptObservation(replace(observation, **{channel: kept}), completeness)
