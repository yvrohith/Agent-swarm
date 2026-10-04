"""Independent finite checks for the saved exact audit frontier.

The Bellman checker enumerates feasible actions and child-frontier products from
the retained witness, rather than asking the production planner for an answer.
The tiny oracle enumerates whole deterministic decision trees without memoizing
or pruning child trees. Physical filtering/certificates reuse the preserved
archive validators; this is not an independent physical-model proof.
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from itertools import combinations, product

from studies.audit_aware_acquisition import reference as audit_reference
from tracebench.evidence_acquisition.model import Model, canonical, pin

ARMS = ("no_audit", "cost_order", "constant_first", "closure_informed",
        "closure_informed_affordable", "exact_frontier")
ANCHORS = (0, 25, 50, 100)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nondominated(points):
    """Exact deterministic frontier, with cost applying to every signature."""
    points = set(points)
    return sorted((d, cost) for d, cost in points if not any(
        od >= d and ocost <= cost and (od, ocost) != (d, cost) for od, ocost in points))


def _state_id(scope, nominal_mask, design_mask, remaining, budget):
    return "state_" + pin({"scope_pin": scope, "nominal_mask": hex(nominal_mask),
                           "design_mask": hex(design_mask), "remaining_actions": sorted(remaining), "budget": budget})


def _choice_order(choice, costs):
    if choice["action"] is None:
        return (0, 0, "", b"")
    return (1, costs[choice["action"]], choice["action"], canonical([
        [c["outcome"], c["state_id"], c["d"], c["l"]] for c in choice["children"]]))


def verify_bellman(query_ids, costs, nominal_rows, design_signatures, nominal_pin, solver):
    """Inductively verify every saved state and every feasible action/branch.

    Nominal masks index the unchanged nominal world rows, including duplicates;
    objective multiplicities come exclusively from distinct design signatures.
    The verifier never calls the production dynamic program or its pruning code.
    """
    query_ids = tuple(query_ids)
    nominal_rows = tuple(map(tuple, nominal_rows))
    design = tuple(sorted(set(map(tuple, design_signatures))))
    require(0 < len(query_ids) <= 8 and 0 < len(design) <= 256, "Inherited frontier bounds exceeded")
    require(set(nominal_rows) <= set(design), "Design envelope excludes nominal witnesses")
    root = solver["root"]
    history = root["base_history"]
    remaining = sorted(set(query_ids) - {h["query_id"] for h in history})
    design_pin = pin({"query_ids": list(query_ids), "signatures": [list(s) for s in design]})
    scope = pin({"nominal_pin": nominal_pin, "design_pin": design_pin, "base_history": history})
    selected_nominal = _selected(set(nominal_rows), query_ids, history)
    selected_design = _selected(design, query_ids, history)
    nm = sum(1 << i for i, s in enumerate(nominal_rows) if s in selected_nominal)
    tm = sum(1 << i for i, s in enumerate(design) if s in selected_design)
    require(bool(nm) and bool(tm), "Root has no compatible nominal/design support")
    residual = sum(costs[q] for q in remaining)
    audit_reference._same(root, {"nominal_pin": nominal_pin, "design_pin": design_pin, "scope_pin": scope,
                                "query_ids": list(query_ids), "base_history": history,
                                "nominal_mask": hex(nm), "design_mask": hex(tm),
                                "remaining_actions": remaining, "residual_cost": residual}, "Bellman root")
    states = {s["state_id"]: s for s in solver["states"]}
    require(len(states) == len(solver["states"]) and len(states) <= 100000, "Duplicate/capped Bellman states")
    combinations_checked = 0
    verified = {}
    edges = defaultdict(set)

    def validate_descriptor(state):
        n, t = int(state["nominal_mask"], 16), int(state["design_mask"], 16)
        available, budget = state["remaining_actions"], state["budget"]
        require(type(budget) is int and 0 <= budget <= residual and available == sorted(set(available))
                and set(available) <= set(remaining), "Invalid Bellman action set/budget")
        require(n & ~nm == 0 and t & ~tm == 0 and t > 0, "Bellman support escapes its root")
        require(state["state_id"] == _state_id(scope, n, t, available, budget), "Bellman state digest mismatch")
        acquired = set(remaining) - set(available)
        observations = []
        for qid in acquired:
            values = {s[query_ids.index(qid)] for i, s in enumerate(design) if t & (1 << i)}
            require(len(values) == 1, "Paid Bellman action has multiple observed answers")
            observations.append({"query_id": qid, "outcome_id": next(iter(values))})
        possible_n = _selected(set(nominal_rows), query_ids, history + observations)
        possible_t = _selected(design, query_ids, history + observations)
        require(n == sum(1 << i for i, s in enumerate(nominal_rows) if s in possible_n)
                and t == sum(1 << i for i, s in enumerate(design) if s in possible_t),
                "State masks are not exact support under their paid observations")
        require(budget + sum(costs[q] for q in acquired) <= residual, "Counterfactual path exceeds every root budget")

    for state in sorted(states.values(), key=lambda s: (len(s["remaining_actions"]), s["state_id"])):
        validate_descriptor(state)
        n, t = int(state["nominal_mask"], 16), int(state["design_mask"], 16)
        available, budget = state["remaining_actions"], state["budget"]
        require(state["terminal_conflict"] == (n == 0), "Incorrect terminal-conflict state")
        stop = {"action": None, "children": []}
        candidates = {(t.bit_count() if not n else 0, 0): stop}
        actions = {a["query_id"]: a for a in state["actions"]}
        expected_actions = {q for q in available if costs[q] <= budget} if n else set()
        require(len(actions) == len(state["actions"]) and set(actions) == expected_actions,
                "Bellman witness omits or adds a feasible action")
        for qid in sorted(expected_actions):
            action, position = actions[qid], query_ids.index(qid)
            require(action["cost"] == costs[qid], "Incorrect Bellman action price")
            branches, choices = [], []
            outcomes = sorted({s[position] for i, s in enumerate(design) if t & (1 << i)})
            for outcome in outcomes:
                child_n = sum(1 << i for i, s in enumerate(nominal_rows) if n & (1 << i) and s[position] == outcome)
                child_t = sum(1 << i for i, s in enumerate(design) if t & (1 << i) and s[position] == outcome)
                child_u = [q for q in available if q != qid]
                child_id = _state_id(scope, child_n, child_t, child_u, budget - costs[qid])
                require(child_id in verified, "Missing or unverified Bellman child state")
                edges[state["state_id"]].add(child_id)
                branches.append({"outcome": outcome, "child_state_id": child_id, "design_count": child_t.bit_count()})
                choices.append([(outcome, child_id, d, cost) for d, cost in verified[child_id]])
            require(action["branches"] == branches, "Incorrect exhaustive Bellman branch partition")
            for children in product(*choices):
                combinations_checked += 1
                require(combinations_checked <= 10000000, "Bellman child-combination verification cap exceeded")
                pair = (sum(c[2] for c in children), t.bit_count() * costs[qid] + sum(c[3] for c in children))
                choice = {"action": qid, "children": [{"outcome": o, "state_id": child, "d": d, "l": cost}
                                                       for o, child, d, cost in children]}
                if pair not in candidates or _choice_order(choice, costs) < _choice_order(candidates[pair], costs):
                    candidates[pair] = choice
        frontier = [{"d": d, "l": cost, "choice": candidates[d, cost]}
                    for d, cost in sorted(nondominated(candidates), reverse=True)]
        require(state["frontier"] == frontier, "Bellman frontier/value/canonical tie is not exact")
        verified[state["state_id"]] = {(p["d"], p["l"]) for p in frontier}
    resources = solver["resources"]
    state_cap, combination_cap = resources["state_cap"], resources["combination_cap"]
    require(type(state_cap) is int and 0 < state_cap <= 100000
            and type(combination_cap) is int and 0 < combination_cap <= 10000000, "Undeclared enlarged resource cap")
    pending = solver["pending_states"]
    pending_ids = {s["state_id"] for s in pending}
    require(len(pending_ids) == len(pending) and not pending_ids & set(states), "Duplicate pending/completed state")
    for state in pending:
        validate_descriptor(state)
    audit_reference._same(resources, {"solver_states": len(states) + len(pending), "completed_states": len(states),
                                      "pending_states": len(pending), "requested_budget_count": residual + 1,
                                      "total_frontier_points": sum(len(s["frontier"]) for s in states.values()),
                                      "maximum_frontier_size": max((len(s["frontier"]) for s in states.values()), default=0)},
                          "Bellman resource accounting")
    require(resources["solver_states"] <= state_cap and combinations_checked <= resources["child_combinations"] <= combination_cap,
            "Invalid solver cap/counter accounting")
    completed = solver["status"] == "complete"
    if completed:
        require(solver["cap"] is None and not pending and resources["child_combinations"] == combinations_checked
                and resources["completed_budget_count_before_cap"] == residual + 1,
                "Completed exact solve retains a cap, pending work or incorrect combination count")
        entries = {e["budget"]: e for e in solver["budget_frontiers"]}
        require(len(entries) == len(solver["budget_frontiers"]) and set(entries) == set(range(residual + 1)),
                "Exact frontier is missing integer root budgets")
        visited = set()
        max_detection = -1
        for budget in range(residual + 1):
            entry = entries[budget]
            state_id = _state_id(scope, nm, tm, remaining, budget)
            require(entry["state_id"] == state_id and state_id in states, "Incorrect root-budget state binding")
            require(entry["frontier"] == states[state_id]["frontier"], "Root frontier differs from verified witness")
            canonical_point = min(entry["frontier"], key=lambda p: (-p["d"], p["l"], _choice_order(p["choice"], costs)))
            require(entry["canonical_point"] == canonical_point, "Primary E point is not detection/cost optimal")
            require(canonical_point["d"] >= max_detection, "Maximum detection decreases with budget")
            max_detection = canonical_point["d"]
            pending = [state_id]
            while pending:
                current = pending.pop()
                if current not in visited:
                    visited.add(current)
                    pending.extend(edges[current])
        require(visited == set(states), "Unused states escape the complete reachable Bellman witness")
        require(max_detection == len(selected_design - selected_nominal), "Full budget misses a detectable design signature")
    else:
        require(solver["status"] == "unavailable" and not solver["budget_frontiers"],
                "Unavailable exact solve contains an optimum claim")
        cap = solver["cap"]
        require(isinstance(cap, dict) and cap["kind"] in {"solver_states", "child_combinations"}
                and cap["limit"] == {"solver_states": state_cap, "child_combinations": combination_cap}[cap["kind"]]
                and resources[cap["kind"]] == cap["limit"], "Unavailable solve lacks its declared cap evidence")
        completed_budgets = [b for b in range(residual + 1) if _state_id(scope, nm, tm, remaining, b) in states]
        require(completed_budgets == list(range(len(completed_budgets)))
                and resources["completed_budget_count_before_cap"] == len(completed_budgets),
                "Unavailable solver misreports its completed budget prefix")
    return {"status": "passed" if completed else "unavailable", "optimality_verified": completed,
            "states_checked": len(states), "child_combinations_checked": combinations_checked,
            "root_budgets_checked": residual + 1 if completed else 0}


def verify_root(problem, root, design_signatures):
    queries = problem["queries"]
    nominal_rows = [tuple("present" if q["record_id"] in w["retained_record_ids"] else "missing"
                          for q in queries) for w in problem["worlds"]]
    require(root["solver"]["root"]["base_history"] == root["base_history"], "Solver is bound to a different H0")
    return verify_bellman([q["id"] for q in queries], {q["id"]: q["cost"] for q in queries},
                          nominal_rows, design_signatures, pin(problem), root["solver"])


def signatures_from_worlds(problem, worlds):
    return {tuple("present" if q["record_id"] in w["retained_record_ids"] else "missing"
                  for q in problem["queries"]) for w in worlds}


def _selected(signatures, query_ids, history):
    return audit_reference.compatible(signatures, query_ids, history)


def exhaustive_tree_oracle(query_ids, costs, nominal_signatures, design_signatures,
                           base_history, budget):
    """Enumerate *all* decision trees on at most three remaining actions.

    No dynamic programming, child-frontier pruning, production-planner calls,
    or state-cache reuse: each complete tree is scored over its compatible
    distinct signature set. Only the final list of whole trees is Pareto filtered.
    """
    query_ids = tuple(query_ids)
    nominal = set(map(tuple, nominal_signatures))
    design = set(map(tuple, design_signatures))
    require(nominal <= design, "Nominal signatures missing from design envelope")
    remaining = tuple(q for q in query_ids if q not in {h["query_id"] for h in base_history})
    require(len(remaining) <= 3, "Exhaustive tree oracle is limited to three remaining actions")
    require(type(budget) is int and budget >= 0 and all(type(costs[q]) is int and costs[q] > 0
                                                     for q in query_ids), "Invalid pathwise budget/cost")
    nominal = _selected(nominal, query_ids, base_history)
    design = _selected(design, query_ids, base_history)
    require(bool(design), "Empty tiny design population")
    positions = {q: i for i, q in enumerate(query_ids)}

    def trees(n, t, available, funds):
        if not n:
            return [(len(t), 0, {"action": None, "children": []})]
        output = [(0, 0, {"action": None, "children": []})]
        for qid in available:
            if costs[qid] > funds:
                continue
            outcomes = sorted({s[positions[qid]] for s in t})
            descendants = []
            for outcome in outcomes:
                tn = {s for s in t if s[positions[qid]] == outcome}
                nn = {s for s in n if s[positions[qid]] == outcome}
                descendants.append(trees(nn, tn, tuple(q for q in available if q != qid), funds - costs[qid]))
            for children in product(*descendants):
                output.append((sum(c[0] for c in children), len(t) * costs[qid] + sum(c[1] for c in children),
                               {"action": qid, "children": [{"outcome": outcome, "tree": child[2],
                                                             "d": child[0], "l": child[1]}
                                                            for outcome, child in zip(outcomes, children, strict=True)]}))
        return output

    all_trees = trees(nominal, design, remaining, budget)
    frontier = nondominated((d, cost) for d, cost, _ in all_trees)
    return {"tree_count": len(all_trees), "frontier": [{"d": d, "l": cost} for d, cost in frontier],
            "canonical_value": {"d": max(frontier)[0], "l": min(cost for d, cost in frontier if d == max(frontier)[0])},
            "trees": all_trees}


def subset_minimum(problem, base_history, signature):
    """Separate exhaustive weighted contradiction-subset enumeration."""
    nominal = Model(problem)
    qids = tuple(nominal.queries)
    signature = tuple(signature)
    require(len(signature) == len(qids), "Hindsight signature has the wrong length")
    require(signature in _selected({signature}, qids, base_history), "Hindsight signature contradicts its root")
    current = [w for w in problem["worlds"] if all(
        ("present" if nominal.queries[h["query_id"]]["record_id"] in w["retained_record_ids"] else "missing")
        == h["outcome_id"] for h in base_history)]
    require(bool(current), "Preserved root already conflicts with nominal support")
    answers = dict(zip(qids, signature, strict=True))
    for qid, query in nominal.queries.items():
        require(answers[qid] in query["outcomes"], "Hindsight has an undeclared typed outcome")
    aliases = defaultdict(set)
    for qid in qids:
        aliases[nominal.queries[qid]["record_id"]].add(answers[qid])
    require(all(len(values) == 1 for values in aliases.values()), "Hindsight physical aliases disagree")
    remaining = sorted(q for q in qids if q not in {h["query_id"] for h in base_history})
    feasible = []
    for size in range(len(remaining) + 1):
        for subset in combinations(remaining, size):
            covered = all(any(("present" if nominal.queries[q]["record_id"] in w["retained_record_ids"] else "missing")
                              != answers[q] for q in subset) for w in current)
            if covered:
                feasible.append((sum(nominal.queries[q]["cost"] for q in subset), size, subset))
    if not feasible:
        return None
    cost, size, subset = min(feasible)
    return {"minimum_cost": cost, "cardinality": size, "query_ids": list(subset),
            "additional_history": [{"query_id": q, "outcome_id": answers[q]} for q in subset],
            "nominal_world_ids": [w["id"] for w in current]}


def affordable_choice(problem, nominal, design, history, funds):
    """Independent D-affordable calculation; hypothetical support stays intact."""
    qids = tuple(q["id"] for q in problem["queries"])
    possible = _selected(nominal, qids, history)
    envelope = _selected(design, qids, history)
    require(bool(envelope), "Empty fixed design envelope")
    if not possible:
        return None
    queried = {h["query_id"] for h in history}
    candidates = [q for q in problem["queries"] if q["id"] not in queried and q["cost"] <= funds]
    if not candidates:
        return None
    scores = {}
    for query in candidates:
        position = qids.index(query["id"])
        branches = {s[position] for s in possible}
        scores[query["id"]] = Fraction(sum(s[position] not in branches for s in envelope), query["cost"])
    if any(scores.values()):
        return min(candidates, key=lambda q: (-scores[q["id"]], q["cost"], q["id"]))["id"]
    constant = [q for q in candidates if len({s[qids.index(q["id"])] for s in possible}) == 1]
    return min(constant or candidates, key=lambda q: (q["cost"], q["id"]))["id"]


def frontier_choice(solver, budget, audit_history):
    """Replay only saved paid answers through a previously verified policy tree."""
    require(solver["status"] == "complete", "Unavailable exact frontier cannot select an action")
    states = {s["state_id"]: s for s in solver["states"]}
    entry = next((r for r in solver["budget_frontiers"] if r["budget"] == budget), None)
    require(entry is not None, "Missing exact root budget")
    point = entry["canonical_point"]
    for paid in audit_history:
        require(point["choice"]["action"] == paid["query_id"], "Path differs from exact backpointer action")
        branch = next((c for c in point["choice"]["children"] if c["outcome"] == paid["outcome_id"]), None)
        require(branch is not None, "Exact policy has no acquired outcome branch")
        child = states[branch["state_id"]]
        point = next((p for p in child["frontier"] if (p["d"], p["l"]) == (branch["d"], branch["l"])), None)
        require(point is not None, "Exact branch references an absent child pair")
    return point["choice"]["action"]


def verify_path(problem, root, row):
    """Directly inspect one executed path, including every empty lookup's charge."""
    queries = {q["id"]: q for q in problem["queries"]}
    qids = tuple(queries)
    base = root["base_history"]
    signature = tuple(row["outcomes"])
    nominal = signatures_from_worlds(problem, problem["worlds"])
    design = set(map(tuple, root["signatures"]))
    arm, budget = row["arm"], row["integer_budget"]
    require(arm in ARMS and type(budget) is int and 0 <= budget <= root["residual_cost"], "Invalid arm or root budget")
    require(signature in design, "Executed signature is outside its fixed root envelope")
    require(row["base_history"] == base and row["history"] == base + row["audit_history"], "Changed original stopping prefix")
    require(signature in _selected({signature}, qids, row["history"]), "Paid outcomes differ from retained physical records")
    require(bool(_selected(nominal, qids, base)), "Original prefix already conflicts")
    expected_population = "original" if signature in nominal else "new"
    require(row["population"] == expected_population, "Incorrect original/new signature classification")
    base_cost, base_bytes = audit_reference._history_costs(problem, base)
    audit_reference._same(row, {"audit_budget": budget, "residual_cost": root["residual_cost"],
                                "base_cost": base_cost, "base_query_count": len(base),
                                "base_returned_bytes": base_bytes,
                                "baseline_certificate": root["baseline"]["certificate"],
                                "original_proposal": root["baseline"]["status"]}, "Preserved nominal prefix")
    prefix, added_cost, added_bytes, conflict = list(base), 0, 0, None
    seen = {queries[h["query_id"]]["record_id"] for h in base}
    aliases = 0

    def select(history, paid_cost):
        if arm == "exact_frontier":
            return frontier_choice(root["solver"], budget, history[len(base):])
        if arm == "closure_informed_affordable":
            return affordable_choice(problem, nominal, design, history, budget - paid_cost)
        return audit_reference.choose(problem, nominal, design, history, arm)

    for index, item in enumerate(row["audit_history"], 1):
        require(conflict is None, "Further spending after first alarm")
        qid, outcome = item["query_id"], item["outcome_id"]
        require(select(prefix, added_cost) == qid, "Executed action violates allowed-information policy")
        possible = _selected(nominal, qids, prefix)
        require(bool(possible), "Acquisition after empty nominal support")
        branches = sorted({s[qids.index(qid)] for s in possible})
        added_cost += queries[qid]["cost"]
        added_bytes += len(canonical(queries[qid]["outcomes"][outcome]))
        require(added_cost <= budget, "Path exceeds hard extra budget")
        aliases += queries[qid]["record_id"] in seen
        seen.add(queries[qid]["record_id"])
        prefix.append(item)
        require(bool(_selected(design, qids, prefix)), "Actual paid outcome left fixed design envelope")
        if not _selected(nominal, qids, prefix):
            require(len(branches) == 1 and outcome not in branches, "Unsound first-conflict branch")
            conflict = {"added_query_index": index, "added_cost": added_cost, "total_cost": base_cost + added_cost,
                        "query_id": qid, "outcome_id": outcome, "nominal_outcomes_before": branches}
    alarm = conflict is not None
    require(alarm == (not _selected(nominal, qids, prefix)), "Alarm disagrees with direct support")
    require(not alarm or expected_population == "new", "False alarm on nominal signature")
    chosen = None if alarm else select(prefix, added_cost)
    if arm == "no_audit":
        require(not row["audit_history"], "Baseline performs extra acquisition")
        termination, next_query = "baseline_no_audit", None
    elif alarm:
        termination, next_query = "nominal_conflict", None
    elif arm == "exact_frontier":
        require(chosen is None, "Exact path stops before selected action")
        termination, next_query = ("catalogue_exhausted" if len(prefix) == len(qids) else "exact_policy_stop"), None
    elif arm == "closure_informed_affordable":
        require(chosen is None, "Affordable comparator stops before feasible action")
        termination, next_query = ("catalogue_exhausted" if len(prefix) == len(qids) else "no_affordable_action"), None
    elif chosen is not None:
        require(added_cost + queries[chosen]["cost"] > budget, "Fixed order stops before affordable next query")
        termination, next_query = "next_action_unaffordable", chosen
    else:
        require(len(prefix) == len(qids), "Fixed order stops before catalogue exhaustion")
        termination, next_query = "catalogue_exhausted", None
    audit_reference._same(row, {"added_cost": added_cost, "total_cost": base_cost + added_cost,
                                "added_query_count": len(row["audit_history"]), "total_query_count": len(prefix),
                                "added_returned_bytes": added_bytes, "total_returned_bytes": base_bytes + added_bytes,
                                "first_conflict": conflict,
                                "status": "nominal_model_conflict" if alarm else "no_conflict_observed",
                                "termination_reason": termination, "next_query": next_query,
                                "proposal_withheld": alarm and root["baseline"]["status"] in audit_reference.DEFINITE}, "Executed path")
    audit_reference._same(row["coverage"], {"catalogue_actions": len(qids), "base_actions": len(base),
                                           "audited_actions": len(row["audit_history"]), "total_acquired_actions": len(prefix),
                                           "remaining_actions": len(qids) - len(prefix), "complete": len(prefix) == len(qids),
                                           "distinct_record_ids_queried": len(seen), "added_alias_queries": aliases}, "Catalogue coverage")
    return {"detected": alarm, "cost": added_cost, "history": prefix}


