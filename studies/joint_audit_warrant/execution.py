"""Charged replay of saved E, sequential substantiation, and the joint policy.

Only the private passive archive receives the realized signature. Prospective
choices use paid history, the original remaining allowance, and declared fixed
hypotheses. Saved E follows its original point/child backpointers verbatim.
"""
from __future__ import annotations

import copy
from time import perf_counter

from studies.audit_aware_acquisition.auditing import PassiveAuditArchive, _history, _signature
from studies.exact_audit_frontier.execution import _certificate_cache, validate_baseline
from studies.exact_audit_frontier.frontier import state_id
from studies.joint_audit_warrant.support import DEFINITE, require
from tracebench.evidence_acquisition.model import canonical, pin

ARMS = ("exact_frontier", "E_then_support", "joint_frontier")


class SavedEPolicy:
    """Read-only paid-history replay; no solver or support-favorable retie."""

    def __init__(self, nominal, design_signatures, saved_solver):
        self.nominal = nominal
        self.query_ids = tuple(nominal.query_ids)
        self.design_signatures = tuple(sorted({_signature(nominal, s) for s in design_signatures}))
        require(set(nominal.signature_cells) <= set(self.design_signatures), "Saved E envelope omits nominal support")
        self.saved = copy.deepcopy(saved_solver)
        require(self.saved["status"] == "complete", "Saved E policy is unavailable")
        self.saved_solver_pin = pin(saved_solver)
        root = self.saved["root"]
        self.base_history = copy.deepcopy(_history(nominal, root["base_history"]))
        self.design_pin = pin({"query_ids": list(self.query_ids),
                               "signatures": [list(s) for s in self.design_signatures]})
        self.scope_pin = pin({"nominal_pin": nominal.model_pin, "design_pin": self.design_pin,
                              "base_history": self.base_history})
        acquired = {row["query_id"] for row in self.base_history}
        remaining = sorted(set(self.query_ids) - acquired)
        self.residual_cost = sum(nominal.queries[qid]["cost"] for qid in remaining)
        require(root["nominal_pin"] == nominal.model_pin and root["design_pin"] == self.design_pin
                and root["scope_pin"] == self.scope_pin and root["query_ids"] == list(self.query_ids)
                and root["remaining_actions"] == remaining and root["residual_cost"] == self.residual_cost,
                "Saved E root model/envelope/history/catalogue pins disagree")
        require(root["nominal_mask"] == hex(nominal.compatible(self.base_history))
                and root["design_mask"] == hex(self._mask(self.base_history)), "Saved E root support masks disagree")
        self._states = {row["state_id"]: row for row in self.saved["states"]}
        self._budgets = {row["budget"]: row for row in self.saved["budget_frontiers"]}
        require(len(self._states) == len(self.saved["states"])
                and len(self._budgets) == len(self.saved["budget_frontiers"]),
                "Saved E has duplicate state or allowance rows")

    def _mask(self, history):
        positions = {qid: i for i, qid in enumerate(self.query_ids)}
        mask = sum(1 << i for i, signature in enumerate(self.design_signatures)
                   if all(signature[positions[h["query_id"]]] == h["outcome_id"] for h in history))
        require(bool(mask), "Paid history has empty saved E design support")
        return mask

    def _state(self, identifier, history, remaining_budget):
        require(identifier in self._states, "Saved E child state is absent")
        state = self._states[identifier]
        nominal_mask, design_mask = self.nominal.compatible(history), self._mask(history)
        remaining = tuple(sorted(set(self.query_ids) - {h["query_id"] for h in history}))
        expected = state_id(self.scope_pin, nominal_mask, design_mask, remaining, remaining_budget)
        require(identifier == expected and state["nominal_mask"] == hex(nominal_mask)
                and state["design_mask"] == hex(design_mask)
                and state["remaining_actions"] == list(remaining)
                and state["budget"] == remaining_budget
                and state["terminal_conflict"] == (not bool(nominal_mask)),
                "Saved E backpointer state does not match paid history and remaining allowance")
        return state

    def choose(self, history, remaining_budget):
        require(type(remaining_budget) is int and remaining_budget >= 0, "Invalid saved E remaining allowance")
        history = _history(self.nominal, history)
        require(history[:len(self.base_history)] == self.base_history, "Saved E history does not extend H0")
        suffix = history[len(self.base_history):]
        spent = sum(self.nominal.queries[row["query_id"]]["cost"] for row in suffix)
        allowance = spent + remaining_budget
        require(allowance in self._budgets, "Saved E has no original allowance row")
        root = self._budgets[allowance]
        prefix, residual = copy.deepcopy(self.base_history), allowance
        state = self._state(root["state_id"], prefix, residual)
        point = root["canonical_point"]
        require(root["frontier"] == state["frontier"] and point == state["frontier"][0],
                "Saved E canonical point is not its retained root choice")
        for observed in suffix:
            choice = point["choice"]
            require(choice["action"] == observed["query_id"], "Paid path departs from saved E choice")
            require(bool(self.nominal.compatible(prefix)), "Saved E path continues after first conflict")
            children = [child for child in choice["children"] if child["outcome"] == observed["outcome_id"]]
            require(len(children) == 1, "Saved E backpointer omits or repeats a paid outcome")
            child = children[0]
            residual -= self.nominal.queries[observed["query_id"]]["cost"]
            require(residual >= 0, "Saved E path exceeds its original allowance")
            prefix.append(observed)
            state = self._state(child["state_id"], prefix, residual)
            selected = [candidate for candidate in state["frontier"]
                        if (candidate["d"], candidate["l"]) == (child["d"], child["l"])]
            require(len(selected) == 1, "Saved E child point is absent or ambiguous")
            point = selected[0]
        action = point["choice"]["action"]
        if not self.nominal.compatible(history):
            require(action is None, "Saved E continues acquisition after a conflict")
        if action is not None:
            require(action in state["remaining_actions"]
                    and self.nominal.queries[action]["cost"] <= remaining_budget,
                    "Saved E selects a repeated or unaffordable action")
        return action


