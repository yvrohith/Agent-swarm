"""Driver failure accounting and freeze guards, using development inputs only."""
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
        return importlib.import_module(f"studies.exact_audit_frontier.{name}")
    finally:
        sys.path.pop(0)


@pytest.fixture(scope="module")
def development_results():
    driver = module("analysis")
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    problem = next(p for p in problems if p["problem_id"] == "acq_94103")
    with gzip.open(ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz", "rt") as handle:
        saved = [c for c in json.load(handle) if c["problem_id"] == problem["problem_id"]]
    complete = driver.analyze_problem(problem, saved)
    capped = driver.analyze_problem(problem, saved, state_cap=1)
    return problem, complete, capped


def test_capped_roots_retain_the_entire_unavailable_exact_grid(development_results):
    problem, complete, capped = development_results
    exact = module("analysis").EXACT
    assert len(capped["roots"]) == len(complete["roots"]) > 1
    assert len(capped["design_runs"]) == len(complete["design_runs"])
    assert len(capped["runs"]) == len(complete["runs"])
    assert len(capped["cells"]) == len(complete["cells"]) == 72
    for root in capped["roots"]:
        assert root["exact_status"] == "unavailable"
        assert root["solver"]["budget_frontiers"] == []
        assert root["solver"]["states"]  # Partial feasible witnesses are retained.
        assert len(root["hindsight"]) == root["signature_count"]
        for row in root["hindsight"]:
            if row["minimum_cost"] is not None:
                assert row["certificate"]["status"] == "inconsistent"
        selected = [row for row in capped["design_runs"] if row["root_id"] == root["root_id"]]
        for budget in range(root["residual_cost"] + 1):
            rows = [r for r in selected if r["integer_budget"] == budget and r["arm"] == exact]
            assert len(rows) == root["signature_count"]
            assert all(r["execution_status"] == "unavailable" for r in rows)
    assert all(row["execution_status"] == ("unavailable" if row["arm"] == exact else "completed")
               for row in capped["design_runs"] + capped["runs"])
    # Original comparators and the separately named affordable control survive
    # exactly; timing is intentionally not part of this equality assertion.
    def decisions(result):
        return {(r["root_id"], r["integer_budget"], r["arm"], tuple(r["outcomes"])):
                (r["history"], r["added_cost"], r["status"])
                for r in result["design_runs"] if r["arm"] != exact}
    assert decisions(capped) == decisions(complete)
    assert problem["problem_id"] == "acq_94103"


def test_unavailable_exact_results_are_not_reweighted_away(development_results):
    problem, complete, capped = development_results
    driver = module("analysis")
    # A second explicit aggregation identity lets the test distinguish a
    # retained missing denominator from renormalization over one completed row.
    cells = copy.deepcopy(complete["cells"])
    for cell in cells:
        cell["problem_id"] = "aggregation_complete_fixture"
    groups = {problem["problem_id"]: "shared_structure", "aggregation_complete_fixture": "shared_structure"}
    summary = driver.summarize([*capped["cells"], *cells], groups)
    selected = [r for r in summary["conditions"] if r["arm"] == driver.EXACT
                and r["stratum"] == "all" and r["population"] == "all"]
    assert {r["weighting"] for r in selected} == {"equal_problem", "structure_balanced"}
    for row in selected:
        assert row["problem_count"] == 2 and not row["pooled_counts_complete"]
        assert row["unavailable_problems"] == [problem["problem_id"]]
        metric = row["metrics"]["added_cost"]
        assert metric["mean"] is None
        assert metric["expected_problems"] == 2
        assert metric["defined_problems"] == 1
    design = driver.summarize_design(capped["roots"], {problem["problem_id"]: "only_structure"})
    for row in design["per_problem"]:
        assert row["root_count"] == len(capped["roots"])
        assert row["signature_count"] == sum(r["signature_count"] for r in capped["roots"])
        assert len(row["unavailable_exact_roots"]) == len(capped["roots"])
        assert row["counts"]["exact_detection"] is None
        assert row["arms"][driver.EXACT]["d"] is None
        assert row["arms"]["closure_informed_affordable"]["d"] is not None
    for row in design["summary"]:
        metric = row["metrics"][driver.EXACT + ":added_cost_per_all_signature"]
        assert metric["mean"] is None
        assert metric["expected_problems"] == 1 and metric["defined_problems"] == 0
        assert metric["failed_problems"] == [problem["problem_id"]]


def test_missing_or_duplicate_aggregate_cells_are_rejected(development_results):
    problem, complete, _ = development_results
    driver = module("analysis")
    groups = {problem["problem_id"]: "one_structure"}
    for cells in (complete["cells"][:-1], complete["cells"] + [complete["cells"][0]]):
        with pytest.raises(ValueError, match="must remain present"):
            driver.summarize(cells, groups)


@pytest.mark.parametrize("field", ["roots", "design_runs", "runs", "cells"])
def test_missing_schedule_rows_are_rejected_before_summary(development_results, monkeypatch, field):
    _, complete, _ = development_results
    driver = module("analysis")
    expected = {"roots": len(complete["roots"]),
                "root_integer_budget_cells": sum(r["residual_cost"] + 1 for r in complete["roots"]),
                "integer_design_runs_six_arms": len(complete["design_runs"]),
                "anchor_cells": len(complete["cells"]), "anchor_runs": len(complete["runs"])}
    monkeypatch.setattr(driver, "settings", lambda: {"expected_schedule": {"development": expected}})
    fields = ("roots", "design_runs", "runs", "cells")
    assert driver._check_schedule(*(complete[key] for key in fields), True) == expected
    incomplete = {**complete, field: complete[field][:-1]}
    with pytest.raises(ValueError, match="fixed schedule differs"):
        driver._check_schedule(*(incomplete[key] for key in fields), True)


@pytest.mark.parametrize("field", ["arms", "caps"])
def test_settings_reject_changed_arms_or_caps(tmp_path, monkeypatch, field):
    driver = module("analysis")
    config = json.loads((ROOT / "studies/exact_audit_frontier/config.json").read_text())
    if field == "arms":
        config[field].remove("closure_informed_affordable")
    else:
        config[field]["states_per_root"] += 1
    (tmp_path / "config.json").write_text(json.dumps(config))
    monkeypatch.setattr(driver, "STUDY", tmp_path)
    with pytest.raises(ValueError, match="fixed authorized"):
        driver.settings()


def test_freeze_rejects_post_outcome_chronology_before_writing(tmp_path, monkeypatch):
    driver = module("analysis")
    config = json.loads((ROOT / "studies/exact_audit_frontier/config.json").read_text())
    (tmp_path / "config.json").write_text(json.dumps(config))
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        (tmp_path / name).write_text(json.dumps({"status": "passed", "new_evaluation_policy_outcomes_observed": 1}))
    monkeypatch.setattr(driver, "STUDY", tmp_path)
    monkeypatch.setattr(driver, "verify_input_provenance", lambda: None)
    with pytest.raises(ValueError, match="not pre-outcome"):
        driver.freeze()
    assert not (tmp_path / "freeze.json").exists()


@pytest.mark.parametrize("mutation", ["missing_source", "changed_source"])
def test_freeze_requires_current_development_qualification(tmp_path, monkeypatch, mutation):
    driver = module("analysis")
    source = tmp_path / "source.py"
    source.write_text("# qualified source\n")
    qualified = {"source.py": driver.digest(source)}
    if mutation == "missing_source":
        qualified.clear()
    else:
        source.write_text("# modified after qualification\n")
    for name in ("baseline_verification.json", "pre_freeze_checks.json"):
        (tmp_path / name).write_text(json.dumps({"status": "passed", "new_evaluation_policy_outcomes_observed": 0}))
    (tmp_path / "development_checks.json").write_text(json.dumps({
        "status": "passed", "new_evaluation_policy_outcomes_observed": 0, "source_sha256": qualified}))
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    monkeypatch.setattr(driver, "STUDY", tmp_path)
    monkeypatch.setattr(driver, "settings", lambda: {})
    monkeypatch.setattr(driver, "verify_input_provenance", lambda: None)
    monkeypatch.setattr(driver, "dependencies", lambda: [source])
    with pytest.raises(ValueError, match="source closure|after development qualification"):
        driver.freeze()
    assert not (tmp_path / "freeze.json").exists()


def test_existing_output_directory_and_file_are_never_overwritten(tmp_path, monkeypatch):
    driver = module("analysis")
    marker = tmp_path / "retained.json"
    marker.write_text('{"retained":true}\n')
    before = marker.read_bytes()
    monkeypatch.setattr(driver, "verify_freeze", lambda: 0)
    monkeypatch.setattr(driver, "verify_preservation", lambda: {})
    with pytest.raises(FileExistsError):
        driver.execute(tmp_path)
    with pytest.raises(FileExistsError):
        driver.write_new(marker, {"replacement": True})
    assert marker.read_bytes() == before
    assert list(tmp_path.iterdir()) == [marker]


@pytest.mark.parametrize("checker_status", ["failed", "unrecognized_status"])
def test_failed_checker_status_cannot_be_labeled_verified(tmp_path, monkeypatch, checker_status):
    driver, reference = module("analysis"), module("reference")
    data = {"manifest.json": {"freeze_sha256": "fixed", "files_sha256": {}},
            **{name: [] for name in ("roots.json.gz", "design_runs.json.gz", "runs.json.gz", "per_condition.json.gz")},
            **{name: {} for name in ("certificates.json.gz", "summary.json.gz", "paired.json.gz", "design_summary.json.gz")}}
    monkeypatch.setattr(driver, "verify_freeze", lambda: 0)
    monkeypatch.setattr(driver, "digest", lambda path: "fixed")
    monkeypatch.setattr(driver, "read", lambda path: copy.deepcopy(data[Path(path).name]))
    monkeypatch.setattr(driver, "_inputs", lambda development: ([], [], [], {}))
    monkeypatch.setattr(driver, "_check_schedule", lambda *args: {})
    monkeypatch.setattr(driver, "legacy_parity", lambda *args: {"status": "passed"})
    monkeypatch.setattr(reference, "verify_all", lambda *args: {"status": checker_status})
    for name in ("summarize", "paired_differences", "summarize_design"):
        monkeypatch.setattr(driver, name, lambda *args: {})
    with pytest.raises(ValueError, match="[Cc]heck|[Vv]erif"):
        driver.verify_outputs(tmp_path)