def verify_hindsight(problem, root, result, cert_checks=None, context=None):
    signature, base = tuple(result["full_signature"]), root["base_history"]
    require(signature in set(map(tuple, root["signatures"])), "Hindsight row belongs to another root")
    audit_reference._same(result, {"schema_version": 1, "nominal_model_pin": pin(problem), "root_pin": root["root_pin"],
                                   "root_id": root["root_id"], "base_history": base,
                                   "signature_pin": pin(signature)}, "Hindsight identity")
    expected = subset_minimum(problem, base, signature)
    if expected is None:
        audit_reference._same(result, {"status": "unavailable", "reason": "no_catalogue_contradiction",
                                       **dict.fromkeys(("minimum_cost", "cardinality", "query_ids", "additional_history",
                                                        "typed_observations", "nominal_world_coverage", "certificate", "certificate_pin")),
                                       "subsets_checked": 0}, "Nominal-compatible hindsight")
        return {"minimum_cost": None, "subsets_enumerated": 1 << len(root["unqueried_query_ids"])}
    audit_reference._same(result, {"status": "available", "reason": None,
                                   **{name: expected[name] for name in ("minimum_cost", "cardinality", "query_ids", "additional_history")}},
                          "Exact hindsight subset")
    queries = {q["id"]: q for q in problem["queries"]}
    qids = tuple(queries)
    answers = dict(zip(qids, signature, strict=True))
    observations = [{**h, "record_id": queries[h["query_id"]]["record_id"], "cost": queries[h["query_id"]]["cost"],
                     "observable": queries[h["query_id"]]["outcomes"][h["outcome_id"]]} for h in expected["additional_history"]]
    require(result["typed_observations"] == observations, "Hindsight typed payload differs from the actual signature")
    coverage = []
    for index, world in enumerate(problem["worlds"]):
        if world["id"] not in expected["nominal_world_ids"]:
            continue
        disagree = [q for q in expected["query_ids"] if
                    ("present" if queries[q]["record_id"] in world["retained_record_ids"] else "missing") != answers[q]]
        require(bool(disagree), "Hindsight subset leaves a compatible nominal witness")
        coverage.append({"world_id": world["id"], "world_index": index, "disagreed_query_ids": disagree})
    require(result["nominal_world_coverage"] == coverage, "Hindsight world-disagreement coverage is incorrect")
    remaining = root["unqueried_query_ids"]
    ranked = sorted((sum(queries[q]["cost"] for q in s), len(s), tuple(sorted(s)))
                    for size in range(len(remaining) + 1) for s in combinations(remaining, size))
    require(result["subsets_checked"] == ranked.index((expected["minimum_cost"], expected["cardinality"],
                                                        tuple(expected["query_ids"]))) + 1, "Incorrect subset search count")
    cert = result["certificate"]
    require(pin(cert) == result["certificate_pin"] and cert["history"] == base + expected["additional_history"]
            and cert["model_pin"] == pin(problem) and cert["status"] == "inconsistent", "Hindsight certificate binding is invalid")
    if cert_checks is None:
        require(Model(problem).verify_certificate(cert), "Hindsight contradiction certificate failed")
    else:
        require(cert_checks.registry.get(result["certificate_pin"]) == cert, "Hindsight certificate missing from global registry")
        cert_checks.check(result["certificate_pin"], context, cert["history"], expanded=False)
    return {"minimum_cost": expected["minimum_cost"], "subsets_enumerated": 1 << len(remaining)}


