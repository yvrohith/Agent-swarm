"""Four fixed paid audit orders after a retained nominal stopping proposal.

Selection sees only the nominal hypothesis space and paid history. The informed
arm additionally receives distinct hypothetical signatures of a fixed k=2
closure. Actual signatures live only in the private lookup/evaluator boundary.
"""
from __future__ import annotations

import copy
from fractions import Fraction
from time import perf_counter

from tracebench.evidence_acquisition.model import canonical

ARMS = ("no_audit", "cost_order", "constant_first", "closure_informed")
BUDGET_PERCENTAGES = (0, 25, 50, 100)
DEFINITE = {"established", "ruled_out"}


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def _query_ids(nominal):
    return tuple(nominal.queries)


def _history(nominal, history):
    history = list(history)
    _check(all(isinstance(row, dict) and set(row) == {"query_id", "outcome_id"}
               for row in history), "malformed paid history")
    ids = [row["query_id"] for row in history]
    _check(len(ids) == len(set(ids)), "catalogue action was queried more than once")
    for row in history:
        qid, outcome = row["query_id"], row["outcome_id"]
        _check(qid in nominal.queries and outcome in nominal.queries[qid]["outcomes"],
               "paid history contains unknown action/outcome")
    return history


def _signature(nominal, signature):
    signature = tuple(signature)
    qids = _query_ids(nominal)
    _check(len(signature) == len(qids), "signature does not cover the original catalogue")
    by_record = {}
    for qid, outcome in zip(qids, signature, strict=True):
        query = nominal.queries[qid]
        _check(outcome in query["outcomes"], "signature contains an undeclared outcome")
        record_id = query.get("record_id", qid)
        _check(record_id not in by_record or by_record[record_id] == outcome,
               "physical aliases have inconsistent observable answers")
        by_record[record_id] = outcome
    return signature


class AuditSelector:
    """History-only selection. No k, budget, actual archive, or truth input.

    No cross-run choice cache is used. The fixed design tuple is deduplicated:
    neither nominal parent multiplicity nor omission provenance is available.
    """

    def __init__(self, nominal, arm, design_signatures=None):
        _check(arm in ARMS, "unknown audit arm")
        _check(0 < len(nominal.queries) <= 8, "audit catalogue exceeds frozen bounds")
        _check(all(type(q["cost"]) is int and q["cost"] > 0 and len(q["outcomes"]) <= 2
                   for q in nominal.queries.values()), "invalid audit cost/outcome catalogue")
        self.nominal = nominal
        self.arm = arm
        self.query_ids = _query_ids(nominal)
        if arm == "closure_informed":
            _check(design_signatures is not None, "closure_informed requires fixed design signatures")
            signatures = {_signature(nominal, signature) for signature in design_signatures}
            _check(0 < len(signatures) <= 256, "fixed design signature cap exceeded or envelope empty")
            _check(set(nominal.signature_cells) <= signatures, "fixed design envelope omits nominal support")
            self.design_signatures = tuple(sorted(signatures))
        else:
            _check(design_signatures is None, "nominal-only auditor cannot receive an expanded design envelope")
            self.design_signatures = None

    def _remaining(self, history):
        queried = {row["query_id"] for row in history}
        return tuple(qid for qid in self.query_ids if qid not in queried)

    def _design_compatible(self, history):
        _check(self.design_signatures is not None, "arm has no expanded design envelope")
        positions = {qid: index for index, qid in enumerate(self.query_ids)}
        signatures = tuple(signature for signature in self.design_signatures
                           if all(signature[positions[row["query_id"]]] == row["outcome_id"]
                                  for row in history))
        _check(bool(signatures), "paid history has empty fixed k=2 design-envelope compatibility")
        return signatures

    def validate_history(self, history):
        history = _history(self.nominal, history)
        if self.arm == "closure_informed":
            self._design_compatible(history)
        return self.nominal.compatible(history)

    def _cost_key(self, qid):
        return self.nominal.queries[qid]["cost"], qid

    def _constant_first(self, state, remaining):
        constants = [qid for qid in remaining
                     if len([cell for cell in self.nominal.partition(state, qid).values() if cell]) == 1]
        return min(constants or remaining, key=self._cost_key) if remaining else None

    def detection_scores(self, history):
        _check(self.arm == "closure_informed", "detection scores belong only to closure_informed")
        history = _history(self.nominal, history)
        signatures = self._design_compatible(history)
        state = self.nominal.compatible(history)
        _check(bool(state), "detection scoring requires nonempty nominal support")
        scores = {}
        for qid in self._remaining(history):
            position = self.query_ids.index(qid)
            branches = self.nominal.partition(state, qid)
            conflicting = sum(not branches.get(signature[position], 0) for signature in signatures)
            scores[qid] = Fraction(conflicting, self.nominal.queries[qid]["cost"])
        return scores

    def choose(self, history):
        history = _history(self.nominal, history)
        state = self.validate_history(history)
        remaining = self._remaining(history)
        if self.arm == "no_audit" or not state or not remaining:
            return None
        if self.arm == "cost_order":
            return min(remaining, key=self._cost_key)
        if self.arm == "constant_first":
            return self._constant_first(state, remaining)
        scores = self.detection_scores(history)
        positive = [qid for qid in remaining if scores[qid] > 0]
        if positive:
            return min(positive, key=lambda qid: (-scores[qid], *self._cost_key(qid)))
        return self._constant_first(state, remaining)


