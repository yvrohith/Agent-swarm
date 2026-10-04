"""Paid integer-budget execution and retrospective minimum contradictions.

The original audit selectors and passive archive remain unchanged. Actual
signatures enter only the archive constructor and hindsight/evaluator functions;
prospective selectors receive declared hypotheses, paid history and budget.
"""
from __future__ import annotations

import copy
from itertools import combinations
from time import perf_counter

from studies.audit_aware_acquisition.analysis import CertificateCache
from studies.audit_aware_acquisition.auditing import (
    AuditSelector,
    PassiveAuditArchive,
    _baseline,
    _history,
    _signature,
)
from tracebench.evidence_acquisition.model import canonical, indices, pin

ORIGINAL_ARMS = ("no_audit", "cost_order", "constant_first", "closure_informed")
ARMS = (*ORIGINAL_ARMS, "closure_informed_affordable", "exact_frontier")
BASELINE_FIELDS = ("history", "cost", "query_count", "returned_bytes", "status",
                   "certificate", "certificate_valid")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _certificate_cache(cache):
    cache = CertificateCache() if cache is None else cache
    require(isinstance(cache, CertificateCache), "Certificate cache must use the unchanged checker-backed implementation")
    return cache


def validate_baseline(nominal, baseline, *, certificate_cache=None):
    """Bind the saved paid proposal to exact certificate bytes and accounting."""
    projected = {key: copy.deepcopy(baseline[key]) for key in BASELINE_FIELDS}
    require(projected["certificate_valid"] is True, "Original stopping certificate is unverified")
    cache = _certificate_cache(certificate_cache)
    certificate_id = cache.get(nominal, _history(nominal, projected["history"]))
    certificate = cache.certificates[certificate_id]
    expected = projected["certificate"]
    require(certificate_id == expected if isinstance(expected, str)
            else canonical(certificate) == canonical(expected),
            "Saved original nominal certificate reference/bytes mismatch")
    # Only after checker-backed validation may the old accounting guard use
    # a compact reference instead of repeating verification of literal bytes.
    history, cost, size = _baseline(nominal, {**projected, "certificate": certificate_id})
    return projected, cost, size


def root_identity(nominal, history, design_signatures):
    """A root binds the nominal contract, common fixed envelope and paid H0."""
    design = tuple(sorted(set(map(tuple, design_signatures))))
    identity = {"nominal_model_pin": nominal.model_pin,
                "design_signature_set_pin": pin(design), "base_history": copy.deepcopy(history)}
    return {**identity, "root_pin": pin(identity), "root_id": "audit_root_" + pin(identity)[:24]}


