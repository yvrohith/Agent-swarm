"""Joint-objective correctness on declared tiny fixtures and saved development only."""

import copy
import gzip
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(study, name):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.{study}.{name}")
    finally:
        sys.path.remove(str(ROOT))


def ref():
    return module("joint_audit_warrant", "reference")


def bits(row):
    return tuple("present" if value else "missing" for value in row)


class TinyNominal:
    def __init__(self, rows, costs, alias=False):
        self.rows = tuple(map(bits, rows))
        self.queries = {f"q{i}": {"cost": cost, "record_id": "alias" if alias else f"r{i}",
                                  "outcomes": {"missing": {}, "present": {}}} for i, cost in enumerate(costs)}
        self.query_ids = tuple(self.queries)
        self.model_pin = ref().pin({"rows": self.rows, "queries": self.queries})
        self.signature_cells = defaultdict(int)
        for i, row in enumerate(self.rows):
            self.signature_cells[row] |= 1 << i

    def compatible(self, history):
        return sum(1 << i for i, row in enumerate(self.rows) if all(
            row[self.query_ids.index(h["query_id"])] == h["outcome_id"] for h in history))

    def partition(self, state, qid):
        position = self.query_ids.index(qid)
        return {outcome: sum(1 << i for i, row in enumerate(self.rows)
                             if state & (1 << i) and row[position] == outcome)
                for outcome in ("missing", "present")}


class TinySupport:
    """Explicit physical truth table; production and reference get separate views."""

    def __init__(self, nominal, truth_sets, proposal="established"):
        self.nominal, self.base_history, self.proposal = nominal, [], proposal
        self.truth_sets = truth_sets
        self.design_signatures = tuple(sorted(truth_sets))
        self.physical_pin = ref().pin({"truths": [[s, sorted(values)] for s, values in sorted(truth_sets.items())]})

    def reward(self, mask):
        chosen = [s for i, s in enumerate(self.design_signatures) if mask & (1 << i)]
        if not chosen:
            raise ValueError("empty physical support")
        if self.proposal not in {"established", "ruled_out"}:
            return 0
        physical_values = {truth for signature in chosen for truth in self.truth_sets[signature]}
        if physical_values != {self.proposal == "established"}:
            return 0
        return sum(signature in self.nominal.signature_cells for signature in chosen)


def fixture(name):
    alias, proposal = False, "established"
    if name == "detection_useless_support":
        rows, truth, costs = [(0,), (1,)], {(0,): {True}, (1,): {False, True}}, (1,)
    elif name == "competition":
        rows, truth, costs = [(0, 0), (0, 1)], {(0, 0): {True}, (0, 1): {False, True}, (1, 0): {True}}, (1, 1)
    elif name == "already_supported":
        rows, truth, costs = [(0,)], {(0,): {True}, (1,): {True}}, (2,)
    elif name == "irreducible":
        rows, truth, costs = [(0,), (1,)], {(0,): {False, True}, (1,): {False, True}}, (1,)
        proposal = "archive_irreducible"
    elif name == "permanently_unavailable":
        rows, truth, costs = [(0,), (1,)], {(0,): {False, True}, (1,): {False, True}}, (1,)
    elif name == "old_cost_tie":
        rows, truth, costs = [(0, 0)], {(0, 0): {True}, (1, 0): {True}, (0, 1): {False}}, (1, 1)
    elif name == "branch_budgets":
        rows, truth, costs = [(0, 0), (1, 1)], {(0, 0): {True}, (1, 1): {True}, (0, 1): {True}, (1, 0): {False}}, (1, 1)
    elif name == "aliases":
        rows, truth, costs = [(0, 0), (1, 1)], {(0, 0): {True}, (1, 1): {False, True}}, (1, 3)
        alias = True
    else:
        rows, truth, costs = [(0, 0, 0), (0, 1, 1)], {
            (0, 0, 0): {True}, (0, 1, 1): {False, True}, (1, 0, 0): {True}, (0, 0, 1): {False}}, (1, 2, 1)
    nominal = TinyNominal(rows, costs, alias=alias)
    support = TinySupport(nominal, {bits(row): values for row, values in truth.items()}, proposal)
    return nominal, support