class PassiveAuditArchive:
    """Charge retrieval before exposing an answer; actual signature stays private.

    Initial history is already paid and cannot be queried again. Public counters
    cover additional retrieval only. The selector never receives this object.
    This boundary prevents accidental data flow, not arbitrary Python introspection.
    """

    def __init__(self, nominal, signature, initial_history=()):
        signature = _signature(nominal, signature)
        self._nominal = nominal
        self._answers = dict(zip(_query_ids(nominal), signature, strict=True))
        initial_history = _history(nominal, initial_history)
        _check(all(self._answers[row["query_id"]] == row["outcome_id"] for row in initial_history),
               "actual archive contradicts the supplied nominal stopping history")
        self._queried = {row["query_id"] for row in initial_history}
        self.history = []
        self.cost = self.returned_bytes = 0

    def __call__(self, query_id):
        _check(query_id in self._answers and query_id not in self._queried,
               "unknown or repeated paid audit lookup")
        query = self._nominal.queries[query_id]
        outcome = self._answers[query_id]
        observable = copy.deepcopy(query["outcomes"][outcome])
        size = len(canonical(observable))
        self.cost += query["cost"]
        self.returned_bytes += size
        self._queried.add(query_id)
        self.history.append({"query_id": query_id, "outcome_id": outcome})
        return {"query_id": query_id, "outcome_id": outcome, "observable": observable,
                "cost": query["cost"], "canonical_bytes": size}


def _baseline(nominal, baseline):
    history = copy.deepcopy(_history(nominal, baseline["history"]))
    state = nominal.compatible(history)
    _check(bool(state), "audit requires a consistent original nominal stopping proposal")
    status = nominal.terminal(state)
    _check(status in {*DEFINITE, "archive_irreducible"} and baseline["status"] == status,
           "base history is not the original nominal terminal proposal")
    cost = sum(nominal.queries[row["query_id"]]["cost"] for row in history)
    byte_count = sum(len(canonical(nominal.queries[row["query_id"]]["outcomes"][row["outcome_id"]]))
                     for row in history)
    _check((baseline["cost"], baseline["query_count"], baseline["returned_bytes"])
           == (cost, len(history), byte_count), "base retrieval accounting mismatch")
    certificate = baseline["certificate"]
    if isinstance(certificate, dict):
        _check(nominal.verify_certificate(certificate) and certificate["history"] == history,
               "invalid original nominal certificate")
    else:
        # The driver verifies referenced retained bytes once per distinct pin.
        # A hash alone is not evidence access or independent validation.
        _check(isinstance(certificate, str) and len(certificate) == 64
               and all(char in "0123456789abcdef" for char in certificate)
               and baseline.get("certificate_valid") is True,
               "unverified or malformed retained certificate reference")
    return history, cost, byte_count