def execute_audit(nominal, baseline, signature, arm, budget, *, support, saved_e,
                  joint_planner=None, certificate_cache=None):
    """One paid session with an unchanged H0 and one original extra allowance."""
    started = perf_counter()
    require(arm in ARMS, "Unknown joint-study arm")
    cache = _certificate_cache(certificate_cache)
    baseline, base_cost, base_bytes = validate_baseline(nominal, baseline, certificate_cache=cache)
    base_history = copy.deepcopy(baseline["history"])
    history = copy.deepcopy(base_history)
    require(support.nominal is nominal and support.base_history == base_history
            and support.proposal == baseline["status"], "Executor support contract is bound to a different root")
    require(saved_e.nominal is nominal and saved_e.base_history == base_history
            and saved_e.design_signatures == support.design_signatures,
            "Executor saved E is bound to a different model/root/envelope")
    residual_cost = saved_e.residual_cost
    require(type(budget) is int and 0 <= budget <= residual_cost, "Integer audit allowance outside root bounds")
    if arm == "joint_frontier":
        require(joint_planner is not None and joint_planner.nominal is nominal
                and joint_planner.support is support and joint_planner.base_history == base_history,
                "Joint executor requires its bound support planner")
        require(joint_planner.status == "complete", "Joint root unavailable or not fully solved")
    else:
        require(joint_planner is None, "Only the joint policy may receive the joint planner")
    support.mask(history)
    archive = PassiveAuditArchive(nominal, signature, initial_history=base_history)
    state = nominal.compatible(history)
    checking_seconds, selection_seconds = perf_counter() - started, 0.0
    added_cost = added_bytes = aliases = 0
    base_ids = {row["query_id"] for row in base_history}
    seen_records = {nominal.queries[qid]["record_id"] for qid in base_ids}
    phases = {name: {"history": [], "cost": 0, "returned_bytes": 0} for name in ("detection", "support", "joint")}
    phase = "joint" if arm == "joint_frontier" else "detection"
    transition = first_conflict = None
    while True:
        require(bool(state), "Unreported nominal conflict")
        started = perf_counter()
        remaining_budget = budget - added_cost
        if phase == "detection":
            action = saved_e.choose(history, remaining_budget)
            if action is None and arm == "E_then_support":
                transition = copy.deepcopy(history)
                phase = "support"
        elif phase == "joint":
            action = joint_planner.choose(history, remaining_budget)
        if phase == "support":
            mask = support.mask(history)
            if support.proposal not in DEFINITE:
                termination, action = "support_not_definite", None
            elif support.supported(mask):
                termination, action = "proposal_supported", None
            elif not support.attainable(mask):
                termination, action = "support_unattainable", None
            else:
                acquired = {row["query_id"] for row in history}
                affordable = [qid for qid in nominal.query_ids if qid not in acquired
                              and nominal.queries[qid]["cost"] <= remaining_budget]
                action = min(affordable, key=lambda qid: (nominal.queries[qid]["cost"], qid)) if affordable else None
                termination = "no_affordable_support_action"
        selection_seconds += perf_counter() - started
        if action is None:
            if phase != "support":
                termination = "catalogue_exhausted" if len(history) == len(nominal.query_ids) else (
                    "exact_policy_stop" if phase == "detection" else "joint_policy_stop")
            break
        require(action in nominal.queries and action not in {row["query_id"] for row in history},
                "Policy selected a repeated or unknown catalogue action")
        query = nominal.queries[action]
        require(query["cost"] <= remaining_budget, "Policy selected an unaffordable action")
        predicted = sorted(outcome for outcome, branch in nominal.partition(state, action).items() if branch)
        returned = archive(action)
        started = perf_counter()
        outcome = returned.get("outcome_id")
        require(returned.get("query_id") == action and outcome in query["outcomes"], "Paid archive returned an undeclared answer")
        size = len(canonical(query["outcomes"][outcome]))
        require(returned.get("cost") == query["cost"] and returned.get("canonical_bytes") == size
                and canonical(returned.get("observable")) == canonical(query["outcomes"][outcome]),
                "Paid archive observable or accounting mismatch")
        row = {"query_id": action, "outcome_id": outcome}
        history.append(row)
        added_cost += query["cost"]
        added_bytes += size
        phases[phase]["history"].append(copy.deepcopy(row))
        phases[phase]["cost"] += query["cost"]
        phases[phase]["returned_bytes"] += size
        aliases += query["record_id"] in seen_records
        seen_records.add(query["record_id"])
        state = nominal.compatible(history)
        support.mask(history)  # Empty physical compatibility is a failure, never a proof.
        checking_seconds += perf_counter() - started
        if not state:
            first_conflict = {"added_query_index": len(history) - len(base_history), "added_cost": added_cost,
                              "total_cost": base_cost + added_cost, "query_id": action, "outcome_id": outcome,
                              "nominal_outcomes_before": predicted}
            termination = "nominal_conflict"
            break
    alarm = first_conflict is not None
    final_pin = cache.get(nominal, history)
    require((cache.certificates[final_pin]["status"] == "inconsistent") == alarm,
            "Alarm and unchanged nominal contradiction certificate disagree")
    require(archive.history == history[len(base_history):] and archive.cost == added_cost
            and archive.returned_bytes == added_bytes, "Private archive and execution accounting disagree")
    result = {
        "arm": arm, "budget_percent": None, "integer_budget": budget, "audit_budget": budget,
        "residual_cost": residual_cost, "base_history": base_history, "history": history,
        "audit_history": copy.deepcopy(history[len(base_history):]), "base_cost": base_cost,
        "added_cost": added_cost, "total_cost": base_cost + added_cost,
        "base_query_count": len(base_history), "added_query_count": len(history) - len(base_history),
        "total_query_count": len(history), "base_returned_bytes": base_bytes,
        "added_returned_bytes": added_bytes, "total_returned_bytes": base_bytes + added_bytes,
        "status": "nominal_model_conflict" if alarm else "no_conflict_observed",
        "termination_reason": termination, "next_query": None, "first_conflict": first_conflict,
        "original_proposal": baseline["status"], "proposal_withheld": alarm and baseline["status"] in DEFINITE,
        "baseline_certificate": copy.deepcopy(baseline["certificate"]), "nominal_certificate_pin": final_pin,
        "coverage": {"catalogue_actions": len(nominal.query_ids), "base_actions": len(base_history),
                     "audited_actions": len(history) - len(base_history), "total_acquired_actions": len(history),
                     "remaining_actions": len(nominal.query_ids) - len(history),
                     "complete": len(history) == len(nominal.query_ids),
                     "distinct_record_ids_queried": len(seen_records), "added_alias_queries": aliases},
        "phase_histories": {name: values["history"] for name, values in phases.items()},
        "sequential_transition_history": transition, "saved_e_solver_pin": saved_e.saved_solver_pin,
        "selection_seconds": selection_seconds, "checking_seconds": checking_seconds,
    }
    for name, values in phases.items():
        result.update({name + "_phase_cost": values["cost"],
                       name + "_phase_query_count": len(values["history"]),
                       name + "_phase_returned_bytes": values["returned_bytes"]})
    return result
