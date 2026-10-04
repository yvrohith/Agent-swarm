"""Joint-study driver guards on retained development data only."""
import copy
import gzip
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name="analysis"):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.joint_audit_warrant.{name}")
    finally:
        sys.path.pop(0)


def read(path):
    path = ROOT / path
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as handle:
            return json.load(handle)
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def development():
    driver = module()
    problem = next(p for p in read("studies/evidence_acquisition/development_problems.json")
                   if p["problem_id"] == "acq_94103")
    def selected(path):
        return [row for row in read(path) if row["problem_id"] == problem["problem_id"]]
    saved = selected("studies/audit_aware_acquisition/development_baseline.json.gz")
    old_roots = selected("studies/joint_audit_warrant/development_old_roots.json.gz")
    old_design = selected("studies/joint_audit_warrant/development_old_design_runs.json.gz")
    old_anchors = selected("studies/joint_audit_warrant/development_old_anchor_runs.json.gz")
    before = driver.canonical([problem, saved, old_roots, old_design, old_anchors])
    complete = driver.analyze_problem(problem, saved, old_roots, old_design)
    capped = driver.analyze_problem(problem, saved, old_roots, old_design, state_cap=1)
    assert driver.canonical([problem, saved, old_roots, old_design, old_anchors]) == before
    return problem, complete, capped, old_roots, old_design, old_anchors


