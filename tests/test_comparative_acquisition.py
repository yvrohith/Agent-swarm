"""Competent nominal baselines, qualified only on tiny/development fixtures."""
import copy
import json
import math
from fractions import Fraction
from itertools import product

import pytest
from test_acquisition_policies import TinyModel, xor_model

from studies.comparative_validity import acquisition as diagnostic
from tracebench.evidence_acquisition.model import Model
from tracebench.evidence_acquisition.policies import ChargedLookup, Planner, run_policy


def explicit_mutual_information(model, state, query):
    """Direct joint tau/outcome masses, independent from entropy subtraction."""
    column = list(model.queries).index(query)
    total = model.mass(state)
    joint, classes, outcomes = {}, {}, {}
    for i, prior in enumerate(model.priors):
        if state & (1 << i):
            label, outcome = model.tau[i], model.answers[i][column]
            p = prior / total
            joint[label, outcome] = joint.get((label, outcome), Fraction()) + p
            classes[label] = classes.get(label, Fraction()) + p
            outcomes[outcome] = outcomes.get(outcome, Fraction()) + p
    return math.fsum(float(p) * math.log2(float(p / (classes[c] * outcomes[o])))
                     for (c, o), p in joint.items())


@pytest.mark.parametrize("priors", [None, [Fraction(1, 10), Fraction(1, 5), Fraction(3, 10), Fraction(2, 5)]])
def test_tau_information_matches_direct_joint_distribution(priors):
    model = TinyModel([(0, 0), (0, 0), (1, 0), (1, 1)], [False, True, False, True], [1, 2], priors)
    assert "archive_irreducible" in model.tau
    for state in (model.full_state, 3, 12):
        for query in model.queries:
            assert diagnostic.terminal_gain(model, state, query) == pytest.approx(
                explicit_mutual_information(model, state, query), abs=1e-12)


def test_terminal_class_information_ignores_nuisance_world_entropy():
    model = TinyModel(list(product((0, 1), repeat=3)),
                      [bool(x[2]) for x in product((0, 1), repeat=3)], [1, 1, 1])
    assert Planner(model, "world_entropy").choose([]) == "q0"
    assert diagnostic.ComparativePlanner(model, "terminal_class_entropy").choose([]) == "q2"


@pytest.mark.parametrize("policy", diagnostic.NEW_POLICIES)
def test_zero_gain_complementarity_continues_to_correct_certificate(policy):
    model = xor_model(costs=(2, 1))
    assert all(diagnostic.terminal_gain(model, model.full_state, q) == 0 for q in model.queries)
    for signature in sorted(model.signature_cells):
        planner = diagnostic.ComparativePlanner(model, policy)
        assert planner.choose([]) == "q1"
        result = run_policy(model, policy, ChargedLookup(model, signature), planner=planner)
        assert result["cost"] == 3
        assert result["query_count"] == 2
        assert result["status"] == model.terminal(model.signature_cells[signature])


def test_schema_skip_does_not_charge_or_insert_inferred_answers():
    model = TinyModel([(0, 0), (0, 1)], [False, True], [1, 2])
    original = run_policy(model, "schema_aware", ChargedLookup(model, ("0", "1")))
    history = []
    planner = diagnostic.ComparativePlanner(model, "schema_skip")
    assert planner.choose(history) == "q1"
    assert history == []
    lookup = ChargedLookup(model, ("0", "1"))
    result = run_policy(model, "schema_skip", lookup, planner=planner)
    assert original["cost"] == 3 and result["cost"] == 2
    assert result["history"] == lookup.history == [{"query_id": "q1", "outcome_id": "1"}]
    assert result["returned_bytes"] == lookup.bytes_returned


def test_schema_skip_uses_updated_state_not_only_initial_constants():
    model = TinyModel([(0, 0, 0), (0, 0, 1), (1, 1, 0), (1, 1, 1)],
                      [False, True, True, False], [1, 1, 2])
    planner = diagnostic.ComparativePlanner(model, "schema_skip")
    assert planner.choose([]) == "q0"
    assert planner.choose([{"query_id": "q0", "outcome_id": "0"}]) == "q2"


def test_class_gain_ties_use_fixed_tolerance_then_cost_and_id(monkeypatch):
    model = xor_model()
    planner = diagnostic.ComparativePlanner(model, "terminal_class_entropy")
    monkeypatch.setattr(diagnostic, "terminal_gain", lambda m, s, q: 0.5 + (5e-13 if q == "q1" else 0))
    assert planner.choose([]) == "q0"
    monkeypatch.setattr(diagnostic, "terminal_gain", lambda m, s, q: 0.5 + (5e-11 if q == "q1" else 0))
    assert planner.choose([]) == "q1"


