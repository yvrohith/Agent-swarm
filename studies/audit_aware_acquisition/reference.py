"""Independent checks of saved audit trajectories and their physical support.

Selection is recomputed directly from hypothetical signature sets. This module
does not import the new audit selector or trust its flags. The unchanged prior
study's physical reconstruction and certificate checkers are reused; this is not
an independently implemented physical semantics or nominal exact optimizer.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from itertools import product
from math import isfinite

from studies.archive_model_misspecification import reference as physical_reference
from tracebench.evidence_acquisition.model import Model, canonical, pin

ARMS = ("no_audit", "cost_order", "constant_first", "closure_informed")
BUDGETS = (0, 25, 50, 100)
KS = (0, 1, 2)
DEFINITE = {"established", "ruled_out"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def direct_support(problem, worlds):
    """Derive observations from record membership and truth from physical facts."""
    queries = problem["queries"]
    records = {r["id"]: r for r in problem["record_catalog"]}
    for query in queries:
        require(query["outcomes"]["present"] == records[query["record_id"]]
                and query["outcomes"]["missing"] == {"kind": "lookup_empty", "scope": query["scope"]},
                "Typed archive outcomes do not match the retained-record interface")
    return [{"id": world["id"],
             "signature": tuple("present" if q["record_id"] in world["retained_record_ids"] else "missing"
                                for q in queries),
             "truth": physical_reference.claim_value(problem, world)} for world in worlds]


def compatible(signatures, query_ids, history):
    positions = {qid: index for index, qid in enumerate(query_ids)}
    require(len({h["query_id"] for h in history}) == len(history), "Repeated paid query")
    for item in history:
        require(set(item) == {"query_id", "outcome_id"} and item["query_id"] in positions
                and item["outcome_id"] in {"present", "missing"}, "Invalid observed lookup")
    return {tuple(signature) for signature in signatures if all(
        signature[positions[h["query_id"]]] == h["outcome_id"] for h in history)}


def statuses(support, query_ids, history):
    selected = compatible({w["signature"] for w in support}, query_ids, history)
    worlds = [w for w in support if w["signature"] in selected]
    truths = {w["truth"] for w in worlds}
    claim = ("model_conflict" if not truths else "established" if truths == {True}
             else "ruled_out" if truths == {False} else "unresolved")
    if claim != "unresolved":
        return claim, claim
    by_signature = defaultdict(set)
    for world in worlds:
        by_signature[world["signature"]].add(world["truth"])
    terminal = "archive_irreducible" if all(v == {False, True} for v in by_signature.values()) else "unresolved_pending"
    return claim, terminal


def choose(problem, nominal_signatures, design_signatures, history, arm):
    """Fixed independent selector: no actual signature, omission, truth or k."""
    require(arm in ARMS, "Unknown audit arm")
    queries = {q["id"]: q for q in problem["queries"]}
    query_ids = tuple(queries)
    possible = compatible(nominal_signatures, query_ids, history)
    if not possible or arm == "no_audit":
        return None
    asked = {h["query_id"] for h in history}
    remaining = [qid for qid in query_ids if qid not in asked]
    if not remaining:
        return None
    costs = {qid: queries[qid]["cost"] for qid in remaining}
    positions = {qid: index for index, qid in enumerate(query_ids)}
    if arm == "cost_order":
        return min(remaining, key=lambda qid: (costs[qid], qid))
    if arm == "closure_informed":
        envelope = compatible(set(map(tuple, design_signatures)), query_ids, history)
        require(bool(envelope), "Paid history is outside the fixed k=2 design envelope")
        scores = {qid: Fraction(sum(not any(n[positions[qid]] == s[positions[qid]] for n in possible)
                                   for s in envelope), costs[qid]) for qid in remaining}
        if any(scores.values()):
            return min(remaining, key=lambda qid: (-scores[qid], costs[qid], qid))
    constant = [qid for qid in remaining if len({s[positions[qid]] for s in possible}) == 1]
    return min(constant or remaining, key=lambda qid: (costs[qid], qid))


def _history_costs(problem, history):
    queries = {q["id"]: q for q in problem["queries"]}
    return (sum(queries[h["query_id"]]["cost"] for h in history),
            sum(len(canonical(queries[h["query_id"]]["outcomes"][h["outcome_id"]])) for h in history))


class _CertificateChecks:
    """One local verification cache; only immutable certificate bindings are keys."""

    def __init__(self, registry):
        self.registry = registry
        self.checked = set()
        self.references = 0
        self.nominal_distinct = self.expanded_distinct = self.all_query_witness_checks = 0

    def check(self, reference, context, history, *, expanded, count_reference=True):
        require(reference in self.registry, "Missing certificate")
        cert = self.registry[reference]
        require(pin(cert) == reference, "Certificate digest mismatch")
        require(cert["history"] == history, "Certificate references a different paid history")
        require((cert.get("certificate_kind") == "expanded_archive_support") == expanded,
                "Certificate crosses nominal/expanded contracts")
        model_pin = context["expansion"]["model_pin"] if expanded else pin(context["problem"])
        contract_pin = context["expansion"]["contract_pin"] if expanded else "nominal"
        require(cert["model_pin"] == model_pin, "Certificate names a different physical model")
        if expanded:
            require(cert["k"] == context["k"] and cert["contract_pin"] == contract_pin,
                    "Certificate names a different omission contract")
        key = (model_pin, contract_pin, pin(history), reference)
        if key not in self.checked:
            if expanded:
                result = physical_reference.verify_expanded_certificate(
                    context["problem"], context["k"], cert, context["rebuilt"])
                self.expanded_distinct += 1
                self.all_query_witness_checks += result["all_query_witness_checks"]
            else:
                require(context["nominal_model"].verify_certificate(cert), "Invalid nominal certificate")
                claim, terminal = statuses(context["nominal_support"], context["query_ids"], history)
                require(cert["status"] == ("inconsistent" if claim == "model_conflict" else terminal),
                        "Nominal certificate disagrees with direct physical filtering")
                self.nominal_distinct += 1
            self.checked.add(key)
        self.references += count_reference


def _contexts(problems, conditions):
    population_size = len(problems)
    problems = {p["problem_id"]: p for p in problems}
    require(bool(problems) and len(problems) == population_size, "Empty or duplicate declared problem population")
    saved = {(c["problem_id"], c["k"]): c for c in conditions}
    require(len(saved) == len(conditions) and set(saved) == set(product(problems, KS)),
            "Missing or duplicate saved omission condition")
    contexts = {}
    for (pid, k), condition in saved.items():
        require(condition.get("census_status") == condition.get("policy_status") == "completed"
                and condition.get("status") == "completed", "Baseline condition is unavailable")
        problem = problems[pid]
        rebuilt = physical_reference.verify_expansion(problem, k, condition["expansion"])
        nominal = Model(problem)
        query_ids = tuple(q["id"] for q in problem["queries"])
        nominal_support = direct_support(problem, problem["worlds"])
        support = direct_support(problem, condition["expansion"]["worlds"])
        signature_rows = {tuple(r["outcomes"]): r for r in condition["signature_rows"]}
        require(len(signature_rows) == len(condition["signature_rows"])
                and set(signature_rows) == {w["signature"] for w in support}, "Saved signature population differs from physical support")
        contexts[pid, k] = {"problem": problem, "k": k, "expansion": condition["expansion"],
                            "rebuilt": rebuilt, "nominal_model": nominal, "query_ids": query_ids,
                            "nominal_support": nominal_support, "expanded_support": support,
                            "nominal_signatures": {w["signature"] for w in nominal_support},
                            "signature_rows": signature_rows, "baseline": condition}
    for (pid, _), context in contexts.items():
        context["design_signatures"] = set(contexts[pid, 2]["signature_rows"])
    return contexts


def _same(row, expected, label):
    for key, value in expected.items():
        require(key in row and row[key] == value, f"{label}: {key} disagrees with direct verification")


def support_flags(proposal, initial, final, full, alarm):
    """Warrant changes and audit withdrawal are separate axes."""
    definite = proposal in DEFINITE
    supported_initially = definite and initial[0] == proposal
    supported_finally = definite and final[0] == proposal
    restored = definite and not supported_initially and supported_finally
    irreducible = proposal == "archive_irreducible"
    require(not supported_initially or supported_finally, "Compatible extra evidence removed a warranted definite claim")
    if definite:
        disposition = ("definite_proposal_withdrawn" if alarm else "definite_supported_remaining"
                       if supported_initially else "definite_warrant_restored" if restored
                       else "definite_still_unsupported")
    else:
        require(irreducible, "Unknown initial stopping proposal")
        disposition = ("withdrawn_irreducibility" if alarm else "irreducibility_warranted"
                       if final[1] == "archive_irreducible" else "irreducibility_overstrong")
    return {
        "initially_supported_definite": supported_initially,
        "initially_unsupported_definite": definite and not supported_initially,
        "finally_supported_definite": supported_finally,
        "finally_unsupported_definite": definite and not supported_finally,
        "supported_definite_remaining": supported_initially and supported_finally,
        "warrant_restored": restored,
        "unwithdrawn_warrant_restored": restored and not alarm,
        "still_unsupported_without_conflict": definite and not supported_finally and not alarm,
        "withdrawn_definite": definite and alarm,
        "preaudit_irreducible": irreducible,
        "irreducibility_warranted_at_start": irreducible and initial[1] == "archive_irreducible",
        "irreducibility_warranted_at_end": irreducible and final[1] == "archive_irreducible",
        "irreducibility_overstrong": irreducible and final[1] != "archive_irreducible",
        "residual_full_archive_ambiguity": full[0] == "unresolved",
        "disposition": disposition,
    }


def _verify_run(row, context, certificates, action_contexts):
    problem, k = context["problem"], context["k"]
    queries = {q["id"]: q for q in problem["queries"]}
    qids = context["query_ids"]
    actual = tuple(row["outcomes"])
    original = context["signature_rows"][actual]
    baseline = original["policy"]
    base = baseline["history"]
    audit_history, history = row["audit_history"], row["history"]
    arm, budget_percent = row["arm"], row["budget_percent"]
    nominal_signatures, design = context["nominal_signatures"], context["design_signatures"]
    _, proposal = statuses(context["nominal_support"], qids, base)
    require(proposal in {*DEFINITE, "archive_irreducible"}, "Original policy did not stop consistently")
    require(baseline["status"] == proposal, "Baseline proposal differs from nominal physical support")
    require(baseline.get("failure") is None and baseline.get("certificate_valid") is True,
            "Unavailable or uncertified nominal baseline")
    base_cost, base_bytes = _history_costs(problem, base)
    _same(baseline, {"cost": base_cost, "query_count": len(base), "returned_bytes": base_bytes}, "Baseline accounting")
    require(history == base + audit_history and row["base_history"] == base,
            "Audit does not preserve the exact nominal stopping prefix")
    require(actual in compatible({actual}, qids, history), "Recorded retrieval disagrees with physical archive")
    _same(row, {"problem_id": problem["problem_id"], "stratum": problem["stratum"],
                "subtype": problem["subtype"], "k": k, "signature_id": original["signature_id"],
                "population": "original" if actual in nominal_signatures else "new",
                "base_nominal_proposal": proposal, "original_proposal": proposal,
                "baseline_certificate": baseline["certificate"]}, "Run identity")
    require(row["population"] == original["population"], "Saved population disagrees with nominal support")
    residual_cost = sum(q["cost"] for qid, q in queries.items() if qid not in {h["query_id"] for h in base})
    budget = residual_cost * budget_percent // 100
    added_cost = 0
    first_conflict = None
    seen_records = {queries[h["query_id"]]["record_id"] for h in base}
    aliases = alias_cost = alias_bytes = initial_lookups = 0
    prefix = list(base)
    paid_checks = 0

    def next_action(paid):
        action = choose(problem, nominal_signatures, design, paid, arm)
        key = (pin(problem), arm, pin(paid))
        require(key not in action_contexts or action_contexts[key] == action,
                "Identical paid history selects different actions")
        action_contexts[key] = action
        if arm == "closure_informed":
            require(bool(compatible(design, qids, paid)), "Empty fixed design envelope")
        return action

    next_action(prefix)
    for index, item in enumerate(audit_history, 1):
        require(first_conflict is None, "Audit spends after first nominal conflict")
        query_id, outcome = item["query_id"], item["outcome_id"]
        require(next_action(prefix) == query_id, "Paid action differs from the fixed independent selector")
        possible_before = compatible(nominal_signatures, qids, prefix)
        require(bool(possible_before), "Audit spends with empty nominal support")
        branches = sorted({signature[qids.index(query_id)] for signature in possible_before})
        added_cost += queries[query_id]["cost"]
        require(added_cost <= budget, "Audit exceeds rounded residual-catalogue budget")
        record = queries[query_id]["record_id"]
        aliases += record in seen_records
        if record in seen_records:
            alias_cost += queries[query_id]["cost"]
            alias_bytes += len(canonical(queries[query_id]["outcomes"][outcome]))
        initial_lookups += record in problem["initial_record_ids"]
        seen_records.add(record)
        prefix.append(item)
        paid_checks += 1
        remaining_nominal = compatible(nominal_signatures, qids, prefix)
        if arm == "closure_informed":
            require(bool(compatible(design, qids, prefix)), "Paid outcome left the fixed design envelope")
        if not remaining_nominal:
            require(len(branches) == 1 and outcome not in branches,
                    "A nonconstant binary lookup cannot first empty nominal support")
            first_conflict = {"added_query_index": index, "added_cost": added_cost,
                              "total_cost": base_cost + added_cost, "query_id": query_id,
                              "outcome_id": outcome, "nominal_outcomes_before": branches}
    alarm = first_conflict is not None
    if arm == "no_audit":
        require(not audit_history, "Baseline arm performs extra retrieval")
        termination, next_query = "baseline_no_audit", None
    elif alarm:
        termination, next_query = "nominal_conflict", None
    else:
        selected = next_action(history)
        if selected is None:
            require(len(history) == len(qids), "Audit stopped before exhausting the catalogue")
            termination, next_query = "catalogue_exhausted", None
        else:
            require(added_cost + queries[selected]["cost"] > budget,
                    "Audit stopped before an affordable next action")
            termination, next_query = "next_action_unaffordable", selected
    final_claim, _ = statuses(context["nominal_support"], qids, history)
    require(alarm == (final_claim == "model_conflict"), "First-conflict detection disagrees with direct support")
    require(not (alarm and actual in nominal_signatures), "False alarm on a nominal full signature")
    if budget_percent == 0:
        require(not audit_history, "Zero budget changes the nominal stopping history")
    if budget_percent == 100 and arm != "no_audit":
        require(alarm == (actual not in nominal_signatures), "Full-budget exhaustive conflict detection failed")
    counted_added_cost, added_bytes = _history_costs(problem, audit_history)
    require(added_cost == counted_added_cost, "Additional cost discrepancy")
    _same(row, {"audit_budget": budget, "residual_cost": residual_cost,
                "base_cost": base_cost, "added_cost": added_cost, "total_cost": base_cost + added_cost,
                "base_query_count": len(base), "added_query_count": len(audit_history), "total_query_count": len(history),
                "base_returned_bytes": base_bytes, "added_returned_bytes": added_bytes,
                "total_returned_bytes": base_bytes + added_bytes,
                "status": "nominal_model_conflict" if alarm else "no_conflict_observed",
                "termination_reason": termination, "next_query": next_query, "first_conflict": first_conflict,
                "proposal_withheld": alarm and proposal in DEFINITE}, "Audit accounting or stopping")
    _same(row["coverage"], {"catalogue_actions": len(qids), "base_actions": len(base),
                           "audited_actions": len(audit_history), "total_acquired_actions": len(history),
                           "remaining_actions": len(qids) - len(history), "complete": len(history) == len(qids),
                           "distinct_record_ids_queried": len(seen_records), "added_alias_queries": aliases}, "Coverage")
    require(all(isinstance(row[name], (int, float)) and isfinite(row[name]) and row[name] >= 0
                for name in ("selection_seconds", "checking_seconds")), "Invalid implementation timing")
    initial = statuses(context["expanded_support"], qids, base)
    final = statuses(context["expanded_support"], qids, history)
    full_history = [{"query_id": qid, "outcome_id": value} for qid, value in zip(qids, actual, strict=True)]
    full = statuses(context["expanded_support"], qids, full_history)
    require(initial[0] != "model_conflict" and final[0] != "model_conflict",
            "Realized archive is absent from its evaluated physical support")
    _same(row, {"baseline_expanded_claim_status": initial[0], "baseline_expanded_terminal_status": initial[1],
                "final_expanded_claim_status": final[0], "final_expanded_terminal_status": final[1]}, "Expanded warrant")
    support = support_flags(proposal, initial, final, full, alarm)
    _same(row["support"], support, "Support classification")
    _same(row, {"detected": alarm, "complete_nominal_conflict": actual not in nominal_signatures,
                "full_conflict_missed": actual not in nominal_signatures and not alarm,
                "false_alarm": alarm and actual in nominal_signatures,
                "catalogue_exhausted": len(history) == len(qids), "catalogue_query_count": len(qids),
                "alias_added_queries": aliases, "alias_added_cost": alias_cost, "alias_added_bytes": alias_bytes,
                "added_lookups_of_initial_records": initial_lookups, "unique_queried_record_count": len(seen_records)},
          "Retrospective archive classification")
    require(row["joint_category"] == {"alarm": alarm, "proposal": proposal, "final_claim_status": final[0],
                                      "final_terminal_status": final[1], "warrant_restored": support["warrant_restored"],
                                      "withdrawn_definite": support["withdrawn_definite"], "disposition": support["disposition"]},
            "Joint detection/warrant category disagrees with direct verification")
    refs = row["certificates"]
    require(set(refs) == {"base_nominal", "base_expanded", "final_nominal", "final_expanded"}, "Incomplete run certificate references")
    require(refs["base_nominal"] == baseline["certificate"]
            and refs["base_expanded"] == baseline["expanded_certificate"], "Baseline certificate reference was changed")
    for key in ("base_nominal", "base_expanded"):
        require(refs[key] in context["baseline"]["certificates"]
                and certificates.registry.get(refs[key]) == context["baseline"]["certificates"][refs[key]],
                "Baseline certificate bytes were changed")
    for name, paid, expanded in (("base_nominal", base, False), ("base_expanded", base, True),
                                 ("final_nominal", history, False), ("final_expanded", history, True)):
        certificates.check(refs[name], context, paid, expanded=expanded)
    return {"paid_prefix_checks": paid_checks, "first_conflict_checks": int(alarm),
            "full_budget_endpoint_checks": int(budget_percent == 100 and arm != "no_audit")}


def verify_runs(problems, saved_conditions, runs, certificates):
    """Check the whole declared population, not a successful subset of it.

    Raises on malformed/unavailable/incomplete inputs. Callers must retain the
    failed phase explicitly; a missing row or resource-cap failure cannot pass.
    Certificate semantics are checked once per distinct immutable binding, while
    each of the four references on every run is always bound to its exact history.
    """
    contexts = _contexts(problems, saved_conditions)
    expected = {(pid, k, signature, arm, budget) for (pid, k), context in contexts.items()
                for signature, arm, budget in product(context["signature_rows"], ARMS, BUDGETS)}
    by_key = {}
    for row in runs:
        key = (row["problem_id"], row["k"], tuple(row["outcomes"]), row["arm"], row["budget_percent"])
        require(key not in by_key, "Duplicate per-signature audit run")
        by_key[key] = row
    require(set(by_key) == expected, "Missing or unexpected audit runs in the declared population")
    cert_checks = _CertificateChecks(certificates)
    counts = defaultdict(int)
    action_contexts, cross_k_paths = {}, {}
    referenced = set()
    for (pid, k, signature, arm, budget), row in by_key.items():
        verified = _verify_run(row, contexts[pid, k], cert_checks, action_contexts)
        for name, value in verified.items():
            counts[name] += value
        referenced.update(row["certificates"].values())
        path_key = (pid, signature, arm, budget)
        fields = ("base_history", "history", "audit_history", "base_cost", "added_cost", "total_cost",
                  "base_returned_bytes", "added_returned_bytes", "total_returned_bytes",
                  "audit_budget", "residual_cost", "status", "termination_reason", "next_query", "first_conflict")
        path = {name: row[name] for name in fields}
        if path_key in cross_k_paths:
            require(cross_k_paths[path_key] == path, "Matching signatures have different audit paths across k")
            counts["cross_k_path_checks"] += 1
        cross_k_paths[path_key] = path
        full = by_key[pid, k, signature, arm, 100]["audit_history"]
        require(row["audit_history"] == full[:len(row["audit_history"])], "Budget changed the fixed audit order")
        counts["budget_prefix_checks"] += 1
    # A registry may retain extra distinct certificates. Check their semantics too,
    # without calling them additional run-reference checks or empirical trials.
    for reference in set(certificates) - referenced:
        cert = certificates[reference]
        expanded = cert.get("certificate_kind") == "expanded_archive_support"
        matches = [c for c in contexts.values() if cert.get("model_pin") ==
                   (c["expansion"]["model_pin"] if expanded else pin(c["problem"]))]
        require(bool(matches), "Unreferenced certificate has no declared model")
        cert_checks.check(reference, matches[0], cert["history"], expanded=expanded, count_reference=False)
    require(len(cert_checks.checked) == len(certificates), "Distinct certificate coverage mismatch")
    return {"status": "passed", "problem_count": len(problems), "condition_count": len(contexts),
            "aggregate_cell_count": len(contexts) * len(ARMS) * len(BUDGETS), "run_count": len(runs),
            **dict(counts), "unique_paid_action_contexts": len(action_contexts),
            "certificate_references_checked": cert_checks.references,
            "distinct_certificates_checked": len(cert_checks.checked),
            "distinct_nominal_certificates_checked": cert_checks.nominal_distinct,
            "distinct_expanded_certificates_checked": cert_checks.expanded_distinct,
            "distinct_certificate_all_query_witness_checks": cert_checks.all_query_witness_checks,
            "unreferenced_certificates_checked": len(set(certificates) - referenced),
            "independence_scope": "Direct physical filtering and independent audit ordering/accounting; unchanged prior physical validator, claim semantics and certificate checkers reused; no independent nominal exact optimization."}
