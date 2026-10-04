"""Planner boundary guards and physical aliases; no evaluation inputs are loaded."""
import copy
import importlib
import sys
from pathlib import Path

import pytest


def frontier_module():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        return importlib.import_module("studies.exact_audit_frontier.frontier")
    finally:
        sys.path.pop(0)


class ObservationTable:
    def __init__(self, aliases=False):
        self.queries = {
            "a": {"cost": 1, "record_id": "first", "outcomes": {"0": {}, "1": {}}},
            "b": {"cost": 2, "record_id": "first" if aliases else "second",
                  "outcomes": {"0": {}, "1": {}}},
        }
        self.rows = (("1", "1"),) if aliases else (("0", "0"), ("1", "1"))
        self.signature_cells = {row: 1 << index for index, row in enumerate(self.rows)}
        self.model_pin = frontier_module().pin({"queries": self.queries, "rows": self.rows})

    def compatible(self, history):
        positions = {qid: position for position, qid in enumerate(self.queries)}
        return sum(1 << index for index, row in enumerate(self.rows)
                   if all(row[positions[item["query_id"]]] == item["outcome_id"] for item in history))

    def partition(self, state, qid):
        position = tuple(self.queries).index(qid)
        return {outcome: sum(1 << index for index, row in enumerate(self.rows)
                             if state & (1 << index) and row[position] == outcome)
                for outcome in ("0", "1")}


DESIGN = (("0", "0"), ("0", "1"), ("1", "0"), ("1", "1"))


def test_physical_alias_consistency_is_required_before_planning():
    nominal = ObservationTable(aliases=True)
    with pytest.raises(ValueError, match="aliases"):
        frontier_module().FrontierPlanner(nominal, DESIGN, [])


def test_separately_priced_aliases_remain_actions_without_independent_evidence():
    nominal = ObservationTable(aliases=True)
    planner = frontier_module().FrontierPlanner(nominal, [("0", "0"), ("1", "1")], [])
    result = planner.solve()
    root = result["budget_frontiers"][3]
    assert [(p["d"], p["l"]) for p in root["frontier"]] == [(1, 2), (0, 0)]
    root_state = next(state for state in result["states"] if state["state_id"] == root["state_id"])
    assert [(a["query_id"], a["cost"]) for a in root_state["actions"]] == [("a", 1), ("b", 2)]
    assert planner.choose([], 3) == "a"
    # A paid authentic positive predicts the alias; it does not acquire it.
    assert planner.choose([{"query_id": "a", "outcome_id": "1"}], 2) is None
    assert root_state["remaining_actions"] == ["a", "b"]


@pytest.mark.parametrize("design, message", [
    ([], "envelope empty"),
    ([("0", "0")], "omits nominal"),
    ([("0",)], "lacks"),
    ([("0", "unlisted")], "undeclared outcome"),
])
def test_invalid_design_contract_fails_closed(design, message):
    with pytest.raises(ValueError, match=message):
        frontier_module().FrontierPlanner(ObservationTable(), design, [])


@pytest.mark.parametrize("history, message", [
    ([{"query_id": "a"}], "malformed"),
    ([{"query_id": "a", "outcome_id": "0"}] * 2, "more than once"),
    ([{"query_id": "absent", "outcome_id": "0"}], "undeclared"),
    ([{"query_id": "a", "outcome_id": "invalid"}], "undeclared"),
    ([{"query_id": "a", "outcome_id": "0"}, {"query_id": "b", "outcome_id": "1"}],
     "already contradicts"),
])
def test_invalid_preserved_history_is_rejected(history, message):
    with pytest.raises(ValueError, match=message):
        frontier_module().FrontierPlanner(ObservationTable(), DESIGN, history)


@pytest.mark.parametrize("kwargs", [
    {"state_cap": 100001}, {"combination_cap": 10000001},
    {"state_cap": True}, {"combination_cap": 0},
])
def test_frozen_caps_cannot_be_increased_or_malformed(kwargs):
    with pytest.raises(ValueError, match="cap must"):
        frontier_module().FrontierPlanner(ObservationTable(), DESIGN, [], **kwargs)


def test_construction_copies_the_preserved_root_and_export_cannot_mutate_solver():
    history = [{"query_id": "a", "outcome_id": "0"}]
    planner = frontier_module().FrontierPlanner(ObservationTable(), DESIGN, history)
    history[0]["outcome_id"] = "1"
    assert planner.base_history == [{"query_id": "a", "outcome_id": "0"}]
    result = planner.solve()
    expected = copy.deepcopy(result["budget_frontiers"])
    result["budget_frontiers"][-1]["canonical_point"]["d"] = 99
    result["root"]["base_history"].clear()
    assert planner.export()["budget_frontiers"] == expected
    assert len(planner.base_history) == 1


@pytest.mark.parametrize("remaining", [-1, True, 0.5, 4])
def test_invalid_remaining_budget_cannot_start_an_unplanned_cell(remaining):
    planner = frontier_module().FrontierPlanner(ObservationTable(), DESIGN, [])
    planner.solve()
    with pytest.raises(ValueError, match="remaining budget"):
        planner.choose([], remaining)


def test_execution_must_extend_the_bound_root_and_complete_the_solver_first(monkeypatch):
    history = [{"query_id": "a", "outcome_id": "0"}]
    planner = frontier_module().FrontierPlanner(ObservationTable(), DESIGN, history)
    with pytest.raises(ValueError, match="not completely solved"):
        planner.choose(history, 2)
    planner.solve()
    with pytest.raises(ValueError, match="does not extend"):
        planner.choose([], 2)
    with pytest.raises(ValueError, match="more than once"):
        planner.choose(history + history, 0)
    with pytest.raises(ValueError, match="remaining budget"):
        planner.choose(history + [{"query_id": "b", "outcome_id": "0"}], 1)

    def no_new_planning(*args):
        raise AssertionError("execution attempted fresh optimization")

    monkeypatch.setattr(planner, "_solve", no_new_planning)
    before = planner.resource_snapshot()
    assert planner.choose(history, 2) == "b"
    assert planner.choose(history + [{"query_id": "b", "outcome_id": "0"}], 0) is None
    after = planner.resource_snapshot()
    assert before["solver_states"] == after["solver_states"]
    assert before["child_combinations"] == after["child_combinations"]


def test_empty_design_compatibility_is_not_an_alarm_in_a_different_envelope():
    nominal = ObservationTable()
    planner = frontier_module().FrontierPlanner(nominal, nominal.rows, [])
    planner.solve()
    with pytest.raises(ValueError, match="empty fixed k=2"):
        planner.choose([{"query_id": "a", "outcome_id": "0"},
                        {"query_id": "b", "outcome_id": "1"}], 0)
