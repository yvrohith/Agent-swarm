import hashlib
import json
from pathlib import Path

import pytest

from tracebench.wiki_loader import PARSER_VERSION, load_fixture

FIXTURES = Path(__file__).parent / "fixtures" / "wiki"


def fixture_files(tmp_path, records):
    path = tmp_path / "records.jsonl"
    data = "".join(json.dumps(record) + "\n" for record in records).encode()
    path.write_bytes(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "source_kind": "synthetic_fixture", "schema_version": PARSER_VERSION,
        "revision_file": {"name": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                          "bytes": len(data), "records": len(records)},
    }))
    return path, manifest


def sample():
    return {"site": "DSE", "page": "AlphaPage", "revision_id": "1",
            "timestamp": "2020-01-01T00:00:00Z", "author": "fixture-author", "text": "Hello"}


def test_fixture_loader_pins_inert_records_without_fabricated_receipt_streams():
    loaded = load_fixture(FIXTURES / "synthetic_revisions.jsonl", FIXTURES / "manifest.json")
    assert len(loaded.revisions) == 23
    assert loaded.source_manifest["source_kind"] == "synthetic_fixture"
    assert not loaded.source_manifest["publisher_origin_authenticated"]
    assert any("<script>" in (r.text or "") for r in loaded.revisions)
    raw_lines = (FIXTURES / "synthetic_revisions.jsonl").read_bytes().splitlines(keepends=True)
    for revision in loaded.revisions:
        assert hashlib.sha256(raw_lines[revision.source_line - 1]).hexdigest() == revision.record_sha256
    inventory = {item["evidence_type"]: item for item in loaded.telemetry_inventory}
    for kind in ("server_requests", "authenticated_delivery", "authenticated_context", "source_selection"):
        assert inventory[kind]["availability"] == "unavailable"
        assert "none" in inventory[kind]["completeness_assurance"]
    assert not hasattr(loaded, "requests")
    assert not hasattr(loaded, "contexts")


def test_manifest_mismatch_rejected(tmp_path):
    path, manifest = fixture_files(tmp_path, [sample()])
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA-256"):
        load_fixture(path, manifest)


def test_unverified_public_schema_is_not_silently_accepted(tmp_path):
    path, manifest = fixture_files(tmp_path, [sample()])
    value = json.loads(manifest.read_text())
    value["source_kind"] = "publisher_export"
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="publisher export"):
        load_fixture(path, manifest)


@pytest.mark.parametrize("changes", [
    {"unexpected_request_log": []}, {"author": {}}, {"page": ""},
    {"timestamp": 123}, {"is_creation": "yes"}, {"flags": "redacted"},
])
def test_unsupported_records_fail_closed_without_silent_exclusions(tmp_path, changes):
    path, manifest = fixture_files(tmp_path, [sample() | changes])
    with pytest.raises(ValueError):
        load_fixture(path, manifest)


def test_duplicate_revision_identity_rejected_but_missing_author_retained(tmp_path):
    record = sample() | {"author": None}
    path, manifest = fixture_files(tmp_path, [record])
    assert load_fixture(path, manifest).revisions[0].author is None
    path, manifest = fixture_files(tmp_path, [record, record])
    with pytest.raises(ValueError, match="Duplicate revision"):
        load_fixture(path, manifest)


def test_count_mismatch_rejected(tmp_path):
    path, manifest = fixture_files(tmp_path, [sample()])
    value = json.loads(manifest.read_text())
    value["revision_file"]["records"] = 12
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="record count"):
        load_fixture(path, manifest)


# Tiny fictional records matching the inspected publisher schema; no public
# corpus rows or bodies are redistributed in test fixtures.
def publisher_revision(seq=1, **changes):
    raw = b"Source text."
    return {
        "wiki": "dse", "name": "FictionalPage", "page_key": "dse~FictionalPage",
        "rev_id": f"dse~FictionalPage@{seq}", "seq": seq,
        "body": raw.decode("latin1"), "body_encoding": "ascii",
        "body_len": len(raw), "body_sha256": hashlib.sha256(raw).hexdigest(),
        "time": f"2020-01-01T00:0{seq}:00Z", "uncertainty_seconds": 1,
        "label": "fictional-handle", "diff_base": f"dse~FictionalPage@{seq - 1}" if seq > 1 else None,
        "diff_base_reason": None if seq > 1 else "page_created",
        "relation_type": None, "request_action": "form_edit",
        "request_time": f"2020-01-01T00:0{seq}:00Z",
    } | changes


