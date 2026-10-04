"""Small independent finite fixtures, never evaluation-seed policy runs."""

import copy
import json
from fractions import Fraction
from itertools import product

import pytest

from tracebench.evidence_acquisition.policies import (
    POLICIES,
    ChargedLookup,
    Planner,
    budget_for,
    hindsight_minimum,
    run_policy,
    schema_order,
)


class TinyModel:
    """A test-only explicit truth table, independent of the study generator."""

    def __init__(self, answers, claims, costs, priors=None, kinds=None):
        self.answers = tuple(tuple(str(x) for x in row) for row in answers)
        self.claims = tuple(claims)
        self.full_state = (1 << len(claims)) - 1
        self.priors = tuple(priors or [Fraction(1, len(claims))] * len(claims))
        self.problem = {
            "claim": {"source_ids": ["s"], "recipient": "r", "window": [0, 10]}
        }
        self.queries = {
            f"q{i}": {
                "cost": cost,
                "kind": kinds[i] if kinds else "context_receipt",
                "scope": {"source_id": "s", "recipient": "r", "window": [0, 10]},
                "outcomes": {
                    outcome: {"kind": "retained" if outcome == "1" else "missing", "q": i}
                    for outcome in sorted({row[i] for row in self.answers})
                },
            }
            for i, cost in enumerate(costs)
        }
        self.signature_cells = {}
        for i, signature in enumerate(self.answers):
            self.signature_cells[signature] = self.signature_cells.get(signature, 0) | (1 << i)
        self.tau = tuple(self._label(self.signature_cells[row]) for row in self.answers)

    def _label(self, state):
        labels = {self.claims[i] for i in range(len(self.claims)) if state & (1 << i)}
        if labels == {True}:
            return "established"
        if labels == {False}:
            return "ruled_out"
        return "archive_irreducible"

    def mass(self, state):
        return sum(
            (p for i, p in enumerate(self.priors) if state & (1 << i)), Fraction()
        )

    def partition(self, state, query_id):
        column = tuple(self.queries).index(query_id)
        result = {}
        for i, row in enumerate(self.answers):
            if state & (1 << i):
                result[row[column]] = result.get(row[column], 0) | (1 << i)
        return result

    def compatible(self, history):
        state = self.full_state
        for row in history:
            state = self.partition(state, row["query_id"]).get(row["outcome_id"], 0)
        return state

    def terminal(self, state):
        if not state:
            return "inconsistent"
        possible = {self.tau[i] for i in range(len(self.claims)) if state & (1 << i)}
        return next(iter(possible)) if len(possible) == 1 else None

    def certificate(self, history, status=None):
        actual = self.terminal(self.compatible(history)) or "unresolved_pending"
        if status is not None and status != actual:
            raise ValueError("wrong requested certificate")
        return {"history": copy.deepcopy(history), "status": actual}

    def verify_certificate(self, certificate):
        return certificate == self.certificate(certificate["history"])


def xor_model(costs=(1, 1)):
    return TinyModel([(0, 0), (0, 1), (1, 0), (1, 1)], [False, True, True, False], costs)


def full_history(model, signature):
    return [
        {"query_id": q, "outcome_id": outcome}
        for q, outcome in zip(model.queries, signature, strict=True)
    ]


def exhaustive_tree_expected_cost(model):
    """Enumerate all complete decision-tree cost vectors, without the DP cache."""
    # Derive terminal classes directly from the truth table, not model.terminal.
    classes = []
    for row in model.answers:
        labels = {c for r, c in zip(model.answers, model.claims, strict=True) if r == row}
        classes.append(tuple(sorted(labels)))

    def trees(indices, columns):
        if len({classes[i] for i in indices}) == 1:
            return [{i: 0 for i in indices}]
        results = []
        for column in columns:
            partitions = {}
            for i in indices:
                partitions.setdefault(model.answers[i][column], []).append(i)
            children = [
                trees(child, [c for c in columns if c != column])
                for child in partitions.values()
            ]
            for branches in product(*children):
                results.append({
                    i: model.queries[f"q{column}"]["cost"] + cost
                    for branch in branches for i, cost in branch.items()
                })
        return results

    costs = trees(list(range(len(model.claims))), list(range(len(model.queries))))
    return min(sum(model.priors[i] * cost for i, cost in tree.items()) for tree in costs)


@pytest.mark.parametrize("fixture", [
    TinyModel([(0, 0, 0), (0, 1, 0), (1, 0, 1), (1, 1, 1)],
              [False, True, True, False], [1, 2, 4]),
    TinyModel([(0, 0, 0), (0, 0, 0), (1, 0, 1), (1, 1, 1)],
              [False, True, True, False], [2, 1, 4]),
])
def test_exact_dp_matches_independent_enumeration_of_complete_trees(fixture):
    planner = Planner(fixture, "exact_optimal")
    assert planner.optimal_value() == exhaustive_tree_expected_cost(fixture)
    assert isinstance(planner.optimal_value(), Fraction)
    states = planner.solver_states
    planner.optimal_value()
    assert planner.solver_states == states


