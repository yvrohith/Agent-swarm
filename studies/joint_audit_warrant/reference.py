"""Independent joint-frontier, physical-warrant and paid-path verification.

The whole-tree oracle uses no dynamic program or child-frontier pruning. The
saved Bellman witness is checked by exhaustive feasible action/branch products
with an independent three-objective dominance implementation. Preserved physical
validators, claim semantics, canonicalization and certificate checkers are shared
dependencies, not independently established real-world assumptions.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import product

from studies.audit_aware_acquisition import reference as audit_reference
from studies.exact_audit_frontier import reference as exact_reference
from tracebench.evidence_acquisition.model import canonical, pin

ANCHORS = (0, 25, 50, 100)
ARMS = ("exact_frontier", "E_then_support", "joint_frontier")
ROOT_FIELDS = ("nominal_model_pin", "design_signature_set_pin", "base_history", "root_pin", "root_id",
               "baseline", "signatures", "root_signature_set_pin", "signature_count", "original_signature_count",
               "new_signature_count", "unqueried_query_ids", "residual_cost", "original_path_verified",
               "problem_id", "stratum", "subtype")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nondominated(triples):
    values = set(triples)
    return sorted((d, w, cost) for d, w, cost in values if not any(
        od >= d and ow >= w and oc <= cost and (od, ow, oc) != (d, w, cost)
        for od, ow, oc in values))


def support_state(nominal_signatures, physical_truths, possible, proposal):
    """Every physical realization in every compatible signature remains relevant."""
    possible = set(possible)
    require(bool(possible) and possible <= physical_truths.keys(), "Empty or undeclared physical support")
    values = set().union(*(physical_truths[s] for s in possible))
    require(bool(values), "Empty physical-world support is not definite warrant")
    claim = "established" if values == {True} else "ruled_out" if values == {False} else "unresolved"
    terminal = claim if claim != "unresolved" else (
        "archive_irreducible" if all(physical_truths[s] == {False, True} for s in possible) else "unresolved_pending")
    definite = proposal in {"established", "ruled_out"}
    supported = definite and claim == proposal
    desired = proposal == "established"
    attainable = definite and any(physical_truths[s] == {desired} for s in possible)
    reward = len(set(nominal_signatures) & possible) if supported else 0
    return {"claim_status": claim, "terminal_status": terminal, "supported": supported,
            "support_attainable": attainable, "reward": reward}


def physical_truths(problem, expanded_worlds):
    by_signature = defaultdict(set)
    for world in audit_reference.direct_support(problem, expanded_worlds):
        by_signature[world["signature"]].add(world["truth"])
    return dict(by_signature)


def physical_pin(problem, expansion):
    return pin({"expanded_model_pin": expansion["model_pin"], "expanded_contract_pin": expansion["contract_pin"],
                "expanded_support_pin": expansion["support_pin"], "claim": problem["claim"]})


def exhaustive_tree_oracle(query_ids, costs, nominal_rows, truth_sets, proposal, base_history, budget):
    """Enumerate all complete deterministic trees on at most three actions."""
    query_ids = tuple(query_ids)
    nominal = set(map(tuple, nominal_rows))
    design = set(truth_sets)
    require(nominal <= design, "Hypothetical physical support omits a nominal signature")
    remaining = tuple(q for q in query_ids if q not in {h["query_id"] for h in base_history})
    require(len(remaining) <= 3, "Whole-tree oracle is limited to three remaining actions")
    require(type(budget) is int and budget >= 0 and all(type(costs[q]) is int and costs[q] > 0 for q in query_ids),
            "Invalid hard budget or action price")
    root_n = audit_reference.compatible(nominal, query_ids, base_history)
    root_t = audit_reference.compatible(design, query_ids, base_history)
    positions = {q: i for i, q in enumerate(query_ids)}

    def trees(n, t, available, funds):
        support = support_state(nominal, truth_sets, t, proposal)
        if not n:
            require(not t & nominal, "Conflict branch contains a nominal signature")
            return [(len(t), 0, 0, {"action": None, "children": []})]
        output = [(0, support["reward"], 0, {"action": None, "children": []})]
        for qid in available:
            if costs[qid] > funds:
                continue
            outcomes = sorted({s[positions[qid]] for s in t})
            alternatives = []
            for outcome in outcomes:
                nn = {s for s in n if s[positions[qid]] == outcome}
                tt = {s for s in t if s[positions[qid]] == outcome}
                alternatives.append(trees(nn, tt, tuple(q for q in available if q != qid), funds - costs[qid]))
            for children in product(*alternatives):
                output.append((sum(c[0] for c in children), sum(c[1] for c in children),
                               len(t) * costs[qid] + sum(c[2] for c in children),
                               {"action": qid, "children": [{"outcome": outcome, "tree": child[3],
                                                             "d": child[0], "w": child[1], "l": child[2]}
                                                            for outcome, child in zip(outcomes, children, strict=True)]}))
        return output

    all_trees = trees(root_n, root_t, remaining, budget)
    frontier = nondominated((d, w, cost) for d, w, cost, _ in all_trees)
    d, w, cost = min(frontier, key=lambda p: (-p[0], -p[1], p[2]))
    return {"tree_count": len(all_trees), "frontier": [{"d": d, "w": w, "l": cost} for d, w, cost in frontier],
            "canonical_value": {"d": d, "w": w, "l": cost}, "trees": all_trees}


def choice_order(choice, costs):
    qid = choice["action"]
    if qid is None:
        return (0, 0, "", b"")
    return (1, costs[qid], qid, canonical([[c["outcome"], c["state_id"], c["d"], c["w"], c["l"]]
                                          for c in choice["children"]]))


def verify_bellman(query_ids, costs, nominal_rows, truth_sets, proposal, nominal_pin, physical_model_pin,
                   solver, old_solver=None):
    """Check every affordable action and every combination of verified children."""
    qids, nominal_rows = tuple(query_ids), tuple(map(tuple, nominal_rows))
    design, nominal_signatures = tuple(sorted(truth_sets)), set(nominal_rows)
    require(0 < len(qids) <= 8 and 0 < len(design) <= 256 and nominal_signatures <= set(design), "Invalid bounded design support")
    root, states = solver["root"], {s["state_id"]: s for s in solver["states"]}
    history = root["base_history"]
    remaining = sorted(set(qids) - {h["query_id"] for h in history})
    nset = audit_reference.compatible(nominal_signatures, qids, history)
    tset = audit_reference.compatible(design, qids, history)
    nm = sum(1 << i for i, s in enumerate(nominal_rows) if s in nset)
    tm = sum(1 << i for i, s in enumerate(design) if s in tset)
    require(bool(nm) and bool(tm), "Original paid root must retain nominal and physical support")
    residual = sum(costs[q] for q in remaining)
    requested, budgets = root["requested_budgets"], root["budgets"]
    require(0 < len(requested) <= 4 and all(type(b) is int and 0 <= b <= residual for b in requested)
            and budgets == sorted(set(requested)), "Invalid anchored budget schedule")
    design_pin = pin({"query_ids": list(qids), "signatures": [list(s) for s in design]})
    scope = pin({"nominal_pin": nominal_pin, "design_pin": design_pin, "physical_pin": physical_model_pin,
                 "proposal": proposal, "base_history": history})
    audit_reference._same(root, {"nominal_pin": nominal_pin, "design_pin": design_pin, "physical_pin": physical_model_pin,
                                "scope_pin": scope, "proposal": proposal, "query_ids": list(qids),
                                "nominal_mask": hex(nm), "design_mask": hex(tm),
                                "remaining_actions": remaining, "residual_cost": residual}, "Joint Bellman root")
    require(len(states) == len(solver["states"]) and len(states) <= 100000, "Duplicate or excessive joint states")
    combinations_checked, verified, edges = 0, {}, defaultdict(set)

    def descriptor(state):
        n, t = int(state["nominal_mask"], 16), int(state["design_mask"], 16)
        available, budget = state["remaining_actions"], state["budget"]
        require(type(budget) is int and 0 <= budget <= residual and available == sorted(set(available))
                and set(available) <= set(remaining), "Invalid joint state action set or budget")
        require(n & ~nm == 0 and t & ~tm == 0 and t > 0, "Joint state leaves its physical root")
        require(state["state_id"] == exact_reference._state_id(scope, n, t, available, budget), "Joint state digest mismatch")
        possible = {s for i, s in enumerate(design) if t & (1 << i)}
        paid = []
        for q in set(remaining) - set(available):
            values = {s[qids.index(q)] for s in possible}
            require(len(values) == 1, "A paid query retains multiple possible observed answers")
            paid.append({"query_id": q, "outcome_id": next(iter(values))})
        nallowed = audit_reference.compatible(nominal_signatures, qids, history + paid)
        tallowed = audit_reference.compatible(design, qids, history + paid)
        require(n == sum(1 << i for i, s in enumerate(nominal_rows) if s in nallowed)
                and possible == tallowed, "State masks omit compatible nominal/physical possibilities")
        original_budget = budget + sum(costs[h["query_id"]] for h in paid)
        require(original_budget in budgets, "Counterfactual state is outside all declared pathwise allowances")
        return n, t, available, budget, possible

    for state in sorted(states.values(), key=lambda s: (len(s["remaining_actions"]), s["state_id"])):
        n, t, available, budget, possible = descriptor(state)
        support = support_state(nominal_signatures, truth_sets, possible, proposal)
        reward = support["reward"] if n else 0
        require(n or not possible & nominal_signatures, "Alarm state contains an original signature")
        require(state["terminal_conflict"] == (n == 0) and state["stop_reward"] == reward, "Incorrect physical STOP reward")
        candidates = {(0 if n else len(possible), reward, 0): {"action": None, "children": []}}
        actions = {a["query_id"]: a for a in state["actions"]}
        feasible = {q for q in available if costs[q] <= budget} if n else set()
        require(len(actions) == len(state["actions"]) and set(actions) == feasible, "Omitted or extra affordable Bellman action")
        for q in sorted(feasible):
            action, position = actions[q], qids.index(q)
            require(action["cost"] == costs[q], "Incorrect joint action price")
            branches, choices = [], []
            for outcome in sorted({s[position] for s in possible}):
                cn = sum(1 << i for i, s in enumerate(nominal_rows) if n & (1 << i) and s[position] == outcome)
                ct = sum(1 << i for i, s in enumerate(design) if t & (1 << i) and s[position] == outcome)
                child_id = exact_reference._state_id(scope, cn, ct, [a for a in available if a != q], budget - costs[q])
                require(child_id in verified, "Missing or unverified joint child state")
                edges[state["state_id"]].add(child_id)
                branches.append({"outcome": outcome, "child_state_id": child_id, "design_count": ct.bit_count()})
                choices.append([(outcome, child_id, *triple) for triple in verified[child_id]])
            require(action["branches"] == branches, "Joint branch partition does not cover all hypothetical outcomes")
            for children in product(*choices):
                combinations_checked += 1
                require(combinations_checked <= 10000000, "Joint child-combination verification cap exceeded")
                triple = (sum(c[2] for c in children), sum(c[3] for c in children),
                          len(possible) * costs[q] + sum(c[4] for c in children))
                choice = {"action": q, "children": [{"outcome": o, "state_id": child, "d": d, "w": w, "l": cost}
                                                     for o, child, d, w, cost in children]}
                if triple not in candidates or choice_order(choice, costs) < choice_order(candidates[triple], costs):
                    candidates[triple] = choice
        expected = [{"d": d, "w": w, "l": cost, "choice": candidates[d, w, cost]}
                    for d, w, cost in sorted(nondominated(candidates), key=lambda p: (-p[0], -p[1], p[2]))]
        require(state["frontier"] == expected, "Joint frontier, Pareto dominance or canonical tie is incorrect")
        verified[state["state_id"]] = {(p["d"], p["w"], p["l"]) for p in expected}
    resources, pending = solver["resources"], solver["pending_states"]
    state_cap, combo_cap = resources["state_cap"], resources["combination_cap"]
    require(type(state_cap) is int and 0 < state_cap <= 100000 and type(combo_cap) is int and 0 < combo_cap <= 10000000,
            "Joint resource cap was silently enlarged")
    require(len({s["state_id"] for s in pending}) == len(pending)
            and not {s["state_id"] for s in pending} & set(states), "Duplicate pending/completed joint state")
    for state in pending:
        descriptor(state)
    audit_reference._same(resources, {"solver_states": len(states) + len(pending), "completed_states": len(states),
                                      "pending_states": len(pending), "requested_budget_count": len(budgets),
                                      "requested_anchor_count": len(requested),
                                      "total_frontier_points": sum(len(s["frontier"]) for s in states.values()),
                                      "maximum_frontier_size": max((len(s["frontier"]) for s in states.values()), default=0)},
                          "Joint resource accounting")
    require(resources["solver_states"] <= state_cap and combinations_checked <= resources["child_combinations"] <= combo_cap,
            "Joint cap counters do not match retained work")
    completed = solver["status"] == "complete"
    entries = {e["budget"]: e for e in solver["budget_frontiers"]}
    projections = []
    if completed:
        require(set(entries) == set(budgets) and len(entries) == len(solver["budget_frontiers"]), "Missing joint anchor frontier")
        require(not pending and solver["cap"] is None and resources["child_combinations"] == combinations_checked
                and resources["completed_budget_count_before_cap"] == len(budgets), "Incomplete joint solve claims optimality")
        visited = set()
        for budget in budgets:
            entry = entries[budget]
            sid = exact_reference._state_id(scope, nm, tm, remaining, budget)
            require(entry["state_id"] == sid and sid in states and entry["frontier"] == states[sid]["frontier"],
                    "Joint root frontier differs from its verified witness")
            primary = min(entry["frontier"], key=lambda p: (-p["d"], -p["w"], p["l"], choice_order(p["choice"], costs)))
            require(entry["canonical_point"] == primary, "J is not the frozen lexicographic optimum")
            projected = exact_reference.nondominated((p["d"], p["l"]) for p in entry["frontier"])
            if old_solver is not None:
                require(old_solver["root"]["nominal_pin"] == nominal_pin and old_solver["root"]["design_pin"] == design_pin
                        and old_solver["root"]["base_history"] == history, "Historical E uses different hypothetical inputs")
                old = next((e for e in old_solver["budget_frontiers"] if e["budget"] == budget), None)
                require(old is not None and projected == sorted((p["d"], p["l"]) for p in old["frontier"]),
                        "Full joint projection disagrees with the saved detection-cost frontier")
            projections.append({"budget": budget, "points": [{"d": d, "l": cost} for d, cost in projected]})
            todo = [sid]
            while todo:
                current = todo.pop()
                if current not in visited:
                    visited.add(current)
                    todo.extend(edges[current])
            if budget == residual:
                ceiling = sum(s in nominal_signatures and support_state(nominal_signatures, truth_sets, {s}, proposal)["supported"]
                              for s in tset)
                require(primary["d"] == len(tset - nominal_signatures) and primary["w"] == ceiling,
                        "Full-budget joint detection/support ceiling is not attained")
        require(visited == set(states), "Unused joint states escape the reachable witness")
    else:
        require(solver["status"] == "unavailable" and not entries, "Unavailable joint solve contains an exact frontier")
        cap = solver["cap"]
        require(isinstance(cap, dict) and cap["kind"] in {"solver_states", "child_combinations"}
                and cap["limit"] == {"solver_states": state_cap, "child_combinations": combo_cap}[cap["kind"]]
                and resources[cap["kind"]] == cap["limit"], "Joint cap lacks declared resource evidence")
        done = [b for b in budgets if exact_reference._state_id(scope, nm, tm, remaining, b) in states]
        require(done == budgets[:len(done)] and resources["completed_budget_count_before_cap"] == len(done),
                "Incorrect completed anchor prefix before cap")
    return {"status": "passed" if completed else "unavailable", "optimality_verified": completed,
            "states_checked": len(states), "child_combinations_checked": combinations_checked,
            "unique_anchor_frontiers_checked": len(entries), "projections": projections}


def assessment(context, proposal, history, truth_sets):
    possible = audit_reference.compatible(truth_sets, context["query_ids"], history)
    state = support_state(context["nominal_signatures"], truth_sets, possible, proposal)
    return {"claim_status": state["claim_status"], "terminal_status": state["terminal_status"],
            "supported": state["supported"], "attainable": state["support_attainable"], "reward": state["reward"],
            "compatible_signature_count": len(possible),
            "compatible_original_signature_count": len(possible & context["nominal_signatures"]),
            "compatible_physical_world_count": sum(w["signature"] in possible for w in context["expanded_support"]),
            "nominal_conflict": not bool(audit_reference.compatible(context["nominal_signatures"], context["query_ids"], history))}


def joint_choice(solver, budget, history):
    require(solver["status"] == "complete", "Unavailable joint root cannot provide a policy")
    states = {s["state_id"]: s for s in solver["states"]}
    entry = next((e for e in solver["budget_frontiers"] if e["budget"] == budget), None)
    require(entry is not None, "Joint policy was not solved at this allowance")
    point = entry["canonical_point"]
    for observed in history:
        choice = point["choice"]
        require(choice["action"] == observed["query_id"], "Paid joint path departs from its canonical backpointer")
        child = next((c for c in choice["children"] if c["outcome"] == observed["outcome_id"]), None)
        require(child is not None and child["state_id"] in states, "Missing observed joint outcome branch")
        point = next((p for p in states[child["state_id"]]["frontier"]
                      if (p["d"], p["w"], p["l"]) == (child["d"], child["w"], child["l"])), None)
        require(point is not None, "Missing joint child triple")
    return point["choice"]["action"]


def verify_path(context, root, old_root, old_e, row, truth_sets):
    """Reconstruct every action and all physical support using paid evidence only."""
    problem, qids = context["problem"], context["query_ids"]
    queries = {q["id"]: q for q in problem["queries"]}
    base, proposal = root["base_history"], root["baseline"]["status"]
    arm, budget, signature = row["arm"], row["integer_budget"], tuple(row["outcomes"])
    require(arm in ARMS and budget in root["integer_budgets"], "Unknown joint-study policy or allowance")
    require(signature in set(map(tuple, root["signatures"])), "Executed signature belongs to another original root")
    require(row["base_history"] == base and row["history"] == base + row["audit_history"], "Nominal stopping prefix changed")
    require(signature in audit_reference.compatible({signature}, qids, row["history"]), "Paid answer differs from physical archive")
    require(row["saved_e_solver_pin"] == pin(old_root["solver"]), "Saved E solver reference changed")
    require(old_e["base_history"] == base and old_e["integer_budget"] == budget
            and tuple(old_e["outcomes"]) == signature, "Old E comparison uses different inputs")
    # This preserved independent checker replays the exact old backpointers and
    # directly checks its charges. It does not rerun or retie the old optimizer.
    exact_reference.verify_path(problem, old_root, old_e)
    old_suffix = old_e["audit_history"]
    phases = {name: [] for name in ("detection", "support", "joint")}
    if arm == "exact_frontier":
        for name, value in old_e.items():
            if name not in {"selection_seconds", "checking_seconds", "certificates"}:
                require(row.get(name) == value, "Historical E scientific path or accounting changed")
        phases["detection"] = row["audit_history"]
    elif arm == "E_then_support":
        require(row["audit_history"][:len(old_suffix)] == old_suffix, "Sequential baseline changes E's original detection phase")
        phases["detection"] = old_suffix
        phases["support"] = row["audit_history"][len(old_suffix):]
    else:
        phases["joint"] = row["audit_history"]
    base_cost, base_bytes = audit_reference._history_costs(problem, base)
    prefix, cost, size, conflict = list(base), 0, 0, None
    seen = {queries[h["query_id"]]["record_id"] for h in base}
    aliases = 0
    for index, observed in enumerate(row["audit_history"], 1):
        require(conflict is None, "Retrieval continues after the first alarm")
        qid, outcome = observed["query_id"], observed["outcome_id"]
        n = audit_reference.compatible(context["nominal_signatures"], qids, prefix)
        require(bool(n), "Acquisition starts with empty nominal compatibility")
        if arm == "joint_frontier":
            selected = joint_choice(root["solver"], budget, prefix[len(base):])
        elif index <= len(old_suffix):
            selected = exact_reference.frontier_choice(old_root["solver"], budget, prefix[len(base):])
        else:
            require(arm == "E_then_support" and old_e["status"] != "nominal_model_conflict", "Unexpected support phase")
            state = assessment(context, proposal, prefix, truth_sets)
            require(proposal in audit_reference.DEFINITE and not state["supported"] and state["attainable"],
                    "Sequential baseline queries after its support stopping condition")
            asked = {h["query_id"] for h in prefix}
            affordable = [q for q in qids if q not in asked and queries[q]["cost"] <= budget - cost]
            selected = min(affordable, key=lambda q: (queries[q]["cost"], q)) if affordable else None
        require(qid == selected, "Executed action disagrees with the fixed prospective policy")
        branches = sorted({s[qids.index(qid)] for s in n})
        cost += queries[qid]["cost"]
        size += len(canonical(queries[qid]["outcomes"][outcome]))
        require(cost <= budget, "Sequential/joint path exceeds its one original allowance")
        aliases += queries[qid]["record_id"] in seen
        seen.add(queries[qid]["record_id"])
        prefix.append(observed)
        physical = assessment(context, proposal, prefix, truth_sets)
        if physical["nominal_conflict"]:
            require(len(branches) == 1 and outcome not in branches, "Unsound nominal alarm")
            conflict = {"added_query_index": index, "added_cost": cost, "total_cost": base_cost + cost,
                        "query_id": qid, "outcome_id": outcome, "nominal_outcomes_before": branches}
    alarm = conflict is not None
    final = assessment(context, proposal, prefix, truth_sets)
    initial = assessment(context, proposal, base, truth_sets)
    original = signature in context["nominal_signatures"]
    require(alarm == final["nominal_conflict"] and not (alarm and original), "Alarm does not match nominal support")
    transition = None
    if alarm:
        termination = "nominal_conflict"
        if arm == "E_then_support" and old_e["status"] != "nominal_model_conflict":
            transition = old_e["history"]
    elif arm == "exact_frontier":
        termination = old_e["termination_reason"]
    elif arm == "joint_frontier":
        require(joint_choice(root["solver"], budget, row["audit_history"]) is None, "Joint path stops before selected action")
        termination = "catalogue_exhausted" if len(prefix) == len(qids) else "joint_policy_stop"
    else:
        transition = old_e["history"]
        if proposal not in audit_reference.DEFINITE:
            termination = "support_not_definite"
        elif final["supported"]:
            termination = "proposal_supported"
        elif not final["attainable"]:
            termination = "support_unattainable"
        else:
            asked = {h["query_id"] for h in prefix}
            require(not any(q not in asked and queries[q]["cost"] <= budget - cost for q in qids),
                    "Sequential policy stops while support remains attainable with an affordable query")
            termination = "no_affordable_support_action"
    expected = {"audit_budget": budget, "residual_cost": root["residual_cost"], "base_cost": base_cost,
                "base_query_count": len(base), "base_returned_bytes": base_bytes,
                "added_cost": cost, "total_cost": base_cost + cost, "added_query_count": len(row["audit_history"]),
                "total_query_count": len(prefix), "added_returned_bytes": size, "total_returned_bytes": base_bytes + size,
                "status": "nominal_model_conflict" if alarm else "no_conflict_observed", "next_query": None,
                "first_conflict": conflict, "termination_reason": termination, "original_proposal": proposal,
                "proposal_withheld": alarm and proposal in audit_reference.DEFINITE,
                "baseline_certificate": root["baseline"]["certificate"], "sequential_transition_history": transition,
                "phase_histories": phases, "population": "original" if original else "new", "design_support": final,
                "design_supported_original": original and final["supported"] and not alarm,
                "design_initially_supported_original": original and initial["supported"],
                "design_newly_supported_original": original and final["supported"] and not alarm and not initial["supported"]}
    for name, phase_history in phases.items():
        phase_cost, phase_size = audit_reference._history_costs(problem, phase_history)
        expected.update({name + "_phase_cost": phase_cost, name + "_phase_query_count": len(phase_history),
                         name + "_phase_returned_bytes": phase_size})
    audit_reference._same(row, expected, "Paid joint-study path")
    audit_reference._same(row["coverage"], {"catalogue_actions": len(qids), "base_actions": len(base),
                                           "audited_actions": len(row["audit_history"]), "total_acquired_actions": len(prefix),
                                           "remaining_actions": len(qids) - len(prefix), "complete": len(prefix) == len(qids),
                                           "distinct_record_ids_queried": len(seen), "added_alias_queries": aliases}, "Catalogue coverage")
    return {"detected": alarm, "supported_original": expected["design_supported_original"], "cost": cost}


def verify_measurements(root, old_root, grouped_runs):
    new = {e["budget"]: e for e in root["solver"]["budget_frontiers"]}
    old = {e["budget"]: e for e in old_root["solver"]["budget_frontiers"]}
    points, summaries = [], []
    for budget in root["integer_budgets"]:
        frontier = new[budget]["frontier"] if budget in new else None
        old_pairs = sorted({(p["d"], p["l"]) for p in old[budget]["frontier"]})
        projection = exact_reference.nondominated((p["d"], p["l"]) for p in frontier) if frontier is not None else None
        require(projection is None or projection == old_pairs, "Recorded joint projection changes the old detection frontier")
        current = {}
        for arm in ARMS:
            selected = grouped_runs[budget, arm]
            complete = all(r["execution_status"] == "completed" for r in selected)
            point = {"integer_budget": budget, "arm": arm, "status": "completed" if complete else "unavailable",
                     "signature_count": root["signature_count"],
                     "d": sum(r["status"] == "nominal_model_conflict" for r in selected) if complete else None,
                     "w": sum(r["design_supported_original"] for r in selected) if complete else None,
                     "l": sum(r["added_cost"] for r in selected) if complete else None,
                     "newly_supported_original": sum(r["design_newly_supported_original"] for r in selected) if complete else None,
                     "original_cost": sum(r["added_cost"] for r in selected if r["population"] == "original") if complete else None,
                     "new_cost": sum(r["added_cost"] for r in selected if r["population"] == "new") if complete else None,
                     "phase_costs": {phase: sum(r[phase + "_phase_cost"] for r in selected) if complete else None
                                     for phase in ("detection", "support", "joint")}, "dominating_joint_point": None}
            if complete:
                require(point["d"] == old[budget]["canonical_point"]["d"], "A feasible arm loses or exceeds maximum detection")
                require(point["newly_supported_original"] == point["w"] - root["support_baseline"]["initial_supported"],
                        "Already-supported proposals are misreported as restored")
                require(point["w"] <= root["support_baseline"]["full_archive_support_ceiling"], "Support exceeds full-archive ceiling")
                if arm == "exact_frontier":
                    require(point["l"] == old[budget]["canonical_point"]["l"], "E no longer realizes its saved cost optimum")
                if frontier is not None:
                    eligible = [p for p in frontier if p["d"] >= point["d"] and p["w"] >= point["w"] and p["l"] <= point["l"]]
                    require(bool(eligible), "A feasible policy triple escapes the exact joint frontier")
                    point["dominating_joint_point"] = min(eligible, key=lambda p: (p["l"], -p["d"], -p["w"], canonical(p)))
                    if arm == "joint_frontier":
                        require(tuple(point[key] for key in ("d", "w", "l")) == tuple(new[budget]["canonical_point"][key]
                                                                                         for key in ("d", "w", "l")),
                                "Paid J executions do not realize their Bellman triple")
            current[arm] = point
            points.append(point)
        e, sequential, joint = (current[arm] for arm in ARMS)
        maximum_detection = old[budget]["canonical_point"]["d"]
        levels = sorted((p for p in frontier if p["d"] == maximum_detection), key=lambda p: (p["w"], p["l"], canonical(p))) \
            if frontier is not None else None
        curve = []
        if levels is not None:
            for threshold in range(root["support_baseline"]["full_archive_support_ceiling"] + 1):
                candidates = [p for p in levels if p["w"] >= threshold]
                selected = min(candidates, key=lambda p: (p["l"], -p["w"], canonical(p))) if candidates else None
                curve.append({"minimum_supported_original": threshold, "minimum_cost": selected["l"] if selected else None,
                              "attaining_point": selected})
        free = [p for p in levels or () if p["l"] <= e["l"]]
        free = min(free, key=lambda p: (-p["w"], p["l"], canonical(p))) if free else None

        def difference(a, b, key):
            return a[key] - b[key] if a[key] is not None and b[key] is not None else None

        summary = {"integer_budget": budget, "detection_ceiling": maximum_detection,
                   "saved_detection_cost_frontier": [{"d": d, "l": cost} for d, cost in old_pairs],
                   "joint_projection": [{"d": d, "l": cost} for d, cost in projection] if projection is not None else None,
                   "projection_equal": True if frontier is not None else None,
                   "maximum_detection_nondominated_support_levels": levels,
                   "support_threshold_price_curve": curve if frontier is not None else None,
                   "zero_extra_e_cost_point": free, "zero_extra_cost_support_gain": free["w"] - e["w"] if free is not None else None,
                   "joint_support_gain_vs_e": difference(joint, e, "w"),
                   "joint_support_gain_vs_sequential": difference(joint, sequential, "w"),
                   "joint_added_cost_vs_e": difference(joint, e, "l"),
                   "joint_added_cost_vs_sequential": difference(joint, sequential, "l"),
                   "sequential_support_gain_vs_e": difference(sequential, e, "w"),
                   "sequential_added_cost_vs_e": difference(sequential, e, "l"),
                   "sequential_matched_support_point": sequential["dominating_joint_point"],
                   "sequential_matched_support_cost_saving": sequential["l"] - sequential["dominating_joint_point"]["l"]
                   if sequential["dominating_joint_point"] is not None else None}
        summaries.append(summary)
    require(root["design_points"] == points, "Root reward/cost points do not reproduce from verified paid paths")
    require(root["budget_summary"] == summaries, "Support prices or saved-E comparisons do not reproduce exactly")


def verify_all(problems, saved_conditions, old_roots, old_design_runs, roots, design_runs, runs, certificates):
    contexts = audit_reference._contexts(problems, saved_conditions)
    by_problem = {p["problem_id"]: p for p in problems}
    old_by_root = {(r["problem_id"], r["root_id"]): r for r in old_roots}
    by_root = {(r["problem_id"], r["root_id"]): r for r in roots}
    require(len(old_by_root) == len(old_roots) and len(by_root) == len(roots) and set(by_root) == set(old_by_root),
            "New study omits, adds or duplicates historical roots")
    require({pid for pid, _ in by_root} == set(by_problem), "Historical root population differs from declared problems")
    old_e_index = {(r["problem_id"], r["root_id"], r["integer_budget"], tuple(r["outcomes"])): r
                   for r in old_design_runs if r["arm"] == "exact_frontier"}
    require(len(old_e_index) == sum(r["arm"] == "exact_frontier" for r in old_design_runs), "Duplicate saved E execution")
    truths = {pid: physical_truths(problem, contexts[pid, 2]["expansion"]["worlds"]) for pid, problem in by_problem.items()}
    checker = audit_reference._CertificateChecks(certificates)
    references, signature_roots = set(), {}
    counts = defaultdict(int)
    for key in ("joint_roots_verified", "joint_roots_unavailable", "completed_design_paths_checked", "unavailable_design_rows",
                "completed_anchor_paths_checked", "unavailable_anchor_rows"):
        counts[key] = 0
    for (pid, rid), root in by_root.items():
        problem, old, context = by_problem[pid], old_by_root[pid, rid], contexts[pid, 2]
        require(all(root[field] == old[field] for field in ROOT_FIELDS), "Historical root metadata or original proposal changed")
        require(root["old_root_pin"] == pin(old) and root["old_solver_pin"] == pin(old["solver"]), "Historical root/solver binding changed")
        require(old["exact_status"] == "completed" and old["solver"]["status"] == "complete", "Unavailable old E cannot be silently replaced")
        signatures = set(map(tuple, root["signatures"]))
        compatible = audit_reference.compatible(truths[pid], context["query_ids"], root["base_history"])
        require(signatures == compatible and len(signatures) == len(root["signatures"]), "Root grouping omits compatible physical signatures")
        proposal = root["baseline"]["status"]
        for signature in signatures:
            require((pid, signature) not in signature_roots, "A design signature belongs to multiple nominal roots")
            source = context["signature_rows"][signature]["policy"]
            require(source["history"] == root["base_history"] and source["status"] == proposal
                    and source["certificate"] == root["baseline"]["certificate"], "Root no longer preserves the nominal stopping proposal")
            signature_roots[pid, signature] = root
        anchors = [{"budget_percent": p, "integer_budget": root["residual_cost"] * p // 100} for p in ANCHORS]
        integer_budgets = sorted({a["integer_budget"] for a in anchors})
        audit_reference._same(root, {"anchor_budgets": anchors, "integer_budgets": integer_budgets,
                                     "physical_pin": physical_pin(problem, context["expansion"])}, "Joint schedule/physical contract")
        require(root["solver"]["root"]["base_history"] == root["base_history"]
                and root["solver"]["root"]["requested_budgets"] == [a["integer_budget"] for a in anchors],
                "Joint solver changed H0 or the anchored schedule")
        baseline = assessment(context, proposal, root["base_history"], truths[pid])
        original_count = len(signatures & context["nominal_signatures"])
        definite_count = original_count if proposal in audit_reference.DEFINITE else 0
        ceiling = sum(s in context["nominal_signatures"] and support_state(context["nominal_signatures"], truths[pid], {s}, proposal)["supported"]
                      for s in signatures)
        expected_baseline = {"original_definite_count": definite_count, "initial_supported": baseline["reward"],
                             "initially_unsupported": definite_count - baseline["reward"],
                             "full_archive_support_ceiling": ceiling, "full_archive_unsupported_floor": definite_count - ceiling}
        require(root["support_baseline"] == expected_baseline, "Support reward baseline or full-archive ceiling is incorrect")
        queries = problem["queries"]
        nominal_rows = [w["signature"] for w in context["nominal_support"]]
        verified = verify_bellman([q["id"] for q in queries], {q["id"]: q["cost"] for q in queries}, nominal_rows,
                                  truths[pid], proposal, pin(problem), root["physical_pin"], root["solver"], old["solver"])
        completed = verified["optimality_verified"]
        require(root["joint_status"] == ("completed" if completed else "unavailable") and root["failure"] == root["solver"]["cap"],
                "Joint root availability is not supported by retained solver evidence")
        counts["joint_roots_verified" if completed else "joint_roots_unavailable"] += 1
        for key in ("states_checked", "child_combinations_checked", "unique_anchor_frontiers_checked"):
            counts[key] += verified[key]
    require(set(signature_roots) == {(pid, s) for pid in by_problem for s in truths[pid]}, "Root population omits declared design signatures")
    expected_design = {(pid, rid, budget, arm, tuple(signature)) for (pid, rid), root in by_root.items()
                       for budget, arm, signature in product(root["integer_budgets"], ARMS, root["signatures"])}
    design_index, grouped = {}, defaultdict(list)
    for row in design_runs:
        key = (row["problem_id"], row["root_id"], row["integer_budget"], row["arm"], tuple(row["outcomes"]))
        require(key in expected_design and key not in design_index, "Unexpected or duplicate anchored design execution")
        pid, rid, budget, arm, signature = key
        root, old, context = by_root[pid, rid], old_by_root[pid, rid], contexts[pid, 2]
        require(row["budget_percent"] is None, "Unique design execution is mislabeled as a repeated anchor")
        require(row["population"] == ("original" if signature in context["nominal_signatures"] else "new"), "Design population is wrong")
        old_key = (pid, rid, budget, signature)
        require(old_key in old_e_index, "A required saved E path is missing")
        grouped[pid, rid, budget, arm].append(row)
        if row["execution_status"] == "unavailable":
            require(arm == "joint_frontier" and root["joint_status"] == "unavailable" and row["failure"] == root["failure"],
                    "Unexpected failed execution cannot count as a successful result")
            require(not {"history", "status", "added_cost", "certificates", "design_supported_original"} & set(row),
                    "Unavailable joint path contains fabricated results")
            counts["unavailable_design_rows"] += 1
        else:
            require(row["execution_status"] == "completed", "Unknown design execution status")
            verify_path(context, root, old, old_e_index[old_key], row, truths[pid])
            refs = row["certificates"]
            require(set(refs) == {"base_nominal", "final_nominal", "base_design", "final_design"}
                    and refs["base_nominal"] == root["baseline"]["certificate"]
                    and refs["final_nominal"] == row["nominal_certificate_pin"], "Design certificate references are incomplete or changed")
            for name, history, expanded in (("base_nominal", row["base_history"], False), ("final_nominal", row["history"], False),
                                            ("base_design", row["base_history"], True), ("final_design", row["history"], True)):
                checker.check(refs[name], context, history, expanded=expanded)
            references.update(refs.values())
            counts["completed_design_paths_checked"] += 1
        design_index[key] = row
    require(set(design_index) == expected_design, "Anchored design grid is missing executions or explicit capped placeholders")
    for (pid, rid), root in by_root.items():
        verify_measurements(root, old_by_root[pid, rid], {(b, arm): grouped[pid, rid, b, arm]
                                                        for b, arm in product(root["integer_budgets"], ARMS)})
    expected_anchors = {(pid, k, arm, percent, signature) for (pid, k), context in contexts.items()
                        for arm, percent, signature in product(ARMS, ANCHORS, context["signature_rows"])}
    anchor_index = {}
    for row in runs:
        pid, k, arm, percent, signature = row["problem_id"], row["k"], row["arm"], row["budget_percent"], tuple(row["outcomes"])
        key = (pid, k, arm, percent, signature)
        require(key in expected_anchors and key not in anchor_index, "Unexpected or duplicate actual-k anchor")
        root, context = signature_roots[pid, signature], contexts[pid, k]
        budget = root["residual_cost"] * percent // 100
        require(row["root_id"] == root["root_id"] and row["integer_budget"] == budget, "Actual-k view changed the planning allowance or root")
        executed = design_index[pid, root["root_id"], budget, arm, signature]
        exact_reference._verify_anchor(context, root, row, executed, checker)
        if row["execution_status"] == "completed":
            audit_reference._same(row, {"claim_established": row["final_expanded_claim_status"] == "established",
                                        "claim_ruled_out": row["final_expanded_claim_status"] == "ruled_out",
                                        "claim_unresolved": row["final_expanded_claim_status"] == "unresolved",
                                        "operational_pending": row["final_expanded_terminal_status"] == "unresolved_pending",
                                        "operational_irreducible": row["final_expanded_terminal_status"] == "archive_irreducible"},
                                  "Actual-k aggregate-driving status flags")
            references.update(row["certificates"].values())
            counts["completed_anchor_paths_checked"] += 1
        else:
            counts["unavailable_anchor_rows"] += 1
        anchor_index[key] = row
    require(set(anchor_index) == expected_anchors, "Actual-k anchor grid is incomplete")
    for reference in set(certificates) - references:
        cert = certificates[reference]
        expanded = cert.get("certificate_kind") == "expanded_archive_support"
        candidates = [c for c in contexts.values() if cert.get("model_pin") ==
                      (c["expansion"]["model_pin"] if expanded else pin(c["problem"]))]
        require(bool(candidates), "Unreferenced certificate belongs to an undeclared model")
        checker.check(reference, candidates[0], cert["history"], expanded=expanded, count_reference=False)
    require(len(checker.checked) == len(certificates), "Incomplete global distinct-certificate verification")
    return {"status": "unavailable_joint_roots_verified" if counts["joint_roots_unavailable"] else "passed",
            "joint_optimality_status": "partial_unavailable" if counts["joint_roots_unavailable"] else "complete",
            "unavailable_root_ids": [r["root_id"] for r in roots if r["joint_status"] != "completed"],
            "problem_count": len(problems), "root_count": len(roots), **dict(counts),
            "design_grid_rows": len(expected_design), "anchor_grid_rows": len(expected_anchors),
            "distinct_certificates_checked": len(checker.checked), "certificate_references_checked": checker.references,
            "distinct_nominal_certificates_checked": checker.nominal_distinct,
            "distinct_expanded_certificates_checked": checker.expanded_distinct,
            "distinct_certificate_all_query_witness_checks": checker.all_query_witness_checks,
            "unreferenced_certificates_checked": len(set(certificates) - references),
            "independence_limits": "Independent all-physical reward filtering, Bellman triples/pruning/ties, paid action/phase/cost replay and root price arithmetic; preserved physical validators, claim semantics, old E path checker and certificate checker reused. Whole-tree tiny oracle has no DP or child pruning. This is finite model validation, not validation of real-world assumptions."}
