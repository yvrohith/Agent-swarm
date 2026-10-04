"""Support-preserving prior sensitivity using the frozen finite acquisition engine.

This module never generates problems or writes files. Callers freeze inputs and
source before executing evaluation; development uses the four retained problems.
"""
from __future__ import annotations

import copy
from collections import Counter
from fractions import Fraction
from time import perf_counter

from tracebench.evidence_acquisition.model import Model, canonical, indices, pin
from tracebench.evidence_acquisition.policies import (
    POLICIES,
    ChargedLookup,
    Planner,
    run_policy,
)

DISTRIBUTIONS = ("q0", "qS", "qT", "qMinus", "qPlus")
MODES = ("frozen_p0", "matched_q")
STATES = ("established", "ruled_out", "archive_irreducible")
EXACT_STATE_CAP = 100_000


def number(value):
    value = Fraction(value)
    return {"exact": str(value), "value": float(value)}


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def _weights(model, weights):
    values = tuple(Fraction(value) for value in weights)
    _check(len(values) == len(model.worlds) and all(value > 0 for value in values)
           and sum(values) == 1, "prior must normalize exactly with original positive support")
    return values


def record_presence(payload):
    """Count a typed retained record, including completeness; never empty wrappers.

    The frozen schema returns one record or lookup_empty per catalogue action.
    Multiple actions retrieving the same record each count once in b(w), as the
    specified perturbation is action-based rather than a unique-record count.
    """
    _check(isinstance(payload, dict), "outcome is not a typed observable object")
    kind = payload.get("kind")
    if kind == "lookup_empty":
        _check(set(payload) == {"kind", "scope"} and isinstance(payload["scope"], dict),
               "malformed empty-lookup wrapper")
        return False
    _check(kind in {"request_receipt", "delivery_receipt", "context_receipt",
                    "completeness", "archive_record"}, "unknown typed archive outcome")
    _check(isinstance(payload.get("id"), str) and bool(payload["id"])
           and payload.get("authenticated") is True and isinstance(payload.get("scope"), dict)
           and "time" in payload, "malformed retained record")
    if kind.endswith("_receipt"):
        _check(isinstance(payload.get("event_id"), str), "receipt lacks event identity")
    elif kind == "completeness":
        _check(payload.get("logging_complete") is True and payload.get("event_kind") == "context",
               "invalid completeness record")
    return True


def retained_action_counts(model):
    return tuple(sum(record_presence(model.queries[qid]["outcomes"][outcome])
                     for qid, outcome in zip(model.query_ids, signature, strict=True))
                 for signature in model.answers)


def signature_masses(model, weights):
    weights = _weights(model, weights)
    result = {signature: sum((weights[i] for i in indices(cell)), Fraction())
              for signature, cell in sorted(model.signature_cells.items())}
    _check(sum(result.values()) == 1, "signature mass omitted latent worlds")
    return result


def deployment_priors(model):
    original = _weights(model, model.priors)
    signature_sizes = Counter(model.answers)
    class_sizes = Counter(model.tau)
    counts = retained_action_counts(model)
    sparse = tuple(p * Fraction(1, 2 ** b) for p, b in zip(original, counts, strict=True))
    dense = tuple(p * 2 ** b for p, b in zip(original, counts, strict=True))
    result = {
        "q0": original,
        "qS": tuple(Fraction(1, len(signature_sizes) * signature_sizes[s]) for s in model.answers),
        "qT": tuple(Fraction(1, len(class_sizes) * class_sizes[t]) for t in model.tau),
        "qMinus": tuple(p / sum(sparse) for p in sparse),
        "qPlus": tuple(p / sum(dense) for p in dense),
    }
    for values in result.values():
        _weights(model, values)
        signature_masses(model, values)
    return result