@pytest.mark.parametrize("policy", diagnostic.NEW_POLICIES)
def test_initial_terminal_state_costs_zero_and_invalid_histories_rejected(policy):
    model = TinyModel([(0,), (0,)], [False, True], [1])
    result = run_policy(model, policy, ChargedLookup(model, ("0",)),
                        planner=diagnostic.ComparativePlanner(model, policy))
    assert result["status"] == "archive_irreducible" and result["cost"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        diagnostic.ComparativePlanner(model, policy).choose([
            {"query_id": "q0", "outcome_id": "0"}, {"query_id": "q0", "outcome_id": "0"}])


def test_ec2_explicit_pairs_match_original_for_irreducible_and_definite_classes():
    model = TinyModel([(0, 0), (0, 0), (1, 0), (1, 1)], [False, True, False, True], [1, 2])
    assert diagnostic.check_ec2(model, [model.full_state, 3, 12]) == 6


@pytest.fixture(scope="module")
def development():
    problems = json.loads((diagnostic.ORIGINAL / "development_problems.json").read_text())
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    assert all(p["split"] == "development" for p in problems)
    return problems


@pytest.mark.parametrize("index", range(4))
def test_development_uses_complete_positive_prior_mass_and_same_terminal_semantics(development, index):
    problem = development[index]
    unchanged = copy.deepcopy(problem)
    result = diagnostic.new_problem_results(problem)
    model = Model(problem)
    assert problem == unchanged
    assert len(result["rows"]) == 20
    assert all(row["signature_count"] == len(model.signature_cells) for row in result["rows"])
    for row in result["rows"]:
        weights = diagnostic.deployment_priors(model)[row["deployment"]]
        assert all(weight > 0 for weight in weights) and sum(weights) == 1
        paths = [p for p in result["trajectories"] if all(p[k] == row[k] for k in
                 ("deployment", "planning_mode", "policy"))]
        expected = sum((sum(weights[i] for i in diagnostic.indices(model.signature_cells[signature]))
                        * paths[index]["cost"] for index, signature in enumerate(sorted(model.signature_cells))),
                       Fraction())
        assert Fraction(row["expected"]["cost"]["exact"]) == expected
        for path in paths:
            signature = sorted(model.signature_cells)[path["signature_index"]]
            assert path["status"] == model.terminal(model.signature_cells[signature])
    assert result["ec2_pair_arithmetic_checks"] > 0


def fake_summary_inputs():
    problems = [{"problem_id": p, "stratum": "fixture", "unweighted_structure_fingerprint": g}
                for p, g in [("a", "g1"), ("b", "g1"), ("c", "g2")]]
    rows = []
    for pid, deployment, mode, policy in product(("a", "b", "c"), diagnostic.DISTRIBUTIONS,
                                                 diagnostic.MODES, diagnostic.ALL_POLICIES):
        cost = 0 if policy == "exact_optimal" else {"a": 2, "b": 4, "c": 9}[pid]
        rows.append({"problem_id": pid, "deployment": deployment, "planning_mode": mode,
                     "policy": policy, "availability": "complete",
                     "expected": {"cost": diagnostic.number(cost)}})
    return rows, problems


def test_exact_aggregation_weights_repeated_structures_without_dropping_zero_optima():
    rows, problems = fake_summary_inputs()
    result = diagnostic.summarize(rows, problems)
    for rule, expected in [("equal_problem", Fraction(5)), ("structure_balanced", Fraction(6))]:
        row = next(r for r in result["policy_summaries"] if r["policy"] == "schema_skip"
                   and r["deployment"] == "q0" and r["planning_mode"] == "frozen_p0"
                   and r["stratum"] == "all" and r["weighting"] == rule)
        assert Fraction(row["expected_cost"]["mean"]["exact"]) == expected
        assert row["zero_optimum_problems"] == ["a", "b", "c"]
        assert row["positive_optimum_ratio"] is None
    assert all(r["wins"] + r["ties"] + r["losses"] == 3 for r in result["paired_summaries"])


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "below_optimum"])
def test_summary_fails_closed_on_identity_or_optimality_defect(mutation):
    rows, problems = fake_summary_inputs()
    if mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "missing":
        rows.pop()
    else:
        rows[0]["expected"]["cost"] = diagnostic.number(-1)
    with pytest.raises(ValueError):
        diagnostic.summarize(rows, problems)


def test_json_duplicate_keys_rejected_and_output_never_overwritten(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text('{"id": 1, "id": 2}')
    with pytest.raises(ValueError, match="duplicate"):
        diagnostic.read(path)
    with pytest.raises(FileExistsError):
        diagnostic.write_new(path, {})


@pytest.fixture
def tiny_freeze(monkeypatch, tmp_path):
    (tmp_path / "source.py").write_text("frozen = True\n")
    monkeypatch.setattr(diagnostic, "ROOT", tmp_path)
    monkeypatch.setattr(diagnostic, "STUDY", tmp_path)
    monkeypatch.setattr(diagnostic, "source_dependencies", lambda: ["source.py"])
    diagnostic.create_freeze({"status": "passed", "evaluation_outcomes_observed": 0,
                               "focused_tests_passed": 1, "code_review": "tiny fixture"})
    return tmp_path


def test_freeze_is_explicit_and_cannot_be_recreated_or_repin_changed_code(tiny_freeze):
    assert diagnostic.verify_freeze() == 1
    with pytest.raises(FileExistsError):
        diagnostic.create_freeze({"status": "passed", "evaluation_outcomes_observed": 0,
                                   "focused_tests_passed": 1, "code_review": "tiny fixture"})
    (tiny_freeze / "source.py").write_text("frozen = False\n")
    with pytest.raises(ValueError, match="freeze mismatch"):
        diagnostic.verify_freeze()


def test_execution_rejects_existing_output_before_evaluation(tiny_freeze, monkeypatch):
    output = tiny_freeze / "existing"
    output.mkdir()
    monkeypatch.setattr(diagnostic, "historical_rows", lambda _: pytest.fail("evaluation reached"))
    with pytest.raises(ValueError, match="already exists"):
        diagnostic.execute(output)


def test_execution_rejects_missing_freeze_before_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, "STUDY", tmp_path)
    monkeypatch.setattr(diagnostic, "historical_rows", lambda _: pytest.fail("evaluation reached"))
    with pytest.raises(FileNotFoundError):
        diagnostic.execute(tmp_path / "unused")


def test_freeze_rejects_post_outcome_or_failed_prechecks(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, "STUDY", tmp_path)
    for prechecks in ({"status": "passed", "evaluation_outcomes_observed": 1},
                      {"status": "failed", "evaluation_outcomes_observed": 0}):
        with pytest.raises(ValueError, match="before evaluation"):
            diagnostic.create_freeze(prechecks)
