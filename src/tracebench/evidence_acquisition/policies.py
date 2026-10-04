"""Five passive acquisition policies over the same declared finite archive model.

Only ChargedLookup holds a realized archive signature. Planners receive the model
of hypothetical possibilities and the history of already paid observations.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from itertools import combinations
from time import perf_counter
from typing import Any

POLICIES = ("read_all", "schema_aware", "world_entropy", "pair_cut", "exact_optimal")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _members(state: int):
    while state:
        bit = state & -state
        yield bit.bit_length() - 1
        state ^= bit


def budget_for(model: Any, percent: int) -> int:
    """Floor the percentage of the fixed cost of retrieving the whole catalogue."""
    if type(percent) is not int or not 0 <= percent <= 100:
        raise ValueError("budget percent must be an integer between zero and 100")
    return sum(query["cost"] for query in model.queries.values()) * percent // 100


def schema_order(model: Any) -> tuple[str, ...]:
    """Visible scope/kind rank, then positive cost and opaque query ID.

    Relevant context receipts and completeness declarations share the first
    rank; relevant delivery/request receipts share the second. All other
    records share the third. Receipt windows must overlap the half-open claim
    window; completeness windows must cover it entirely.
    """
    claim = model.problem["claim"]

    def key(query_id: str):
        query = model.queries[query_id]
        scope = query.get("scope", {})
        window = scope.get("window", ())
        kind = query["kind"]
        window_relevant = len(window) == 2 and (
            window[0] <= claim["window"][0] and window[1] >= claim["window"][1]
            if kind == "completeness"
            else window[0] < claim["window"][1] and claim["window"][0] < window[1]
        )
        relevant = (
            scope.get("source_id") in claim["source_ids"]
            and scope.get("recipient") == claim["recipient"]
            and window_relevant
        )
        if relevant and kind in {"context_receipt", "completeness"}:
            rank = 0
        elif relevant and kind in {"delivery_receipt", "request_receipt"}:
            rank = 1
        else:
            rank = 2
        return rank, query["cost"], query_id

    return tuple(sorted(model.queries, key=key))


class ChargedLookup:
    """Evaluator boundary: reveal a selected archive answer only after a charge.

    ``signature`` is evaluator-only input in catalogue order. It is not passed
    to Planner. This is an interface boundary, not a Python security sandbox.
    Canonical returned bytes count the observable payload alone, excluding the
    accounting envelope. A missing-record payload still has nonzero bytes.
    """

    def __init__(self, model: Any, signature: tuple[str, ...]):
        signature = tuple(signature)
        if signature not in model.signature_cells:
            raise ValueError("lookup signature is not a possible archive")
        self._model = model
        self._answers = dict(zip(model.queries, signature, strict=True))
        self._queried: set[str] = set()
        self.history: list[dict[str, str]] = []
        self.cost = 0
        self.bytes_returned = 0

    def __call__(self, query_id: str) -> dict[str, Any]:
        if query_id not in self._model.queries:
            raise ValueError("unknown query")
        if query_id in self._queried:
            raise ValueError("repeat lookups do not supply new evidence")
        query = self._model.queries[query_id]
        outcome_id = self._answers[query_id]
        payload_bytes = _canonical(query["outcomes"][outcome_id])
        self.cost += query["cost"]
        self.bytes_returned += len(payload_bytes)
        self._queried.add(query_id)
        self.history.append({"query_id": query_id, "outcome_id": outcome_id})
        return {
            "query_id": query_id,
            "outcome_id": outcome_id,
            "observable": json.loads(payload_bytes),
            "cost": query["cost"],
            "canonical_bytes": len(payload_bytes),
        }


class Planner:
    """Reusable per-model/per-policy planner; caches never hold realized answers.

    Reuse the same instance across signature and budget evaluations. Runtime and
    solver-state deltas are then reported per run, with totals on this object.
    Model preprocessing occurs outside this class and must be timed separately.
    """

    def __init__(self, model: Any, policy: str):
        if policy not in POLICIES:
            raise ValueError("unknown acquisition policy")
        self.model = model
        self.policy = policy
        self.order = schema_order(model) if policy == "schema_aware" else tuple(model.queries)
        self._values: dict[tuple[int, tuple[str, ...]], Fraction] = {}
        self._actions: dict[tuple[int, tuple[str, ...]], str | None] = {}
        self._edges: dict[int, Fraction] = {}
        self.solver_states = 0
        self.planning_seconds = 0.0

    def _remaining(self, history: list[dict[str, str]]) -> tuple[str, ...]:
        queried = [row["query_id"] for row in history]
        if len(set(queried)) != len(queried):
            raise ValueError("duplicate query in acquisition history")
        if set(queried) - self.model.queries.keys():
            raise ValueError("unknown historical query")
        return tuple(query_id for query_id in self.order if query_id not in queried)

    def edge_mass(self, state: int) -> Fraction:
        """E(S), using original prior masses, never renormalized within S."""
        if state not in self._edges:
            masses: dict[str, Fraction] = {}
            for index in _members(state):
                label = self.model.tau[index]
                masses[label] = masses.get(label, Fraction()) + self.model.priors[index]
            values = list(masses.values())
            self._edges[state] = sum(
                (left * right for left, right in combinations(values, 2)), Fraction()
            )
        return self._edges[state]

    def pair_gain(self, state: int, query_id: str) -> Fraction:
        mass = self.model.mass(state)
        if not mass:
            return Fraction()
        after = sum(
            (
                self.model.mass(child) / mass * self.edge_mass(child)
                for child in self.model.partition(state, query_id).values()
                if child
            ),
            Fraction(),
        )
        return self.edge_mass(state) - after

    def entropy_gain(self, state: int, query_id: str) -> float:
        """A deterministic query's expected world entropy gain is H(outcome)."""
        mass = self.model.mass(state)
        if not mass:
            return 0.0
        probabilities = sorted(
            self.model.mass(child) / mass
            for child in self.model.partition(state, query_id).values()
            if child
        )
        return -math.fsum(float(p) * math.log2(float(p)) for p in probabilities)

    def _solve(self, state: int, remaining: tuple[str, ...]) -> tuple[Fraction, str | None]:
        # Positive-cost constant queries cannot improve a certificate. Remove
        # them before memoization, preserving the catalogue's fixed order.
        remaining = tuple(
            query_id for query_id in remaining
            if len([s for s in self.model.partition(state, query_id).values() if s]) > 1
        )
        key = state, remaining
        if key in self._values:
            return self._values[key], self._actions[key]
        self.solver_states += 1
        if self.model.terminal(state) is not None:
            value, action = Fraction(), None
        else:
            if not remaining:
                raise ValueError("nonterminal archive without an informative remaining query")
            mass = self.model.mass(state)
            candidates = []
            for query_id in remaining:
                rest = tuple(q for q in remaining if q != query_id)
                value = Fraction(self.model.queries[query_id]["cost"]) + sum(
                    (
                        self.model.mass(child) / mass * self._solve(child, rest)[0]
                        for child in self.model.partition(state, query_id).values()
                        if child
                    ),
                    Fraction(),
                )
                candidates.append((value, self.model.queries[query_id]["cost"], query_id))
            value, _, action = min(candidates)
        self._values[key], self._actions[key] = value, action
        return value, action

    def optimal_value(
        self, state: int | None = None, remaining: tuple[str, ...] | None = None
    ) -> Fraction:
        if self.policy != "exact_optimal":
            raise ValueError("optimal value is available only from the exact policy")
        started = perf_counter()
        try:
            return self._solve(
                self.model.full_state if state is None else state,
                tuple(self.model.queries) if remaining is None else remaining,
            )[0]
        finally:
            self.planning_seconds += perf_counter() - started

    def choose(self, history: list[dict[str, str]]) -> str | None:
        started = perf_counter()
        try:
            remaining = self._remaining(history)
            state = self.model.compatible(history)
            if not state:
                return None
            if self.policy != "read_all" and self.model.terminal(state) is not None:
                return None
            if not remaining:
                if self.model.terminal(state) is None:
                    raise ValueError("exhausted archive without a terminal certificate")
                return None
            if self.policy in {"read_all", "schema_aware"}:
                return remaining[0]
            if self.policy == "exact_optimal":
                return self._solve(state, remaining)[1]
            gain = self.pair_gain if self.policy == "pair_cut" else self.entropy_gain
            return min(
                remaining,
                key=lambda q: (
                    -gain(state, q) / self.model.queries[q]["cost"],
                    self.model.queries[q]["cost"], q,
                ),
            )
        finally:
            self.planning_seconds += perf_counter() - started


