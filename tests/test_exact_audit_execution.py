"""Integer-budget audit execution on four saved development cases and tiny fixtures."""

import copy
import gzip
import importlib
import inspect
import json
import runpy
import sys
from pathlib import Path

import pytest

from tracebench.evidence_acquisition.model import Model, canonical, pin

ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / "tests/test_audit_aware_acquisition.py"))
tiny_correlated = HELPERS["tiny_correlated"]
tiny_with_expensive_constant = HELPERS["tiny_with_expensive_constant"]


def module(study, name):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.{study}.{name}")
    finally:
        sys.path.remove(str(ROOT))


@pytest.fixture(scope="module")
def execution():
    return module("exact_audit_frontier", "execution")


@pytest.fixture(scope="module")
def frontier():
    return module("exact_audit_frontier", "frontier")


@pytest.fixture(scope="module")
def expanded():
    return module("archive_model_misspecification", "expanded")


@pytest.fixture(scope="module")
def development():
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    saved = json.loads(gzip.decompress((ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz").read_bytes()))
    legacy = json.loads(gzip.decompress((ROOT / "studies/exact_audit_frontier/development_legacy_audit.json.gz").read_bytes()))
    assert {r["problem_id"] for r in legacy} == {p["problem_id"] for p in problems}
    return problems, {(c["problem_id"], c["k"]): c for c in saved}, legacy


def empty_baseline(nominal):
    certificate = nominal.certificate([])
    assert certificate["status"] == "established" and nominal.verify_certificate(certificate)
    return {"history": [], "cost": 0, "query_count": 0, "returned_bytes": 0,
            "status": "established", "certificate": pin(certificate), "certificate_valid": True}


def tiny_setup(execution, expanded, problem):
    nominal = Model(problem)
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    baseline = empty_baseline(nominal)
    roots = execution.verify_roots(nominal, design, [{"outcomes": list(s), "policy": baseline} for s in design])
    assert len(roots) == 1
    return nominal, design, roots[0]


def run(execution, nominal, design, root, signature, arm, budget, *, planner=None, cache=None):
    return execution.execute_audit(nominal, root["baseline"], signature, arm, budget,
                                   design_signatures=design if arm not in execution.ORIGINAL_ARMS[:3] else None,
                                   planner=planner, certificate_cache=cache)


@pytest.mark.parametrize("index", range(4))
def test_all_saved_development_percentage_anchors_preserve_original_arms(execution, development, index):
    problems, saved, legacy = development
    problem = problems[index]
    nominal = Model(problem)
    cache = execution.CertificateCache()
    design = tuple(tuple(r["outcomes"]) for r in saved[problem["problem_id"], 2]["signature_rows"])
    sources = {(k, tuple(r["outcomes"])): r["policy"] for k in (0, 1, 2)
               for r in saved[problem["problem_id"], k]["signature_rows"]}
    for old in (r for r in legacy if r["problem_id"] == problem["problem_id"]):
        baseline = sources[old["k"], tuple(old["outcomes"])]
        observed = execution.execute_audit(nominal, baseline, old["outcomes"], old["arm"], old["audit_budget"],
                                           design_signatures=design if old["arm"] == "closure_informed" else None,
                                           certificate_cache=cache)
        for field in observed.keys() & old.keys() - {"budget_percent", "selection_seconds", "checking_seconds"}:
            assert observed[field] == old[field], field
        assert observed["integer_budget"] == old["audit_budget"]
        assert observed["nominal_certificate_pin"] == old["certificates"]["final_nominal"]
    assert cache.stats()["distinct_certificates_verified"] < cache.stats()["cache_references"]


def test_saved_root_groups_cover_every_compatible_signature_once(execution, development):
    problems, saved, _ = development
    for problem in problems:
        nominal = Model(problem)
        rows = saved[problem["problem_id"], 2]["signature_rows"]
        design = tuple(tuple(r["outcomes"]) for r in rows)
        roots = execution.verify_roots(nominal, design, rows)
        covered = []
        for root in roots:
            history = root["base_history"]
            expected = {s for s in design if all(s[nominal.query_ids.index(h["query_id"])] == h["outcome_id"] for h in history)}
            assert set(map(tuple, root["signatures"])) == expected
            assert root["signature_count"] == len(expected)
            assert root["original_signature_count"] + root["new_signature_count"] == len(expected)
            assert root["base_history"] == root["baseline"]["history"]
            assert set(root["baseline"]) == set(execution.BASELINE_FIELDS)
            assert root["root_pin"] == execution.root_identity(nominal, history, design)["root_pin"]
            covered.extend(map(tuple, root["signatures"]))
        assert len(covered) == len(set(covered)) == len(design)


def test_root_grouping_rejects_missing_duplicate_or_inconsistent_retained_paths(execution, development):
    problems, saved, _ = development
    nominal = Model(problems[0])
    rows = saved[problems[0]["problem_id"], 2]["signature_rows"]
    design = tuple(tuple(r["outcomes"]) for r in rows)
    for invalid in (rows[:-1], rows + rows[:1]):
        with pytest.raises(ValueError):
            execution.verify_roots(nominal, design, invalid)
    altered = copy.deepcopy(rows)
    baseline = altered[0]["policy"]
    old_query = baseline["history"][0]["query_id"]
    alias = next(qid for qid in nominal.query_ids if qid != old_query
                 and nominal.queries[qid]["record_id"] == nominal.queries[old_query]["record_id"])
    baseline["history"][0]["query_id"] = alias
    baseline["cost"] = nominal.queries[alias]["cost"]
    baseline["returned_bytes"] = len(canonical(nominal.queries[alias]["outcomes"][baseline["history"][0]["outcome_id"]]))
    baseline["certificate"] = pin(nominal.certificate(baseline["history"]))
    with pytest.raises(ValueError, match="disagree on a prefix"):
        execution.verify_roots(nominal, design, altered)


def test_affordable_control_does_not_change_original_d_cutoff(execution, expanded, development):
    nominal, design, root = tiny_setup(execution, expanded, tiny_with_expensive_constant(development[0][0]))
    signature = ("missing", "present")
    original = run(execution, nominal, design, root, signature, "closure_informed", 1)
    affordable = run(execution, nominal, design, root, signature, "closure_informed_affordable", 1)
    assert original["audit_history"] == [] and original["added_cost"] == 0
    assert original["next_query"] == "q_expensive_constant"
    assert original["termination_reason"] == "next_action_unaffordable"
    assert affordable["audit_history"] == [{"query_id": "q_a", "outcome_id": "missing"}]
    assert affordable["added_cost"] == 1 and affordable["added_returned_bytes"] > 0
    assert affordable["termination_reason"] == "no_affordable_action"
    assert nominal.queries["q_expensive_constant"]["cost"] == 4


def test_complementary_queries_constant_alarm_and_hindsight_alias_minimum(execution, frontier, expanded, development):
    nominal, design, root = tiny_setup(execution, expanded, tiny_correlated(development[0][0]))
    planner = frontier.FrontierPlanner(nominal, design, root["base_history"])
    assert planner.solve()["status"] == "complete"
    signature = ("missing", "present", "present")
    certificate = execution.hindsight(nominal, root, signature)
    assert certificate["status"] == "available" and certificate["minimum_cost"] == 3
    assert certificate["query_ids"] == ["q_a", "q_b"]  # Expensive alias cannot improve the minimum.
    assert certificate["cardinality"] == 2
    assert len(certificate["nominal_world_coverage"]) == len(nominal.worlds)
    assert nominal.verify_certificate(certificate["certificate"])
    for world in certificate["nominal_world_coverage"]:
        assert world["disagreed_query_ids"]
    for row in certificate["typed_observations"]:
        assert row["observable"] == nominal.queries[row["query_id"]]["outcomes"][row["outcome_id"]]
    for budget in range(root["residual_cost"] + 1):
        result = run(execution, nominal, design, root, signature, "exact_frontier", budget, planner=planner)
        assert result["added_cost"] <= budget
        assert (result["status"] == "nominal_model_conflict") == (budget >= 3)
        if budget >= 3:
            assert result["audit_history"] == certificate["additional_history"]
            assert result["first_conflict"]["added_query_index"] == 2
            assert result["first_conflict"]["nominal_outcomes_before"] == ["missing"]
            assert result["coverage"]["remaining_actions"] == 1
            assert result["added_cost"] == 3 and result["coverage"]["added_alias_queries"] == 0


def test_hindsight_original_unavailable_and_pin_alias_tampering_rejected(execution, expanded, development):
    nominal, design, root = tiny_setup(execution, expanded, tiny_correlated(development[0][0]))
    for signature in nominal.signature_cells:
        result = execution.hindsight(nominal, root, signature)
        assert result["status"] == "unavailable" and result["reason"] == "no_catalogue_contradiction"
        assert result["minimum_cost"] is result["certificate"] is result["additional_history"] is None
    damaged = {**root, "root_pin": "0" * 64}
    with pytest.raises(ValueError, match="identity pin mismatch"):
        execution.hindsight(nominal, damaged, design[0])
    with pytest.raises(ValueError, match="physical aliases"):
        execution.hindsight(nominal, root, ("missing", "present", "missing"))


def test_hindsight_ties_use_cardinality_then_sorted_opaque_ids(execution, expanded, development):
    # Equal-cost aliases offer two certificates with the same cardinality.
    problem = tiny_correlated(development[0][0])
    problem["queries"][2]["cost"] = 2
    nominal, design, root = tiny_setup(execution, expanded, problem)
    result = execution.hindsight(nominal, root, ("missing", "present", "present"))
    assert result["minimum_cost"] == 3 and result["query_ids"] == ["q_a", "q_b"]

    # A separately retained constant receipt costs two, tying the two unit-cost
    # complementary receipts. The one-action contradiction wins cardinality.
    problem = tiny_correlated(development[0][0])
    problem["queries"][1]["cost"] = 1
    record = copy.deepcopy(next(r for r in problem["record_catalog"] if r["id"] == "record_context_0"))
    record["id"] = "unit_constant_receipt"
    problem["record_catalog"].append(record)
    for world in problem["worlds"]:
        world["retained_record_ids"].append(record["id"])
    query = problem["queries"][2]
    query.update(id="q_constant", record_id=record["id"], cost=2)
    query["outcomes"]["present"] = record
    nominal, design, root = tiny_setup(execution, expanded, problem)
    signature = ("missing", "present", "missing")
    assert signature in design
    result = execution.hindsight(nominal, root, signature)
    assert result["minimum_cost"] == 2 and result["cardinality"] == 1
    assert result["query_ids"] == ["q_constant"]


def test_integer_selector_has_only_allowed_information_and_budget(execution, frontier, expanded, development):
    nominal, design, root = tiny_setup(execution, expanded, tiny_correlated(development[0][0]))
    planner = frontier.FrontierPlanner(nominal, design, root["base_history"])
    planner.solve()
    assert set(inspect.signature(execution.IntegerSelector.choose).parameters) == {"self", "history", "remaining_budget"}
    histories = [[], [{"query_id": "q_a", "outcome_id": "missing"}], [{"query_id": "q_a", "outcome_id": "present"}]]
    for arm in execution.ARMS:
        selector = execution.IntegerSelector(nominal, arm, design if arm not in execution.ORIGINAL_ARMS[:3] else None,
                                              planner if arm == "exact_frontier" else None)
        first = {(canonical(h), b): selector.choose(h, b) for h in histories for b in (0, 1, 2)}
        second = {(canonical(h), b): selector.choose(h, b) for h in reversed(histories) for b in (2, 1, 0)}
        assert first == second


def test_runtime_rejects_bad_roots_certificates_budgets_and_unavailable_exact_solver(execution, frontier, expanded, development):
    nominal, design, root = tiny_setup(execution, expanded, tiny_correlated(development[0][0]))
    signature = design[0]
    for invalid in (True, -1, root["residual_cost"] + 1):
        with pytest.raises(ValueError, match="Integer audit budget outside"):
            run(execution, nominal, design, root, signature, "no_audit", invalid)
    damaged = copy.deepcopy(root)
    damaged["baseline"]["certificate"] = "0" * 64
    with pytest.raises(ValueError, match="reference/bytes mismatch"):
        run(execution, nominal, design, damaged, signature, "no_audit", 0)
    with pytest.raises(ValueError, match="checker-backed implementation"):
        run(execution, nominal, design, root, signature, "no_audit", 0, cache=object())
    planner = frontier.FrontierPlanner(nominal, design, [], state_cap=1)
    assert planner.solve()["status"] == "unavailable"
    with pytest.raises(ValueError, match="not fully solved"):
        run(execution, nominal, design, root, signature, "exact_frontier", 0, planner=planner)


def test_paid_development_execution_attains_frontier_and_respects_hindsight_bound(execution, frontier, development):
    problems, saved, _ = development
    roots_checked = 0
    for problem in problems:
        nominal = Model(problem)
        cache = execution.CertificateCache()
        rows = saved[problem["problem_id"], 2]["signature_rows"]
        design = tuple(tuple(row["outcomes"]) for row in rows)
        roots = execution.verify_roots(nominal, design, rows, certificate_cache=cache)
        for root in roots:
            roots_checked += 1
            planner = frontier.FrontierPlanner(nominal, design, root["base_history"])
            solved = planner.solve()
            assert solved["status"] == "complete"
            minima = {tuple(s): execution.hindsight(nominal, root, s, certificate_cache=cache)["minimum_cost"]
                      for s in root["signatures"]}
            prior_detections = 0
            for budget_row in solved["budget_frontiers"]:
                budget = budget_row["budget"]
                points = {}
                for arm in execution.ARMS:
                    detection = cost = 0
                    for signature in root["signatures"]:
                        result = run(execution, nominal, design, root, signature, arm, budget,
                                     planner=planner if arm == "exact_frontier" else None, cache=cache)
                        assert result["base_history"] == root["base_history"]
                        assert result["added_cost"] <= budget
                        assert len({h["query_id"] for h in result["history"]}) == len(result["history"])
                        alarm = result["status"] == "nominal_model_conflict"
                        if alarm:
                            assert minima[tuple(signature)] is not None
                            assert minima[tuple(signature)] <= result["added_cost"]
                            assert tuple(signature) not in nominal.signature_cells
                            assert not nominal.compatible(result["history"])
                        detection += alarm
                        cost += result["added_cost"]
                    points[arm] = detection, cost
                    assert any(p["d"] >= detection and p["l"] <= cost for p in budget_row["frontier"])
                optimum = budget_row["canonical_point"]
                assert points["exact_frontier"] == (optimum["d"], optimum["l"])
                assert optimum["d"] >= prior_detections
                prior_detections = optimum["d"]
                assert optimum["d"] <= sum(m is not None and m <= budget for m in minima.values())
                if budget == root["residual_cost"]:
                    assert optimum["d"] == root["new_signature_count"]
    assert roots_checked > 0


