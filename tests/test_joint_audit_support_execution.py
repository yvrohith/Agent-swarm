"""Fixed-M2 support and paid runtime checks on saved development/tiny fixtures."""
import copy
import gzip
import importlib
import inspect
import json
import sys
from itertools import combinations
from pathlib import Path

import pytest

from tracebench.evidence_acquisition.model import Model, canonical, indices, pin

ROOT = Path(__file__).resolve().parents[1]


def load(study, module):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.{study}.{module}")
    finally:
        sys.path.remove(str(ROOT))


@pytest.fixture(scope="module")
def api():
    return (load("joint_audit_warrant", "support"), load("joint_audit_warrant", "execution"),
            load("joint_audit_warrant", "frontier"), load("exact_audit_frontier", "frontier"),
            load("archive_model_misspecification", "expanded"), load("audit_aware_acquisition", "analysis"))


@pytest.fixture(scope="module")
def development():
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    study = ROOT / "studies/joint_audit_warrant"
    roots = json.loads(gzip.decompress((study / "development_old_roots.json.gz").read_bytes()))
    runs = json.loads(gzip.decompress((study / "development_old_design_runs.json.gz").read_bytes()))
    assert {r["problem_id"] for r in roots} == {p["problem_id"] for p in problems}
    return problems, roots, runs


def contract(api, problem, root):
    nominal, expanded = Model(problem), api[4].ExpandedModel(problem, 2)
    support = api[0].SupportContract(nominal, expanded, root["base_history"], root["baseline"]["status"])
    saved = api[1].SavedEPolicy(nominal, support.design_signatures, root["solver"])
    return nominal, expanded, support, saved


def baseline(nominal, history):
    cert = nominal.certificate(history)
    assert nominal.verify_certificate(cert)
    return {"history": history, "cost": sum(nominal.queries[h["query_id"]]["cost"] for h in history),
            "query_count": len(history), "returned_bytes": sum(len(canonical(nominal.queries[h["query_id"]]["outcomes"][h["outcome_id"]])) for h in history),
            "status": cert["status"], "certificate": pin(cert), "certificate_valid": True}


def support_only_fixture(problem):
    """No new root signatures; a nonreceipt observation can substantiate absence.

    Three explicit physical worlds: no context with either nuisance answer, and
    retained context with nuisance absent. Omitting that receipt gives an
    observationally overlapping opposite witness only on nuisance-absent paths.
    """
    problem = copy.deepcopy(problem)
    problem["worlds"] = [problem["worlds"][i] for i in (0, 1, 6)]
    problem["prior"] = ["1/3"] * 3
    records = {r["id"]: r for r in problem["record_catalog"]}
    problem["queries"] = []
    for qid, rid, cost in (("q_context", "record_context_0", 1),
                           ("q_nuisance", "nuisance", 2), ("q_nuisance_alias", "nuisance", 4)):
        record = records[rid]
        problem["queries"].append({"id": qid, "record_id": rid, "kind": record["kind"],
                                    "scope": copy.deepcopy(record["scope"]), "cost": cost,
                                    "outcomes": {"present": copy.deepcopy(record),
                                                 "missing": {"kind": "lookup_empty", "scope": copy.deepcopy(record["scope"])}}})
    Model(problem)
    return problem


def tiny_setup(api, development):
    problem = support_only_fixture(development[0][0])
    nominal, expanded = Model(problem), api[4].ExpandedModel(problem, 2)
    h0 = [{"query_id": "q_context", "outcome_id": "missing"}]
    base = baseline(nominal, h0)
    assert base["status"] == "ruled_out"
    support = api[0].SupportContract(nominal, expanded, h0, base["status"])
    old = api[3].FrontierPlanner(nominal, support.design_signatures, h0)
    assert old.solve()["status"] == "complete"
    saved = api[1].SavedEPolicy(nominal, support.design_signatures, old.export())
    return nominal, expanded, support, saved, base