def run_policy(
    model: Any, policy: str, lookup: Any, budget: int | None = None, *,
    planner: Planner | None = None,
) -> dict[str, Any]:
    """Execute a fixed policy through paid lookups; never adapt it to a budget.

    If its next action is unaffordable, stop, even if a cheaper one exists.
    Read-all continues past early certificates, except at a budget stop, where
    an already available certificate still counts. At full budget it reads all.
    """
    if budget is None:
        budget = sum(query["cost"] for query in model.queries.values())
    if type(budget) is not int or budget < 0:
        raise ValueError("budget must be a nonnegative integer")
    if planner is None:
        planner = Planner(model, policy)
    if planner.model is not model or planner.policy != policy:
        raise ValueError("planner model or policy mismatch")
    before_seconds, before_states = planner.planning_seconds, planner.solver_states
    history: list[dict[str, str]] = []
    cost = byte_count = 0
    next_query = None
    while True:
        query_id = planner.choose(history)
        if query_id is None:
            stop_reason = "archive_exhausted" if policy == "read_all" else "certificate"
            break
        expected_cost = model.queries[query_id]["cost"]
        if cost + expected_cost > budget:
            next_query, stop_reason = query_id, "next_query_exceeds_budget"
            break
        result = lookup(query_id)
        if result.get("query_id") != query_id:
            raise ValueError("lookup returned a different query")
        outcome_id = result.get("outcome_id")
        outcomes = model.queries[query_id]["outcomes"]
        if outcome_id not in outcomes:
            raise ValueError("lookup returned an undeclared outcome")
        expected_bytes = len(_canonical(outcomes[outcome_id]))
        if (
            result.get("cost") != expected_cost
            or result.get("canonical_bytes") != expected_bytes
            or _canonical(result.get("observable")) != _canonical(outcomes[outcome_id])
        ):
            raise ValueError("lookup accounting or observable content mismatch")
        cost += expected_cost
        byte_count += expected_bytes
        history.append({"query_id": query_id, "outcome_id": outcome_id})
    state = model.compatible(history)
    logical_status = model.terminal(state)
    if logical_status is None:
        if stop_reason != "next_query_exceeds_budget":
            raise ValueError("unresolved archive without budget exhaustion")
        status = "budget_exhausted_unresolved"
        certificate = model.certificate(history, status="unresolved_pending")
    else:
        status = logical_status
        certificate = model.certificate(history, status=logical_status)
    verified = model.verify_certificate(certificate)
    if not verified:
        raise ValueError("generated certificate failed independent validation")
    return {
        "policy": policy, "budget": budget, "history": history,
        "cost": cost, "query_count": len(history), "returned_bytes": byte_count,
        "status": status, "stop_reason": stop_reason, "next_query": next_query,
        "certificate": certificate, "certificate_valid": verified,
        "planning_seconds": planner.planning_seconds - before_seconds,
        "solver_states": planner.solver_states - before_states,
        "solver_states_total": planner.solver_states,
    }


