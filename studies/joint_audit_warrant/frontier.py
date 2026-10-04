"""Anchored exact detection/support/cost frontiers on the fixed physical model.

The historical solver supplies catalogue and paid-history validation only.
The three-objective recurrence, Pareto pruning, support reward, scope pins,
and anchor schedule are new and leave the detection-only implementation intact.
"""
from __future__ import annotations

from itertools import product
from time import perf_counter, process_time

from studies.exact_audit_frontier.frontier import (
    COMBINATION_CAP,
    STATE_CAP,
    FrontierCap,
    FrontierPlanner,
)
from tracebench.evidence_acquisition.model import canonical, pin


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def choice_key(queries, choice):
    """Previous STOP/cost/ID ordering, extended to encode each child's support."""
    action = choice["action"]
    if action is None:
        return (0, 0, "", b"")
    children = [[child["outcome"], child["state_id"], child["d"], child["w"], child["l"]]
                for child in choice["children"]]
    return (1, queries[action]["cost"], action, canonical(children))


class JointFrontierPlanner(FrontierPlanner):
    """A fixed root/proposal/physical closure, solved only at supplied anchors.

    ``support`` binds the same nominal object and ordered root, a globally
    sorted distinct signature table, the physical-model pin, the fixed proposal,
    and ``reward(mask)`` over ALL physical realizations in those signature cells.
    No realized archive, actual omission condition, or realized truth is accepted.
    """

    def __init__(self, nominal, support, base_history, budgets,
                 state_cap=STATE_CAP, combination_cap=COMBINATION_CAP):
        base_history = list(base_history)
        _check(support.nominal is nominal, "support contract belongs to a different nominal object")
        _check(support.base_history == base_history, "support contract belongs to a different paid root")
        _check(isinstance(support.physical_pin, str) and support.physical_pin,
               "support requires a pinned physical claim contract")
        _check(support.proposal in {"established", "ruled_out", "archive_irreducible"},
               "unsupported original nominal proposal")
        super().__init__(nominal, support.design_signatures, base_history,
                         state_cap=state_cap, combination_cap=combination_cap)
        _check(tuple(support.design_signatures) == self.design_signatures,
               "physical support masks require the globally sorted distinct signature table")
        self.support = support
        self.physical_pin = support.physical_pin
        self.proposal = support.proposal
        self._original_signature_mask = sum(1 << i for i, signature in enumerate(self.design_signatures)
                                            if signature in nominal.signature_cells)
        self.requested_budgets = tuple(budgets)
        _check(0 < len(self.requested_budgets) <= 4
               and all(type(b) is int and 0 <= b <= self.residual_cost for b in self.requested_budgets),
               "joint solver requires one to four valid integer anchor allowances")
        self.budgets = tuple(sorted(set(self.requested_budgets)))
        self.scope_pin = pin({"nominal_pin": nominal.model_pin, "design_pin": self.design_pin,
                              "physical_pin": self.physical_pin, "proposal": self.proposal,
                              "base_history": self.base_history})

    def _reward(self, design):
        value = self.support.reward(design)
        _check(type(value) is int and 0 <= value <= (design & self._original_signature_mask).bit_count(),
               "physical support reward is not a count of compatible original signatures")
        _check(self.proposal in {"established", "ruled_out"} or value == 0,
               "an originally nondefinite proposal cannot earn definite-support credit")
        return value

    def _remember_candidate(self, best_by_detection_support, candidate):
        key = candidate["d"], candidate["w"]
        previous = best_by_detection_support.get(key)
        if (previous is None or candidate["l"] < previous["l"]
                or (candidate["l"] == previous["l"]
                    and choice_key(self.nominal.queries, candidate["choice"])
                    < choice_key(self.nominal.queries, previous["choice"]))):
            best_by_detection_support[key] = candidate

    @staticmethod
    def _nondominated(best_by_detection_support):
        """Three-dimensional exact dominance; no scalar objective substitution.

        Visit decreasing detection then support. A prefix-minimum Fenwick table
        on reversed support ranks answers whether an earlier point has at least
        as much support and no larger cost. Equal (d,w) already has minimum l.
        """
        candidates = sorted(best_by_detection_support.values(), key=lambda p: (-p["d"], -p["w"], p["l"]))
        maximum_support = max(p["w"] for p in candidates)
        minima = [None] * (maximum_support + 2)
        frontier = []
        for candidate in candidates:
            rank = maximum_support - candidate["w"] + 1
            index, minimum = rank, None
            while index:
                if minima[index] is not None:
                    minimum = minima[index] if minimum is None else min(minimum, minima[index])
                index -= index & -index
            if minimum is not None and minimum <= candidate["l"]:
                continue
            frontier.append(candidate)
            index = rank
            while index < len(minima):
                minima[index] = candidate["l"] if minima[index] is None else min(minima[index], candidate["l"])
                index += index & -index
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
        _check(count > 0, "joint recurrence reached an empty physical design branch")
        actions = []
        if not nominal:
            _check(not (design & self._original_signature_mask),
                   "nominal conflict incorrectly retains an original signature")
            stop_reward = 0
            frontier = [{"d": count, "w": 0, "l": 0, "choice": {"action": None, "children": []}}]
        else:
            stop_reward = self._reward(design)
            stop = {"d": 0, "w": stop_reward, "l": 0, "choice": {"action": None, "children": []}}
            best = {(0, stop_reward): stop}
            for qid in sorted(remaining, key=lambda q: (self.nominal.queries[q]["cost"], q)):
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
                    child = self._solve((nominal_branches.get(outcome, 0), branch_design,
                                         after_actions, budget - cost))
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
                        "w": sum(point["w"] for point in children),
                        "l": count * cost + sum(point["l"] for point in children),
                        "choice": {"action": qid, "children": [
                            {"outcome": outcome, "state_id": child["state_id"],
                             "d": point["d"], "w": point["w"], "l": point["l"]}
                            for (outcome, child), point in zip(child_states, children, strict=True)]},
                    }
                    _check(candidate["d"] + candidate["w"] <= count,
                           "joint rewards double-count an original alarm or unsupported signature")
                    self._remember_candidate(best, candidate)
            frontier = self._nondominated(best)
        result = {**descriptor, "terminal_conflict": not nominal, "stop_reward": stop_reward,
                  "frontier": frontier, "actions": actions}
        self._states[key] = result
        del self._pending[key]
        return result

    def solve(self):
        """Solve only unique supplied anchors; a cap invalidates all root anchors."""
        if self.status != "pending":
            return self.export()
        started_wall, started_cpu = perf_counter(), process_time()
        try:
            for budget in self.budgets:
                state = self._solve((self._root_nominal, self._root_design, self._root_remaining, budget))
                self._budget_frontiers.append({"budget": budget, "state_id": state["state_id"],
                                               "frontier": state["frontier"],
                                               "canonical_point": state["frontier"][0]})
                self._completed_budget_count += 1
            self.status = "complete"
        except FrontierCap as exc:
            self.status, self._cap, self._budget_frontiers = "unavailable", exc.detail, []
        finally:
            self._solve_wall = perf_counter() - started_wall
            self._solve_cpu = process_time() - started_cpu
        return self.export()

    def resource_snapshot(self):
        return {**super().resource_snapshot(), "requested_budget_count": len(self.budgets),
                "requested_anchor_count": len(self.requested_budgets)}

    def export(self):
        result = super().export()
        result["root"].update({"physical_pin": self.physical_pin, "proposal": self.proposal,
                               "requested_budgets": list(self.requested_budgets), "budgets": list(self.budgets)})
        return result

    def choose(self, history, remaining_budget):
        """Read a solved canonical J action using only paid history and allowance.

        Independent pathwise branch budgets and additive d,w,l mean the parent's
        lexicographic optimum uses the same lexicographic optimum in every child.
        Unrequested root budgets are rejected even if an internal state happens
        to exist from another anchor's recursion.
        """
        history = self._history(history)
        _check(history[:len(self.base_history)] == self.base_history,
               "paid history does not extend this preserved joint root")
        spent = sum(self.nominal.queries[row["query_id"]]["cost"]
                    for row in history[len(self.base_history):])
        _check(type(remaining_budget) is int and spent + remaining_budget in self.budgets,
               "execution allowance was not a requested joint anchor")
        return super().choose(history, remaining_budget)