def solve(name, budgets=None, **limits):
    nominal, support = fixture(name)
    residual = sum(q["cost"] for q in nominal.queries.values())
    budgets = budgets or [residual * percent // 100 for percent in (0, 25, 50, 100)]
    planner = module("joint_audit_warrant", "frontier").JointFrontierPlanner(nominal, support, [], budgets, **limits)
    old = module("exact_audit_frontier", "frontier").FrontierPlanner(nominal, support.design_signatures, []).solve()
    return nominal, support, planner.solve(), old


def check(nominal, support, result, old=None):
    return ref().verify_bellman(nominal.query_ids, {q: data["cost"] for q, data in nominal.queries.items()},
                               nominal.rows, support.truth_sets, support.proposal,
                               nominal.model_pin, support.physical_pin, result, old)


@pytest.mark.parametrize("name", ["detection_useless_support", "competition", "already_supported", "irreducible",
                                  "permanently_unavailable", "old_cost_tie", "branch_budgets", "aliases", "three_actions"])
def test_every_frontier_triple_matches_unpruned_whole_tree_enumeration(name):
    nominal, support, result, old = solve(name)
    assert check(nominal, support, result, old)["optimality_verified"]
    costs = {q: data["cost"] for q, data in nominal.queries.items()}
    for entry in result["budget_frontiers"]:
        oracle = ref().exhaustive_tree_oracle(nominal.query_ids, costs, nominal.rows, support.truth_sets,
                                             support.proposal, [], entry["budget"])
        assert sorted((p["d"], p["w"], p["l"]) for p in entry["frontier"]) == sorted(
            (p["d"], p["w"], p["l"]) for p in oracle["frontier"])
        assert {name: entry["canonical_point"][name] for name in ("d", "w", "l")} == oracle["canonical_value"]
        for point in entry["frontier"]:
            candidates = []
            for d, w, cost, tree in oracle["trees"]:
                if (d, w, cost) != (point["d"], point["w"], point["l"]):
                    continue
                qid = tree["action"]
                children = []
                if qid is not None:
                    for child in tree["children"]:
                        history = [{"query_id": qid, "outcome_id": child["outcome"]}]
                        compatible = ref().audit_reference.compatible(support.design_signatures, nominal.query_ids, history)
                        mask = sum(1 << i for i, s in enumerate(support.design_signatures) if s in compatible)
                        state_id = ref().exact_reference._state_id(result["root"]["scope_pin"], nominal.compatible(history), mask,
                                                                   sorted(set(nominal.query_ids) - {qid}), entry["budget"] - costs[qid])
                        children.append({"outcome": child["outcome"], "state_id": state_id,
                                         "d": child["d"], "w": child["w"], "l": child["l"]})
                candidates.append({"action": qid, "children": children})
            assert point["choice"] == min(candidates, key=lambda c: ref().choice_order(c, costs))


def test_support_objective_can_buy_detection_useless_evidence():
    _, _, result, old = solve("detection_useless_support")
    assert old["budget_frontiers"][-1]["canonical_point"]["choice"]["action"] is None
    assert [(p["d"], p["w"], p["l"]) for p in result["budget_frontiers"][-1]["frontier"]] == [(0, 1, 2), (0, 0, 0)]


def test_support_competes_with_detection_and_lower_support_is_cheaper():
    _, _, result, _ = solve("competition", [0, 1, 2])
    one = next(e for e in result["budget_frontiers"] if e["budget"] == 1)
    assert {(p["d"], p["w"], p["l"]) for p in one["frontier"]} == {(1, 0, 3), (0, 1, 3), (0, 0, 0)}
    full = result["budget_frontiers"][-1]["frontier"]
    assert {(1, 0, 3), (1, 1, 5)} <= {(p["d"], p["w"], p["l"]) for p in full}


def test_old_e_cost_tie_is_preserved_while_joint_objective_can_improve_support():
    _, _, result, old = solve("old_cost_tie", [0, 1, 2])
    old_point = old["budget_frontiers"][1]["canonical_point"]
    joint = result["budget_frontiers"][1]["canonical_point"]
    assert old_point["choice"]["action"] == "q0" and joint["choice"]["action"] == "q1"
    assert (old_point["d"], old_point["l"]) == (joint["d"], joint["l"]) == (1, 3)
    assert joint["w"] == 1


def test_mixed_physical_cells_do_not_earn_support_or_imply_empty_support():
    nominal, support, result, _ = solve("permanently_unavailable")
    assert all(entry["canonical_point"]["w"] == 0 for entry in result["budget_frontiers"])
    state = ref().support_state(set(nominal.rows), support.truth_sets, {bits((0,))}, "established")
    assert state["claim_status"] == "unresolved" and not state["supported"] and not state["support_attainable"]
    with pytest.raises(ValueError, match="Empty"):
        ref().support_state(set(nominal.rows), support.truth_sets, set(), "established")


@pytest.mark.parametrize("tamper", ["reward", "frontier", "branch", "action", "scope", "counter", "anchor", "projection"])
def test_joint_witness_tampering_is_rejected(tamper):
    nominal, support, result, old = solve("competition")
    state = next(s for s in result["states"] if s["actions"])
    if tamper == "reward":
        state["stop_reward"] += 1
    elif tamper == "frontier":
        state["frontier"][0]["w"] += 1
    elif tamper == "branch":
        state["actions"][0]["branches"].pop()
    elif tamper == "action":
        state["actions"].pop()
    elif tamper == "scope":
        result["root"]["physical_pin"] = "wrong_physical_model"
    elif tamper == "counter":
        result["resources"]["child_combinations"] += 1
    elif tamper == "anchor":
        result["budget_frontiers"].pop()
    else:
        old["budget_frontiers"][-1]["frontier"][0]["l"] += 1
    with pytest.raises(ValueError):
        check(nominal, support, result, old)


@pytest.mark.parametrize("limits", [{"state_cap": 1}, {"combination_cap": 1}])
def test_caps_withhold_all_joint_optimality_claims(limits):
    nominal, support, result, old = solve("competition", **limits)
    assert result["status"] == "unavailable" and not result["budget_frontiers"]
    verified = check(nominal, support, result, old)
    assert verified["status"] == "unavailable" and not verified["optimality_verified"]


def test_hidden_realization_metadata_and_iteration_order_do_not_select_actions():
    nominal, support, result, _ = solve("competition")
    changed = copy.deepcopy(support)
    changed.actual_k, changed.realized_signature, changed.omitted_records = 999, ("secret",), ["unqueried"]
    changed.truth_sets = dict(reversed(list(changed.truth_sets.items())))
    planner = module("joint_audit_warrant", "frontier").JointFrontierPlanner(
        changed.nominal, changed, [], result["root"]["requested_budgets"])
    other = planner.solve()
    assert other["root"] == result["root"] and other["states"] == result["states"]


@pytest.fixture(scope="module")
def development():
    def read(path):
        data = path.read_bytes()
        return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)
    problems = read(ROOT / "studies/evidence_acquisition/development_problems.json")
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    assert all(p["split"] == "development" for p in problems)
    cells = read(ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz")
    old_roots = read(ROOT / "studies/joint_audit_warrant/development_old_roots.json.gz")
    old_runs = read(ROOT / "studies/joint_audit_warrant/development_old_design_runs.json.gz")
    fixtures = []
    driver = module("joint_audit_warrant", "analysis")
    for problem in problems:
        selected_cells = [c for c in cells if c["problem_id"] == problem["problem_id"]]
        selected_roots = [r for r in old_roots if r["problem_id"] == problem["problem_id"]]
        selected_runs = [r for r in old_runs if r["problem_id"] == problem["problem_id"]]
        cache = driver.CertificateCache()
        output = driver.analyze_problem(problem, selected_cells, selected_roots, selected_runs, cache=cache)
        assert all(cell["status"] == "completed" for cell in output["cells"])
        fixtures.append(([problem], selected_cells, selected_roots, selected_runs,
                         output["roots"], output["design_runs"], output["runs"], cache.certificates))
    return fixtures


@pytest.mark.parametrize("index", range(4))
def test_every_saved_development_path_reward_projection_and_certificate_is_checked(index, development):
    arguments = development[index]
    checked = ref().verify_all(*arguments)
    assert checked["status"] == "passed" and checked["joint_optimality_status"] == "complete"
    assert checked["joint_roots_verified"] == len(arguments[4])
    assert checked["completed_design_paths_checked"] == len(arguments[5])
    assert checked["completed_anchor_paths_checked"] == len(arguments[6])
    assert checked["distinct_certificates_checked"] == len(arguments[7])
    assert checked["certificate_references_checked"] > checked["distinct_certificates_checked"]


@pytest.mark.parametrize("kind", ["missing_design", "missing_anchor", "old_pin", "baseline", "physical_count", "reward",
                                  "phase_cost", "phase_history", "transition", "stop", "actual_k_flag",
                                  "certificate", "point", "price", "matched_support_saving"])
def test_saved_joint_results_tampering_is_rejected(kind, development):
    problems, cells, old_roots, old_runs, roots, design, anchors, certs = copy.deepcopy(development[1])
    if kind == "missing_design":
        design.pop()
    elif kind == "missing_anchor":
        anchors.pop()
    elif kind == "old_pin":
        old_roots[0]["solver"]["root"]["design_pin"] = "changed_historical_input"
    elif kind == "baseline":
        roots[0]["support_baseline"]["initial_supported"] += 1
    elif kind == "physical_count":
        design[0]["design_support"]["compatible_physical_world_count"] += 1
    elif kind == "reward":
        design[0]["design_supported_original"] = not design[0]["design_supported_original"]
    elif kind in {"phase_cost", "phase_history", "transition", "stop"}:
        row = next(r for r in design if r["arm"] == "E_then_support")
        if kind == "phase_cost":
            row["support_phase_cost"] += 1
        elif kind == "phase_history":
            row["phase_histories"]["joint"] = [{"query_id": "unpaid", "outcome_id": "missing"}]
        elif kind == "transition":
            row["sequential_transition_history"] = [{"query_id": "unpaid", "outcome_id": "missing"}]
        else:
            row["termination_reason"] = "archive_irreducible"
    elif kind == "actual_k_flag":
        anchors[-1]["claim_established"] = not anchors[-1]["claim_established"]
    elif kind == "certificate":
        design[-1]["certificates"]["final_design"] = "0" * 64
    elif kind == "point":
        roots[0]["design_points"][0]["w"] += 1
    elif kind == "price":
        item = next(p for root in roots for b in root["budget_summary"] for p in b["support_threshold_price_curve"]
                    if p["minimum_cost"] is not None)
        item["minimum_cost"] += 1
    else:
        roots[0]["budget_summary"][0]["sequential_matched_support_cost_saving"] += 1
    with pytest.raises(ValueError):
        ref().verify_all(problems, cells, old_roots, old_runs, roots, design, anchors, certs)


def test_capped_joint_roots_keep_all_e_sequential_and_placeholder_denominators(development):
    driver = module("joint_audit_warrant", "analysis")
    problems, cells, old_roots, old_runs, _, _, _, _ = development[0]
    cache = driver.CertificateCache()
    output = driver.analyze_problem(problems[0], cells, old_roots, old_runs, cache=cache, state_cap=1)
    arguments = (problems, cells, old_roots, old_runs, output["roots"], output["design_runs"], output["runs"], cache.certificates)
    checked = ref().verify_all(*arguments)
    assert checked["status"] == "unavailable_joint_roots_verified"
    assert checked["joint_roots_verified"] == 0 and checked["joint_roots_unavailable"] == len(output["roots"])
    assert checked["unavailable_design_rows"] > 0 and checked["unavailable_anchor_rows"] > 0
    assert all(r["execution_status"] == "completed" for r in output["design_runs"] if r["arm"] != "joint_frontier")
    placeholder = next(r for r in output["design_runs"] if r["execution_status"] == "unavailable")
    placeholder["design_supported_original"] = False
    with pytest.raises(ValueError, match="fabricated"):
        ref().verify_all(*arguments)


def test_coincident_anchors_remain_distinct_views_of_one_paid_execution():
    nominal, support, result, old = solve("detection_useless_support")
    assert result["root"]["requested_budgets"] == [0, 0, 0, 1]
    assert result["root"]["budgets"] == [0, 1]
    assert result["resources"]["requested_anchor_count"] == 4
    assert check(nominal, support, result, old)["unique_anchor_frontiers_checked"] == 2