def hindsight_minimum(model: Any, full_history: list[dict[str, str]]) -> dict[str, Any]:
    """Global subset minimum for a known complete archive; not a search policy."""
    query_ids = [row["query_id"] for row in full_history]
    if len(query_ids) != len(set(query_ids)) or set(query_ids) != set(model.queries):
        raise ValueError("hindsight requires exactly one result for every query")
    state = model.compatible(full_history)
    target = model.terminal(state)
    if target is None or target == "inconsistent":
        raise ValueError("full observed history must be a consistent terminal archive")
    ordered = sorted(full_history, key=lambda row: row["query_id"])
    candidates = []
    for count in range(len(ordered) + 1):
        for subset in combinations(ordered, count):
            cost = sum(model.queries[row["query_id"]]["cost"] for row in subset)
            candidates.append((cost, count, tuple(row["query_id"] for row in subset), subset))
    for cost, count, _, subset in sorted(candidates):
        history = list(subset)
        if model.terminal(model.compatible(history)) != target:
            continue
        certificate = model.certificate(history, status=target)
        if not model.verify_certificate(certificate):
            raise ValueError("hindsight certificate failed independent validation")
        return {
            "cost": cost, "query_count": count,
            "returned_bytes": sum(len(_canonical(
                model.queries[row["query_id"]]["outcomes"][row["outcome_id"]]
            )) for row in history),
            "history": history, "status": target, "certificate": certificate,
            "certificate_valid": True,
        }
    raise ValueError("complete archive lacked its own hindsight certificate")
