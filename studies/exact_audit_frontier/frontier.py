"""Exact deterministic conflict-detection frontiers on a fixed signature census.

Only hypothetical nominal support, the fixed k=2 answer table, paid history,
and a hard remaining budget enter planning. This module has no archive lookup,
actual-k input, target-truth objective, or expected-prior weighting.
"""
from __future__ import annotations

import copy
from itertools import product
from time import perf_counter, process_time

from tracebench.evidence_acquisition.model import canonical, pin

STATE_CAP = 100_000
COMBINATION_CAP = 10_000_000


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def state_id(scope_pin, nominal_mask, design_mask, remaining_actions, budget):
    """Stable identifier for one pinned sufficient state (also used in witnesses)."""
    return "state_" + pin({
        "scope_pin": scope_pin,
        "nominal_mask": hex(nominal_mask),
        "design_mask": hex(design_mask),
        "remaining_actions": list(remaining_actions),
        "budget": budget,
    })


def choice_key(queries, choice):
    """Frozen equal-pair tie, including the canonical child-choice byte order."""
    action = choice["action"]
    if action is None:
        return (0, 0, "", b"")
    children = [[child["outcome"], child["state_id"], child["d"], child["l"]]
                for child in choice["children"]]
    return (1, queries[action]["cost"], action, canonical(children))


class FrontierCap(RuntimeError):
    """A deterministic root-wide cap, never a best-so-far exact result."""

    def __init__(self, kind, limit, pending_state_id, query_id=None):
        self.detail = {"kind": kind, "limit": limit,
                       "pending_state_id": pending_state_id, "query_id": query_id}
        super().__init__(f"exact frontier {kind} cap reached ({limit})")


