import hashlib
import json
from pathlib import Path

import pytest

from tracebench.cli import main
from tracebench.wiki_loader import load_fixture
from tracebench.wiki_study import run_loaded_study

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"


def test_fixture_audit_is_deterministic_separate_and_verifies_outputs(tmp_path):
    loaded = load_fixture(FIXTURES / "synthetic_revisions.jsonl", FIXTURES / "manifest.json")
    protocol = tmp_path / "ANALYSIS.md"
    protocol.write_text("Frozen synthetic fixture extraction validation only.\n")
    first, second = tmp_path / "first", tmp_path / "second"
    result = run_loaded_study(loaded, protocol, first, target_site="DSE")
    run_loaded_study(loaded, protocol, second, target_site="DSE")
    assert result["source_kind"] == "synthetic_fixture"
    assert all((first / p.name).read_bytes() == p.read_bytes() for p in second.iterdir())
    review = json.loads((first / "review_sheet.json").read_text())
    assert not review["independent_human_validation"]
    for status, entries in review["categories"].items():
        assert len(entries) <= 10
        assert [e["selection_sha256"] for e in entries] == sorted(e["selection_sha256"] for e in entries)
        assert all(e["candidate"]["status"] == status for e in entries)
        assert all(all(v is None for v in e["human_review"].values()) for e in entries)
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["analysis_protocol_sha256"] == hashlib.sha256(protocol.read_bytes()).hexdigest()
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
    report = (first / "REPORT.md").read_text()
    assert "SYNTHETIC FIXTURE ONLY" in report
    assert "<script>" not in report
    assert "source use unobserved" in report
    with pytest.raises(ValueError, match="not empty"):
        run_loaded_study(loaded, protocol, first, target_site="DSE")


def test_cli_requires_saved_protocol(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["wiki-fixture-audit", "--revisions", str(FIXTURES / "synthetic_revisions.jsonl"),
              "--manifest", str(FIXTURES / "manifest.json"),
              "--protocol", str(tmp_path / "missing.md"), "--output", str(tmp_path / "output")])
    assert error.value.code == 2
    assert not (tmp_path / "output").exists()