def _verify_anchor(context, root, row, executed, checks):
    problem, qids = context["problem"], context["query_ids"]
    signature = tuple(row["outcomes"])
    original = context["signature_rows"][signature]
    for key, value in executed.items():
        if key not in {"budget_percent", "certificates"}:
            require(row.get(key) == value, "Actual-k anchor changed an already verified prospective path")
    audit_reference._same(row, {"signature_id": original["signature_id"], "stratum": problem["stratum"],
                                "subtype": problem["subtype"]}, "Anchor metadata")
    if row["execution_status"] != "completed":
        return
    baseline, history = original["policy"], row["history"]
    require(baseline["history"] == root["base_history"], "Anchor has a different nominal stopping proposal")
    initial = audit_reference.statuses(context["expanded_support"], qids, row["base_history"])
    final = audit_reference.statuses(context["expanded_support"], qids, history)
    full = audit_reference.statuses(context["expanded_support"], qids, [
        {"query_id": qid, "outcome_id": answer} for qid, answer in zip(qids, signature, strict=True)])
    require(final[0] != "model_conflict", "Expanded actual support cannot explain its paid answers")
    alarm = row["status"] == "nominal_model_conflict"
    proposal = baseline["status"]
    support = audit_reference.support_flags(proposal, initial, final, full, alarm)
    require(row["support"] == support, "Anchor support/warrant/withdrawal classification is incorrect")
    conflict = signature not in context["nominal_signatures"]
    audit_reference._same(row, {"base_nominal_proposal": proposal,
                                "baseline_expanded_claim_status": initial[0], "baseline_expanded_terminal_status": initial[1],
                                "final_expanded_claim_status": final[0], "final_expanded_terminal_status": final[1],
                                "complete_nominal_conflict": conflict, "detected": alarm,
                                "full_conflict_missed": conflict and not alarm, "false_alarm": alarm and not conflict,
                                "catalogue_exhausted": len(history) == len(qids), "catalogue_query_count": len(qids)}, "Anchor classification")
    joint = {"alarm": alarm, "proposal": proposal, "final_claim_status": final[0], "final_terminal_status": final[1],
             "warrant_restored": support["warrant_restored"], "withdrawn_definite": support["withdrawn_definite"],
             "disposition": support["disposition"]}
    require(row["joint_category"] == joint, "Anchor joint classification is incorrect")
    queries = {q["id"]: q for q in problem["queries"]}
    seen = {queries[h["query_id"]]["record_id"] for h in row["base_history"]}
    count = cost = size = initial_count = 0
    for h in row["audit_history"]:
        query = queries[h["query_id"]]
        if query["record_id"] in seen:
            count += 1
            cost += query["cost"]
            size += len(canonical(query["outcomes"][h["outcome_id"]]))
        initial_count += query["record_id"] in problem["initial_record_ids"]
        seen.add(query["record_id"])
    audit_reference._same(row, {"alias_added_queries": count, "alias_added_cost": cost, "alias_added_bytes": size,
                                "added_lookups_of_initial_records": initial_count, "unique_queried_record_count": len(seen)},
                          "Anchor alias accounting")
    refs = row["certificates"]
    require(set(refs) == {"base_nominal", "base_expanded", "final_nominal", "final_expanded"}, "Missing anchor certificate reference")
    require(refs["base_nominal"] == baseline["certificate"] and refs["base_expanded"] == baseline["expanded_certificate"],
            "Historical baseline certificate reference changed")
    for name, paid, expanded in (("base_nominal", row["base_history"], False), ("base_expanded", row["base_history"], True),
                                 ("final_nominal", history, False), ("final_expanded", history, True)):
        checks.check(refs[name], context, paid, expanded=expanded)


