"""Independent physical reconstruction for the bounded archive-loss study.

The unchanged nominal validator checks original inputs. Expansion, claim truth,
query signatures and compatible sets are recomputed here from physical fields;
no expanded model, cached status, or omission-closure routine is imported.
Canonical JSON/hash helpers and the original nominal checker are shared.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from itertools import combinations

from studies.acquisition_prior_robustness.sensitivity import CappedPlanner
from tracebench.evidence_acquisition.model import Model, canonical, pin


def require(condition, message):
    if not condition:
        raise ValueError(message)


def covers(scope, event):
    return (scope["source_id"] == event["source_id"]
            and scope["recipient"] == event["recipient"]
            and scope["window"][0] <= event["time"] < scope["window"][1])


def physical(world, retained=None):
    return {"occurring_event_ids": sorted(world["occurring_event_ids"]),
            "retained_record_ids": sorted(world["retained_record_ids"] if retained is None else retained),
            "recipient_writes": copy.deepcopy(world["recipient_writes"]),
            "source_mechanism": world["source_mechanism"],
            "selected_source_ids": sorted(world["selected_source_ids"])}


def claim_value(problem, world):
    """Derive Boolean truth from events/decisions, not stored hypothesis labels."""
    claim = problem["claim"]
    events = {event["id"]: event for event in problem["event_catalog"]}
    target = next(w for w in world["recipient_writes"] if w["id"] == claim["target_write_id"])
    exposure = []
    for source in claim["source_ids"]:
        scope = {"source_id": source, "recipient": claim["recipient"], "window": claim["window"]}
        present = any(events[e]["kind"] == "context" and covers(scope, events[e])
                      and events[e]["time"] < target["time"] for e in world["occurring_event_ids"])
        exposure.append((source, present))
    if claim["kind"] == "all_context_exposure":
        return all(present for _, present in exposure)
    if claim["kind"] == "any_context_exposure":
        return any(present for _, present in exposure)
    require(claim["kind"] == "source_use", "Unknown claim kind")
    return any(present and source in world["selected_source_ids"] for source, present in exposure)


def full_signature(problem, world):
    retained = set(world["retained_record_ids"])
    return tuple("present" if q["record_id"] in retained else "missing" for q in problem["queries"])


def reconstruct(problem, k):
    """Enumerate the specified finite omission closure by a separate code path."""
    require(type(k) is int and k in (0, 1, 2), "Unsupported omission budget")
    Model(problem)  # Original completeness/chronology validator remains intact.
    records = {r["id"]: r for r in problem["record_catalog"]}
    events = {e["id"]: e for e in problem["event_catalog"]}
    queried = {q["record_id"] for q in problem["queries"]}
    initial = set(problem["initial_record_ids"])
    by_physical, generated = {}, 0
    for index, parent in enumerate(problem["worlds"]):
        retained = set(parent["retained_record_ids"])
        eligible = sorted(r for r in retained & queried - initial if records[r]["kind"] == "context_receipt")
        for count in range(min(k, len(eligible)) + 1):
            for omitted in combinations(eligible, count):
                generated += 1
                body = physical(parent, retained - set(omitted))
                key = canonical(body)
                if key not in by_physical:
                    by_physical[key] = {"id": "physical_" + pin(body)[:24], **body, "origins": []}
                current = set(body["retained_record_ids"])
                violations = []
                for scope in parent["complete_context_scopes"]:
                    for event_id in sorted(parent["occurring_event_ids"]):
                        event = events[event_id]
                        if (event["kind"] == "context" and covers(scope, event)
                                and not any(records[r].get("event_id") == event_id for r in current)):
                            violations.append({"event_id": event_id, "scope": copy.deepcopy(scope),
                                               "omitted_record_ids": [r for r in omitted
                                                                      if records[r].get("event_id") == event_id]})
                applicable, violated_assertions, support_only = [], set(), []
                for record_id in omitted:
                    event_id = records[record_id]["event_id"]
                    assertion_ids = sorted(r for r in current if records[r]["kind"] == "completeness"
                                           and covers(records[r]["scope"], events[event_id]))
                    applicable.append({"omitted_record_id": record_id, "event_id": event_id,
                                       "assertion_ids": assertion_ids,
                                       "initial_assertion_ids": sorted(set(assertion_ids) & initial)})
                    if not assertion_ids:
                        support_only.append(record_id)
                    if not any(records[r].get("event_id") == event_id for r in current):
                        violated_assertions.update(assertion_ids)
                by_physical[key]["origins"].append({
                    "parent_world_id": parent["id"], "parent_world_index": index,
                    "nominal_retained_record_ids": sorted(retained),
                    "nominal_complete_context_scopes": copy.deepcopy(parent["complete_context_scopes"]),
                    "omitted_record_ids": list(omitted),
                    "affected_query_ids": sorted(q["id"] for q in problem["queries"] if q["record_id"] in omitted),
                    "violated_nominal_completeness": violations,
                    "applicable_retained_assertions": applicable,
                    "violated_retained_assertion_ids": sorted(violated_assertions),
                    "support_only_omitted_record_ids": support_only})
                require(claim_value(problem, body) == claim_value(problem, parent),
                        "Omission changed event-derived truth")
                require(initial <= set(body["retained_record_ids"]), "Initial evidence was omitted")
    worlds = sorted(by_physical.values(), key=lambda w: w["id"])
    require(len(worlds) <= 4096, "Expanded world safety cap exceeded")
    require(len({full_signature(problem, w) for w in worlds}) <= 256, "Signature safety cap exceeded")
    nominal = [{"id": parent["id"], **physical(parent)} for parent in problem["worlds"]]
    expanded_keys = {canonical(physical(w)) for w in worlds}
    require(all(canonical(physical(w)) in expanded_keys for w in nominal), "Nominal embedding lost")
    return {"worlds": worlds, "nominal_worlds": nominal, "generated_candidates": generated,
            "physical_world_count": len(worlds), "nominal_world_count": len(nominal),
            "signature_count": len({full_signature(problem, w) for w in worlds})}


def inspect_history(problem, worlds, history):
    """Direct filtering plus an exhaustive partition of the remaining worlds."""
    queries = {q["id"]: q for q in problem["queries"]}
    positions = {qid: index for index, qid in enumerate(queries)}
    for item in history:
        require(set(item) == {"query_id", "outcome_id"}, "Invalid acquired history item")
        require(item["query_id"] in queries and item["outcome_id"] in ("present", "missing"),
                "Unknown lookup in acquired history")
    compatible = [w for w in worlds if all(full_signature(problem, w)[positions[h["query_id"]]] == h["outcome_id"]
                                          for h in history)]
    values = {claim_value(problem, w) for w in compatible}
    claim = ("model_conflict" if not values else "established" if values == {True}
             else "ruled_out" if values == {False} else "unresolved")
    cells = defaultdict(list)
    for world in compatible:
        cells[full_signature(problem, world)].append(world)
    cell_rows = []
    for signature, members in sorted(cells.items()):
        truths = {claim_value(problem, w) for w in members}
        status = ("archive_irreducible" if len(truths) == 2 else
                  "established" if truths == {True} else "ruled_out")
        cell_rows.append({"signature": list(signature), "world_ids": sorted(w["id"] for w in members),
                          "terminal_status": status})
    classes = {c["terminal_status"] for c in cell_rows}
    terminal = "model_conflict" if not classes else next(iter(classes)) if len(classes) == 1 else "unresolved_pending"
    return {"claim_status": claim, "terminal_status": terminal,
            "compatible_world_ids": sorted(w["id"] for w in compatible), "signature_cells": cell_rows}


def check_same_signature_opposites(problem, left, right):
    """Check every catalogue action, including aliases and unqueried actions."""
    require(claim_value(problem, left) != claim_value(problem, right), "Witnesses do not oppose the claim")
    require(full_signature(problem, left) == full_signature(problem, right),
            "Witnesses differ on a catalogue action")
    return len(problem["queries"])


def _contract(problem, k):
    return {
        "schema_version": 1, "contract_id": "bounded-context-receipt-loss-v1", "omission_budget": k,
        "nominal_problem_pin": pin(problem),
        "mechanism": "all subsets of at most k unique retained queried noninitial context receipt IDs",
        "authenticity": "surviving positive receipts truthfully identify unchanged occurring events",
        "completeness_assumption_change": "retained completeness bytes authenticate a nominal assertion; affected assertions do not guarantee completeness of the post-omission retrievable archive",
        "initial_evidence": "unaltered and not eligible for omission",
        "physical_truth": "event occurrence, timestamps, write context, source selection and output mechanism unchanged",
        "nominal_snapshot_metadata": "parent assignments and complete_context_scopes are provenance, not current facts",
        "support_semantics": "finite loss closure only, with no new probability distribution or invented event mechanism",
        "world_cap": 4096, "signature_cap": 256,
    }


def _pins(problem, k, rebuilt):
    contract = _contract(problem, k)
    support = pin([physical(w) for w in rebuilt["worlds"]])
    return {"contract": contract, "contract_pin": pin(contract), "nominal_problem_pin": pin(problem),
            "support_pin": support, "model_pin": pin({"nominal_problem_pin": pin(problem),
                                                       "contract_pin": pin(contract), "physical_support_pin": support})}


def _origin_bytes(origin):
    value = copy.deepcopy(origin)
    value["violated_nominal_completeness"] = sorted(value["violated_nominal_completeness"], key=canonical)
    return canonical(value)


def verify_expansion(problem, k, saved, rebuilt=None):
    rebuilt = reconstruct(problem, k) if rebuilt is None else rebuilt
    require(saved["problem_id"] == problem["problem_id"] and saved["k"] == k, "Expansion identity mismatch")
    for key, expected in _pins(problem, k, rebuilt).items():
        require(saved[key] == expected, f"Expanded contract/support binding mismatch: {key}")
    require(saved["query_order"] == [q["id"] for q in problem["queries"]], "Query order changed")
    expected = {w["id"]: w for w in rebuilt["worlds"]}
    require(len(saved["worlds"]) == len(expected), "Physical support count differs")
    require(len({w["id"] for w in saved["worlds"]}) == len(expected), "Duplicate physical world ID")
    origins = []
    for world in saved["worlds"]:
        require(world["id"] in expected, "Unexpected expanded physical realization")
        other = expected[world["id"]]
        require(physical(world) == physical(other), "Physical fields differ from independent reconstruction")
        require(sorted(map(_origin_bytes, world["provenance"])) == sorted(map(_origin_bytes, other["origins"])),
                "Omission/retention/completeness provenance differs")
        origins.extend(other["origins"])
    require(saved["answers"] == [list(full_signature(problem, w)) for w in saved["worlds"]],
            "Saved query answers do not follow physical records/aliases")
    embedding = [{"nominal_world_id": parent["id"], "nominal_world_index": index,
                  "expanded_world_id": "physical_" + pin(physical(parent))[:24]}
                 for index, parent in enumerate(problem["worlds"])]
    require(saved["embedding"] == embedding, "Nominal support embedding differs")
    nominal_signatures = {full_signature(problem, w) for w in rebuilt["nominal_worlds"]}
    signatures = {full_signature(problem, w) for w in rebuilt["worlds"]}
    stats = {"nominal_world_count": len(problem["worlds"]),
             "generated_world_count": rebuilt["generated_candidates"], "deduplicated_world_count": len(expected),
             "signature_count": len(signatures), "nominal_signature_count": len(nominal_signatures),
             "overlapping_signature_count": len(signatures & nominal_signatures),
             "new_signature_count": len(signatures - nominal_signatures),
             "nonempty_omission_constructions": sum(bool(o["omitted_record_ids"]) for o in origins),
             "constructions_violating_nominal_completeness": sum(bool(o["violated_nominal_completeness"]) for o in origins),
             "constructions_violating_retained_assertions": sum(bool(o["violated_retained_assertion_ids"]) for o in origins),
             "constructions_with_support_only_omissions": sum(bool(o["support_only_omitted_record_ids"]) for o in origins),
             "nominal_embedding_count": len(embedding), "no_truncation": True}
    require(saved["stats"] == stats, "Expansion census counts differ")
    return rebuilt


def verify_expanded_certificate(problem, k, candidate, rebuilt):
    """Check binding, exhaustive support and actual witnesses independently."""
    bindings = _pins(problem, k, rebuilt)
    require(candidate["schema_version"] == 1 and candidate["scope_limit"] ==
            "only this named loss-closure contract and the unchanged permitted query catalogue",
            "Certificate schema or scientific scope changed")
    for key, value in bindings.items():
        require(candidate[key] == value, f"Certificate contract/support binding mismatch: {key}")
    require(candidate["certificate_kind"] == "expanded_archive_support" and candidate["k"] == k
            and candidate["contract_id"] == bindings["contract"]["contract_id"], "Wrong certificate contract")
    require(candidate["claim"] == problem["claim"], "Certificate claim changed")
    require(candidate["initial_evidence"] == problem["initial_evidence"]
            and candidate["initial_evidence_pin"] == pin(problem["initial_evidence"]), "Certificate initial evidence changed")
    queries = {q["id"]: q for q in problem["queries"]}
    require(candidate["query_order"] == list(queries), "Certificate query order changed")
    history = candidate["history"]
    actual = inspect_history(problem, rebuilt["worlds"], history)
    require(candidate["acquired_evidence"] == [queries[h["query_id"]]["outcomes"][h["outcome_id"]]
                                               for h in history], "Certificate acquired evidence differs")
    require(candidate["claim_status"] == actual["claim_status"]
            and candidate["terminal_status"] == actual["terminal_status"], "Certificate status unsupported")
    compatible = set(actual["compatible_world_ids"])
    require(candidate["compatible_world_count"] == len(compatible), "Certificate compatible count differs")
    worlds = {w["id"]: w for w in rebuilt["worlds"]}
    all_query_checks = 0
    if actual["claim_status"] != "unresolved":
        ids = candidate["exhaustive_compatible_hypotheses"]
        require(set(ids) == compatible and len(ids) == len(compatible), "Certificate exhaustive witnesses differ")
    else:
        pair = candidate["opposite_claim_witnesses"]
        require(len(pair) == 2 and set(pair) <= compatible
                and {claim_value(problem, worlds[wid]) for wid in pair} == {False, True}, "Invalid unresolved witnesses")
        if actual["terminal_status"] == "archive_irreducible":
            covered = candidate["all_remaining_signature_cells"]
            by_signature = {tuple(c["signature"]): c for c in actual["signature_cells"]}
            require(len(covered) == len(by_signature), "Irreducibility fails to cover all signature cells")
            seen = set()
            for cell in covered:
                signature = tuple(cell["complete_query_signature"])
                require(signature in by_signature and signature not in seen, "Unknown or duplicate irreducible cell")
                seen.add(signature)
                ids = set(by_signature[signature]["world_ids"])
                pair = cell["opposite_claim_witnesses"]
                require(cell["compatible_world_count"] == len(ids) and len(pair) == 2 and set(pair) <= ids,
                        "Wrong irreducible-cell witnesses/count")
                all_query_checks += check_same_signature_opposites(problem, worlds[pair[0]], worlds[pair[1]])
    return {"all_query_witness_checks": all_query_checks, "compatible_worlds": len(compatible)}


def verify_cell(problem, k, cell):
    """Verify a saved complete census and its policy histories without core caches.

    The nominal optimizer itself is reused only to check unchanged action choices;
    all physical support and inference checks here use independent reconstruction.
    """
    require(cell["problem_id"] == problem["problem_id"] and cell["k"] == k, "Cell identity mismatch")
    require(cell["stratum"] == problem["stratum"] and cell["subtype"] == problem.get("subtype", problem["stratum"]),
            "Cell stratum/subtype changed")
    if cell.get("census_status") != "completed":
        require(cell.get("status") == "unavailable" and bool(cell.get("failure")), "Unexplained unavailable cell")
        return {"verified": False, "status": "unavailable", "failure": copy.deepcopy(cell["failure"])}
    rebuilt = verify_expansion(problem, k, cell["expansion"])
    worlds, nominal_worlds = rebuilt["worlds"], rebuilt["nominal_worlds"]
    nominal = Model(problem)
    planner = CappedPlanner(nominal, "exact_optimal", state_cap=100_000)
    queries = {q["id"]: q for q in problem["queries"]}
    positions = {qid: index for index, qid in enumerate(queries)}
    expanded_by_id = {w["id"]: w for w in worlds}
    nominal_by_id = {w["id"]: w for w in nominal_worlds}
    signatures = {full_signature(problem, w) for w in worlds}
    nominal_signatures = {full_signature(problem, w) for w in nominal_worlds}
    rows = cell["signature_rows"]
    require(len(rows) == len(signatures) and {tuple(r["outcomes"]) for r in rows} == signatures,
            "Census does not retain every expanded full signature exactly once")
    verification = {"verified": True, "signature_rows": len(rows), "policy_histories": 0,
                    "policy_prefixes": 0, "nominal_certificates": 0, "expanded_certificates": 0,
                    "all_query_witness_checks": 0, "counterexamples": 0, "nominal_conflicts": 0,
                    "embedding_checks": len(nominal_worlds), "nested_support_checks": 0,
                    "provenance_constructions": rebuilt["generated_candidates"],
                    "monotonic_definite_histories": 0, "preserved_mixed_full_cells": 0,
                    "partial_irreducibility_changes": 0, "unavailable_policy_histories": 0}
    if k:
        smaller = reconstruct(problem, k - 1)
        require({canonical(physical(w)) for w in smaller["worlds"]}
                <= {canonical(physical(w)) for w in worlds}, "Expanded supports are not nested")
        verification["nested_support_checks"] = len(smaller["worlds"])
    certificates = cell["certificates"]
    for key, certificate in certificates.items():
        require(pin(certificate) == key, "Certificate locator hash differs")
        if certificate.get("certificate_kind") == "expanded_archive_support":
            checked = verify_expanded_certificate(problem, k, certificate, rebuilt)
            verification["expanded_certificates"] += 1
            verification["all_query_witness_checks"] += checked["all_query_witness_checks"]
        else:
            require(nominal.verify_certificate(certificate), "Original checker rejects nominal certificate")
            direct = inspect_history(problem, nominal_worlds, certificate["history"])
            expected = "inconsistent" if direct["terminal_status"] == "model_conflict" else direct["terminal_status"]
            require(certificate["status"] == expected
                    and certificate["compatible_world_count"] == len(direct["compatible_world_ids"]),
                    "Nominal certificate disagrees with independently filtered support")
            verification["nominal_certificates"] += 1

    def cert_link(key, history, expanded):
        require(key in certificates, "Missing referenced certificate")
        cert = certificates[key]
        require(cert["history"] == history, "Certificate belongs to a different acquired history")
        require((cert.get("certificate_kind") == "expanded_archive_support") == expanded,
                "Certificate was relabeled across contracts")

    def monotonic(history, old, new, *, complete=False):
        if old["claim_status"] == "model_conflict":
            return
        # Explicit physical witnesses preserve nominal compatibility; prior
        # weights and the evaluator's actual realization are never consulted.
        old_keys = {canonical(physical(nominal_by_id[wid])) for wid in old["compatible_world_ids"]}
        new_keys = {canonical(physical(expanded_by_id[wid])) for wid in new["compatible_world_ids"]}
        require(old_keys <= new_keys, "History lost an embedded nominal witness")
        if old["claim_status"] in {"established", "ruled_out"}:
            require(new["claim_status"] in {old["claim_status"], "unresolved"}, "Definite claim reversed under expansion")
            verification["monotonic_definite_histories"] += 1
        else:
            require(new["claim_status"] == "unresolved", "Nominal opposite witnesses disappeared")
            if complete:
                require(new["terminal_status"] == "archive_irreducible", "Mixed full-signature cell lost ambiguity")
                verification["preserved_mixed_full_cells"] += 1
        if not complete and old["terminal_status"] == "archive_irreducible" and new["terminal_status"] != "archive_irreducible":
            verification["partial_irreducibility_changes"] += 1

    expected_row_values = []
    for row in rows:
        signature = tuple(row["outcomes"])
        history = [{"query_id": qid, "outcome_id": outcome}
                   for qid, outcome in zip(queries, signature, strict=True)]
        old = inspect_history(problem, nominal_worlds, history)
        new = inspect_history(problem, worlds, history)
        require(row["signature_id"] == pin({"query_ids": tuple(queries), "outcomes": signature}), "Signature identity differs")
        for prefix, actual in (("nominal", old), ("expanded", new)):
            require(row[prefix + "_claim_status"] == actual["claim_status"]
                    and row[prefix + "_terminal_status"] == actual["terminal_status"], "Full-signature status differs")
        original = signature in nominal_signatures
        require(row["population"] == ("original" if original else "new"), "Original/new denominator changed")
        monotonic(history, old, new, complete=True)
        transition = ("nominal_conflict" if not original else "definite_to_unresolved"
                      if old["claim_status"] in {"established", "ruled_out"} and new["claim_status"] == "unresolved"
                      else "originally_ambiguous" if old["claim_status"] == "unresolved" else "unchanged_definite")
        require(row["transition"] == transition, "Saved transition differs")
        cert_link(row["nominal_certificate"], history, False)
        cert_link(row["expanded_certificate"], history, True)
        witness = row["counterexample"]
        if transition == "definite_to_unresolved":
            require(isinstance(witness, dict), "Missing opposite counterexample")
            left = nominal_worlds[witness["nominal_world_index"]]
            right = cell["expansion"]["worlds"][witness["expanded_world_index"]]
            require(left["id"] == witness["nominal_world_id"] and right["id"] == witness["expanded_world_id"], "Witness index/ID differs")
            require(witness["nominal_claim_value"] == claim_value(problem, left)
                    and witness["expanded_claim_value"] == claim_value(problem, right), "Stored witness truth differs from physical facts")
            require(tuple(witness["full_signature"]) == signature == full_signature(problem, left), "Counterexample belongs to another archive")
            verification["all_query_witness_checks"] += check_same_signature_opposites(problem, left, right)
            verification["counterexamples"] += 1
        else:
            require(witness is None, "Unexpected definite-loss witness")
        if not original:
            require(not old["compatible_world_ids"], "Nominal-conflict certificate has a compatible witness")
            verification["nominal_conflicts"] += 1

        policy = row["policy"]
        paid = policy["history"]
        require(len({h["query_id"] for h in paid}) == len(paid), "Policy repeats a lookup")
        cost = returned_bytes = 0
        for index, item in enumerate(paid):
            before = paid[:index]
            direct_before = inspect_history(problem, nominal_worlds, before)
            require(direct_before["terminal_status"] == "unresolved_pending", "Query after nominal conflict/termination")
            require(planner.choose(before) == item["query_id"], "Policy differs from original nominal exact action")
            require(item["outcome_id"] == signature[positions[item["query_id"]]], "Paid observation differs from actual archive signature")
            query = queries[item["query_id"]]
            cost += query["cost"]
            returned_bytes += len(canonical(query["outcomes"][item["outcome_id"]]))
            after = paid[:index + 1]
            old_after = inspect_history(problem, nominal_worlds, after)
            new_after = inspect_history(problem, worlds, after)
            monotonic(after, old_after, new_after)
            require(old_after["claim_status"] != "model_conflict" or index == len(paid) - 1,
                    "Policy continued after its first model conflict")
            verification["policy_prefixes"] += 1
        final_old = inspect_history(problem, nominal_worlds, paid)
        final_new = inspect_history(problem, worlds, paid)
        monotonic(paid, final_old, final_new)
        for prefix, actual in (("", final_old), ("expanded_", final_new)):
            require(policy[prefix + "claim_status"] == actual["claim_status"]
                    and policy[prefix + "terminal_status"] == actual["terminal_status"], "Policy-stop inference differs")
        require(policy["cost"] == cost and policy["query_count"] == len(paid)
                and policy["returned_bytes"] == returned_bytes, "Paid lookup accounting differs")
        if policy["status"] == "unavailable":
            require(bool(policy.get("failure")), "Unavailable policy lacks a failure reason")
            verification["unavailable_policy_histories"] += 1
        elif final_old["claim_status"] == "model_conflict":
            require(policy["status"] == "model_conflict_detected", "Conflict was not marked at policy stop")
        else:
            require(final_old["terminal_status"] in {"established", "ruled_out", "archive_irreducible"}
                    and policy["status"] == final_old["terminal_status"] and planner.choose(paid) is None,
                    "Nominal policy stopped before its unchanged terminal rule")
        cert_link(policy["certificate"], paid, False)
        cert_link(policy["expanded_certificate"], paid, True)
        require(policy["certificate_valid"] is True, "Policy certificate marked invalid")
        unsupported = final_old["claim_status"] in {"established", "ruled_out"} and final_new["claim_status"] == "unresolved"
        overstrong = final_old["terminal_status"] == "archive_irreducible" and final_new["terminal_status"] != "archive_irreducible"
        classification = ("policy_unavailable" if policy["status"] == "unavailable" else
                          "conflict_detected" if final_old["claim_status"] == "model_conflict" else
                          "full_conflict_missed" if not original else
                          "nominal_compatible_unsupported_definite" if unsupported else
                          "nominal_archive_irreducibility_overstrong" if overstrong else
                          "nominal_conclusion_remains_justified")
        require(policy["classification"] == classification and policy["unsupported_definite"] == unsupported
                and policy["overstrong_archive_irreducibility"] == overstrong, "Policy outcome classification differs")
        verification["policy_histories"] += 1
        expected_row_values.append({"original": original, "old": old["claim_status"], "new": new["claim_status"],
                                    "transition": transition, "classification": classification,
                                    "unsupported_definite": unsupported, "overstrong_archive_irreducibility": overstrong,
                                    "unavailable": policy["status"] == "unavailable", "cost": cost, "queries": len(paid)})
    _verify_counts_and_controls(problem, cell, rebuilt, expected_row_values)
    return verification


def _verify_counts_and_controls(problem, cell, rebuilt, rows):
    old = [r for r in rows if r["original"]]
    new = [r for r in rows if not r["original"]]
    expected = {"original_signatures": len(old), "new_signatures": len(new), "expanded_signatures": len(rows)}
    for label in ("established", "ruled_out", "unresolved"):
        expected["original_" + label] = sum(r["old"] == label for r in old)
        expected["new_" + label] = sum(r["new"] == label for r in new)
    for label in ("established", "ruled_out"):
        expected["lost_" + label] = sum(r["old"] == label and r["new"] == "unresolved" for r in old)
        expected["unchanged_" + label] = expected["original_" + label] - expected["lost_" + label]
    expected["original_definite"] = expected["original_established"] + expected["original_ruled_out"]
    expected["lost_definite"] = expected["lost_established"] + expected["lost_ruled_out"]
    for population, selected in (("original", old), ("new", new), ("all", rows)):
        expected[population + "_policy_unavailable"] = sum(r["unavailable"] for r in selected)
        for flag in ("unsupported_definite", "overstrong_archive_irreducibility"):
            expected[population + "_" + flag] = sum(r[flag] for r in selected)
        for label in ("conflict_detected", "full_conflict_missed", "nominal_compatible_unsupported_definite",
                      "nominal_archive_irreducibility_overstrong", "nominal_conclusion_remains_justified"):
            expected[population + "_" + label] = sum(r["classification"] == label for r in selected)
        expected[population + "_query_count"] = sum(r["queries"] for r in selected)
        expected[population + "_retrieval_cost"] = sum(r["cost"] for r in selected)
    require(cell["counts"] == expected, "Saved transition/policy count denominators differ")
    records = {r["id"]: r for r in problem["record_catalog"]}
    eligible = {q["record_id"] for q in problem["queries"] if records[q["record_id"]]["kind"] == "context_receipt"}
    eligible -= set(problem["initial_record_ids"])
    controls = {
        "no_eligible_omissions": not any(eligible & set(w["retained_record_ids"]) for w in problem["worlds"]),
        "no_new_signatures": not new, "no_changed_conclusions": expected["lost_definite"] == 0,
        "no_support_change": len(rebuilt["worlds"]) == len({canonical(physical(w)) for w in rebuilt["nominal_worlds"]}),
        "nominal_initially_irreducible": inspect_history(problem, rebuilt["nominal_worlds"], [])["terminal_status"] == "archive_irreducible"}
    require(cell["controls"] == controls, "Saved unaffected-control classification differs")
    available = expected["all_policy_unavailable"] == 0
    require(cell["policy_status"] == ("completed" if available else "unavailable")
            and cell["status"] == ("completed" if available else "policy_unavailable"),
            "Cell availability conceals an unfinished policy")
