"""Compare receipt conjunction with evidence-aware candidate classification.

All predictions remain heuristic source-attribution candidates. A valid context
receipt establishes exposure under the declared authentication assumption; it
does not establish realized source selection. Unknown candidates are reported
separately and never promoted to predictions.
"""

from collections import defaultdict
from dataclasses import dataclass, replace

from .corruption import ReceiptObservation
from .estimators import estimate
from .model import ContextEntry, Delivery, Edge, Request, Write
from .observe import Telemetry

POLICIES = ("conjunction", "evidence_aware")


@dataclass(frozen=True)
class InferenceResult:
    """Partition the common candidate universe by the selected policy.

    For evidence_aware, excluded means complete relevant logging justifies
    excluding exposure. For conjunction, excluded only means rejected by the
    original filter: missing records can make that rejection unjustified.
    No set is a set of verified source-use edges.
    """

    predictions: frozenset[Edge]
    unresolved: frozenset[Edge]
    excluded: frozenset[Edge]
    candidates: frozenset[Edge]


def _valid_request(request: Request, source: Write, target: Write,
                   before: float) -> bool:
    return (request.run_id == target.run_id and request.page == source.page
            and source.timestamp < request.timestamp < before)


def _valid_delivery(delivery: Delivery, source: Write, target: Write,
                    before: float, requests_by_id: dict[str, list[Request]]) -> bool:
    return (delivery.run_id == target.run_id
            and delivery.source_event_id == source.event_id
            and source.timestamp < delivery.timestamp < before
            and all(_valid_request(request, source, target, delivery.timestamp)
                    for request in requests_by_id.get(delivery.request_id, ())))


def _valid_context(entry: ContextEntry, source: Write, target: Write,
                   requests_by_id: dict[str, list[Request]],
                   deliveries_by_id: dict[str, list[Delivery]]) -> bool:
    # A trusted downstream receipt does not require an upstream log to survive.
    # But any surviving upstream references must agree in identity and ordering.
    return (entry.run_id == target.run_id
            and entry.source_event_id == source.event_id
            and source.timestamp < entry.timestamp < target.timestamp
            and entry.concepts == source.concepts
            and entry.witness_tokens == source.witness_tokens
            and all(_valid_request(request, source, target, entry.timestamp)
                    for request in requests_by_id.get(entry.request_id, ()))
            and all(_valid_delivery(delivery, source, target, entry.timestamp,
                                    requests_by_id)
                    for delivery in deliveries_by_id.get(entry.request_id, ())))


def infer(receipts: ReceiptObservation, method: str, policy: str) -> InferenceResult:
    """Classify one identical observation without simulator or loss-mask access."""
    if not isinstance(receipts, ReceiptObservation):
        raise TypeError("infer requires a ReceiptObservation, not simulator truth")
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy {policy!r}; choose from {POLICIES}")
    observation = receipts.observation
    completeness = receipts.completeness
    candidates = estimate(replace(observation, regime=Telemetry.IDENTITY,
                                  requests=(), deliveries=(), contexts=()), method)
    if policy == "conjunction":
        predictions = estimate(observation, method)
        return InferenceResult(predictions, frozenset(), candidates - predictions, candidates)
    if not completeness.receipts_authenticated:
        # Completeness does not substitute for provenance. This study generates
        # authentic records only, but callers cannot assert exposure via a flag
        # explicitly denying that assumption.
        return InferenceResult(frozenset(), candidates, frozenset(), candidates)

    writes = {write.event_id: write for write in observation.writes}
    requests_by_id = defaultdict(list)
    requests_by_run_page = defaultdict(list)
    deliveries_by_id = defaultdict(list)
    deliveries_by_run_source = defaultdict(list)
    contexts_by_run_source = defaultdict(list)
    for request in observation.requests:
        requests_by_id[request.request_id].append(request)
        requests_by_run_page[(request.run_id, request.page)].append(request)
    for delivery in observation.deliveries:
        deliveries_by_id[delivery.request_id].append(delivery)
        deliveries_by_run_source[(delivery.run_id, delivery.source_event_id)].append(delivery)
    for entry in observation.contexts:
        contexts_by_run_source[(entry.run_id, entry.source_event_id)].append(entry)

    predictions, unresolved, excluded = set(), set(), set()
    for edge in candidates:
        source, target = (writes[event_id] for event_id in edge)
        receipt_key = (target.run_id, source.event_id)
        if any(_valid_context(entry, source, target, requests_by_id, deliveries_by_id)
               for entry in contexts_by_run_source[receipt_key]):
            predictions.add(edge)
        elif completeness.contexts:
            excluded.add(edge)
        elif completeness.deliveries and not any(
            _valid_delivery(delivery, source, target, target.timestamp, requests_by_id)
            for delivery in deliveries_by_run_source[receipt_key]
        ):
            excluded.add(edge)
        elif completeness.requests and not any(
            _valid_request(request, source, target, target.timestamp)
            for request in requests_by_run_page[(target.run_id, source.page)]
        ):
            excluded.add(edge)
        else:
            unresolved.add(edge)
    return InferenceResult(frozenset(predictions), frozenset(unresolved),
                           frozenset(excluded), candidates)