def audit(nominal, baseline, lookup, selector, budget_percent):
    """Budget-censor a fixed audit order; budget never enters query selection.

    Expanded warrant is deliberately absent here: a separate evaluator checks
    the same final paid history under the actual evaluation contract.
    """
    _check(selector.nominal is nominal, "audit selector/model identity mismatch")
    _check(type(budget_percent) is int and budget_percent in BUDGET_PERCENTAGES,
           "audit budget outside the frozen levels")
    started = perf_counter()
    base_history, base_cost, base_bytes = _baseline(nominal, baseline)
    history = copy.deepcopy(base_history)
    base_ids = {row["query_id"] for row in base_history}
    residual_ids = tuple(qid for qid in nominal.queries if qid not in base_ids)
    residual_cost = sum(nominal.queries[qid]["cost"] for qid in residual_ids)
    budget = residual_cost * budget_percent // 100
    state = selector.validate_history(history)
    checking_seconds = perf_counter() - started
    selection_seconds = 0.0
    added_cost = added_bytes = alias_count = 0
    first_conflict = next_query = None
    seen_records = {nominal.queries[qid].get("record_id", qid) for qid in base_ids}
    if selector.arm == "no_audit":
        termination = "baseline_no_audit"
    else:
        while True:
            _check(bool(state), "unreported nominal conflict")
            started = perf_counter()
            query_id = selector.choose(history)
            selection_seconds += perf_counter() - started
            if query_id is None:
                _check(len(history) == len(nominal.queries), "audit stopped early at a nominal terminal state")
                termination = "catalogue_exhausted"
                break
            _check(query_id in residual_ids and query_id not in {row["query_id"] for row in history},
                   "audit selected a repeated or noncatalogue query")
            query = nominal.queries[query_id]
            if added_cost + query["cost"] > budget:
                termination, next_query = "next_action_unaffordable", query_id
                break
            nominal_outcomes = sorted(outcome for outcome, cell in nominal.partition(state, query_id).items() if cell)
            returned = lookup(query_id)
            started = perf_counter()
            outcome = returned.get("outcome_id")
            _check(returned.get("query_id") == query_id and outcome in query["outcomes"],
                   "lookup returned a different or undeclared answer")
            payload = query["outcomes"][outcome]
            size = len(canonical(payload))
            _check(returned.get("cost") == query["cost"] and returned.get("canonical_bytes") == size
                   and canonical(returned.get("observable")) == canonical(payload),
                   "charged lookup payload/accounting mismatch")
            added_cost += query["cost"]
            added_bytes += size
            record_id = query.get("record_id", query_id)
            alias_count += record_id in seen_records
            seen_records.add(record_id)
            history.append({"query_id": query_id, "outcome_id": outcome})
            # Nominal compatibility is updated before any stopping decision.
            state = nominal.compatible(history)
            # The design envelope must still cover even a final conflicting answer.
            selector.validate_history(history)
            checking_seconds += perf_counter() - started
            if not state:
                first_conflict = {"added_query_index": len(history) - len(base_history),
                                  "added_cost": added_cost, "total_cost": base_cost + added_cost,
                                  "query_id": query_id, "outcome_id": outcome,
                                  "nominal_outcomes_before": nominal_outcomes}
                termination = "nominal_conflict"
                break
    alarm = first_conflict is not None
    added_history = copy.deepcopy(history[len(base_history):])
    return {
        "arm": selector.arm, "budget_percent": budget_percent,
        "audit_budget": budget, "residual_cost": residual_cost,
        "base_history": base_history, "history": history, "audit_history": added_history,
        "base_cost": base_cost, "added_cost": added_cost, "total_cost": base_cost + added_cost,
        "base_query_count": len(base_history), "added_query_count": len(added_history),
        "total_query_count": len(history), "base_returned_bytes": base_bytes,
        "added_returned_bytes": added_bytes, "total_returned_bytes": base_bytes + added_bytes,
        "status": "nominal_model_conflict" if alarm else "no_conflict_observed",
        "termination_reason": termination, "next_query": next_query,
        "first_conflict": first_conflict, "original_proposal": baseline["status"],
        "proposal_withheld": alarm and baseline["status"] in DEFINITE,
        "baseline_certificate": copy.deepcopy(baseline["certificate"]),
        "coverage": {"catalogue_actions": len(nominal.queries), "base_actions": len(base_history),
                     "audited_actions": len(added_history), "total_acquired_actions": len(history),
                     "remaining_actions": len(nominal.queries) - len(history),
                     "complete": len(history) == len(nominal.queries),
                     "distinct_record_ids_queried": len(seen_records),
                     "added_alias_queries": alias_count},
        "selection_seconds": selection_seconds, "checking_seconds": checking_seconds,
    }
