"""Transparent candidate-edge baselines, not causal identification procedures.

Temporal uses same-page preceding writes inside a fixed window. Witness uses
exact witness-token overlap. Successive telemetry levels filter their candidate
sets; therefore their prediction counts cannot increase. With the simulator's
complete, correct logging, true candidates survive: recall is constant and
defined precision cannot decrease. Absolute target-rate error can worsen.
Neither estimates a Hawkes process.
"""

from collections import defaultdict

from .model import Edge, Write
from .observe import Observation, Telemetry

METHODS = ("temporal", "witness")


def estimate(observation: Observation, method: str) -> frozenset[Edge]:
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}; choose from {METHODS}")
    if not isinstance(observation, Observation):
        raise TypeError("estimate requires an Observation, not simulator truth")
    level = list(Telemetry).index(observation.regime)
    requests_by_run_page = defaultdict(list)
    for request in observation.requests:
        requests_by_run_page[(request.run_id, request.page)].append(request.timestamp)
    deliveries_by_run_source = defaultdict(list)
    for receipt in observation.deliveries:
        deliveries_by_run_source[(receipt.run_id, receipt.source_event_id)].append(receipt.timestamp)
    contexts_by_run_source = defaultdict(list)
    for entry in observation.contexts:
        contexts_by_run_source[(entry.run_id, entry.source_event_id)].append(entry.timestamp)

    by_page: dict[str, list[Write]] = defaultdict(list)
    token_sources: dict[str, list[Write]] = defaultdict(list)
    edges = set()
    for target in sorted(observation.writes, key=lambda w: (w.timestamp, w.event_id)):
        if method == "temporal":
            candidates = [source for source in by_page[target.page]
                          if 0 < target.timestamp - source.timestamp <= observation.temporal_window]
        else:
            candidates_by_id = {
                source.event_id: source
                for token in target.witness_tokens
                for source in token_sources[token]
                if source.timestamp < target.timestamp
            }
            candidates = list(candidates_by_id.values())
        for source in candidates:
            # Observed handle reuse is weak identity evidence available at level 0.
            if source.handle == target.handle:
                continue
            if level >= 1 and source.run_id == target.run_id:
                continue
            if level >= 2 and not any(
                source.timestamp < time < target.timestamp
                for time in requests_by_run_page[(target.run_id, source.page)]
            ):
                continue
            if level >= 3 and not any(
                source.timestamp < time < target.timestamp
                for time in deliveries_by_run_source[(target.run_id, source.event_id)]
            ):
                continue
            if level >= 4 and not any(
                source.timestamp < time < target.timestamp
                for time in contexts_by_run_source[(target.run_id, source.event_id)]
            ):
                continue
            edges.add((source.event_id, target.event_id))
        by_page[target.page].append(target)
        for token in target.witness_tokens:
            token_sources[token].append(target)
    return frozenset(edges)