def test_all_physical_realizations_and_full_cells_define_support(api, development):
    for problem in development[0]:
        for root in (r for r in development[1] if r["problem_id"] == problem["problem_id"]):
            nominal, expanded, support, _ = contract(api, problem, root)
            remaining = sorted(set(nominal.query_ids) - {h["query_id"] for h in support.base_history})
            histories = {}
            for signature in root["signatures"]:
                answers = dict(zip(nominal.query_ids, signature, strict=True))
                for count in range(len(remaining) + 1):
                    for subset in combinations(remaining, count):
                        history = support.base_history + [{"query_id": q, "outcome_id": answers[q]} for q in subset]
                        histories[canonical(history)] = history
            for history in histories.values():
                assessed = support.assess(history)
                state = expanded.compatible(history)
                assert state
                physical_values = {expanded.claim_values[i] for i in indices(state)}
                expected = support.proposal in {"established", "ruled_out"} and physical_values == {support.proposal == "established"}
                assert assessed["supported"] == expected
                assert assessed["claim_status"] == expanded.claim_status(history)
                assert assessed["terminal_status"] == expanded.terminal_status(history)
                assert assessed["compatible_physical_world_count"] == state.bit_count()
                assert assessed["reward"] == assessed["compatible_original_signature_count"] * expected


def test_mixed_cell_is_not_support_and_attainability_is_not_irreducibility(api, development):
    nominal, _, support, _, _ = tiny_setup(api, development)
    root = support.assess(support.base_history)
    assert root["terminal_status"] == "unresolved_pending"
    assert not root["supported"] and root["attainable"] and root["reward"] == 0
    observed = support.base_history + [{"query_id": "q_nuisance", "outcome_id": "missing"}]
    mixed = support.assess(observed)
    assert mixed["compatible_signature_count"] == 1 and mixed["compatible_physical_world_count"] == 2
    assert mixed["terminal_status"] == "archive_irreducible"
    assert not mixed["supported"] and not mixed["attainable"] and mixed["reward"] == 0
    observed[-1]["outcome_id"] = "present"
    established = support.assess(observed)
    assert established["supported"] and established["reward"] == 1
    assert established["claim_status"] == "ruled_out" and nominal.compatible(observed)


def test_support_reward_ignores_physical_multiplicity_and_empty_is_failure(api, development):
    _, _, support, _, _ = tiny_setup(api, development)
    selected = next(i for i, s in enumerate(support.design_signatures) if s == ("missing", "present", "present"))
    assert support.reward(1 << selected) == 1
    problem = support_only_fixture(development[0][0])
    world = copy.deepcopy(problem["worlds"][1])
    world["id"] = "unit_additional_unobserved_delivery_failure"
    world["occurring_event_ids"].remove("delivery_0")
    world["retained_record_ids"].remove("record_delivery_0")
    problem["worlds"].append(world)
    problem["prior"] = ["1/4"] * 4
    nominal, expanded = Model(problem), api[4].ExpandedModel(problem, 2)
    alternative = api[0].SupportContract(nominal, expanded, support.base_history, support.proposal)
    assert alternative.reward(1 << selected) == 1
    observed = support.base_history + [{"query_id": "q_nuisance", "outcome_id": "present"}]
    assert alternative.assess(observed)["compatible_physical_world_count"] == 2
    for value in (0, -1, True, support.full_mask << 1):
        for method in (support.supported, support.attainable, support.reward):
            with pytest.raises(ValueError):
                method(value)
    with pytest.raises(ValueError):
        support.mask(support.base_history + [{"query_id": "q_nuisance", "outcome_id": "present"},
                                            {"query_id": "q_nuisance_alias", "outcome_id": "missing"}])


def test_opposite_conclusion_and_original_irreducibility_never_reward(api, development):
    seen = set()
    for problem in development[0]:
        for root in (r for r in development[1] if r["problem_id"] == problem["problem_id"]):
            _, _, support, _ = contract(api, problem, root)
            if support.proposal == "archive_irreducible":
                seen.add("irreducible")
                assert support.reward(support.root_mask) == 0
                assert not support.attainable(support.root_mask)
            for i in indices(support.root_mask):
                if support.proposal in {"established", "ruled_out"} and support._truth[i] == {support.proposal != "established"}:
                    seen.add("opposite")
                    assert not support.supported(1 << i) and not support.attainable(1 << i)
    assert "irreducible" in seen


