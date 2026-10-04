"""Independent archive filtering on the four fixed development problems only."""

import copy
import gzip
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.audit_aware_acquisition.{name}")
    finally:
        sys.path.remove(str(ROOT))


@pytest.fixture(scope="module")
def reference():
    return module("reference")


@pytest.fixture(scope="module")
def development():
    driver = module("analysis")
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    assert all(p["split"] == "development" for p in problems)
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    conditions = json.loads(gzip.decompress(
        (ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz").read_bytes()))
    fixtures = []
    for problem in problems:
        cells = [c for c in conditions if c["problem_id"] == problem["problem_id"]]
        cache = driver.CertificateCache()
        output = driver.analyze_problem(problem, cells, cache=cache)
        assert len(output["cells"]) == 48
        assert all(c["status"] == "completed" for c in output["cells"])
        fixtures.append(([problem], cells, output["runs"], cache.certificates))
    return fixtures


@pytest.mark.parametrize("index", range(4))
def test_all_development_runs_and_distinct_certificates_verify(index, reference, development):
    problems, cells, runs, certificates = development[index]
    result = reference.verify_runs(problems, cells, runs, certificates)
    assert result["status"] == "passed"
    assert result["aggregate_cell_count"] == 48
    assert result["run_count"] == len(runs)
    assert result["certificate_references_checked"] == 4 * len(runs)
    assert result["distinct_certificates_checked"] == len(certificates)
    assert result["distinct_certificates_checked"] < result["certificate_references_checked"]
    assert result["cross_k_path_checks"] > 0
    assert result["budget_prefix_checks"] == len(runs)


@pytest.mark.parametrize("field", [
    "detected", "complete_nominal_conflict", "full_conflict_missed", "false_alarm",
    "catalogue_exhausted", "catalogue_query_count", "alias_added_queries",
    "alias_added_cost", "alias_added_bytes", "added_lookups_of_initial_records",
    "unique_queried_record_count", "added_cost", "audit_budget", "added_returned_bytes",
])
def test_aggregate_driving_fields_cannot_escape_verification(field, reference, development):
    problems, cells, runs, certificates = copy.deepcopy(development[0])
    runs[0][field] = (not runs[0][field]) if isinstance(runs[0][field], bool) else runs[0][field] + 1
    with pytest.raises(ValueError, match="disagrees"):
        reference.verify_runs(problems, cells, runs, certificates)


@pytest.mark.parametrize("kind", ["support", "disposition", "joint", "coverage", "history", "next_action"])
def test_classifications_and_paid_history_are_checked(kind, reference, development):
    problems, cells, runs, certificates = copy.deepcopy(development[0])
    row = runs[0]
    if kind == "support":
        row["support"]["warrant_restored"] = not row["support"]["warrant_restored"]
    elif kind == "disposition":
        row["support"]["disposition"] = "model_validated"
    elif kind == "joint":
        row["joint_category"]["alarm"] = not row["joint_category"]["alarm"]
    elif kind == "coverage":
        row["coverage"]["complete"] = not row["coverage"]["complete"]
    elif kind == "history":
        row["history"] = [{"query_id": "unpaid", "outcome_id": "missing"}]
    else:
        row["next_query"] = "unpaid"
    with pytest.raises(ValueError):
        reference.verify_runs(problems, cells, runs, certificates)


def test_first_conflict_position_cannot_be_shifted(reference, development):
    problems, cells, runs, certificates = copy.deepcopy(development[1])
    row = next(r for r in runs if r["first_conflict"])
    row["first_conflict"]["added_query_index"] += 1
    with pytest.raises(ValueError, match="first_conflict"):
        reference.verify_runs(problems, cells, runs, certificates)


@pytest.mark.parametrize("kind", ["row", "condition", "failure", "baseline_cap", "duplicate_problem", "duplicate_row"])
def test_missing_or_capped_population_cannot_pass(kind, reference, development):
    problems, cells, runs, certificates = copy.deepcopy(development[0])
    if kind == "row":
        runs.pop()
    elif kind == "condition":
        cells.pop()
    elif kind == "failure":
        cells[0]["policy_status"] = "unavailable"
        cells[0]["failure"] = {"kind": "state_cap", "state_cap": 100000}
    elif kind == "baseline_cap":
        cells[0]["signature_rows"][0]["policy"]["failure"] = {"kind": "state_cap", "state_cap": 100000}
    elif kind == "duplicate_problem":
        problems.append(copy.deepcopy(problems[0]))
    else:
        runs.append(copy.deepcopy(runs[0]))
    with pytest.raises(ValueError):
        reference.verify_runs(problems, cells, runs, certificates)


@pytest.mark.parametrize("kind", ["missing", "digest", "wrong_history", "wrong_contract", "invalid_semantics"])
def test_every_certificate_reference_is_bound_even_when_cached(kind, reference, development):
    problems, cells, runs, certificates = copy.deepcopy(development[0])
    row = runs[-1]
    old_ref = row["certificates"]["final_expanded"]
    if kind == "missing":
        row["certificates"]["final_expanded"] = "0" * 64
    elif kind == "digest":
        certificates[old_ref]["claim_status"] = "model_conflict"
    elif kind == "wrong_history":
        row["certificates"]["final_expanded"] = next(
            key for key, c in certificates.items() if c.get("certificate_kind") == "expanded_archive_support"
            and c["history"] != row["history"])
    else:
        candidate = copy.deepcopy(certificates[old_ref])
        if kind == "wrong_contract":
            candidate["k"] = 17
        else:
            candidate["claim_status"] = "model_conflict"
        replacement = reference.pin(candidate)
        certificates[replacement] = candidate
        row["certificates"]["final_expanded"] = replacement
    with pytest.raises(ValueError):
        reference.verify_runs(problems, cells, runs, certificates)


def test_unused_invalid_certificate_is_not_silently_ignored(reference, development):
    problems, cells, runs, certificates = copy.deepcopy(development[0])
    candidate = copy.deepcopy(next(iter(certificates.values())))
    candidate["model_pin"] = "0" * 64
    certificates[reference.pin(candidate)] = candidate
    with pytest.raises(ValueError, match="no declared model"):
        reference.verify_runs(problems, cells, runs, certificates)


def test_direct_filter_distinguishes_pending_irreducible_and_empty(reference):
    support = [
        {"signature": ("missing", "missing"), "truth": False},
        {"signature": ("missing", "missing"), "truth": True},
        {"signature": ("missing", "present"), "truth": True},
    ]
    assert reference.statuses(support, ("q1", "q2"), []) == ("unresolved", "unresolved_pending")
    assert reference.statuses(support, ("q1", "q2"), [{"query_id": "q2", "outcome_id": "missing"}]) == (
        "unresolved", "archive_irreducible")
    assert reference.statuses(support, ("q1", "q2"), [{"query_id": "q1", "outcome_id": "present"}]) == (
        "model_conflict", "model_conflict")


def test_reference_selectors_recompute_constants_and_ignore_signature_multiplicity(reference):
    problem = {"queries": [{"id": "cheap", "cost": 1}, {"id": "later", "cost": 2}]}
    nominal = {("missing", "missing"), ("present", "present")}
    design = [*nominal, ("missing", "present")]
    assert reference.choose(problem, nominal, design, [], "constant_first") == "cheap"
    history = [{"query_id": "cheap", "outcome_id": "missing"}]
    assert reference.choose(problem, nominal, design, history, "constant_first") == "later"
    assert reference.choose(problem, nominal, design, history, "closure_informed") == "later"
    assert reference.choose(problem, nominal, design * 100, history, "closure_informed") == "later"
    # A nominally constant expensive lookup is preferred even when the cheaper
    # nonconstant lookup would fit a small budget: budgets do not enter selection.
    nominal = {("missing", "present"), ("present", "present")}
    assert reference.choose(problem, nominal, design, [], "constant_first") == "later"
    assert reference.choose(problem, nominal, design, [], "cost_order") == "cheap"


def test_alarm_and_restoration_are_orthogonal(reference):
    flags = reference.support_flags("established", ("unresolved", "unresolved_pending"),
                                    ("established", "established"), ("established", "established"), True)
    assert flags["warrant_restored"] and flags["withdrawn_definite"]
    assert not flags["unwithdrawn_warrant_restored"]
    assert flags["disposition"] == "definite_proposal_withdrawn"
    without_support = reference.support_flags("established", ("unresolved", "unresolved_pending"),
                                              ("unresolved", "archive_irreducible"),
                                              ("unresolved", "archive_irreducible"), True)
    assert without_support["withdrawn_definite"] and not without_support["warrant_restored"]
