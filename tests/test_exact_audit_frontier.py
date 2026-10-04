"""Exact audit tests on declared tiny tables and four development inputs only."""

import copy
import gzip
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.exact_audit_frontier.{name}")
    finally:
        sys.path.remove(str(ROOT))


class TinyNominal:
    """Observation-only two/three-action correctness fixture, not an evaluation problem."""

    def __init__(self, rows, costs):
        self.rows = tuple(tuple("present" if bit else "missing" for bit in row) for row in rows)
        self.queries = {f"q{i}": {"cost": cost, "record_id": f"r{i}",
                                  "outcomes": {"missing": {}, "present": {}}}
                        for i, cost in enumerate(costs)}
        self.query_ids = tuple(self.queries)
        self.model_pin = module("reference").pin({"rows": self.rows, "queries": self.queries})
        self.signature_cells = defaultdict(int)
        for i, row in enumerate(self.rows):
            self.signature_cells[row] |= 1 << i

    def compatible(self, history):
        return sum(1 << i for i, row in enumerate(self.rows) if all(
            row[self.query_ids.index(h["query_id"])] == h["outcome_id"] for h in history))

    def partition(self, state, query_id):
        position = self.query_ids.index(query_id)
        return {outcome: sum(1 << i for i, row in enumerate(self.rows)
                             if state & (1 << i) and row[position] == outcome)
                for outcome in ("missing", "present")}


def toy(name):
    if name == "complementary":
        rows, design, costs = [(0, 0), (1, 1)], [(0, 0), (0, 1), (1, 0), (1, 1)], (1, 1)
    elif name == "constant":
        rows, design, costs = [(1,)], [(0,), (1,)], (2,)
    elif name == "greedy_trap":
        rows, design, costs = [(0, 0, 0), (0, 1, 1)], [(0, 0, 0), (0, 1, 1), (1, 0, 0), (0, 0, 1), (0, 1, 0)], (1, 1, 1)
    else:
        rows, design, costs = [(1, 1)], [(0, 0), (0, 1), (1, 1)], (3, 2)
    nominal = TinyNominal(rows, costs)
    design = tuple(tuple("present" if bit else "missing" for bit in row) for row in design)
    return nominal, design


def check(nominal, design, solver):
    return module("reference").verify_bellman(nominal.query_ids,
                                               {q: data["cost"] for q, data in nominal.queries.items()},
                                               nominal.rows, design, nominal.model_pin, solver)


@pytest.mark.parametrize("name", ["complementary", "constant", "greedy_trap", "unaffordable"])
def test_complete_frontier_matches_exhaustive_whole_tree_oracle(name):
    reference, frontier = module("reference"), module("frontier")
    nominal, design = toy(name)
    planner = frontier.FrontierPlanner(nominal, design, [])
    result = planner.solve()
    assert check(nominal, design, result)["optimality_verified"]
    costs = {q: data["cost"] for q, data in nominal.queries.items()}
    for entry in result["budget_frontiers"]:
        oracle = reference.exhaustive_tree_oracle(nominal.query_ids, costs, nominal.rows, design, [], entry["budget"])
        assert sorted((p["d"], p["l"]) for p in entry["frontier"]) == sorted(
            (p["d"], p["l"]) for p in oracle["frontier"])
        assert {k: entry["canonical_point"][k] for k in ("d", "l")} == oracle["canonical_value"]
        # Enumerated trees retain dominated subtrees too. Convert only the root
        # choice to the frozen child-value encoding, independently of the DP.
        for point in entry["frontier"]:
            candidates = []
            for d, cost, tree in oracle["trees"]:
                if (d, cost) != (point["d"], point["l"]):
                    continue
                qid = tree["action"]
                if qid is None:
                    candidates.append({"action": None, "children": []})
                    continue
                children = []
                for child in tree["children"]:
                    history = [{"query_id": qid, "outcome_id": child["outcome"]}]
                    possible = reference._selected(design, nominal.query_ids, history)
                    mask = sum(1 << i for i, s in enumerate(sorted(design)) if s in possible)
                    state_id = reference._state_id(result["root"]["scope_pin"], nominal.compatible(history), mask,
                                                   sorted(set(nominal.query_ids) - {qid}), entry["budget"] - costs[qid])
                    children.append({"outcome": child["outcome"], "state_id": state_id, "d": child["d"], "l": child["l"]})
                candidates.append({"action": qid, "children": children})
            expected = min(candidates, key=lambda choice: reference._choice_order(choice, costs))
            assert point["choice"] == expected