def release_files(tmp_path, records=None, manifest_changes=None, extra_members=None,
                  checksum_mismatch=False):
    import zipfile

    records = records if records is not None else [publisher_revision()]
    by_page = {}
    for r in records:
        by_page.setdefault((r["wiki"], r["name"]), []).append(r)
    pages = [{"wiki": site, "name": name, "page_key": rows[0]["page_key"],
              "n_revs": len(rows), "n_revs_before": min(row["seq"] for row in rows) - 1}
             for (site, name), rows in by_page.items()]
    labels = [{"label": label} for label in sorted({r["label"] for r in records})]
    events = [{"event_id": f"save:{r['rev_id']}", "event_type": "save", "revision_ref": r["rev_id"]}
              for r in records]
    events.append({"event_id": "probe:fictional:1", "event_type": "probe",
                   "request_action": "browse-bare", "success_observed": False})
    manifest = {
        "tool_versions": {"exporter": "explorer-schema-2"},
        "counts": {k: {"value": len(v)} for k, v in
                   (("revisions", records), ("pages", pages), ("labels", labels))},
        "per_wiki": {site: {"revisions": {"value": sum(r["wiki"] == site for r in records)},
                            "pages": {"value": sum(p["wiki"] == site for p in pages)}}
                     for site in {r["wiki"] for r in records}},
        "population_counts": {"save": {"value": len(records)}, "probe": {"value": 1},
                              "delete": {"value": 0}, "revert": {"value": 0}},
        "body_bytes": {"total": {"value": sum(r["body_len"] for r in records)}},
    } | (manifest_changes or {})
    contents = {name + ".jsonl": "".join(json.dumps(r) + "\n" for r in rows).encode()
                for name, rows in (("pages", pages), ("revisions", records),
                                   ("events", events), ("labels", labels))}
    contents["manifest.json"] = json.dumps(manifest).encode()
    checksums = "".join(hashlib.sha256(value).hexdigest() + "  " + name + "\n"
                        for name, value in contents.items())
    contents["SHA256SUMS"] = checksums.encode()
    if checksum_mismatch:
        contents["revisions.jsonl"] += b"\n"
    contents.update(extra_members or {})
    path = tmp_path / "release.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
    return path


def test_publisher_revision_history_and_unavailable_read_receipts(tmp_path):
    from tracebench.wiki_loader import load_release

    loaded = load_release(release_files(tmp_path, [publisher_revision(), publisher_revision(2)]))
    assert loaded.revisions[0].is_creation
    assert loaded.revisions[1].parent_id == loaded.revisions[0].revision_id
    assert loaded.revisions[1].timestamp_uncertainty_seconds == 1
    assert loaded.source_manifest["internal_checksums_verified"]
    assert loaded.source_manifest["body_hashes_verified"] == 2
    inventory = {row["evidence_type"]: row for row in loaded.telemetry_inventory}
    assert inventory["server_requests"]["availability"] == "limited_save_and_probe_metadata"
    assert inventory["authenticated_context"]["availability"] == "unavailable"
    assert inventory["authenticated_delivery"]["availability"] == "unavailable"
    assert not hasattr(loaded, "contexts") and not hasattr(loaded, "requests")


@pytest.mark.parametrize("encoding,raw,text", [
    ("ascii", b"<script>never_execute()</script>", "<script>never_execute()</script>"),
    ("utf8", "Fictional café".encode("utf-8"), "Fictional café"),
    ("latin1", b"Fictional caf\xe9", "Fictional café"),
])
def test_publisher_byte_preserving_bodies_decode_after_hash_check(tmp_path, encoding, raw, text):
    from tracebench.wiki_loader import load_release

    row = publisher_revision(body=raw.decode("latin1"), body_encoding=encoding,
                             body_len=len(raw), body_sha256=hashlib.sha256(raw).hexdigest())
    loaded = load_release(release_files(tmp_path, [row]))
    assert loaded.revisions[0].text == text
    assert loaded.source_manifest["offset_convention"] == "Python Unicode code points in decoded text"


def test_publisher_gapped_cut_never_becomes_creation(tmp_path):
    from tracebench.wiki_loader import load_release

    row = publisher_revision(3, diff_base=None, diff_base_reason="earlier_revisions_not_published")
    loaded = load_release(release_files(tmp_path, [row]))
    assert not loaded.revisions[0].is_creation
    assert "missing_predecessor" in loaded.revisions[0].flags
    assert loaded.source_manifest["pages_with_earlier_unpublished_revisions"] == 1