def test_support_contract_rejects_wrong_model_root_proposal_and_actual_k(api, development):
    nominal, expanded, support, _, _ = tiny_setup(api, development)
    with pytest.raises(ValueError, match="M2"):
        api[0].SupportContract(nominal, api[4].ExpandedModel(nominal.problem, 1), support.base_history, support.proposal)
    with pytest.raises(ValueError, match="proposal"):
        api[0].SupportContract(nominal, expanded, support.base_history, "established")
    with pytest.raises(ValueError, match="pins"):
        api[0].SupportContract(Model(development[0][1]), expanded, support.base_history, support.proposal)
    with pytest.raises(ValueError, match="ordered H0"):
        support.mask([])


def test_historical_development_E_paths_preserved_exactly(api, development):
    cache = api[5].CertificateCache()
    observed_count = 0
    for problem in development[0]:
        for root in (r for r in development[1] if r["problem_id"] == problem["problem_id"]):
            nominal, _, support, saved = contract(api, problem, root)
            for old in (r for r in development[2] if r["root_id"] == root["root_id"] and r["arm"] == "exact_frontier"):
                result = api[1].execute_audit(nominal, root["baseline"], old["outcomes"], "exact_frontier", old["integer_budget"],
                                              support=support, saved_e=saved, certificate_cache=cache)
                for field in old.keys() & result.keys() - {"selection_seconds", "checking_seconds"}:
                    assert result[field] == old[field], field
                assert result["nominal_certificate_pin"] == old["certificates"]["final_nominal"]
                assert result["detection_phase_cost"] == result["added_cost"]
                observed_count += 1
    assert observed_count == 420  # Historical E verification; new policies use anchors only.


def test_saved_E_replay_rejects_tampered_pins_paths_and_child_points(api, development):
    root = next(r for r in development[1] if any(p["canonical_point"]["choice"]["action"] for p in r["solver"]["budget_frontiers"]))
    problem = next(p for p in development[0] if p["problem_id"] == root["problem_id"])
    nominal, _, support, saved = contract(api, problem, root)
    altered = copy.deepcopy(root["solver"])
    altered["root"]["design_pin"] = "0" * 64
    with pytest.raises(ValueError, match="pins"):
        api[1].SavedEPolicy(nominal, support.design_signatures, altered)
    point = next(p for p in root["solver"]["budget_frontiers"] if p["canonical_point"]["choice"]["action"])
    action = point["canonical_point"]["choice"]["action"]
    child = point["canonical_point"]["choice"]["children"][0]
    altered = copy.deepcopy(root["solver"])
    changed = next(p for p in altered["budget_frontiers"] if p["budget"] == point["budget"])
    changed["canonical_point"]["choice"]["children"][0]["d"] += 1
    changed["frontier"][0] = copy.deepcopy(changed["canonical_point"])
    next(s for s in altered["states"] if s["state_id"] == changed["state_id"])["frontier"][0] = copy.deepcopy(changed["canonical_point"])
    broken = api[1].SavedEPolicy(nominal, support.design_signatures, altered)
    history = root["base_history"] + [{"query_id": action, "outcome_id": child["outcome"]}]
    remaining = point["budget"] - nominal.queries[action]["cost"]
    with pytest.raises(ValueError, match="child point"):
        broken.choose(history, remaining)
    with pytest.raises(ValueError):
        saved.choose([], 0)


def test_sequential_uses_only_remaining_original_allowance_and_same_proposal(api, development):
    nominal, _, support, saved, base = tiny_setup(api, development)
    for budget in (0, 1, 3, 6):
        for signature in (("missing", "present", "present"), ("missing", "missing", "missing")):
            result = api[1].execute_audit(nominal, base, signature, "E_then_support", budget, support=support, saved_e=saved)
            assert result["detection_phase_cost"] == 0
            assert result["sequential_transition_history"] == base["history"]
            assert result["added_cost"] <= budget
            if budget < 2:
                assert result["termination_reason"] == "no_affordable_support_action"
                assert result["added_cost"] == 0 and result["history"] == base["history"]
            else:
                assert result["support_phase_cost"] == result["added_cost"] == 2
                assert result["audit_history"] == [{"query_id": "q_nuisance", "outcome_id": signature[1]}]
                assert result["termination_reason"] == ("proposal_supported" if signature[1] == "present" else "support_unattainable")
                assert result["coverage"]["remaining_actions"] == 1  # Alias stays unqueried and unpaid.
                assert result["added_returned_bytes"] > 0  # Empty lookups are charged too.


