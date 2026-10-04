"""Released-result replay must not depend on ignored local history."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from studies.comparative_validity import public_verify as public


@pytest.fixture
def release(tmp_path):
    manifest = public.read(public.HERE / "public_manifest_v1.json")
    names = set(manifest["authority_sha256"]) | {row["path"] for row in manifest["files"]}
    for name in names:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(public.ROOT / name, destination)
    return tmp_path, manifest


def test_public_closure_needs_no_git_local_artifacts_or_documentation(release):
    root, manifest = release
    result = public.verify_dependencies(root, manifest)
    assert result["status"] == "passed"
    assert result["local_history"] == "not checked"
    assert not (root / "artifacts").exists()
    assert not (root / ".git").exists()
    (root / "README.md").write_text("A current narrative correction\n")
    assert public.verify_dependencies(root, manifest) == result


@pytest.mark.parametrize("name", [
    public.PRIOR + "results/per_problem.json",
    public.PRIOR + "results/details.json.gz",
    public.ORIGINAL + "evaluation_problems.json",
    "src/tracebench/evidence_acquisition/model.py",
    public.PRIOR + "aggregation.py",
])
def test_missing_or_changed_result_label_and_scientific_code_fails(release, name):
    root, manifest = release
    path = root / name
    saved = path.read_bytes()
    path.unlink()
    with pytest.raises(FileNotFoundError):
        public.verify_dependencies(root, manifest)
    path.write_bytes(saved + b" ")
    with pytest.raises(ValueError, match="bytes differ"):
        public.verify_dependencies(root, manifest)


def test_public_manifest_cannot_repin_modified_scoring(release):
    root, manifest = release
    row = next(r for r in manifest["files"] if r["path"] == public.PRIOR + "aggregation.py")
    path = root / row["path"]
    path.write_bytes(path.read_bytes() + b"\n# changed calculation\n")
    row["sha256"] = public.digest(path)
    with pytest.raises(ValueError, match="historical authority"):
        public.verify_dependencies(root, manifest)


def test_duplicate_dependency_is_rejected(release):
    root, manifest = release
    manifest["files"].append(copy.deepcopy(manifest["files"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        public.verify_dependencies(root, manifest)


def test_deleting_a_semantic_dependency_is_rejected(release):
    root, manifest = release
    manifest["files"].pop()
    with pytest.raises(ValueError, match="closure"):
        public.verify_dependencies(root, manifest)


@pytest.mark.parametrize("name", ["../escape", "/tmp/escape", "a/../b", "a//b", "a\\b"])
def test_path_escapes_are_rejected(tmp_path, name):
    with pytest.raises(ValueError, match="escape or alias"):
        public.safe_path(tmp_path, name)


def test_symlink_escape_is_rejected(tmp_path):
    (tmp_path / "out").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        public.safe_path(tmp_path, "out/file")


def test_duplicate_metric_or_signature_identity_fails():
    row = {"problem_id": "p", "signature_index": 0}
    with pytest.raises(ValueError, match="Duplicate trajectory"):
        public.unique_rows([row, row], ("problem_id", "signature_index"), "trajectory")


def test_duplicate_json_key_fails(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"label": true, "label": false}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        public.read(path)


def test_missing_local_files_never_count_as_full_pass(tmp_path):
    saved = {"local_preservation_manifest": "artifacts/local.json",
             "local_preservation_manifest_sha256": "unused when absent",
             "tracked_sha256": {"preserved.json": "unavailable"}}
    result = public.local_history(tmp_path, saved)
    assert result["status"] == "incomplete_or_changed_local_history"
    assert set(result["missing_files"]) == {"artifacts/local.json", "preserved.json"}
    assert result["matched_files"] == 0
    assert result["public_results"] == "not checked"


def test_optional_local_check_hashes_bytes_without_decoding(tmp_path):
    payload = tmp_path / "artifacts/opaque.json"
    payload.parent.mkdir()
    payload.write_bytes(b"not JSON, opaque bytes only")
    local = tmp_path / "artifacts/local.json"
    local.write_text(json.dumps({"sha256": {"artifacts/opaque.json": public.digest(payload)}}))
    saved = {"local_preservation_manifest": "artifacts/local.json",
             "local_preservation_manifest_sha256": public.digest(local), "tracked_sha256": {}}
    assert public.local_history(tmp_path, saved)["status"] == "passed_local_history"
    payload.write_bytes(b"changed")
    assert public.local_history(tmp_path, saved)["changed_files"] == ["artifacts/opaque.json"]


def test_runtime_closure_has_historical_origins_only():
    manifest = public.read(public.HERE / "public_manifest_v1.json")
    for row in manifest["files"]:
        assert row["origin"]["record"] in manifest["authority_sha256"]
        assert not Path(row["path"]).suffix == ".md"
        assert not row["path"].startswith(("artifacts/", "tests/"))


def test_another_installed_checkout_cannot_substitute_for_pinned_sources(monkeypatch):
    from tracebench.evidence_acquisition import model
    monkeypatch.setattr(model, "__file__", "/tmp/another-checkout/model.py")
    with pytest.raises(ValueError, match="another checkout"):
        public.verify_import_origins()
