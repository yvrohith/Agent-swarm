"""Joint planner boundary tests on explicit tiny hypothetical observation tables."""
import copy
import importlib
import sys
from pathlib import Path

import pytest


def module():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        return importlib.import_module("studies.joint_audit_warrant.frontier")
    finally:
        sys.path.pop(0)


class TinyNominal:
    def __init__(self):
        self.queries = {qid: {"cost": cost, "outcomes": {"0": {}, "1": {}}}
                        for qid, cost in (("a", 1), ("b", 2))}
        self.rows = (("0", "0"), ("1", "1"))
        self.signature_cells = {row: 1 << i for i, row in enumerate(self.rows)}
        self.model_pin = module().pin({"queries": self.queries, "rows": self.rows})

    def compatible(self, history):
        positions = {qid: i for i, qid in enumerate(self.queries)}
        return sum(1 << i for i, row in enumerate(self.rows)
                   if all(row[positions[h["query_id"]]] == h["outcome_id"] for h in history))

    def partition(self, state, qid):
        position = tuple(self.queries).index(qid)
        return {outcome: sum(1 << i for i, row in enumerate(self.rows)
                             if state & (1 << i) and row[position] == outcome)
                for outcome in ("0", "1")}


class TinySupport:
    """All physical truth values are retained, including mixed signature cells."""
    def __init__(self, nominal, proposal="established"):
        self.nominal = nominal
        self.base_history = []
        self.design_signatures = (("0", "0"), ("0", "1"), ("1", "0"), ("1", "1"))
        self.truths = ({True}, {False}, {False}, {True, False})
        self.proposal = proposal
        self.physical_pin = module().pin({"truths": [sorted(v) for v in self.truths]})

    def reward(self, mask):
        if not mask:
            raise ValueError("empty physical support")
        values = set().union(*(self.truths[i] for i in range(4) if mask & (1 << i)))
        expected = {True} if self.proposal == "established" else {False}
        if self.proposal not in {"established", "ruled_out"} or values != expected:
            return 0
        return sum(bool(mask & (1 << i)) and signature in self.nominal.signature_cells
                   for i, signature in enumerate(self.design_signatures))


def planner(budgets=(0, 0, 1, 3), **kwargs):
    nominal = TinyNominal()
    return module().JointFrontierPlanner(nominal, TinySupport(nominal), [], budgets, **kwargs)


def test_coincident_anchors_are_retained_but_not_recomputed():
    actual = planner()
    result = actual.solve()
    assert result["status"] == "complete"
    assert result["root"]["requested_budgets"] == [0, 0, 1, 3]
    assert result["root"]["budgets"] == [0, 1, 3]
    assert [row["budget"] for row in result["budget_frontiers"]] == [0, 1, 3]
    assert result["resources"]["requested_anchor_count"] == 4
    assert result["resources"]["requested_budget_count"] == 3
    with pytest.raises(ValueError, match="not a requested joint anchor"):
        actual.choose([], 2)


@pytest.mark.parametrize("budgets", [[], [0, 0, 1, 2, 3], [-1], [4], [True], [0.5]])
def test_invalid_anchor_schedule_fails_closed(budgets):
    with pytest.raises(ValueError, match="anchor allowances"):
        planner(budgets)


@pytest.mark.parametrize("mismatch", ["nominal", "root", "signature_order"])
def test_physical_support_binding_cannot_shift_mask_meanings(mismatch):
    nominal = TinyNominal()
    support = TinySupport(nominal)
    if mismatch == "nominal":
        support.nominal = TinyNominal()
    elif mismatch == "root":
        support.base_history = [{"query_id": "a", "outcome_id": "0"}]
    else:
        support.design_signatures = tuple(reversed(support.design_signatures))
    with pytest.raises(ValueError, match="different|globally sorted"):
        module().JointFrontierPlanner(nominal, support, [], [0, 3])


def test_physical_contract_and_proposal_are_part_of_the_cache_scope():
    nominal = TinyNominal()
    first = TinySupport(nominal)
    changed_physical = TinySupport(nominal)
    changed_physical.physical_pin = "a-different-declared-physical-contract"
    changed_proposal = TinySupport(nominal, "ruled_out")
    results = [module().JointFrontierPlanner(nominal, support, [], [0, 3]).solve()
               for support in (first, changed_physical, changed_proposal)]
    assert len({result["root"]["scope_pin"] for result in results}) == 3
    assert len({result["budget_frontiers"][0]["state_id"] for result in results}) == 3
    assert results[0]["root"]["proposal"] == "established"
    assert results[2]["root"]["proposal"] == "ruled_out"


@pytest.mark.parametrize("kwargs", [{"state_cap": 1}, {"combination_cap": 1}])
def test_caps_withhold_every_joint_anchor_and_keep_partial_witnesses(kwargs):
    actual = planner(**kwargs)
    result = actual.solve()
    assert result["status"] == "unavailable" and not result["budget_frontiers"]
    assert result["states"] and result["resources"]["completed_budget_count_before_cap"] > 0
    assert result["resources"]["solver_states"] <= result["resources"]["state_cap"]
    assert result["resources"]["child_combinations"] <= result["resources"]["combination_cap"]
    assert actual.solve() == result  # No reset, further search, or incumbent claim.
    with pytest.raises(ValueError, match="not completely solved"):
        actual.choose([], 0)


def test_joint_execution_reads_only_completed_anchor_states(monkeypatch):
    actual = planner()
    result = actual.solve()
    root = result["budget_frontiers"][-1]
    expected = root["canonical_point"]["choice"]["action"]
    original_states = copy.deepcopy(result["states"])

    def no_solver(*args):
        raise AssertionError("execution attempted to add planning states")

    monkeypatch.setattr(actual, "_solve", no_solver)
    assert actual.choose([], 3) == expected
    assert actual.export()["states"] == original_states
    result["root"]["budgets"].clear()
    result["budget_frontiers"][-1]["canonical_point"]["w"] = 99
    assert actual.export()["root"]["budgets"] == [0, 1, 3]
    assert actual.export()["budget_frontiers"][-1]["canonical_point"]["w"] != 99


@pytest.mark.parametrize("value", [True, -1, 3])
def test_impossible_support_reward_is_a_contract_failure(value):
    nominal = TinyNominal()
    support = TinySupport(nominal)
    support.reward = lambda mask: value
    actual = module().JointFrontierPlanner(nominal, support, [], [0])
    with pytest.raises(ValueError, match="not a count"):
        actual.solve()


def test_nondefinite_original_proposals_cannot_earn_support_credit():
    nominal = TinyNominal()
    support = TinySupport(nominal, "archive_irreducible")
    support.reward = lambda mask: 1
    actual = module().JointFrontierPlanner(nominal, support, [], [0])
    with pytest.raises(ValueError, match="nondefinite"):
        actual.solve()