class FrontierPlanner:
    """One root, all integer budgets, and a complete Bellman witness table.

    The nominal API is intentionally observation-only: ``queries``,
    ``signature_cells``, ``model_pin``, ``compatible`` and ``partition`` suffice.
    The production caller supplies the unchanged validated Model. Explicit tiny
    observation tables can implement that same API for exhaustive-tree tests.

    All feasible actions are enumerated, including nominal constants, design
    constants, and separately priced physical aliases. Cap counters span the
    entire budget grid, rather than resetting at each budget.
    """

    def __init__(self, nominal, design_signatures, base_history,
                 state_cap=STATE_CAP, combination_cap=COMBINATION_CAP):
        _check(type(state_cap) is int and 0 < state_cap <= STATE_CAP,
               "state cap must be a positive integer no greater than the frozen cap")
        _check(type(combination_cap) is int and 0 < combination_cap <= COMBINATION_CAP,
               "combination cap must be a positive integer no greater than the frozen cap")
        self.nominal = nominal
        self.query_ids = tuple(nominal.queries)
        _check(0 < len(self.query_ids) <= 8, "query catalogue outside frozen bounds")
        _check(all(isinstance(qid, str) and qid for qid in self.query_ids),
               "query identifiers must be nonempty strings")
        _check(all(type(query["cost"]) is int and query["cost"] > 0
                   and 0 < len(query["outcomes"]) <= 2
                   and all(isinstance(outcome, str) for outcome in query["outcomes"])
                   for query in nominal.queries.values()),
               "invalid bounded action cost/outcome catalogue")
        _check(isinstance(nominal.model_pin, str) and nominal.model_pin,
               "a pinned nominal model is required")
        self._positions = {qid: index for index, qid in enumerate(self.query_ids)}
        self.design_signatures = tuple(sorted({self._signature(signature)
                                               for signature in design_signatures}))
        _check(0 < len(self.design_signatures) <= 256,
               "fixed design envelope empty or exceeds the frozen signature cap")
        _check(set(nominal.signature_cells) <= set(self.design_signatures),
               "fixed design envelope omits nominal signatures")
        self.base_history = copy.deepcopy(self._history(base_history))
        self._root_nominal = nominal.compatible(self.base_history)
        _check(bool(self._root_nominal), "preserved acquisition root already contradicts nominal support")
        self._outcome_masks = {
            qid: {outcome: sum(1 << index for index, signature in enumerate(self.design_signatures)
                              if signature[self._positions[qid]] == outcome)
                  for outcome in sorted(nominal.queries[qid]["outcomes"])}
            for qid in self.query_ids
        }
        self._root_design = self._compatible_design(self.base_history)
        observed = {row["query_id"] for row in self.base_history}
        self._root_remaining = tuple(sorted(set(self.query_ids) - observed))
        self.residual_cost = sum(nominal.queries[qid]["cost"] for qid in self._root_remaining)
        self.design_pin = pin({"query_ids": list(self.query_ids),
                               "signatures": [list(signature) for signature in self.design_signatures]})
        self.scope_pin = pin({"nominal_pin": nominal.model_pin, "design_pin": self.design_pin,
                              "base_history": self.base_history})
        self.state_cap = state_cap
        self.combination_cap = combination_cap
        self.status = "pending"
        self._states = {}
        self._pending = {}
        self._admitted = set()
        self._combinations = 0
        self._budget_frontiers = []
        self._cap = None
        self._solve_wall = self._solve_cpu = 0.0
        self._choice_wall = self._choice_cpu = 0.0
        self._choice_calls = 0
        self._completed_budget_count = 0

    def _signature(self, signature):
        signature = tuple(signature)
        _check(len(signature) == len(self.query_ids), "signature lacks a catalogue outcome")
        by_record = {}
        for qid, outcome in zip(self.query_ids, signature, strict=True):
            query = self.nominal.queries[qid]
            _check(outcome in query["outcomes"], "signature contains an undeclared outcome")
            record_id = query.get("record_id", qid)
            _check(record_id not in by_record or by_record[record_id] == outcome,
                   "physical aliases have inconsistent observable outcomes")
            by_record[record_id] = outcome
        return signature

    def _history(self, history):
        history = list(history)
        _check(all(isinstance(row, dict) and set(row) == {"query_id", "outcome_id"}
                   for row in history), "malformed paid history")
        ids = [row["query_id"] for row in history]
        _check(len(ids) == len(set(ids)), "paid action appears more than once")
        for row in history:
            qid, outcome = row["query_id"], row["outcome_id"]
            _check(qid in self.nominal.queries and outcome in self.nominal.queries[qid]["outcomes"],
                   "paid history contains an undeclared action/outcome")
        return history

    def _compatible_design(self, history):
        state = (1 << len(self.design_signatures)) - 1
        for row in history:
            state &= self._outcome_masks[row["query_id"]][row["outcome_id"]]
        _check(bool(state), "paid history has empty fixed k=2 design-envelope compatibility")
        return state

    def _state_descriptor(self, key):
        nominal, design, remaining, budget = key
        return {"state_id": state_id(self.scope_pin, nominal, design, remaining, budget),
                "nominal_mask": hex(nominal), "design_mask": hex(design),
                "remaining_actions": list(remaining), "budget": budget}

    def _remember_candidate(self, best_by_detection, candidate):
        previous = best_by_detection.get(candidate["d"])
        if (previous is None or candidate["l"] < previous["l"]
                or (candidate["l"] == previous["l"]
                    and choice_key(self.nominal.queries, candidate["choice"])
                    < choice_key(self.nominal.queries, previous["choice"]))):
            best_by_detection[candidate["d"]] = candidate

    @staticmethod
    def _nondominated(best_by_detection):
        frontier, cheapest_at_higher_detection = [], None
        for detection in sorted(best_by_detection, reverse=True):
            candidate = best_by_detection[detection]
            if cheapest_at_higher_detection is None or candidate["l"] < cheapest_at_higher_detection:
                frontier.append(candidate)
                cheapest_at_higher_detection = candidate["l"]
        return frontier

    def _solve(self, key):
        if key in self._states:
            return self._states[key]
        descriptor = self._state_descriptor(key)
        if len(self._admitted) >= self.state_cap:
            raise FrontierCap("solver_states", self.state_cap, descriptor["state_id"])
        self._admitted.add(key)
        self._pending[key] = descriptor
        nominal, design, remaining, budget = key
        count = design.bit_count()
        _check(count > 0, "internal empty design branch")
        actions = []
        if not nominal:
            frontier = [{"d": count, "l": 0, "choice": {"action": None, "children": []}}]
        else:
            best = {0: {"d": 0, "l": 0, "choice": {"action": None, "children": []}}}
            ordered_actions = sorted(remaining, key=lambda qid: (self.nominal.queries[qid]["cost"], qid))
            for qid in ordered_actions:
                cost = self.nominal.queries[qid]["cost"]
                if cost > budget:
                    continue
                nominal_branches = self.nominal.partition(nominal, qid)
                after_actions = tuple(action for action in remaining if action != qid)
                child_states, branches = [], []
                for outcome, outcome_mask in self._outcome_masks[qid].items():
                    branch_design = design & outcome_mask
                    if not branch_design:
                        continue
                    child_key = (nominal_branches.get(outcome, 0), branch_design,
                                 after_actions, budget - cost)
                    child = self._solve(child_key)
                    child_states.append((outcome, child))
                    branches.append({"outcome": outcome, "child_state_id": child["state_id"],
                                     "design_count": branch_design.bit_count()})
                actions.append({"query_id": qid, "cost": cost, "branches": branches})
                for children in product(*(child["frontier"] for _, child in child_states)):
                    if self._combinations >= self.combination_cap:
                        raise FrontierCap("child_combinations", self.combination_cap,
                                          descriptor["state_id"], qid)
                    self._combinations += 1
                    candidate = {
                        "d": sum(point["d"] for point in children),
                        "l": count * cost + sum(point["l"] for point in children),
                        "choice": {"action": qid, "children": [
                            {"outcome": outcome, "state_id": child["state_id"],
                             "d": point["d"], "l": point["l"]}
                            for (outcome, child), point in zip(child_states, children, strict=True)]},
                    }
                    self._remember_candidate(best, candidate)
            frontier = self._nondominated(best)
        result = {**descriptor, "terminal_conflict": not nominal,
                  "frontier": frontier, "actions": actions}
        self._states[key] = result
        del self._pending[key]
        return result

    def solve(self):
        """Solve once across 0..R; a cap withholds *all* exact root-budget claims."""
        if self.status != "pending":
            return self.export()
        started_wall, started_cpu = perf_counter(), process_time()
        try:
            for budget in range(self.residual_cost + 1):
                key = (self._root_nominal, self._root_design, self._root_remaining, budget)
                state = self._solve(key)
                self._budget_frontiers.append({
                    "budget": budget, "state_id": state["state_id"],
                    "frontier": state["frontier"], "canonical_point": state["frontier"][0],
                })
                self._completed_budget_count += 1
            self.status = "complete"
        except FrontierCap as exc:
            self.status = "unavailable"
            self._cap = exc.detail
            self._budget_frontiers = []
        finally:
            self._solve_wall = perf_counter() - started_wall
            self._solve_cpu = process_time() - started_cpu
        return self.export()

    def resource_snapshot(self):
        """Whole-root counters; reconstruction overhead is separate from solving."""
        lengths = [len(state["frontier"]) for state in self._states.values()]
        return {
            "state_cap": self.state_cap, "combination_cap": self.combination_cap,
            "solver_states": len(self._admitted), "completed_states": len(self._states),
            "pending_states": len(self._pending), "child_combinations": self._combinations,
            "total_frontier_points": sum(lengths), "maximum_frontier_size": max(lengths, default=0),
            "requested_budget_count": self.residual_cost + 1,
            "completed_budget_count_before_cap": self._completed_budget_count,
            "solve_wall_seconds": self._solve_wall, "solve_cpu_seconds": self._solve_cpu,
            "reconstruction_calls": self._choice_calls,
            "reconstruction_wall_seconds": self._choice_wall,
            "reconstruction_cpu_seconds": self._choice_cpu,
        }

    def export(self):
        """Portable witness; on a cap, retained states are partial evidence only."""
        return copy.deepcopy({
            "schema_version": 1, "status": self.status,
            "root": {"nominal_pin": self.nominal.model_pin, "design_pin": self.design_pin,
                     "scope_pin": self.scope_pin, "query_ids": list(self.query_ids),
                     "base_history": self.base_history, "nominal_mask": hex(self._root_nominal),
                     "design_mask": hex(self._root_design),
                     "remaining_actions": list(self._root_remaining), "residual_cost": self.residual_cost},
            "budget_frontiers": self._budget_frontiers if self.status == "complete" else [],
            "states": sorted(self._states.values(), key=lambda state: state["state_id"]),
            "pending_states": sorted(self._pending.values(), key=lambda state: state["state_id"]),
            "resources": self.resource_snapshot(), "cap": self._cap,
        })

    def choose(self, history, remaining_budget):
        """Canonical E action from paid evidence; never computes a new DP state.

        A maximal-detection, least-cost parent uses that same lexicographic
        objective in every nonempty child: branch budgets are independent and
        rewards/costs add. Thus following each child's first frontier point
        reconstructs the saved primary backpointer without a hidden signature.
        """
        started_wall, started_cpu = perf_counter(), process_time()
        try:
            _check(self.status == "complete", "exact frontier root is not completely solved")
            history = self._history(history)
            _check(history[:len(self.base_history)] == self.base_history,
                   "paid history does not extend this preserved root")
            extra = history[len(self.base_history):]
            spent = sum(self.nominal.queries[row["query_id"]]["cost"] for row in extra)
            _check(type(remaining_budget) is int and 0 <= remaining_budget <= self.residual_cost - spent,
                   "remaining budget is outside this root's feasible integer grid")
            nominal = self.nominal.compatible(history)
            design = self._compatible_design(history)
            observed = {row["query_id"] for row in history}
            remaining = tuple(sorted(set(self.query_ids) - observed))
            key = (nominal, design, remaining, remaining_budget)
            _check(key in self._states, "paid information state was not solved in the complete root grid")
            return self._states[key]["frontier"][0]["choice"]["action"]
        finally:
            self._choice_calls += 1
            self._choice_wall += perf_counter() - started_wall
            self._choice_cpu += process_time() - started_cpu
