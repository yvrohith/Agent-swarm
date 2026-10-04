"""Checkable certain answers and catalogue-relative ambiguity witnesses."""
from __future__ import annotations

import copy

from .model import Model, canonical, indices, pin

_SCOPE = "relative to this finite model, initial evidence, and closed permitted query catalogue"


def certificate(model, history, status=None):
    history = copy.deepcopy(list(history))
    state = model.compatible(history)
    actual = model.terminal(state) or "unresolved_pending"
    if status is not None and status != actual:
        raise ValueError("requested certificate contradicts exhaustive compatibility")
    result = {
        "schema_version": 1, "status": actual, "claim": copy.deepcopy(model.claim),
        "model_pin": pin(model.problem), "assumptions_pin": pin(model.problem["assumptions"]),
        "initial_evidence_pin": pin(model.problem["initial_evidence"]),
        "initial_evidence": copy.deepcopy(model.problem["initial_evidence"]),
        "history": history, "acquired_evidence": [copy.deepcopy(
            model.queries[h["query_id"]]["outcomes"][h["outcome_id"]]) for h in history],
        "scope_limit": _SCOPE, "compatible_world_count": state.bit_count(),
    }
    candidates = list(indices(state))
    if actual in {"established", "ruled_out", "inconsistent"}:
        result["exhaustive_compatible_hypotheses"] = [model.worlds[i]["id"] for i in candidates]
    elif actual == "unresolved_pending":
        result["opposite_claim_witnesses"] = [model.worlds[next(i for i in candidates
                                                            if model.claim_values[i] == value)]["id"]
                                             for value in (False, True)]
    else:
        coverage = []
        for signature, full_cell in sorted(model.signature_cells.items()):
            cell = state & full_cell
            if not cell:
                continue
            members = list(indices(cell))
            if {model.claim_values[i] for i in members} != {False, True}:
                raise ValueError("irreducibility fails for a remaining signature cell")
            witnesses = [model.worlds[next(i for i in members if model.claim_values[i] == value)]["id"]
                         for value in (False, True)]
            coverage.append({"complete_query_signature": list(signature),
                             "compatible_world_count": cell.bit_count(),
                             "opposite_claim_witnesses": witnesses})
        result["all_remaining_signature_cells"] = coverage
    return result


def verify_certificate(model, candidate):
    """Rebuild from pinned model bytes; never trust stored classes or verdicts."""
    try:
        fresh = Model(model.problem)
        expected = certificate(fresh, candidate["history"], candidate["status"])
        return canonical(candidate) == canonical(expected)
    except (ValueError, KeyError, TypeError, IndexError, StopIteration):
        return False