def invariant_model(base, changed):
    """No support, label, observation or stopping change may accompany a prior."""
    left, right = copy.deepcopy(base.problem), copy.deepcopy(changed.problem)
    left.pop("prior")
    right.pop("prior")
    _check(canonical(left) == canonical(right), "prior change altered non-prior problem input")
    _check(base.worlds == changed.worlds and base.query_ids == changed.query_ids
           and base.queries == changed.queries and base.answers == changed.answers
           and base.signature_cells == changed.signature_cells
           and base.claim_values == changed.claim_values and base.tau == changed.tau
           and base.full_state == changed.full_state, "logical model changed under positive prior")
    _weights(changed, changed.priors)
    return True


def with_prior(model, weights):
    problem = copy.deepcopy(model.problem)
    problem["prior"] = [str(value) for value in _weights(model, weights)]
    changed = Model(problem)
    invariant_model(model, changed)
    return changed


class ExactStateCap(RuntimeError):
    """A stopped exact computation is unavailable, never certified optimal."""

    def __init__(self, state_cap, admitted_states):
        self.state_cap = state_cap
        self.admitted_states = admitted_states
        super().__init__(f"exact solve exceeded fixed cap of {state_cap} unique memoized states")


class IncompletePolicy(RuntimeError):
    """Retain finished paths and measured work when a new matched solve stops."""

    def __init__(self, error, trajectories, certificates, runtime):
        super().__init__(str(error))
        self.error = error
        self.trajectories = trajectories
        self.certificates = certificates
        self.runtime = runtime


class CappedPlanner(Planner):
    """Only intercept admission of normalized memo keys; recurrence and ties stay frozen."""

    def __init__(self, model, policy, state_cap=EXACT_STATE_CAP):
        _check(type(state_cap) is int and 0 < state_cap <= EXACT_STATE_CAP, "invalid exact state cap")
        super().__init__(model, policy)
        self.state_cap = state_cap
        self.capped_states = set()
        self.cap_reached = False

    def _solve(self, state, remaining):
        normalized = tuple(qid for qid in remaining
                           if len([cell for cell in self.model.partition(state, qid).values() if cell]) > 1)
        key = state, normalized
        if key not in self._values and key not in self.capped_states:
            if len(self.capped_states) >= self.state_cap:
                self.cap_reached = True
                raise ExactStateCap(self.state_cap, len(self.capped_states))
            self.capped_states.add(key)
        return super()._solve(state, remaining)


def _trajectory_check(model, signature, trajectory, certificate):
    _check(pin(certificate) == trajectory["certificate"], "certificate ID differs from content pin")
    _check(model.verify_certificate(certificate), "existing checker rejected a trajectory certificate")
    history = certificate["history"]
    answers = dict(zip(model.query_ids, signature, strict=True))
    _check(all(answers.get(item["query_id"]) == item["outcome_id"] for item in history),
           "trajectory contradicts evaluator's retained signature")
    _check(len({item["query_id"] for item in history}) == len(history), "repeated query")
    cost = sum(model.queries[item["query_id"]]["cost"] for item in history)
    returned_bytes = sum(len(canonical(model.queries[item["query_id"]]["outcomes"][item["outcome_id"]]))
                         for item in history)
    _check((trajectory["cost"], trajectory["query_count"], trajectory["returned_bytes"])
           == (cost, len(history), returned_bytes), "saved trajectory accounting mismatch")
    status = model.terminal(model.compatible(history))
    _check(status in STATES and status == trajectory["status"] == certificate["status"],
           "full-budget trajectory lacks matching terminal conclusion")
    _check(model.terminal(model.signature_cells[signature]) == status,
           "trajectory disagrees with full-archive terminal class")
    _check(trajectory.get("certificate_valid") is True, "saved trajectory marked invalid")
    return copy.deepcopy(history)