@pytest.mark.parametrize("policy", POLICIES)
def test_complementary_queries_are_not_mistaken_for_no_progress(policy):
    model = xor_model()
    assert all(model.terminal(s) is None for s in model.partition(model.full_state, "q0").values())
    lookup = ChargedLookup(model, ("0", "1"))
    result = run_policy(model, policy, lookup)
    assert result["status"] == "established"
    assert result["certificate_valid"]
    assert result["query_count"] == 2
    assert lookup.history == result["history"]
    assert result["cost"] == lookup.cost == 2


def test_entropy_can_choose_an_irrelevant_observation_without_settling_claim():
    model = TinyModel(
        [(i % 2, int(i < 2)) for i in range(8)],
        [i < 2 for i in range(8)], [1, 1],
        kinds=["archive_record", "context_receipt"],
    )
    planner = Planner(model, "world_entropy")
    assert planner.entropy_gain(model.full_state, "q0") == 1.0
    assert planner.choose([]) == "q0"
    history = [{"query_id": "q0", "outcome_id": "0"}]
    assert model.terminal(model.compatible(history)) is None
    assert Planner(model, "schema_aware").choose([]) == "q1"
    assert Planner(model, "exact_optimal").choose([]) == "q1"
    assert run_policy(model, "world_entropy", ChargedLookup(model, ("0", "1")))["cost"] == 2


def test_pair_cut_uses_original_masses_and_full_archive_answer_classes():
    model = TinyModel([(0, 0), (0, 0), (1, 0), (1, 1)],
                      [False, True, True, False], [1, 2])
    planner = Planner(model, "pair_cut")
    state = model.compatible([{"query_id": "q1", "outcome_id": "0"}])
    # Two worlds share the mixed-signature class and one is established.
    assert planner.edge_mass(state) == Fraction(1, 8)
    assert planner.pair_gain(state, "q0") == Fraction(1, 8)
    assert planner.edge_mass(model.full_state) == Fraction(5, 16)


def test_priors_change_expected_cost_never_logical_compatibility():
    answers, claims, costs = [(1, 0), (0, 1), (0, 0)], [True, False, False], [2, 1]
    high = TinyModel(answers, claims, costs, [Fraction(1, 20), Fraction(9, 10), Fraction(1, 20)])
    low = TinyModel(answers, claims, costs, [Fraction(9, 20), Fraction(1, 10), Fraction(9, 20)])
    assert Planner(high, "exact_optimal").choose([]) == "q1"
    assert Planner(low, "exact_optimal").choose([]) == "q0"
    assert Planner(high, "exact_optimal").optimal_value() == Fraction(6, 5)
    assert Planner(low, "exact_optimal").optimal_value() == 2
    for signature in high.signature_cells:
        for count in range(3):
            history = full_history(high, signature)[:count]
            assert high.compatible(history) == low.compatible(history)
            assert high.certificate(history) == low.certificate(history)


@pytest.mark.parametrize("policy", POLICIES)
def test_same_observed_history_has_same_action_for_distinct_realized_archives(policy):
    model = xor_model()
    lookups = [ChargedLookup(model, signature) for signature in [("0", "0"), ("0", "1")]]
    histories = []
    for lookup in lookups:
        result = lookup("q0")
        histories.append([{key: result[key] for key in ("query_id", "outcome_id")}])
    assert histories[0] == histories[1]
    assert Planner(model, policy).choose(histories[0]) == Planner(model, policy).choose(histories[1])


def test_unaffordable_next_action_stops_without_budget_specific_substitution():
    model = xor_model((4, 1))
    lookup = ChargedLookup(model, ("0", "1"))
    result = run_policy(model, "read_all", lookup, budget=3)
    assert result["status"] == "budget_exhausted_unresolved"
    assert result["next_query"] == "q0"
    assert result["history"] == lookup.history == []
    assert result["cost"] == 0
    assert result["certificate"]["status"] == "unresolved_pending"
    assert [budget_for(model, p) for p in (0, 25, 50, 75, 100)] == [0, 1, 2, 3, 5]


