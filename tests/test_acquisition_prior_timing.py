"""Timing-workload checks use only the four previously frozen development inputs."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from studies.acquisition_prior_robustness.sensitivity import CappedPlanner
from studies.acquisition_prior_robustness.timing import (
    PHASES,
    measure_construction,
    model_state_pin,
    run_timing,
)
from tracebench.evidence_acquisition.model import Model
from tracebench.evidence_acquisition.policies import POLICIES, ChargedLookup, Planner, run_policy

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT = json.loads(
    (ROOT / "studies/evidence_acquisition/development_problems.json").read_text()
)


@pytest.mark.parametrize("policy", POLICIES)
def test_complete_tree_has_same_histories_as_all_saved_model_signature_paths(policy):
    model = Model(DEVELOPMENT[3])
    expected = set()
    expected_leaves = set()
    planner = Planner(model, policy)
    for signature in model.signature_cells:
        result = run_policy(model, policy, ChargedLookup(model, signature), planner=planner)
        history = tuple((row["query_id"], row["outcome_id"]) for row in result["history"])
        expected_leaves.add(history)
        for count in range(len(history) + 1):
            expected.add(history[:count])
    before = model_state_pin(model)
    measured = measure_construction(model, policy)
    assert measured["status"] == "completed"
    assert measured["visited_histories"] == measured["choose_calls"] == len(expected)
    assert measured["terminal_histories"] == measured["certificate_count"] == len(expected_leaves)
    assert measured["decision_count"] == len(expected) - len(expected_leaves)
    assert measured["certificate_failures"] == 0
    assert model_state_pin(model) == before
    assert measured["shared_model_unchanged"]
    if policy == "read_all":
        assert all(len(history) == len(model.queries) for history in expected_leaves)


def test_three_repetitions_have_new_caches_identical_model_and_deterministic_workload():
    planners = []

    def fresh(model, policy):
        planner = CappedPlanner(model, policy)
        assert not planner._values and not planner._actions and not planner._edges
        assert planner.solver_states == 0
        planners.append(planner)
        return planner

    result = run_timing([DEVELOPMENT[0]], planner_factory=fresh)
    assert len(planners) == 15
    assert len({id(p) for p in planners}) == 15
    assert len({id(p.model) for p in planners}) == 1
    assert len(result["model_preprocessing"]) == 1
    assert result["all_three_repetitions_recorded"]
    assert result["completed_repetition_workloads_agree"]
    assert [(row["repetition"], row["policy"]) for row in result["rows"]] == [
        (repeat, policy) for repeat in (1, 2, 3) for policy in POLICIES
    ]
    for row in result["rows"]:
        assert row["status"] == "completed"
        assert set(row["timing"]) == set(PHASES)
        assert all(value >= 0 for phase in row["timing"].values() for value in phase.values())
        assert row["planning_cpu_seconds"] == sum(
            row["timing"][phase]["cpu_seconds"] for phase in ("planner_setup", "planner_decisions")
        )
        assert row["serialized_workload_bytes"] > 0
    assert all(row["recorded_repetitions"] == row["completed_repetitions"] == 3
               for row in result["summary"])


def test_cap_is_retained_in_all_repetitions_and_does_not_become_an_optimal_timing():
    def tiny_cap(model, policy):
        return CappedPlanner(model, policy, state_cap=1)

    result = run_timing([DEVELOPMENT[1]], planner_factory=tiny_cap)
    exact = [row for row in result["rows"] if row["policy"] == "exact_optimal"]
    assert len(exact) == 3
    assert all(row["status"] == "capped" and row["failure"] for row in exact)
    summary = next(row for row in result["summary"]
                   if row["policy"] == "exact_optimal" and row["stratum"] == "all")
    assert summary["capped_repetitions"] == 3
    assert summary["completed_repetitions"] == 0
    assert summary["mean_planning_cpu_seconds"] is None


def test_prefilled_caches_fail_the_cold_cache_contract():
    def warm(model, policy):
        planner = CappedPlanner(model, policy)
        planner._edges[model.full_state] = Fraction(1)
        return planner

    result = measure_construction(Model(DEVELOPMENT[0]), "pair_cut", planner_factory=warm)
    assert result["status"] == "failed"
    assert "fresh planner" in result["failure"]


def test_mutated_shared_model_is_detected_even_if_stored_model_pin_is_unchanged():
    model = Model(DEVELOPMENT[2])
    original_stored_pin = model.model_pin

    def mutating(model, policy):
        model.problem["unexpected_timing_mutation"] = True
        return CappedPlanner(model, policy)

    result = measure_construction(model, "schema_aware", planner_factory=mutating)
    assert model.model_pin == original_stored_pin
    assert result["status"] == "failed"
    assert not result["shared_model_unchanged"]
    assert result["failure"] == "shared validated model was mutated"


def test_duplicate_problems_are_rejected_instead_of_extra_repetitions():
    with pytest.raises(ValueError, match="duplicate timing problem"):
        run_timing([DEVELOPMENT[0], DEVELOPMENT[0]])
