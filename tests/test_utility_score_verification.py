"""The additive score check needs its scientific closure, not a past checkout."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = Path("studies/investigator_utility/openrouter_v1/response_evidence")
ENTRY = BUNDLE / "verify_scores.py"
MANIFEST = BUNDLE / "scoring_manifest_v2.json"
SCORER = Path("src/tracebench/investigator_utility/scoring.py")
STUDY = BUNDLE.parent
FROZEN = STUDY / "frozen"
RESULTS = STUDY / "results"
DECLARED = json.loads((ROOT / MANIFEST).read_text())
DEPENDENCIES = sorted([*DECLARED["files_sha256"], str(MANIFEST)])


@pytest.fixture
def copied(tmp_path):
    root = tmp_path / "minimal"
    for name in DEPENDENCIES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return root


def run(root, cwd):
    return subprocess.run([sys.executable, "-I", "-B", str(root / ENTRY)], cwd=cwd,
                          text=True, capture_output=True, check=False)


def failed(result):
    assert result.returncode == 1
    assert result.stderr.startswith("Verification failed:")
    assert "Traceback" not in result.stderr
    assert not result.stdout


def rewrite(path, change):
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))


def test_current_checkout_and_minimal_tree_from_unrelated_working_directory(copied, tmp_path):
    current = run(ROOT, tmp_path)
    minimal = run(copied, tmp_path)
    assert current.returncode == minimal.returncode == 0, (current.stderr, minimal.stderr)
    assert current.stdout == minimal.stdout
    output = json.loads(minimal.stdout)
    assert (output["responses"], output["development"], output["evaluation"]) == (168, 24, 144)
    assert output["resamples"] == 2000
    assert output["provider_reported_cost_usd"] == "2.8615140"
    assert output["charged_or_reserved_usd"] == "2.9989060"
    assert output["unknown_actual_cost_attempts"] == 1
    assert output["historical_dependencies"] == 14
    assert len(DEPENDENCIES) == output["required_files_including_verifier_and_manifest"] == 16
    assert not (copied / "README.md").exists()
    assert not (copied / "demo").exists()
    assert not (copied / "src/tracebench/__init__.py").exists()
    assert not (copied / BUNDLE / "verify.py").exists()


def test_unrelated_markdown_demo_and_nonimported_code_do_not_affect_scores(copied, tmp_path):
    before = run(copied, tmp_path)
    for name in ("README.md", "LIMITATIONS.md", "demo/index.html", "docs/SUBMISSION.md",
                 "src/tracebench/simulate.py", "src/tracebench/__init__.py"):
        path = copied / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Unrelated deliberately invalid replacement.\n")
    after = run(copied, tmp_path)
    assert before.returncode == after.returncode == 0
    assert before.stdout == after.stdout


@pytest.mark.parametrize("name", [
    BUNDLE / "responses.jsonl", FROZEN / "gold_certificates.json", SCORER,
    FROZEN / "prompt_manifest.json", FROZEN / "config.json",
    RESULTS / "per_case_scores.json", RESULTS / "execution.json",
    RESULTS / "paired_summary.json", BUNDLE / "scoring_cases.json",
])
def test_tampered_scientific_dependency_fails(copied, tmp_path, name):
    path = copied / name
    if name == BUNDLE / "responses.jsonl":
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["completion_text"] = "changed final response"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    elif name == FROZEN / "gold_certificates.json":
        rewrite(path, lambda rows: rows[0]["claims"][0].update(
            status="ruled_out" if rows[0]["claims"][0]["status"] != "ruled_out" else "established"))
    elif name == FROZEN / "prompt_manifest.json":
        rewrite(path, lambda rows: rows.reverse())
    elif name == FROZEN / "config.json":
        rewrite(path, lambda value: value["models"][0].update(input_usd_per_million="999"))
    elif name == RESULTS / "execution.json":
        rewrite(path, lambda value: value.update(charged_or_reserved_usd="0"))
    elif name == RESULTS / "per_case_scores.json":
        rewrite(path, lambda rows: rows[0]["claims"][0].update(
            status_correct=not rows[0]["claims"][0]["status_correct"]))
    else:
        path.write_bytes(path.read_bytes() + b"\n")
    failed(run(copied, tmp_path))


@pytest.mark.parametrize("name", DEPENDENCIES)
def test_every_required_file_is_mandatory(copied, tmp_path, name):
    if name == str(ENTRY):
        # Python itself cannot launch an absent entry point.
        (copied / name).unlink()
        assert run(copied, tmp_path).returncode != 0
    else:
        (copied / name).unlink()
        failed(run(copied, tmp_path))


def test_manifest_cannot_omit_required_pin(copied, tmp_path):
    rewrite(copied / MANIFEST, lambda value: value["files_sha256"].pop(str(SCORER)))
    result = run(copied, tmp_path)
    failed(result)
    assert "dependency closure differs" in result.stderr


def test_changed_current_hash_cannot_replace_existing_historical_pin(copied, tmp_path):
    path = copied / SCORER
    path.write_bytes(path.read_bytes() + b"\n# changed copy\n")
    updated = hashlib.sha256(path.read_bytes()).hexdigest()
    rewrite(copied / MANIFEST,
            lambda value: value["files_sha256"].update({str(SCORER): updated}))
    result = run(copied, tmp_path)
    failed(result)
    assert "Existing historical pin differs" in result.stderr


def test_duplicate_manifest_keys_are_rejected(copied, tmp_path):
    path = copied / MANIFEST
    path.write_text('{"schema_version":2,' + path.read_text()[1:])
    result = run(copied, tmp_path)
    failed(result)
    assert "Duplicate JSON object key" in result.stderr


def test_manifest_path_traversal_is_rejected(copied, tmp_path):
    rewrite(copied / MANIFEST,
            lambda value: value["files_sha256"].update({"../../outside": "0" * 64}))
    failed(run(copied, tmp_path))


def test_dependency_symlink_cannot_escape_copy(copied, tmp_path):
    outside = tmp_path / "outside_scorer.py"
    shutil.copyfile(copied / SCORER, outside)
    (copied / SCORER).unlink()
    (copied / SCORER).symlink_to(outside)
    result = run(copied, tmp_path)
    failed(result)
    assert "escapes its directory" in result.stderr