def test_read_all_exhaustive_even_when_an_initial_certificate_exists():
    model = TinyModel([(0, 0), (1, 1)], [True, True], [1, 2])
    full = run_policy(model, "read_all", ChargedLookup(model, ("0", "0")))
    zero = run_policy(model, "read_all", ChargedLookup(model, ("0", "0")), budget=0)
    assert full["query_count"] == 2 and full["cost"] == 3
    assert zero["query_count"] == 0 and zero["status"] == "established"
    for policy in POLICIES[1:]:
        result = run_policy(model, policy, ChargedLookup(model, ("0", "0")))
        assert result["query_count"] == 0 and result["status"] == "established"


def test_read_all_budget_stop_keeps_an_available_certificate():
    model = TinyModel([(0, 0), (1, 1)], [False, True], [1, 4])
    result = run_policy(model, "read_all", ChargedLookup(model, ("1", "1")), budget=1)
    assert result["status"] == "established"
    assert result["stop_reason"] == "next_query_exceeds_budget"
    assert result["query_count"] == 1


def test_hindsight_global_minimum_not_inclusion_minimal_expensive_certificate():
    model = TinyModel([(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 1)],
                      [False, False, False, True], [1, 1, 4])
    history = full_history(model, ("1", "1", "1"))
    expensive = [history[2]]
    assert model.certificate(expensive)["status"] == "established"
    assert model.terminal(model.full_state) is None
    minimum = hindsight_minimum(model, history)
    assert minimum["cost"] == 2
    assert minimum["query_count"] == 2
    assert [row["query_id"] for row in minimum["history"]] == ["q0", "q1"]
    assert minimum["certificate_valid"]


def test_constant_queries_skipped_by_exact_policy_and_no_retrieval_when_irreducible():
    model = TinyModel([(0, 0), (0, 1)], [False, True], [1, 2])
    planner = Planner(model, "exact_optimal")
    assert planner.choose([]) == "q1"
    assert planner.optimal_value() == 2
    ambiguous = TinyModel([(0,), (0,)], [False, True], [4])
    result = run_policy(ambiguous, "pair_cut", ChargedLookup(ambiguous, ("0",)))
    assert result["status"] == "archive_irreducible"
    assert result["cost"] == 0


def test_charged_lookup_records_payload_bytes_and_rejects_repeat_or_forged_results():
    model = xor_model()
    lookup = ChargedLookup(model, ("0", "1"))
    result = lookup("q0")
    expected = len(json.dumps(result["observable"], sort_keys=True,
                              separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    assert result["canonical_bytes"] == lookup.bytes_returned == expected
    assert lookup.cost == result["cost"] == 1
    with pytest.raises(ValueError, match="repeat"):
        lookup("q0")
    untouched = ChargedLookup(model, ("0", "1"))

    def forged(query_id):
        value = untouched(query_id)
        value["observable"] = {"invented": True}
        return value

    with pytest.raises(ValueError, match="accounting or observable"):
        run_policy(model, "schema_aware", forged)


def test_fixed_order_uses_visible_scope_kind_cost_then_id():
    model = TinyModel([(0,) * 5, (1,) * 5], [False, True], [1, 4, 2, 1, 1],
                      kinds=["archive_record", "context_receipt", "completeness",
                             "delivery_receipt", "context_receipt"])
    model.queries["q4"]["scope"]["recipient"] = "another_run"
    assert schema_order(model) == ("q2", "q1", "q3", "q0", "q4")


def test_narrow_receipt_is_relevant_but_incomplete_scope_cannot_assure_absence():
    model = TinyModel([(0, 0, 0), (1, 1, 1)], [False, True], [2, 1, 1],
                      kinds=["context_receipt", "completeness", "context_receipt"])
    model.queries["q0"]["scope"]["window"] = [2, 3]
    model.queries["q1"]["scope"]["window"] = [2, 3]
    model.queries["q2"]["scope"]["window"] = [10, 12]
    assert schema_order(model) == ("q0", "q1", "q2")


def test_ties_use_cost_then_id_and_shared_cache_reports_deltas():
    model = TinyModel([(0, 0), (1, 1)], [False, True], [1, 1])
    for policy in ("pair_cut", "world_entropy", "exact_optimal"):
        planner = Planner(model, policy)
        first = run_policy(model, policy, ChargedLookup(model, ("0", "0")), planner=planner)
        second = run_policy(model, policy, ChargedLookup(model, ("1", "1")), planner=planner)
        assert first["history"][0]["query_id"] == second["history"][0]["query_id"] == "q0"
        assert second["solver_states"] == 0
        assert first["planning_seconds"] >= 0 and second["planning_seconds"] >= 0


def test_planner_rejects_duplicate_history_and_hindsight_incomplete_archive():
    model = xor_model()
    row = {"query_id": "q0", "outcome_id": "0"}
    with pytest.raises(ValueError, match="duplicate query"):
        Planner(model, "pair_cut").choose([row, row])
    with pytest.raises(ValueError, match="exactly one"):
        hindsight_minimum(model, [row])