def test_capped_joint_roots_retain_every_anchor_and_comparator(development):
    _, complete, capped, _, _, _ = development
    driver = module()
    for key in ("roots", "design_runs", "runs", "cells"):
        assert len(capped[key]) == len(complete[key])
    assert len(capped["cells"]) == 36
    for root in capped["roots"]:
        assert root["joint_status"] == "unavailable"
        assert root["solver"]["budget_frontiers"] == []
        assert root["solver"]["states"]
        expected = [{"budget_percent": p, "integer_budget": p * root["residual_cost"] // 100}
                    for p in (0, 25, 50, 100)]
        assert root["anchor_budgets"] == expected
        assert root["integer_budgets"] == sorted({row["integer_budget"] for row in expected})
        current = [row for row in capped["design_runs"] if row["root_id"] == root["root_id"]]
        assert len(current) == root["signature_count"] * len(root["integer_budgets"]) * 3
        for row in current:
            assert row["execution_status"] == ("unavailable" if row["arm"] == driver.JOINT else "completed")
    def decisions(result):
        return {(r["root_id"], r["integer_budget"], r["arm"], tuple(r["outcomes"])):
                (r["history"], r["added_cost"], r["status"], r["design_supported_original"])
                for r in result["design_runs"] if r["arm"] != driver.JOINT}
    assert decisions(capped) == decisions(complete)


def test_preserved_e_paths_match_exactly_and_changed_history_is_rejected(development):
    _, complete, _, _, _, old_anchors = development
    driver = module()
    assert driver.legacy_parity(complete["runs"], old_anchors)["status"] == "passed"
    changed = copy.deepcopy(complete["runs"])
    row = next(r for r in changed if r["arm"] == driver.E and r["history"])
    row["history"].pop()
    with pytest.raises(ValueError, match="Original E scientific anchor field changed: history"):
        driver.legacy_parity(changed, old_anchors)


def test_projection_checks_full_saved_frontier_not_only_detection_optimum(development):
    _, complete, _, old_roots, _, _ = development
    driver = module()
    root = copy.deepcopy(complete["roots"][0])
    old = next(r for r in old_roots if r["root_id"] == root["root_id"])
    current = [r for r in complete["design_runs"] if r["root_id"] == root["root_id"]]
    assert all(row["projection_equal"] for row in driver.design_measurements(root, current, old)[1])
    root["solver"]["budget_frontiers"][0]["frontier"][0]["l"] += 1
    with pytest.raises(ValueError, match="projection differs"):
        driver.design_measurements(root, current, old)


def test_unavailable_joint_denominators_are_not_renormalized(development):
    problem, complete, capped, _, _, _ = development
    driver = module()
    # One completed synthetic aggregation identity and one unavailable identity
    # distinguish retained missing denominators from silent renormalization.
    completed_cells = copy.deepcopy(complete["cells"])
    for row in completed_cells:
        row["problem_id"] = "aggregation_complete_fixture"
    groups = {problem["problem_id"]: "same_structure", "aggregation_complete_fixture": "same_structure"}
    summary = driver.summarize([*capped["cells"], *completed_cells], groups)
    selected = [row for row in summary["conditions"] if row["arm"] == driver.JOINT
                and row["stratum"] == "all" and row["population"] == "all"]
    assert {row["weighting"] for row in selected} == {"equal_problem", "structure_balanced"}
    for row in selected:
        assert row["problem_count"] == 2 and not row["pooled_counts_complete"]
        metric = row["metrics"]["added_cost"]
        assert metric["mean"] is None
        assert metric["expected_problems"] == 2 and metric["defined_problems"] == 1
        assert row["unavailable_problems"] == [problem["problem_id"]]
    paired = driver.paired_differences([*capped["cells"], *completed_cells], groups)
    for row in paired["summary"]:
        if row["left"] != driver.JOINT or row["stratum"] != "all" or row["population"] != "all":
            continue
        metric = row["metrics"]["added_cost"]
        assert metric["mean"] is None
        assert metric["expected_problems"] == 2 and metric["defined_problems"] == 1
        assert metric["failed_problems"] == [problem["problem_id"]]
    design = driver.summarize_design(capped["roots"], {problem["problem_id"]: "one_structure"})
    for row in design["per_problem"]:
        assert row["root_count"] == len(capped["roots"])
        assert row["signature_count"] == sum(r["signature_count"] for r in capped["roots"])
        assert len(row["unavailable_joint_roots"]) == len(capped["roots"])
        assert row["counts"]["joint_support_gain_vs_e"] is None
        assert row["arms"][driver.JOINT]["w"] is None
        assert row["arms"][driver.SEQUENTIAL]["w"] is not None
    for row in design["summary"]:
        metric = row["metrics"][driver.JOINT + ":added_cost_per_all_signature"]
        assert metric["mean"] is None and metric["expected_problems"] == 1
        assert metric["defined_problems"] == 0 and metric["failed_problems"] == [problem["problem_id"]]


def test_missing_and_duplicate_anchor_cells_fail(development):
    problem, complete, _, _, _, _ = development
    driver = module()
    for rows in (complete["cells"][:-1], complete["cells"] + [complete["cells"][0]]):
        with pytest.raises(ValueError, match="must remain present"):
            driver.summarize(rows, {problem["problem_id"]: "one_structure"})


@pytest.mark.parametrize("field", ["arms", "caps", "extra_budget_percentages", "evaluation_old_roots_source"])
def test_settings_reject_changed_scientific_schedule_and_frozen_source(tmp_path, monkeypatch, field):
    driver = module()
    config = read("studies/joint_audit_warrant/config.json")
    if field == "arms":
        config[field].remove(driver.SEQUENTIAL)
    elif field == "caps":
        config[field]["states_per_root"] += 1
    elif field == "extra_budget_percentages":
        config[field].append(75)
    else:
        config[field] = "a/replacement/source.json"
    (tmp_path / "config.json").write_text(json.dumps(config))
    monkeypatch.setattr(driver, "STUDY", tmp_path)
    with pytest.raises(ValueError, match="[Cc]onfiguration|fixed authorized"):
        driver.settings()


def test_freeze_rejects_observed_new_evaluation_outcomes(tmp_path, monkeypatch):
    driver = module()
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        (tmp_path / name).write_text(json.dumps({"status": "passed", "new_evaluation_policy_outcomes_observed": 1}))
    monkeypatch.setattr(driver, "STUDY", tmp_path)
    monkeypatch.setattr(driver, "settings", lambda: {})
    monkeypatch.setattr(driver, "verify_input_provenance", lambda: None)
    with pytest.raises(ValueError, match="pre-outcome|chronology"):
        driver.freeze()
    assert not (tmp_path / "freeze.json").exists()


@pytest.mark.parametrize("mutation", ["missing_source", "changed_source"])
def test_freeze_requires_unchanged_qualified_sources(tmp_path, monkeypatch, mutation):
    driver = module()
    source = tmp_path / "source.py"
    source.write_text("# qualified source\n")
    qualified = {"source.py": driver.digest(source)}
    if mutation == "missing_source":
        qualified.clear()
    else:
        source.write_text("# changed since qualification\n")
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


def test_existing_output_refuses_before_loading_inputs(tmp_path, monkeypatch):
    driver = module()
    marker = tmp_path / "retained.json"
    marker.write_text('{"retained":true}\n')
    before = marker.read_bytes()
    def no_inputs(*args):
        raise AssertionError("existing output triggered scientific input loading")
    monkeypatch.setattr(driver, "verify_freeze", lambda: 0)
    monkeypatch.setattr(driver, "verify_preservation", lambda: {})
    monkeypatch.setattr(driver, "_inputs", no_inputs)
    with pytest.raises(FileExistsError):
        driver.execute(tmp_path)
    with pytest.raises(FileExistsError):
        driver.write_new(marker, {"replacement": True})
    assert marker.read_bytes() == before
    assert list(tmp_path.iterdir()) == [marker]


@pytest.mark.parametrize("checker_status", ["failed", "unknown_status"])
def test_failed_independent_verification_is_never_labeled_passed(tmp_path, monkeypatch, checker_status):
    driver, reference = module(), module("reference")
    data = {"manifest.json": {"freeze_sha256": "fixed", "files_sha256": {}},
            **{name: [] for name in ("roots.json.gz", "design_runs.json.gz", "runs.json.gz", "per_condition.json.gz")},
            **{name: {} for name in ("certificates.json.gz", "summary.json.gz", "paired.json.gz", "design_summary.json.gz")}}
    monkeypatch.setattr(driver, "verify_freeze", lambda: 0)
    monkeypatch.setattr(driver, "digest", lambda path: "fixed")
    monkeypatch.setattr(driver, "read", lambda path: copy.deepcopy(data[Path(path).name]))
    monkeypatch.setattr(driver, "_inputs", lambda development: ([], [], [], [], [], {}))
    monkeypatch.setattr(driver, "_check_schedule", lambda *args: {})
    monkeypatch.setattr(driver, "legacy_parity", lambda *args: {"status": "passed"})
    monkeypatch.setattr(reference, "verify_all", lambda *args: {"status": checker_status})
    for name in ("summarize", "paired_differences", "summarize_design"):
        monkeypatch.setattr(driver, name, lambda *args: {})
    with pytest.raises(ValueError, match="[Cc]heck|[Vv]erif"):
        driver.verify_outputs(tmp_path)
