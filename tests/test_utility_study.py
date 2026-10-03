import json
import subprocess
from pathlib import Path

import pytest

from tracebench.investigator_utility import __main__ as cli
from tracebench.investigator_utility.prompts import digest
from tracebench.investigator_utility.study import (
    file_hash,
    freeze,
    ignored_output,
    read_json,
    validate_prepared,
    verify_freeze,
    verify_preservation,
    write_json,
)
from tracebench.investigator_utility.synthetic_cases import build_synthetic_cases


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    (root / ".gitignore").write_text("artifacts/\n")
    study = root / "studies/investigator_utility"
    study.mkdir(parents=True)
    code = root / "src/tracebench/investigator_utility/module.py"
    code.parent.mkdir(parents=True)
    code.write_text("# frozen test implementation\n")
    original = root / "original.txt"
    original.write_text("preserve\n")
    write_json(study / "preservation.json", {
        "baseline_head": "test-baseline", "dependency_lock_sha256": "test-lock",
        "files": {"original.txt": file_hash(original)},
    })
    config = read_json(Path(__file__).parents[1] / "studies/investigator_utility/config.json")
    config.update(development_wiki_cases=0, evaluation_wiki_cases=0)
    write_json(study / "config.json", config)
    (study / "ANALYSIS.md").write_text("Test protocol. No calls.\n")
    prepared = root / "artifacts/investigator-utility/prepared"
    prepared.mkdir(parents=True)
    cases, gold, selection = build_synthetic_cases()
    write_json(prepared / "public_cases.json", cases)
    write_json(prepared / "gold.json", gold)
    write_json(prepared / "selection.json", selection)
    monkeypatch.setattr(cli, "ROOT", root)
    monkeypatch.setattr(cli, "STUDY", study)
    return root, study, prepared, config, code


def freeze_setup(setup):
    root, study, prepared, config, code = setup
    frozen = study / "frozen"
    record = freeze(root, prepared, study / "config.json", study / "ANALYSIS.md", frozen)
    return frozen, record


def test_validation_checks_labels_raw_parity_and_disjoint_cases(setup):
    root, _, prepared, config, _ = setup
    result = validate_prepared(prepared, config)
    assert result["gold_certificate_checks"] == 10
    assert result["label_invariance_checks"] == 10
    assert result["same_evidence_checks"] == 10
    assert result["claims"] == 40
    assert not any(result["shortages"].values())
    assert verify_preservation(root)["all_match"]


def test_bad_gold_fails_before_freeze(setup):
    _, _, prepared, config, _ = setup
    gold = read_json(prepared / "gold.json")
    gold[0]["claims"][0]["status"] = "invented"
    (prepared / "gold.json").write_text(json.dumps(gold))
    with pytest.raises(ValueError):
        validate_prepared(prepared, config)


def test_shared_history_between_splits_rejected(setup):
    _, _, prepared, config, _ = setup
    cases = read_json(prepared / "public_cases.json")
    cases[-1]["cluster_id"] = cases[0]["cluster_id"]
    (prepared / "public_cases.json").write_text(json.dumps(cases))
    with pytest.raises(ValueError, match="histories overlap"):
        validate_prepared(prepared, config)


def test_oversized_case_rejected_not_truncated(setup):
    _, _, prepared, config, _ = setup
    config["max_prompt_utf8_bytes"] = 10
    with pytest.raises(ValueError, match="Oversized"):
        validate_prepared(prepared, config)


@pytest.mark.parametrize("which", ["code", "gold", "config", "frozen_view", "baseline"])
def test_freeze_rejects_changed_dependencies(setup, which):
    root, study, prepared, _, code = setup
    frozen, _ = freeze_setup(setup)
    assert verify_freeze(root, frozen)["status"] == "cases_frozen_execution_blocked"
    target = {"code": code, "gold": prepared / "gold.json", "config": study / "config.json",
              "frozen_view": frozen / "view_manifest.json", "baseline": root / "original.txt"}[which]
    target.write_text(target.read_text() + "\n")
    with pytest.raises(ValueError):
        verify_freeze(root, frozen)


def test_freeze_and_outputs_cannot_be_overwritten(setup):
    root, study, prepared, _, _ = setup
    frozen, _ = freeze_setup(setup)
    with pytest.raises(ValueError, match="Freeze already exists"):
        freeze(root, prepared, study / "config.json", study / "ANALYSIS.md", frozen)
    with pytest.raises(FileExistsError):
        write_json(prepared / "gold.json", [])


def test_raw_views_require_ignored_directory(setup):
    root, study, prepared, _, _ = setup
    ignored_output(root, prepared)
    with pytest.raises(ValueError, match="ignored artifacts"):
        ignored_output(root, study / "public_cases.json")


def test_cannot_reset_budget_with_new_ledger_path(setup):
    _, _, _, config, _ = setup
    config["raw_execution_directory"] = "artifacts/new-budget"
    with pytest.raises(ValueError, match="ledger path is fixed"):
        cli._ledger_path(config)


def test_no_access_end_to_end_keeps_model_results_empty(setup):
    _, study, prepared, config, _ = setup
    frozen, record = freeze_setup(setup)
    assert record["models"] == [] and record["evaluation_calls_planned"] == 0
    result = cli.evaluate(prepared, frozen)
    assert result["attempts"] == 0 and result["actual_total_cost_usd"] == "0"
    status = prepared.parent / "execution.json"
    write_json(status, result)
    output = study / "results"
    reported = cli.score_and_report(prepared, frozen, status, output)
    assert reported["model_score_rows"] == 0
    assert read_json(output / "per_case_scores.json") == []
    assert read_json(output / "paired_summary.json")["paired"] == []
    assert len(read_json(output / "sanity_baselines.json")) == 24
    report = (output / "REPORT.md").read_text()
    assert "No investigator evaluation results exist" in report
    assert "Actual model cost (USD): 0" in report
    assert not cli._ledger_path(config).exists()


def test_report_rejects_different_prepared_directory(setup, tmp_path):
    root, study, prepared, _, _ = setup
    frozen, _ = freeze_setup(setup)
    other = root / "artifacts/other"
    other.mkdir()
    for name in ("public_cases.json", "gold.json", "selection.json"):
        (other / name).write_bytes((prepared / name).read_bytes())
    with pytest.raises(ValueError, match="do not belong"):
        cli.score_and_report(other, frozen, tmp_path / "unused.json", study / "results")


def test_development_emits_only_development_prompts_and_no_fake_answers(setup):
    root, _, prepared, config, _ = setup
    output = root / "artifacts/investigator-utility/development"
    result = cli.develop(prepared, config, output)
    assert result["execution"]["attempts"] == 0
    prompts = [p for p in output.glob("*.json") if p.name != "execution.json"]
    assert len(prompts) == 6
    assert all("development" in read_json(p)["user"] for p in prompts)
    assert all(set(read_json(p)) == {"system", "user"} for p in prompts)


def test_report_cannot_mix_current_ledger_with_stale_execution_status(setup):
    _, study, prepared, config, _ = setup
    frozen, _ = freeze_setup(setup)
    result = cli.evaluate(prepared, frozen)
    status = prepared.parent / "execution.json"
    write_json(status, result)
    ledger_dir = cli._ledger_path(config)
    ledger_dir.mkdir()
    (ledger_dir / "attempts.jsonl").write_text(json.dumps({
        "event": "study", "models_hash": digest(config["models"]),
    }) + "\n")
    with pytest.raises(ValueError, match="changed ledger"):
        cli.score_and_report(prepared, frozen, status, study / "results")