def saved_trajectories(model, runs, certificates):
    """Validate and recover exact p0 full-budget paths without choosing new actions."""
    signatures = sorted(model.signature_cells)
    result = {policy: {} for policy in POLICIES}
    for run in runs:
        if run["problem_id"] != model.problem["problem_id"] or run["budget_percent"] != 100:
            continue
        policy, index = run["policy"], run["signature_index"]
        _check(policy in result and type(index) is int and 0 <= index < len(signatures),
               "unknown saved policy/signature identity")
        _check(index not in result[policy], "duplicate saved full-budget trajectory")
        certificate = certificates[run["certificate"]]
        history = _trajectory_check(model, signatures[index], run, certificate)
        _check(Fraction(run["prior_mass"]) == model.mass(model.signature_cells[signatures[index]]),
               "saved trajectory prior mass mismatch")
        result[policy][index] = {key: copy.deepcopy(run[key]) for key in
                                ("cost", "query_count", "returned_bytes", "status", "certificate",
                                 "certificate_valid", "signature_index")}
        result[policy][index]["history"] = history
    for policy in POLICIES:
        _check(set(result[policy]) == set(range(len(signatures))), "missing saved full-budget trajectory")
    return {policy: [rows[i] for i in range(len(signatures))] for policy, rows in result.items()}


def summarize_trajectories(model, weights, trajectories):
    """One complete trajectory per sorted signature, never one representative world mass."""
    masses = signature_masses(model, weights)
    signatures = sorted(model.signature_cells)
    _check(len(trajectories) == len(signatures), "incomplete trajectory set")
    by_index = {row["signature_index"]: row for row in trajectories}
    _check(len(by_index) == len(trajectories) and set(by_index) == set(range(len(signatures))),
           "duplicate or missing signature trajectory")
    metrics = {key: Fraction() for key in ("cost", "query_count", "returned_bytes", *STATES)}
    for index, signature in enumerate(signatures):
        row = by_index[index]
        _check(row["status"] in STATES and row.get("certificate_valid") is True,
               "invalid full-budget trajectory supplied to reweighting")
        mass = masses[signature]
        for key in ("cost", "query_count", "returned_bytes"):
            _check(type(row[key]) is int and row[key] >= 0, "invalid trajectory metric")
            metrics[key] += mass * row[key]
        metrics[row["status"]] += mass
    _check(sum(metrics[status] for status in STATES) == 1, "terminal status mass does not sum to one")
    return {"expected": {key: number(value) for key, value in metrics.items()},
            "signature_count": len(signatures), "certificate_valid": True}


def _prefix_invariance(base, changed, trajectories):
    count = 0
    for trajectory in trajectories:
        history = trajectory["history"]
        for length in range(len(history) + 1):
            prefix = history[:length]
            base_state = base.compatible(prefix)
            changed_state = changed.compatible(prefix)
            _check(base_state == changed_state and base.terminal(base_state) == changed.terminal(changed_state),
                   "certificate status changed under support-preserving prior")
            count += 1
    return count


def _matched(model, policy, state_cap):
    started = perf_counter()
    planner = CappedPlanner(model, policy, state_cap)
    trajectories, certificates = [], {}

    def timing():
        return {"wall_seconds": perf_counter() - started, "planning_seconds": planner.planning_seconds,
                "solver_states": planner.solver_states, "unique_admitted_states": len(planner.capped_states),
                "state_cap": state_cap, "cap_reached": planner.cap_reached,
                "signature_runs": len(trajectories), "timing_scope":
                "one prior/policy with caches shared across complete signature enumeration; includes checker work"}

    try:
        exact_value = planner.optimal_value() if policy == "exact_optimal" else None
        for index, signature in enumerate(sorted(model.signature_cells)):
            result = run_policy(model, policy, ChargedLookup(model, signature), planner=planner)
            cert = result["certificate"]
            cert_id = pin(cert)
            certificates.setdefault(cert_id, cert)
            row = {key: copy.deepcopy(result[key]) for key in
                   ("cost", "query_count", "returned_bytes", "status", "history", "certificate_valid")}
            row.update({"certificate": cert_id, "signature_index": index})
            _trajectory_check(model, signature, row, cert)
            trajectories.append(row)
        metrics = summarize_trajectories(model, model.priors, trajectories)
        if exact_value is not None:
            _check(Fraction(metrics["expected"]["cost"]["exact"]) == exact_value,
                   "executed exact policy does not attain dynamic-program value")
    except (ValueError, RuntimeError, KeyError, TypeError, IndexError) as error:
        raise IncompletePolicy(error, trajectories, certificates, timing()) from error
    return metrics, trajectories, certificates, timing()