def verify_roots(nominal, design_signatures, saved_rows, *, certificate_cache=None):
    """Validate all saved H0 paths and the exact envelope partition they induce.

    The original optimizer is not rerun. Its independently verified retained
    histories define a deterministic prefix/action table, which is replayed on
    every hypothetical signature. The rows must cover the envelope exactly once.
    """
    design_selector = AuditSelector(nominal, "closure_informed", design_signatures)
    design = design_selector.design_signatures
    rows = {}
    for row in saved_rows:
        signature = _signature(nominal, row["outcomes"])
        require(signature not in rows, "Duplicate saved stopping signature")
        rows[signature] = row
    require(set(rows) == set(design), "Saved stopping histories do not cover the entire fixed envelope")
    cache = _certificate_cache(certificate_cache)
    checked_paths, grouped, actions = {}, {}, {}
    for signature in design:
        baseline, _, _ = validate_baseline(nominal, rows[signature]["policy"], certificate_cache=cache)
        history = baseline["history"]
        answers = dict(zip(nominal.query_ids, signature, strict=True))
        require(all(answers[h["query_id"]] == h["outcome_id"] for h in history),
                "Saved H0 contains an answer inconsistent with its signature")
        history_key = canonical(history)
        if history_key not in checked_paths:
            prefix = []
            for observed in history:
                state = nominal.compatible(prefix)
                require(bool(state) and nominal.terminal(state) is None,
                        "Saved original path continues after a nominal terminal state")
                key, action = canonical(prefix), observed["query_id"]
                require(key not in actions or actions[key] == action,
                        "Saved original paths disagree on a prefix action/STOP")
                actions[key] = action
                prefix.append(observed)
            key = canonical(prefix)
            require(key not in actions or actions[key] is None,
                    "Saved original paths disagree on a prefix action/STOP")
            actions[key] = None
            checked_paths[history_key] = baseline
        require(canonical(checked_paths[history_key]) == canonical(baseline),
                "Identical paid histories have different original stopping metadata")
        grouped.setdefault(history_key, []).append(signature)
    for signature in design:
        answers = dict(zip(nominal.query_ids, signature, strict=True))
        prefix = []
        while True:
            require(canonical(prefix) in actions, "Saved original tree omits a compatible envelope branch")
            action = actions[canonical(prefix)]
            if action is None:
                break
            require(action not in {h["query_id"] for h in prefix}, "Saved original tree repeats an action")
            prefix.append({"query_id": action, "outcome_id": answers[action]})
        require(prefix == rows[signature]["policy"]["history"],
                "A compatible signature follows a different original stopping path")
    roots = []
    for history_key, observed in sorted(grouped.items()):
        baseline = checked_paths[history_key]
        history = baseline["history"]
        positions = {qid: index for index, qid in enumerate(nominal.query_ids)}
        possible = {s for s in design if all(s[positions[h["query_id"]]] == h["outcome_id"] for h in history)}
        require(possible == set(observed),
                "H0 grouping excludes compatible signatures with a different saved stopping path")
        acquired = {h["query_id"] for h in history}
        remaining = [qid for qid in nominal.query_ids if qid not in acquired]
        identity = root_identity(nominal, history, design)
        roots.append({**identity, "baseline": baseline, "signatures": [list(s) for s in sorted(possible)],
                      "root_signature_set_pin": pin(tuple(sorted(possible))),
                      "signature_count": len(possible),
                      "original_signature_count": len(possible & nominal.signature_cells.keys()),
                      "new_signature_count": len(possible - nominal.signature_cells.keys()),
                      "unqueried_query_ids": remaining,
                      "residual_cost": sum(nominal.queries[qid]["cost"] for qid in remaining),
                      "original_path_verified": True,
                      "path_verification_scope": "Replay of independently verified retained deterministic H0 tree; original optimizer not rerun"})
    require(sum(root["signature_count"] for root in roots) == len(design),
            "Root grouping does not partition the distinct-signature envelope")
    return roots


class IntegerSelector:
    """Prospective selector: no actual archive, omission condition or truth input."""

    def __init__(self, nominal, arm, design_signatures=None, planner=None):
        require(arm in ARMS, "Unknown frontier-study arm")
        self.nominal, self.arm, self.planner = nominal, arm, planner
        underlying = "closure_informed" if arm in {"closure_informed_affordable", "exact_frontier"} else arm
        self.original = AuditSelector(nominal, underlying, design_signatures)
        if arm == "exact_frontier":
            require(planner is not None and planner.nominal is nominal,
                    "Exact policy requires its bound original nominal model")
            require(tuple(planner.design_signatures) == self.original.design_signatures,
                    "Exact planner and executor use different fixed envelopes")
        else:
            require(planner is None, "Only exact_frontier may receive an exact planner")

    def validate_history(self, history):
        return self.original.validate_history(history)

    def choose(self, history, remaining_budget):
        require(type(remaining_budget) is int and remaining_budget >= 0, "Invalid remaining hard budget")
        history = _history(self.nominal, history)
        state = self.validate_history(history)
        if not state:
            return None
        if self.arm in ORIGINAL_ARMS:
            return self.original.choose(history)
        if self.arm == "exact_frontier":
            return self.planner.choose(history, remaining_budget)
        queried = {h["query_id"] for h in history}
        affordable = [qid for qid, query in self.nominal.queries.items()
                      if qid not in queried and query["cost"] <= remaining_budget]
        if not affordable:
            return None
        scores = self.original.detection_scores(history)
        positive = [qid for qid in affordable if scores[qid] > 0]
        def cost_key(qid):
            return self.nominal.queries[qid]["cost"], qid
        if positive:
            return min(positive, key=lambda qid: (-scores[qid], *cost_key(qid)))
        constants = [qid for qid in affordable
                     if len([part for part in self.nominal.partition(state, qid).values() if part]) == 1]
        return min(constants or affordable, key=cost_key)


