"""The follow-up cannot silently change frozen inputs or overwrite prior outputs."""
import json

import pytest

from studies.acquisition_prior_robustness import analysis


def test_duplicate_json_keys_are_not_silently_accepted(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"probability":"1/2","probability":"1"}')
    with pytest.raises(ValueError, match="Duplicate"):
        analysis.read(path)


def test_both_output_encodings_refuse_overwriting(tmp_path):
    for name, writer in [("plain.json", analysis.write_new),
                         ("compact.json.gz", analysis.write_compressed)]:
        path = tmp_path / name
        writer(path, {"retained": True})
        before = path.read_bytes()
        with pytest.raises(FileExistsError):
            writer(path, {"retained": False})
        assert path.read_bytes() == before


def test_missing_or_changed_frozen_dependency_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    monkeypatch.setattr(analysis, "STUDY", tmp_path)
    monkeypatch.setattr(analysis, "config", lambda: {})
    path = tmp_path / "science.json"
    path.write_text('{"prior":"1/2"}')
    monkeypatch.setattr(analysis, "dependencies", lambda: [path])
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({"files_sha256": {"science.json": analysis.digest(path)}}))
    assert analysis.verify_freeze() == 1
    path.write_text('{"prior":"1"}')
    with pytest.raises(ValueError, match="Freeze mismatch"):
        analysis.verify_freeze()
    path.unlink()
    with pytest.raises(FileNotFoundError):
        analysis.verify_freeze()
    freeze.write_text('{"files_sha256":{}}')
    with pytest.raises(ValueError, match="dependency closure"):
        analysis.verify_freeze()


def test_current_scientific_preservation(tmp_path, monkeypatch):
    path = tmp_path / "protected.json"
    path.write_text('{"unchanged":true}')
    local = tmp_path / "local.json"
    local.write_text('{"sha256":{}}')
    (tmp_path / "preservation.json").write_text(json.dumps({
        "tracked_sha256": {"protected.json": analysis.digest(path)},
        "local_preservation_manifest": "local.json"}))
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    monkeypatch.setattr(analysis, "STUDY", tmp_path)
    assert analysis.verify_preservation() == {
        "historical_tracked_files": 1, "historical_local_files": 0}
    path.write_text('{"unchanged":false}')
    with pytest.raises(ValueError, match="Historical preservation"):
        analysis.verify_preservation()


@pytest.mark.parametrize("baseline_passed", [True, False])
def test_freeze_consumes_actual_audit_status_schema(tmp_path, monkeypatch, baseline_passed):
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    monkeypatch.setattr(analysis, "STUDY", tmp_path)
    monkeypatch.setattr(analysis, "config", lambda: {})
    monkeypatch.setattr(analysis, "verify_preservation", lambda: {})
    monkeypatch.setattr(analysis, "dependencies", lambda: [])
    (tmp_path / "pre_freeze_checks.json").write_text(json.dumps({
        "passed": True, "evaluation_comparisons_observed": 0}))
    (tmp_path / "baseline_reproduction.json").write_text(json.dumps({
        "status": "passed" if baseline_passed else "failed"}))
    (tmp_path / "structure_groups.json").write_text(json.dumps({
        "status": "verified_no_material_collisions_in_existing_inputs",
        "problem_count": 40, "group_count": 30}))
    if baseline_passed:
        assert analysis.freeze()["status"] == "frozen"
        with pytest.raises(FileExistsError):
            analysis.freeze()
    else:
        with pytest.raises(ValueError, match="reproduction"):
            analysis.freeze()
        assert not (tmp_path / "freeze.json").exists()