def verify_all(problems, saved_conditions, roots, design_runs, runs, certificates):
    """Verify complete declared grids; caps remain explicit unavailable E rows.

    A passed *verification* may preserve capped roots, but reports their exact
    optimality as unavailable and never counts their placeholders as executions.
    Unexpected failures, missing rows, or invalid certificates raise immediately.
    """
    contexts = audit_reference._contexts(problems, saved_conditions)
    problems_by_id = {p["problem_id"]: p for p in problems}
    checks = audit_reference._CertificateChecks(certificates)
    by_root, root_for_signature, checked_minima = {}, {}, {}
    counts = defaultdict(int)
    for name in ("exact_roots_verified", "exact_roots_unavailable", "unavailable_design_rows", "unavailable_anchor_rows",
                 "completed_design_paths_checked", "completed_anchor_paths_checked"):
        counts[name] = 0
    references = set()
    for root in roots:
        pid, rid = root["problem_id"], root["root_id"]
        require(pid in problems_by_id and (pid, rid) not in by_root, "Duplicate or unknown root")
        problem, context = problems_by_id[pid], contexts[pid, 2]
        design = tuple(sorted(context["signature_rows"]))
        history = root["base_history"]
        identity = {"nominal_model_pin": pin(problem), "design_signature_set_pin": pin(design), "base_history": history}
        root_pin = pin(identity)
        signatures = set(map(tuple, root["signatures"]))
        possible = _selected(design, context["query_ids"], history)
        require(signatures == possible and len(signatures) == len(root["signatures"]) and bool(signatures),
                "Root signature set is not exactly its compatible design population")
        remaining = [q for q in context["query_ids"] if q not in {h["query_id"] for h in history}]
        queries = {q["id"]: q for q in problem["queries"]}
        audit_reference._same(root, {**identity, "root_pin": root_pin, "root_id": "audit_root_" + root_pin[:24],
                                     "root_signature_set_pin": pin(tuple(sorted(signatures))), "signature_count": len(signatures),
                                     "original_signature_count": len(signatures & context["nominal_signatures"]),
                                     "new_signature_count": len(signatures - context["nominal_signatures"]),
                                     "unqueried_query_ids": remaining,
                                     "residual_cost": sum(queries[q]["cost"] for q in remaining),
                                     "stratum": problem["stratum"], "subtype": problem["subtype"]}, "Root partition and pins")
        baseline_fields = ("history", "cost", "query_count", "returned_bytes", "status", "certificate", "certificate_valid")
        for signature in signatures:
            key = (pid, signature)
            require(key not in root_for_signature, "A design signature belongs to multiple H0 roots")
            old = context["signature_rows"][signature]["policy"]
            require(old["history"] == history and root["baseline"] == {name: old[name] for name in baseline_fields},
                    "Compatible signatures do not share the preserved deterministic stopping path")
            root_for_signature[key] = root
        verified = verify_root(problem, root, design)
        completed = verified["optimality_verified"]
        require(root["exact_status"] == ("completed" if completed else "unavailable")
                and root["failure"] == root["solver"]["cap"], "Root availability differs from verified solver evidence")
        counts["exact_roots_verified" if completed else "exact_roots_unavailable"] += 1
        for name in ("states_checked", "child_combinations_checked", "root_budgets_checked"):
            counts[name] += verified[name]
        minima = {tuple(h["full_signature"]): h for h in root["hindsight"]}
        require(len(minima) == len(root["hindsight"]) and set(minima) == signatures, "Missing or duplicate hindsight signature")
        for signature, minimum in minima.items():
            verified_minimum = verify_hindsight(problem, root, minimum, checks, context)
            checked_minima[pid, rid, signature] = verified_minimum["minimum_cost"]
            counts["hindsight_rows_checked"] += 1
            counts["hindsight_subsets_enumerated"] += verified_minimum["subsets_enumerated"]
            if minimum["certificate_pin"]:
                references.add(minimum["certificate_pin"])
        by_root[pid, rid] = root
    expected_root_signatures = {(pid, signature) for (pid, k), context in contexts.items() if k == 2
                                for signature in context["signature_rows"]}
    require(set(root_for_signature) == expected_root_signatures, "Root population omits a declared problem/signature")
    design_index = {}
    expected_design = {(pid, rid, budget, arm, tuple(signature)) for (pid, rid), root in by_root.items()
                       for budget, arm, signature in product(range(root["residual_cost"] + 1), ARMS, root["signatures"])}
    points = defaultdict(list)
    for row in design_runs:
        key = (row["problem_id"], row["root_id"], row["integer_budget"], row["arm"], tuple(row["outcomes"]))
        require(key not in design_index and key in expected_design, "Duplicate or unexpected integer-budget execution")
        pid, rid, budget, arm, signature = key
        root, context = by_root[pid, rid], contexts[pid, 2]
        require(row["budget_percent"] is None, "Design run incorrectly uses an actual-k percentage label")
        points[pid, rid, budget, arm].append(row)
        if row["execution_status"] == "unavailable":
            require(arm == "exact_frontier" and root["exact_status"] == "unavailable"
                    and row["failure"] == root["failure"], "Unexpected failed execution cannot count as verified success")
            require(not {"history", "status", "added_cost", "certificates"} & set(row), "Unavailable path contains fabricated results")
            counts["unavailable_design_rows"] += 1
        else:
            require(row["execution_status"] == "completed", "Unknown path execution status")
            checked = verify_path(problems_by_id[pid], root, row)
            minimum = checked_minima[pid, rid, signature]
            require(not checked["detected"] or minimum is not None and minimum <= checked["cost"],
                    "Detected path violates independent hindsight lower bound")
            refs = row["certificates"]
            require(set(refs) == {"base_nominal", "final_nominal"}
                    and refs["base_nominal"] == root["baseline"]["certificate"]
                    and refs["final_nominal"] == row["nominal_certificate_pin"], "Design path certificate reference mismatch")
            checks.check(refs["base_nominal"], context, row["base_history"], expanded=False)
            checks.check(refs["final_nominal"], context, row["history"], expanded=False)
            references.update(refs.values())
            counts["completed_design_paths_checked"] += 1
        design_index[key] = row
    require(set(design_index) == expected_design, "Integer-budget execution grid is incomplete")
    for (pid, rid), root in by_root.items():
        frontiers = {entry["budget"]: entry for entry in root["solver"]["budget_frontiers"]}
        expected_points, expected_gaps = [], []
        for budget in range(root["residual_cost"] + 1):
            detections = {}
            for arm in ARMS:
                selected = points[pid, rid, budget, arm]
                complete = all(r["execution_status"] == "completed" for r in selected)
                d = sum(r["status"] == "nominal_model_conflict" for r in selected) if complete else None
                cost = sum(r["added_cost"] for r in selected) if complete else None
                dominator = None
                if complete and budget in frontiers:
                    candidates = [p for p in frontiers[budget]["frontier"] if p["d"] >= d and p["l"] <= cost]
                    require(bool(candidates), "Feasible comparator exceeds exact frontier")
                    dominator = min(candidates, key=lambda p: (p["l"], -p["d"], canonical(p)))
                if arm == "exact_frontier" and complete:
                    optimum = frontiers[budget]["canonical_point"]
                    require((d, cost) == (optimum["d"], optimum["l"]), "Actual canonical policy does not realize its Bellman value")
                expected_points.append({"integer_budget": budget, "arm": arm,
                                        "status": "completed" if complete else "unavailable",
                                        "signature_count": root["signature_count"], "d": d, "l": cost,
                                        "nominal_compatible_cost_sum": sum(r["added_cost"] for r in selected if r["population"] == "original")
                                        if complete else None,
                                        "detected_cost_sum": sum(r["added_cost"] for r in selected if r["status"] == "nominal_model_conflict")
                                        if complete else None, "frontier_dominator": dominator,
                                        "strictly_dominated": (dominator["d"] > d or dominator["l"] < cost) if dominator else None})
                detections[arm] = d
            minima = [checked_minima[pid, rid, tuple(signature)] for signature in root["signatures"]]
            feasible = sum(m is not None and m <= budget for m in minima)
            e, a, old_d = (detections[arm] for arm in ("exact_frontier", "closure_informed_affordable", "closure_informed"))
            gap = {"integer_budget": budget, "full_conflicts": root["new_signature_count"],
                   "hindsight_feasible": feasible, "hindsight_impossible": root["new_signature_count"] - feasible,
                   "exact_detection": e, "search_gap": feasible - e if e is not None else None,
                   "policy_selection_gap": e - a if e is not None and a is not None else None,
                   "affordability_gain": a - old_d if a is not None and old_d is not None else None}
            require(all(gap[name] is None or gap[name] >= 0 for name in
                        ("hindsight_impossible", "search_gap", "policy_selection_gap")), "Negative verified detection-gap component")
            expected_gaps.append(gap)
        require(root["design_points"] == expected_points, "Design points/dominance do not reproduce from executed paths")
        require(root["budget_summary"] == expected_gaps, "Hindsight/search/policy gaps do not reproduce exactly")
    anchor_index = {}
    expected_anchors = {(pid, k, arm, percent, signature) for (pid, k), context in contexts.items()
                        for arm, percent, signature in product(ARMS, ANCHORS, context["signature_rows"])}
    for row in runs:
        pid, k, signature = row["problem_id"], row["k"], tuple(row["outcomes"])
        key = (pid, k, row["arm"], row["budget_percent"], signature)
        require(key not in anchor_index and key in expected_anchors, "Duplicate or unexpected actual-k anchor")
        root = root_for_signature[pid, signature]
        budget = root["residual_cost"] * row["budget_percent"] // 100
        require(row["root_id"] == root["root_id"] and row["integer_budget"] == budget, "Actual-k anchor budget/root changed")
        executed = design_index[pid, root["root_id"], budget, row["arm"], signature]
        _verify_anchor(contexts[pid, k], root, row, executed, checks)
        if row["execution_status"] == "completed":
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
        require(bool(candidates), "Unreferenced certificate is outside the declared models")
        checks.check(reference, candidates[0], cert["history"], expanded=expanded, count_reference=False)
    require(len(checks.checked) == len(certificates), "Incomplete distinct-certificate verification")
    return {"status": "unavailable_exact_roots_verified" if counts["exact_roots_unavailable"] else "passed",
            "exact_optimality_status": "partial_unavailable" if counts["exact_roots_unavailable"] else "complete",
            "unavailable_root_ids": [root["root_id"] for root in roots if root["exact_status"] != "completed"],
            "problem_count": len(problems), "root_count": len(roots), **dict(counts),
            "design_grid_rows": len(expected_design), "anchor_grid_rows": len(expected_anchors),
            "distinct_certificates_checked": len(checks.checked), "certificate_references_checked": checks.references,
            "distinct_nominal_certificates_checked": checks.nominal_distinct,
            "distinct_expanded_certificates_checked": checks.expanded_distinct,
            "distinct_certificate_all_query_witness_checks": checks.all_query_witness_checks,
            "unreferenced_certificates_checked": len(set(certificates) - references),
            "independence_limits": "All Bellman actions/branches/frontiers, subset minima and path semantics checked without production solver/runtime calls; preserved physical reconstruction, claim semantics and certificate checker reused. Original nominal optimizer not independently reproved. Tiny oracle enumerates whole trees without DP."}