def execute_audit(nominal, baseline, signature, arm, budget, *, design_signatures=None,
                  planner=None, certificate_cache=None):
    """Execute one prospective policy through the unchanged charged archive.

    Budget is an integer amount of additional retrieval, not a percentage. The
    returned fields retain the old evaluator's support-classification interface.
    """
    started = perf_counter()
    cache = _certificate_cache(certificate_cache)
    baseline, base_cost, base_bytes = validate_baseline(nominal, baseline, certificate_cache=cache)
    history = copy.deepcopy(baseline["history"])
    base_history = copy.deepcopy(history)
    base_ids = {row["query_id"] for row in history}
    remaining_ids = tuple(qid for qid in nominal.query_ids if qid not in base_ids)
    residual_cost = sum(nominal.queries[qid]["cost"] for qid in remaining_ids)
    require(type(budget) is int and 0 <= budget <= residual_cost, "Integer audit budget outside root bounds")
    selector = IntegerSelector(nominal, arm, design_signatures, planner)
    if arm == "exact_frontier":
        require(planner.base_history == base_history, "Exact planner is bound to a different paid root")
        require(planner.status == "complete", "Exact root unavailable or not fully solved")
    archive = PassiveAuditArchive(nominal, signature, initial_history=base_history)
    state = selector.validate_history(history)
    checking_seconds, selection_seconds = perf_counter() - started, 0.0
    added_cost = added_bytes = aliases = 0
    seen_records = {nominal.queries[qid]["record_id"] for qid in base_ids}
    first_conflict = next_query = None
    if arm == "no_audit":
        termination = "baseline_no_audit"
    else:
        while True:
            require(bool(state), "Unreported nominal conflict")
            started = perf_counter()
            query_id = selector.choose(history, budget - added_cost)
            selection_seconds += perf_counter() - started
            if query_id is None:
                if len(history) == len(nominal.query_ids):
                    termination = "catalogue_exhausted"
                elif arm == "closure_informed_affordable":
                    termination = "no_affordable_action"
                elif arm == "exact_frontier":
                    termination = "exact_policy_stop"
                else:
                    raise ValueError("Original audit order stopped before catalogue exhaustion")
                break
            require(query_id in remaining_ids and query_id not in {h["query_id"] for h in history},
                    "Audit selected a repeated or unknown catalogue action")
            query = nominal.queries[query_id]
            if added_cost + query["cost"] > budget:
                require(arm in ORIGINAL_ARMS, "Budget-aware policy selected an unaffordable action")
                termination, next_query = "next_action_unaffordable", query_id
                break
            predicted = sorted(outcome for outcome, branch in nominal.partition(state, query_id).items() if branch)
            returned = archive(query_id)
            started = perf_counter()
            outcome = returned.get("outcome_id")
            require(returned.get("query_id") == query_id and outcome in query["outcomes"],
                    "Paid archive returned an undeclared answer")
            size = len(canonical(query["outcomes"][outcome]))
            require(returned.get("cost") == query["cost"] and returned.get("canonical_bytes") == size
                    and canonical(returned.get("observable")) == canonical(query["outcomes"][outcome]),
                    "Paid archive observable or accounting mismatch")
            added_cost += query["cost"]
            added_bytes += size
            record_id = query["record_id"]
            aliases += record_id in seen_records
            seen_records.add(record_id)
            history.append({"query_id": query_id, "outcome_id": outcome})
            state = nominal.compatible(history)
            selector.validate_history(history)  # Also check the fixed envelope after a final alarm.
            checking_seconds += perf_counter() - started
            if not state:
                first_conflict = {"added_query_index": len(history) - len(base_history),
                                  "added_cost": added_cost, "total_cost": base_cost + added_cost,
                                  "query_id": query_id, "outcome_id": outcome,
                                  "nominal_outcomes_before": predicted}
                termination = "nominal_conflict"
                break
    alarm = first_conflict is not None
    final_certificate_pin = cache.get(nominal, history)
    nominal_certificate = cache.certificates[final_certificate_pin]
    require((nominal_certificate["status"] == "inconsistent") == alarm,
            "Alarm and nominal contradiction certificate disagree")
    return {
        "arm": arm, "budget_percent": None, "integer_budget": budget,
        "audit_budget": budget, "residual_cost": residual_cost,
        "base_history": base_history, "history": history, "audit_history": copy.deepcopy(history[len(base_history):]),
        "base_cost": base_cost, "added_cost": added_cost, "total_cost": base_cost + added_cost,
        "base_query_count": len(base_history), "added_query_count": len(history) - len(base_history),
        "total_query_count": len(history), "base_returned_bytes": base_bytes,
        "added_returned_bytes": added_bytes, "total_returned_bytes": base_bytes + added_bytes,
        "status": "nominal_model_conflict" if alarm else "no_conflict_observed",
        "termination_reason": termination, "next_query": next_query,
        "first_conflict": first_conflict, "original_proposal": baseline["status"],
        "proposal_withheld": alarm and baseline["status"] in {"established", "ruled_out"},
        "baseline_certificate": copy.deepcopy(baseline["certificate"]),
        "nominal_certificate_pin": final_certificate_pin,
        "coverage": {"catalogue_actions": len(nominal.query_ids), "base_actions": len(base_history),
                     "audited_actions": len(history) - len(base_history), "total_acquired_actions": len(history),
                     "remaining_actions": len(nominal.query_ids) - len(history),
                     "complete": len(history) == len(nominal.query_ids),
                     "distinct_record_ids_queried": len(seen_records), "added_alias_queries": aliases},
        "selection_seconds": selection_seconds, "checking_seconds": checking_seconds,
    }