def test_complementary_tests_use_full_budget_in_each_counterfactual_branch():
    nominal, design = toy("complementary")
    result = module("frontier").FrontierPlanner(nominal, design, []).solve()
    entry = result["budget_frontiers"][2]
    assert {(p["d"], p["l"]) for p in entry["frontier"]} == {(0, 0), (1, 6), (2, 8)}
    assert entry["canonical_point"]["choice"]["action"] == "q0"
    assert all(c["d"] == 1 for c in entry["canonical_point"]["choice"]["children"])


def test_nominal_constant_action_remains_decisive():
    nominal, design = toy("constant")
    result = module("frontier").FrontierPlanner(nominal, design, []).solve()
    assert result["budget_frontiers"][2]["canonical_point"]["d"] == 1
    assert result["budget_frontiers"][2]["canonical_point"]["l"] == 4
    assert result["budget_frontiers"][1]["canonical_point"]["choice"]["action"] is None


def test_declared_greedy_trap_and_unaffordable_preference_are_distinct():
    reference = module("reference")
    nominal, design = toy("greedy_trap")
    problem = {"queries": [{"id": q, **value} for q, value in nominal.queries.items()]}
    assert reference.affordable_choice(problem, set(nominal.rows), set(design), [], 2) == "q0"
    result = module("frontier").FrontierPlanner(nominal, design, []).solve()
    assert result["budget_frontiers"][2]["canonical_point"]["d"] == 2
    assert result["budget_frontiers"][2]["canonical_point"]["choice"]["action"] != "q0"
    nominal, design = toy("unaffordable")
    problem = {"queries": [{"id": q, **value} for q, value in nominal.queries.items()]}
    assert reference.audit_reference.choose(problem, set(nominal.rows), set(design), [], "closure_informed") == "q0"
    assert reference.affordable_choice(problem, set(nominal.rows), set(design), [], 2) == "q1"
    result = module("frontier").FrontierPlanner(nominal, design, []).solve()
    assert result["budget_frontiers"][2]["canonical_point"]["d"] == 1


@pytest.mark.parametrize("change", ["action", "branch", "frontier", "tie", "budget", "cap", "counter", "missing_state"])
def test_bellman_witness_tampering_cannot_claim_exactness(change):
    nominal, design = toy("complementary")
    result = module("frontier").FrontierPlanner(nominal, design, []).solve()
    state = next(s for s in result["states"] if len(s["actions"]) == 2)
    if change == "action":
        state["actions"].pop()
    elif change == "branch":
        state["actions"][0]["branches"].pop()
    elif change == "frontier":
        state["frontier"][0]["d"] += 1
    elif change == "tie":
        chosen = result["budget_frontiers"][2]["canonical_point"]
        chosen["choice"]["action"] = "q1"
    elif change == "budget":
        result["budget_frontiers"].pop()
    elif change == "cap":
        result["resources"]["state_cap"] = 100001
    elif change == "counter":
        result["resources"]["child_combinations"] += 1
    else:
        result["states"].pop()
    with pytest.raises(ValueError):
        check(nominal, design, result)


@pytest.mark.parametrize("limit", [{"state_cap": 1}, {"combination_cap": 1}])
def test_resource_cap_retains_partial_witness_but_no_exact_claim(limit):
    nominal, design = toy("complementary")
    planner = module("frontier").FrontierPlanner(nominal, design, [], **limit)
    result = planner.solve()
    assert result["status"] == "unavailable" and result["budget_frontiers"] == []
    checked = check(nominal, design, result)
    assert checked["status"] == "unavailable" and not checked["optimality_verified"]
    with pytest.raises(ValueError):
        planner.choose([], 1)


def test_cache_scope_contains_model_envelope_root_and_budget_but_no_truth():
    nominal, design = toy("complementary")
    planner = module("frontier").FrontierPlanner(nominal, design, [])
    result = planner.solve()
    changed = copy.deepcopy(nominal)
    changed.claim_values = [False, True]
    changed.actual_k = 999
    changed.realized_signature = design[1]
    duplicate = module("frontier").FrontierPlanner(changed, list(reversed(design)) * 4, []).solve()
    assert result["root"] == duplicate["root"]
    assert result["states"] == duplicate["states"]
    changed.model_pin = "different-hypothetical-model"
    scoped = module("frontier").FrontierPlanner(changed, design, []).solve()
    assert scoped["root"]["scope_pin"] != result["root"]["scope_pin"]