def test_publisher_redactions_and_recreation_flags_retained(tmp_path):
    from tracebench.wiki_loader import load_release

    row = publisher_revision(label="[Admin1]", relation_type="first_recreation_of", request_action="revert")
    revision = load_release(release_files(tmp_path, [row])).revisions[0]
    assert revision.author == "[Admin1]"
    assert set(revision.flags) == {"redacted_author", "publisher_recreation", "publisher_revert"}


def test_publisher_escaped_page_keys_are_not_reconstructed(tmp_path):
    from tracebench.wiki_loader import load_release

    row = publisher_revision(name="Fictional/Page", page_key="dse~Fictional~2fPage",
                             rev_id="dse~Fictional~2fPage@1")
    revision = load_release(release_files(tmp_path, [row])).revisions[0]
    assert revision.page == "Fictional/Page"
    assert revision.revision_id == "dse~Fictional~2fPage@1"


@pytest.mark.parametrize("changes,error", [
    ({"body_sha256": "0" * 64}, "body byte length or SHA-256"),
    ({"body_encoding": "unknown"}, "encoding"),
    ({"uncertainty_seconds": -1}, "uncertainty"),
    ({"diff_base_reason": "guessed"}, "diff-base reason"),
    ({"rev_id": "dse~FictionalPage@9"}, "revision ID"),
    ({"diff_base": "dse~WrongPage@0"}, "creation metadata"),
])
def test_publisher_inconsistent_records_fail_closed(tmp_path, changes, error):
    from tracebench.wiki_loader import load_release

    path = release_files(tmp_path, [publisher_revision(**changes)])
    with pytest.raises(ValueError, match=error):
        load_release(path)


def test_publisher_pin_counts_schema_and_archive_paths_are_checked(tmp_path):
    from tracebench.wiki_loader import load_release

    with pytest.raises(ValueError, match="SHA-256"):
        load_release(release_files(tmp_path, checksum_mismatch=True))
    with pytest.raises(ValueError, match="count mismatch"):
        load_release(release_files(tmp_path, manifest_changes={"counts": {"pages": {"value": 123}}}))
    with pytest.raises(ValueError, match="exporter version"):
        load_release(release_files(tmp_path, manifest_changes={"tool_versions": {"exporter": "unknown"}}))
    with pytest.raises(ValueError, match="archive members"):
        load_release(release_files(tmp_path, extra_members={"../unsafe.txt": b"never extracted"}))
    assert not (tmp_path.parent / "unsafe.txt").exists()


def test_publisher_duplicate_revision_ids_fail_closed(tmp_path):
    from tracebench.wiki_loader import load_release

    row = publisher_revision()
    with pytest.raises(ValueError, match="duplicate revision"):
        load_release(release_files(tmp_path, [row, row]))


def test_supplemental_added_lines_are_not_reconstructed_into_full_snapshots(tmp_path):
    import gzip

    from tracebench.wiki_loader import load_release

    payload = {"recovered": "2020-02-01", "source": "Explicitly synthetic recovered rendering fixture",
               "pages": [{"wiki": "publictestwiki", "name": "Sandbox", "revisions": [
                   {"seq": 1, "time": "2020-01-01T00:00:00Z", "added": ["AlphaPage", "line two"],
                    "removed": ["Never invent this full body"], "append": False},
               ]}]}
    raw = json.dumps(payload).encode()
    other = tmp_path / "other-wikis.json.gz"
    other.write_bytes(gzip.compress(raw))
    loaded = load_release(release_files(tmp_path), other)
    assert len(loaded.revisions) == len(loaded.auxiliary_revisions) == 1
    snippet = loaded.auxiliary_revisions[0]
    assert snippet.text == "AlphaPage\nline two"
    assert snippet.text_kind == "added_line_snippet"
    assert snippet.author is None and snippet.parent_id is None and not snippet.is_creation
    assert snippet.timestamp_uncertainty_seconds is None
    assert snippet.source_json_pointer == "/pages/0/revisions/0/added"
    assert snippet.record_sha256 == hashlib.sha256(raw).hexdigest()
    assert "no full bodies" in loaded.source_manifest["other_wikis"]["interpretation"]