def test_paid_detection_prefix_leaves_no_second_support_allowance(api, development):
    problem = support_only_fixture(development[0][0])
    receipt = copy.deepcopy(next(r for r in problem["record_catalog"] if r["id"] == "record_context_0"))
    receipt["id"] = "unit_context_backup"
    problem["record_catalog"].append(receipt)
    problem["worlds"][2]["retained_record_ids"].append(receipt["id"])
    problem["queries"].append({"id": "q_backup", "record_id": receipt["id"], "kind": receipt["kind"],
                                "scope": copy.deepcopy(receipt["scope"]), "cost": 1,
                                "outcomes": {"present": receipt, "missing": {"kind": "lookup_empty", "scope": copy.deepcopy(receipt["scope"])}}})
    nominal, expanded = Model(problem), api[4].ExpandedModel(problem, 2)
    h0 = [{"query_id": "q_context", "outcome_id": "missing"}]
    base = baseline(nominal, h0)
    support = api[0].SupportContract(nominal, expanded, h0, base["status"])
    old = api[3].FrontierPlanner(nominal, support.design_signatures, h0)
    assert old.solve()["status"] == "complete"
    saved = api[1].SavedEPolicy(nominal, support.design_signatures, old.export())
    for budget in (2, 3):  # Explicit tiny boundary fixture, not an extra development anchor.
        result = api[1].execute_audit(nominal, base, ("missing", "present", "present", "missing"),
                                      "E_then_support", budget, support=support, saved_e=saved)
        assert result["detection_phase_cost"] == 1
        assert result["phase_histories"]["detection"] == [{"query_id": "q_backup", "outcome_id": "missing"}]
        assert result["support_phase_cost"] == (2 if budget == 3 else 0)
        assert result["added_cost"] == (3 if budget == 3 else 1)
        assert result["termination_reason"] == ("proposal_supported" if budget == 3 else "no_affordable_support_action")
    alarm = api[1].execute_audit(nominal, base, ("missing", "missing", "missing", "present"),
                                 "E_then_support", 7, support=support, saved_e=saved)
    assert alarm["termination_reason"] == "nominal_conflict"
    assert alarm["added_query_count"] == 1 and alarm["support_phase_cost"] == 0
    assert alarm["sequential_transition_history"] is None
    # Without the nuisance-present negative world, no full cell supports the
    # original negative proposal: a pure positive cell and a mixed cell remain.
    problem["worlds"] = [problem["worlds"][0], problem["worlds"][2]]
    problem["prior"] = ["1/2", "1/2"]
    nominal, expanded = Model(problem), api[4].ExpandedModel(problem, 2)
    support = api[0].SupportContract(nominal, expanded, h0, "ruled_out")
    assessed = support.assess(h0)
    assert not assessed["attainable"] and assessed["terminal_status"] == "unresolved_pending"
    opposite = support.assess(h0 + [{"query_id": "q_backup", "outcome_id": "present"}])
    assert opposite["claim_status"] == "established" and opposite["nominal_conflict"]
    assert not opposite["supported"] and opposite["reward"] == 0


