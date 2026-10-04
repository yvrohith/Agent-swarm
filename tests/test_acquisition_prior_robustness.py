"""Offline prior checks on saved development inputs and existing tiny test fixtures."""

import copy
import importlib.util
import json
import runpy
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from tracebench.evidence_acquisition.model import Model
from tracebench.evidence_acquisition.policies import POLICIES, ChargedLookup, Planner, run_policy

ROOT = Path(__file__).resolve().parents[1]
EXISTING = runpy.run_path(str(ROOT / "tests/test_acquisition_policies.py"))
TinyModel = EXISTING["TinyModel"]
exhaustive_tree_expected_cost = EXISTING["exhaustive_tree_expected_cost"]
full_history = EXISTING["full_history"]
PRIOR_NAMES = {"q0", "qS", "qT", "qMinus", "qPlus"}


@pytest.fixture(scope="module")
def sensitivity():
    path = ROOT / "studies/acquisition_prior_robustness/sensitivity.py"
    spec = importlib.util.spec_from_file_location("prior_sensitivity_tested", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def development():
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    assert all(p["split"] == "development" for p in problems)
    return [Model(problem) for problem in problems]


@pytest.mark.parametrize("index", range(4))
def test_five_positive_exact_distributions_and_signature_class_masses(sensitivity, development, index):
    model = development[index]
    distributions = sensitivity.deployment_priors(model)
    assert set(distributions) == PRIOR_NAMES
    assert distributions["q0"] == model.priors
    for name, weights in distributions.items():
        assert len(weights) == len(model.worlds)
        assert all(isinstance(p, Fraction) and p > 0 for p in weights)
        assert sum(weights) == 1
        masses = sensitivity.signature_masses(model, weights)
        expected = {sig: sum((weights[i] for i, answer in enumerate(model.answers) if answer == sig),
                             Fraction()) for sig in model.signature_cells}
        assert masses == expected
        assert sum(masses.values()) == 1
        if name == "qS":
            assert set(masses.values()) == {Fraction(1, len(masses))}
    classes = set(model.tau)
    for label in classes:
        assert sum(distributions["qT"][i] for i, value in enumerate(model.tau) if value == label) == Fraction(1, len(classes))
    # Independently count retained records from each world's declared archive,
    # including two catalogue actions aimed at the same physical record twice.
    counts = [sum(q["record_id"] in w["retained_record_ids"] for q in model.queries.values())
              for w in model.worlds]
    for name, direction in (("qMinus", -1), ("qPlus", 1)):
        unnormalized = [p * Fraction(2) ** (direction * b)
                        for p, b in zip(model.priors, counts, strict=True)]
        denominator = sum(unnormalized)
        assert distributions[name] == tuple(p / denominator for p in unnormalized)


def test_presence_uses_typed_payload_not_truthy_outcome_or_empty_wrapper_bytes(sensitivity, development):
    kinds = set()
    for model in development:
        for query in model.queries.values():
            empty, present = query["outcomes"]["missing"], query["outcomes"]["present"]
            assert empty and json.dumps(empty)  # Nonempty wrapper is nevertheless empty evidence.
            assert not sensitivity.record_presence(empty)
            assert sensitivity.record_presence(present)
            kinds.add(present["kind"])
    assert "completeness" in kinds
    assert {"context_receipt", "archive_record"} <= kinds
    with pytest.raises(ValueError):
        sensitivity.record_presence({"kind": "invented_record", "id": "x", "authenticated": True})
    with pytest.raises(ValueError):
        sensitivity.record_presence({"kind": "completeness", "id": "x", "authenticated": False})


@pytest.mark.parametrize("index", range(4))
def test_prior_changes_preserve_world_support_and_history_status(sensitivity, development, index):
    original = development[index]
    snapshot = copy.deepcopy(original.problem)
    histories = [[]]
    for sig in original.signature_cells:
        full = full_history(original, sig)
        histories.extend([full, full[:1], full[::2]])
    for weights in sensitivity.deployment_priors(original).values():
        changed = sensitivity.with_prior(original, weights)
        assert changed.priors == weights
        assert changed.worlds == original.worlds
        assert changed.queries == original.queries
        assert changed.answers == original.answers
        assert changed.signature_cells == original.signature_cells
        assert changed.claim_values == original.claim_values
        assert changed.tau == original.tau
        assert {k: v for k, v in changed.problem.items() if k != "prior"} == {
            k: v for k, v in original.problem.items() if k != "prior"}
        for history in histories:
            state = original.compatible(history)
            assert changed.compatible(history) == state
            assert changed.terminal(state) == original.terminal(state)
            cert = changed.certificate(history)
            assert cert["status"] == original.certificate(history)["status"]
            assert changed.verify_certificate(cert)
    assert original.problem == snapshot


def test_coincident_distributions_keep_their_predeclared_names(sensitivity, development):
    model = development[0]
    balanced = sensitivity.with_prior(model, sensitivity.deployment_priors(model)["qS"])
    distributions = sensitivity.deployment_priors(balanced)
    assert set(distributions) == PRIOR_NAMES
    assert distributions["q0"] == distributions["qS"]


@pytest.mark.parametrize("fixture", [
    # Complementary XOR information, with a strictly nonuniform prior.
    TinyModel([(0, 0), (0, 1), (1, 0), (1, 1)], [False, True, True, False], [1, 2],
              [Fraction(1, 10), Fraction(2, 10), Fraction(3, 10), Fraction(4, 10)]),
    # The third answer is correlated with the first; the full tree enumerator
    # independently explores redundant orders rather than sharing the DP cache.
    TinyModel([(0, 0, 0), (0, 1, 0), (1, 0, 1), (1, 1, 1)],
              [False, True, True, False], [1, 2, 4],
              [Fraction(1, 10), Fraction(4, 10), Fraction(2, 10), Fraction(3, 10)]),
    TinyModel([(0, 0), (0, 1)], [False, True], [1, 2],
              [Fraction(9, 10), Fraction(1, 10)]),
    TinyModel([(0,), (0,)], [False, True], [4],
              [Fraction(2, 3), Fraction(1, 3)]),
    # A mixed signature coexists with two signatures resolving opposite claims.
    TinyModel([(0, 0), (0, 0), (1, 0), (1, 1)], [False, True, True, False], [2, 1],
              [Fraction(1, 10), Fraction(2, 10), Fraction(3, 10), Fraction(4, 10)]),
])
def test_nonuniform_matched_exact_dp_matches_existing_complete_tree_enumerator(sensitivity, fixture):
    planner = sensitivity.CappedPlanner(fixture, "exact_optimal", state_cap=100000)
    expected = exhaustive_tree_expected_cost(fixture)
    assert planner.optimal_value() == expected
    assert isinstance(expected, Fraction)
    assert expected == Planner(fixture, "exact_optimal").optimal_value()


def test_exact_cap_raises_instead_of_reporting_a_capped_value_optimal(sensitivity):
    model = EXISTING["xor_model"]()
    planner = sensitivity.CappedPlanner(model, "exact_optimal", state_cap=1)
    with pytest.raises(sensitivity.ExactStateCap):
        planner.optimal_value()


def _p0_paths(model, policy):
    planner = Planner(model, policy)
    return [{"signature_index": i,
             **run_policy(model, policy, ChargedLookup(model, sig), planner=planner)}
            for i, sig in enumerate(sorted(model.signature_cells))]


@pytest.mark.parametrize("policy", POLICIES)
def test_reweighted_p0_paths_match_direct_development_execution_without_replanning(
        sensitivity, development, monkeypatch, policy):
    model = development[0]
    original = copy.deepcopy(model.problem)
    paths = _p0_paths(model, policy)
    distributions = sensitivity.deployment_priors(model)

    def forbidden(*args, **kwargs):
        raise AssertionError("Frozen-path reweighting must not instantiate a q planner/model")

    monkeypatch.setattr(sensitivity, "with_prior", forbidden)
    monkeypatch.setattr(sensitivity, "CappedPlanner", forbidden)
    for weights in distributions.values():
        measured = sensitivity.summarize_trajectories(model, weights, paths)["expected"]
        # Directly run the unchanged p0 policy in each development world, not a
        # representative world's mass; only the outer workload weighting uses q.
        expected = {metric: Fraction() for metric in
                    ("cost", "query_count", "returned_bytes", "established", "ruled_out", "archive_irreducible")}
        for weight, signature in zip(weights, model.answers, strict=True):
            direct = run_policy(model, policy, ChargedLookup(model, signature))
            assert direct["certificate_valid"]
            for metric in ("cost", "query_count", "returned_bytes"):
                expected[metric] += weight * direct[metric]
            expected[direct["status"]] += weight
        assert {metric: Fraction(value["exact"]) for metric, value in measured.items()} == expected
    assert model.problem == original
    assert model.priors == distributions["q0"]


def test_saved_path_validation_and_reweighting_fail_closed_on_lost_signature_mass(sensitivity, development):
    model = development[0]
    paths = _p0_paths(model, "schema_aware")
    with pytest.raises(ValueError, match="incomplete"):
        sensitivity.summarize_trajectories(model, model.priors, paths[:-1])
    duplicate = [*paths[:-1], paths[0]]
    with pytest.raises(ValueError, match="duplicate or missing"):
        sensitivity.summarize_trajectories(model, model.priors, duplicate)
    invalid = copy.deepcopy(paths)
    invalid[0]["certificate_valid"] = False
    with pytest.raises(ValueError, match="invalid full-budget"):
        sensitivity.summarize_trajectories(model, model.priors, invalid)
    weights = list(model.priors)
    weights[-1] += weights[0]
    weights[0] = Fraction()
    with pytest.raises(ValueError, match="original positive support"):
        sensitivity.with_prior(model, weights)


def test_nonuniform_matched_optimum_is_no_worse_than_any_feasible_development_policy(
        sensitivity, development):
    original = development[1]
    weights = sensitivity.deployment_priors(original)["qMinus"]
    model = sensitivity.with_prior(original, weights)
    optimum = sensitivity.CappedPlanner(model, "exact_optimal").optimal_value()
    for policy in POLICIES:
        paths = _p0_paths(model, policy)  # Here model deliberately carries the matched q.
        expected = sensitivity.summarize_trajectories(model, weights, paths)["expected"]
        value = Fraction(expected["cost"]["exact"])
        assert value >= optimum
        if policy == "exact_optimal":
            assert value == optimum


def test_capped_comparison_retains_unavailable_optimum_and_saved_primary_rows(sensitivity, development):
    model = development[0]
    runs, certificates = [], {}
    signatures = sorted(model.signature_cells)
    for policy in POLICIES:
        for row in _p0_paths(model, policy):
            certificate_id = sensitivity.pin(row["certificate"])
            certificates[certificate_id] = row["certificate"]
            runs.append({**row, "certificate": certificate_id,
                         "problem_id": model.problem["problem_id"], "budget_percent": 100,
                         "prior_mass": str(model.mass(model.signature_cells[signatures[row["signature_index"]]]))})
    result = sensitivity.evaluate_problem(model.problem, runs, certificates, state_cap=1)
    assert len(result["rows"]) == 50
    frozen = [r for r in result["rows"] if r["planning_mode"] == "frozen_p0"]
    assert len(frozen) == 25 and all(r["availability"] == "complete" for r in frozen)
    exact = [r for r in result["rows"]
             if r["planning_mode"] == "matched_q" and r["policy"] == "exact_optimal"]
    assert len(exact) == 5
    assert all(r["availability"] == "unavailable" and r["expected"] is None for r in exact)
    assert all(r["optimum_ratio"] is None and r["zero_optimum"] is None for r in result["rows"])
    assert len(result["failures"]) == 5
    assert all(f["kind"] == "exact_state_cap" and f["admitted_states"] == 1 for f in result["failures"])
    assert all(b["verified"] is None and b["matched_optimum"] is None for b in result["bound_checks"])