def hindsight(nominal, root, signature, *, certificate_cache=None):
    """Exact retrospective minimum contradiction subset; never a policy input."""
    signature = _signature(nominal, signature)
    cache = _certificate_cache(certificate_cache)
    history = copy.deepcopy(_history(nominal, root["base_history"]))
    require(root["nominal_model_pin"] == nominal.model_pin, "Hindsight root names a different nominal model")
    identity = {"nominal_model_pin": nominal.model_pin,
                "design_signature_set_pin": root["design_signature_set_pin"], "base_history": history}
    require(root["root_pin"] == pin(identity) and root["root_id"] == "audit_root_" + pin(identity)[:24],
            "Hindsight root identity pin mismatch")
    require(root["root_signature_set_pin"] == pin(tuple(sorted(set(map(tuple, root["signatures"]))))),
            "Hindsight root signature-set pin mismatch")
    require(signature in set(map(tuple, root["signatures"])), "Signature is outside this paid root")
    answers = dict(zip(nominal.query_ids, signature, strict=True))
    require(all(answers[h["query_id"]] == h["outcome_id"] for h in history), "Signature contradicts paid H0")
    state = nominal.compatible(history)
    require(bool(state), "Preserved H0 must have nonempty nominal support")
    remaining = sorted(set(nominal.query_ids) - {h["query_id"] for h in history})
    common = {"schema_version": 1, "nominal_model_pin": nominal.model_pin,
              "root_pin": root["root_pin"], "root_id": root["root_id"],
              "base_history": history, "full_signature": list(signature), "signature_pin": pin(signature),
              "interpretation": "Retrospective catalogue subset; not an unpaid prospective hint"}
    full = history + [{"query_id": qid, "outcome_id": answers[qid]} for qid in remaining]
    if nominal.compatible(full):
        return {**common, "status": "unavailable", "reason": "no_catalogue_contradiction",
                "minimum_cost": None, "cardinality": None, "query_ids": None,
                "additional_history": None, "typed_observations": None,
                "nominal_world_coverage": None, "certificate": None, "certificate_pin": None,
                "subsets_checked": 0}
    candidates = sorted((sum(nominal.queries[qid]["cost"] for qid in subset), len(subset), subset)
                        for count in range(len(remaining) + 1) for subset in combinations(remaining, count))
    for checked, (cost, count, subset) in enumerate(candidates, 1):
        extra = [{"query_id": qid, "outcome_id": answers[qid]} for qid in subset]
        if nominal.compatible(history + extra):
            continue
        certificate_pin = cache.get(nominal, history + extra)
        certificate = cache.certificates[certificate_pin]
        require(certificate["status"] == "inconsistent",
                "Minimum subset lacks a verified nominal contradiction certificate")
        coverage = []
        for index in indices(state):
            disagree = [qid for qid in subset if nominal.answers[index][nominal.query_ids.index(qid)] != answers[qid]]
            require(bool(disagree), "Contradiction subset leaves an uncovered nominal world")
            coverage.append({"world_id": nominal.worlds[index]["id"], "world_index": index,
                             "disagreed_query_ids": disagree})
        observations = [{**row, "record_id": nominal.queries[row["query_id"]]["record_id"],
                         "cost": nominal.queries[row["query_id"]]["cost"],
                         "observable": copy.deepcopy(nominal.queries[row["query_id"]]["outcomes"][row["outcome_id"]])}
                        for row in extra]
        return {**common, "status": "available", "reason": None,
                "minimum_cost": cost, "cardinality": count, "query_ids": list(subset),
                "additional_history": extra, "typed_observations": observations,
                "nominal_world_coverage": coverage, "certificate": certificate,
                "certificate_pin": certificate_pin, "subsets_checked": checked}
    raise ValueError("New full signature lacks its own exhaustive contradiction subset")