def test_development_anchors_joint_and_sequential_rewards_charges_and_alarms(api, development):
    cache = api[5].CertificateCache()
    for problem in development[0]:
        for root in (r for r in development[1] if r["problem_id"] == problem["problem_id"]):
            nominal, _, support, saved = contract(api, problem, root)
            budgets = [p * root["residual_cost"] // 100 for p in (0, 25, 50, 100)]
            planner = api[2].JointFrontierPlanner(nominal, support, root["base_history"], budgets)
            assert planner.solve()["status"] == "complete"
            points = {p["budget"]: p["canonical_point"] for p in planner.export()["budget_frontiers"]}
            for budget in sorted(set(budgets)):
                totals = {arm: [0, 0, 0] for arm in api[1].ARMS}
                for signature in root["signatures"]:
                    runs = {}
                    for arm in api[1].ARMS:
                        result = api[1].execute_audit(nominal, root["baseline"], signature, arm, budget, support=support,
                                                     saved_e=saved, joint_planner=planner if arm == "joint_frontier" else None,
                                                     certificate_cache=cache)
                        runs[arm] = result
                        supported = support.assess(result["history"])["supported"]
                        alarm = result["status"] == "nominal_model_conflict"
                        totals[arm][0] += alarm
                        totals[arm][1] += supported and not alarm and tuple(signature) in nominal.signature_cells
                        totals[arm][2] += result["added_cost"]
                        assert sum(result[name + "_phase_cost"] for name in ("detection", "support", "joint")) == result["added_cost"] <= budget
                        assert sum(result[name + "_phase_query_count"] for name in ("detection", "support", "joint")) == result["added_query_count"]
                        assert sum(result[name + "_phase_returned_bytes"] for name in ("detection", "support", "joint")) == result["added_returned_bytes"]
                        if alarm:
                            assert result["first_conflict"]["added_query_index"] == result["added_query_count"]
                            assert nominal.compatible(result["history"][:-1]) and not nominal.compatible(result["history"])
                    e, sequential = runs["exact_frontier"], runs["E_then_support"]
                    assert sequential["history"][:len(e["history"])] == e["history"]
                    assert sequential["detection_phase_cost"] == e["added_cost"]
                    if e["first_conflict"]:
                        assert sequential["history"] == e["history"] and sequential["support_phase_cost"] == 0
                assert totals["joint_frontier"] == [points[budget][key] for key in ("d", "w", "l")]
                assert totals["E_then_support"][0] == totals["exact_frontier"][0] == totals["joint_frontier"][0]


def test_prospective_interfaces_only_accept_paid_history_and_declared_hypotheses(api, development):
    assert set(inspect.signature(api[1].SavedEPolicy.choose).parameters) == {"self", "history", "remaining_budget"}
    assert set(inspect.signature(api[0].SupportContract).parameters) == {"nominal", "expanded2", "base_history", "proposal"}
    nominal, _, support, saved, base = tiny_setup(api, development)
    for arm in ("exact_frontier", "E_then_support"):
        forward = {s: api[1].execute_audit(nominal, base, s, arm, 2, support=support, saved_e=saved)
                   for s in (("missing", "missing", "missing"), ("missing", "present", "present"))}
        for signature in reversed(forward):
            repeated = api[1].execute_audit(nominal, base, signature, arm, 2, support=support, saved_e=saved)
            assert repeated["history"] == forward[signature]["history"]
        assert {r["audit_history"][0]["query_id"] for r in forward.values() if r["audit_history"]} <= {"q_nuisance"}


def test_runtime_rejects_invalid_budgets_bindings_certificates_and_capped_planner(api, development):
    nominal, _, support, saved, base = tiny_setup(api, development)
    signature = ("missing", "present", "present")
    for budget in (True, -1, 7):
        with pytest.raises(ValueError, match="allowance"):
            api[1].execute_audit(nominal, base, signature, "exact_frontier", budget, support=support, saved_e=saved)
    changed = copy.deepcopy(base)
    changed["certificate"] = "0" * 64
    with pytest.raises(ValueError, match="certificate"):
        api[1].execute_audit(nominal, changed, signature, "exact_frontier", 0, support=support, saved_e=saved)
    planner = api[2].JointFrontierPlanner(nominal, support, base["history"], [6], state_cap=1)
    assert planner.solve()["status"] == "unavailable"
    with pytest.raises(ValueError, match="unavailable"):
        api[1].execute_audit(nominal, base, signature, "joint_frontier", 6, support=support, saved_e=saved, joint_planner=planner)