@pytest.fixture(scope="module")
def development():
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    assert all(p["split"] == "development" for p in problems)
    cells = json.loads(gzip.decompress((ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz").read_bytes()))
    return problems, cells


@pytest.fixture(scope="module")
def computed_development(development):
    driver = module("analysis")
    fixtures = []
    problems, all_cells = development
    for problem in problems:
        cells = [cell for cell in all_cells if cell["problem_id"] == problem["problem_id"]]
        cache = driver.CertificateCache()
        output = driver.analyze_problem(problem, cells, cache=cache)
        assert all(cell["status"] == "completed" for cell in output["cells"])
        fixtures.append(([problem], cells, output["roots"], output["design_runs"], output["runs"], cache.certificates))
    return fixtures


@pytest.mark.parametrize("index", range(4))
def test_every_development_bellman_state_hindsight_and_paid_path_verifies(index, computed_development):
    arguments = computed_development[index]
    result = module("reference").verify_all(*arguments)
    assert result["status"] == "passed" and result["exact_optimality_status"] == "complete"
    assert result["exact_roots_verified"] == len(arguments[2])
    assert result["completed_design_paths_checked"] == len(arguments[3])
    assert result["completed_anchor_paths_checked"] == len(arguments[4])
    assert result["distinct_certificates_checked"] == len(arguments[5])
    assert result["certificate_references_checked"] > result["distinct_certificates_checked"]


@pytest.mark.parametrize("kind", ["missing_design", "missing_anchor", "root_group", "minimum", "typed_subset",
                                  "subset_coverage", "charge", "stop", "anchor_status", "certificate", "design_point", "gap"])
def test_saved_results_tampering_cannot_pass(kind, computed_development):
    problems, cells, roots, design_runs, runs, certificates = copy.deepcopy(computed_development[1])
    if kind == "missing_design":
        design_runs.pop()
    elif kind == "missing_anchor":
        runs.pop()
    elif kind == "root_group":
        roots[0]["signatures"].pop()
    elif kind in {"minimum", "typed_subset", "subset_coverage"}:
        minimum = next(h for root in roots for h in root["hindsight"] if h["status"] == "available")
        if kind == "minimum":
            minimum["minimum_cost"] += 1
        elif kind == "typed_subset":
            minimum["typed_observations"][0]["observable"] = {"kind": "event_did_not_occur"}
        else:
            minimum["nominal_world_coverage"].pop()
    elif kind == "charge":
        row = next(r for r in design_runs if r["audit_history"])
        row["added_cost"] -= 1
    elif kind == "stop":
        row = next(r for r in design_runs if r["arm"] == "exact_frontier" and r["audit_history"])
        row["termination_reason"] = "model_validated"
    elif kind == "anchor_status":
        runs[-1]["support"]["finally_supported_definite"] = not runs[-1]["support"]["finally_supported_definite"]
    elif kind == "certificate":
        design_runs[-1]["certificates"]["final_nominal"] = "0" * 64
    elif kind == "design_point":
        roots[0]["design_points"][0]["d"] += 1
    else:
        roots[0]["budget_summary"][0]["search_gap"] += 1
    with pytest.raises(ValueError):
        module("reference").verify_all(problems, cells, roots, design_runs, runs, certificates)


def test_capped_root_keeps_full_placeholder_grid_and_never_claims_optimality(development):
    driver, reference = module("analysis"), module("reference")
    problems, all_cells = development
    problem = problems[0]
    cells = [cell for cell in all_cells if cell["problem_id"] == problem["problem_id"]]
    cache = driver.CertificateCache()
    output = driver.analyze_problem(problem, cells, cache=cache, state_cap=1)
    assert all(root["exact_status"] == "unavailable" for root in output["roots"])
    assert all(row["execution_status"] == "unavailable" for row in output["design_runs"] if row["arm"] == "exact_frontier")
    result = reference.verify_all([problem], cells, output["roots"], output["design_runs"], output["runs"], cache.certificates)
    assert result["status"] == "unavailable_exact_roots_verified"
    assert result["exact_optimality_status"] == "partial_unavailable"
    assert result["exact_roots_verified"] == 0
    assert result["unavailable_design_rows"] > 0 and result["unavailable_anchor_rows"] > 0
    bad = next(row for row in output["design_runs"] if row["execution_status"] == "unavailable")
    bad["added_cost"] = 0
    with pytest.raises(ValueError, match="fabricated"):
        reference.verify_all([problem], cells, output["roots"], output["design_runs"], output["runs"], cache.certificates)


def test_independent_subset_minima_distinguish_no_contradiction_from_zero(computed_development):
    reference = module("reference")
    for problems, _, roots, _, _, _ in computed_development:
        problem = problems[0]
        nominal = reference.signatures_from_worlds(problem, problem["worlds"])
        for root in roots:
            for record in root["hindsight"]:
                expected = reference.subset_minimum(problem, root["base_history"], record["full_signature"])
                if tuple(record["full_signature"]) in nominal:
                    assert expected is None and record["minimum_cost"] is None
                    assert record["reason"] == "no_catalogue_contradiction"
                else:
                    assert expected["minimum_cost"] > 0
                    assert expected["minimum_cost"] == record["minimum_cost"]