def _same_saved_paths(original, replanned):
    keys = ("signature_index", "history", "cost", "query_count", "returned_bytes", "status")
    _check([{k: row[k] for k in keys} for row in original]
           == [{k: row[k] for k in keys} for row in replanned],
           "q0 replay differs from frozen p0 policy paths or metrics")


def evaluate_problem(problem, saved_full_runs, certificates, *, state_cap=EXACT_STATE_CAP):
    """Execute all fixed prior comparisons for ONE previously frozen input.

    Primary rows only reweight saved p0 paths. Matched rows retain all outcomes;
    cap/failure rows have expected=None and no purported optimum or ratio.
    Callers control the development/freeze/evaluation boundary and persistence.
    """
    started = perf_counter()
    base = Model(problem)
    source_paths = saved_trajectories(base, saved_full_runs, certificates)
    priors = deployment_priors(base)
    result = {"problem_id": problem["problem_id"], "rows": [], "distributions": [],
              "contrasts": [], "bound_checks": [], "runtime": [], "failures": [],
              "trajectories": [], "certificates": {}, "baseline_input_seconds": perf_counter() - started}
    common = {key: problem[key] for key in ("problem_id", "seed", "stratum", "subtype")}
    common["structure_group"] = problem["unweighted_structure_fingerprint"]
    original_masses = signature_masses(base, base.priors)
    signatures = sorted(base.signature_cells)
    for deployment, weights in priors.items():
        started = perf_counter()
        changed = with_prior(base, weights)
        preprocessing = perf_counter() - started
        masses = signature_masses(base, weights)
        coincides = [name for name, candidate in priors.items() if name != deployment and candidate == weights]
        result["distributions"].append({**common, "deployment": deployment,
            "world_prior": [str(value) for value in weights],
            "retained_action_counts": list(retained_action_counts(base)),
            "signature_masses": [{"signature_index": i, "signature": list(signature),
                                  "mass": number(masses[signature])} for i, signature in enumerate(signatures)],
            "coincides_with": coincides, "invariance_verified": True,
            "validated_model_preprocessing_seconds": preprocessing})
        current = {}
        for policy in POLICIES:
            old_paths = source_paths[policy]
            prefix_count = _prefix_invariance(base, changed, old_paths)
            primary = {**common, "deployment": deployment, "planning_mode": "frozen_p0", "policy": policy,
                       "availability": "complete", "coincides_with": coincides,
                       "status_invariant_prefixes": prefix_count,
                       "trajectory_source": "saved_p0_full_budget", **summarize_trajectories(base, weights, old_paths)}
            current["frozen_p0", policy] = primary
            result["rows"].append(primary)
            if policy in {"read_all", "schema_aware"}:
                secondary = {**primary, "planning_mode": "matched_q",
                             "trajectory_source": "saved_p0_prior_independent_rule"}
                current["matched_q", policy] = secondary
                result["rows"].append(secondary)
                continue
            try:
                metrics, paths, produced, runtime = _matched(changed, policy, state_cap)
                prefixes = _prefix_invariance(base, changed, paths)
                secondary = {**common, "deployment": deployment, "planning_mode": "matched_q", "policy": policy,
                             "availability": "complete", "coincides_with": coincides,
                             "status_invariant_prefixes": prefixes, "trajectory_source": "fresh_matched_prior",
                             **metrics}
                result["certificates"].update(produced)
                for path in paths:
                    result["trajectories"].append({**common, "deployment": deployment,
                                                  "planning_mode": "matched_q", "policy": policy, **path})
                result["runtime"].append({**common, "deployment": deployment, "policy": policy, **runtime})
            except IncompletePolicy as stopped:
                error = stopped.error
                failure = {**common, "deployment": deployment, "policy": policy,
                           "kind": "exact_state_cap" if isinstance(error, ExactStateCap) else "computation_failure",
                           "message": str(error), "completed_signature_runs": len(stopped.trajectories)}
                if isinstance(error, ExactStateCap):
                    failure.update({"state_cap": error.state_cap, "admitted_states": error.admitted_states})
                result["failures"].append(failure)
                result["certificates"].update(stopped.certificates)
                for path in stopped.trajectories:
                    result["trajectories"].append({**common, "deployment": deployment,
                        "planning_mode": "matched_q", "policy": policy, "incomplete_policy": True, **path})
                result["runtime"].append({**common, "deployment": deployment, "policy": policy,
                                          "incomplete_policy": True, **stopped.runtime})
                secondary = {**common, "deployment": deployment, "planning_mode": "matched_q", "policy": policy,
                             "availability": "unavailable", "expected": None, "certificate_valid": None,
                             "failure": failure, "signature_count": len(signatures)}
            else:
                if deployment == "q0":
                    _same_saved_paths(old_paths, paths)
                    _check(metrics["expected"] == primary["expected"], "q0 metrics do not reproduce baseline")
            current["matched_q", policy] = secondary
            result["rows"].append(secondary)
        optimal_row = current["matched_q", "exact_optimal"]
        optimum = (Fraction(optimal_row["expected"]["cost"]["exact"])
                   if optimal_row["availability"] == "complete" else None)
        for row in current.values():
            cost = Fraction(row["expected"]["cost"]["exact"]) if row["expected"] is not None else None
            row["matched_optimum_available"] = optimum is not None
            row["matched_optimum"] = number(optimum) if optimum is not None else None
            row["optimum_excess"] = number(cost - optimum) if cost is not None and optimum is not None else None
            row["optimum_ratio"] = number(cost / optimum) if cost is not None and optimum else None
            row["zero_optimum"] = optimum == 0 if optimum is not None else None
            if cost is not None and optimum is not None:
                _check(cost >= optimum, "a feasible policy beats the matched-prior optimum")
        for mode in MODES:
            proposed = current[mode, "pair_cut"]
            for comparison in ("schema_aware", "world_entropy"):
                reference = current[mode, comparison]
                available = proposed["expected"] is not None and reference["expected"] is not None
                delta = (Fraction(proposed["expected"]["cost"]["exact"])
                         - Fraction(reference["expected"]["cost"]["exact"])) if available else None
                result["contrasts"].append({**common, "deployment": deployment, "planning_mode": mode,
                    "comparison": comparison, "pair_cut_minus_comparison": number(delta) if available else None,
                    "availability": "complete" if available else "unavailable",
                    "relation": "lower" if available and delta < 0 else "higher" if available and delta > 0
                    else "tied" if available else None})
        ratios = [masses[signature] / original_masses[signature] for signature in signatures]
        alpha, beta = min(ratios), max(ratios)
        frozen_exact = Fraction(current["frozen_p0", "exact_optimal"]["expected"]["cost"]["exact"])
        bound = {**common, "deployment": deployment, "alpha": number(alpha), "beta": number(beta),
                 "beta_over_alpha": number(beta / alpha), "frozen_exact_q_cost": number(frozen_exact),
                 "matched_optimum": number(optimum) if optimum is not None else None,
                 "planning_prior_penalty": number(frozen_exact - optimum) if optimum is not None else None,
                 "verified": None, "zero_optimum_identity": None,
                 "availability": "complete" if optimum is not None else "unavailable"}
        if optimum is not None:
            _check(optimum <= frozen_exact <= beta / alpha * optimum, "prior-ratio bound failed")
            bound["verified"] = True
            bound["zero_optimum_identity"] = frozen_exact == 0 if optimum == 0 else None
        result["bound_checks"].append(bound)
    return result
