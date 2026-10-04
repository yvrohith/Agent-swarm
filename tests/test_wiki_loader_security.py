"""Bound adversarial wiki inputs without changing valid release semantics."""

import gzip
import hashlib
import json
import subprocess
import sys

import pytest
from test_wiki_loader import publisher_revision, release_files

from tracebench import wiki_loader


@pytest.mark.parametrize("first,last", [(1, 10**10), (10**20, 10**20 + 2)])
def test_sparse_sequence_ids_reject_with_bounded_resources(tmp_path, first, last):
    rows = [publisher_revision(first, diff_base=None,
                               diff_base_reason=("page_created" if first == 1
                                                 else "earlier_revisions_not_published")),
            publisher_revision(last, diff_base=None,
                               diff_base_reason="earlier_revisions_not_published")]
    path = release_files(tmp_path, rows)
    # A regression must fail safely instead of exhausting the pytest host.
    script = """
import resource
import sys
from pathlib import Path
from tracebench.wiki_loader import load_release
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
try:
    load_release(Path(sys.argv[1]))
except ValueError as error:
    assert 'logical history is not contiguous' in str(error), str(error)
else:
    raise AssertionError('Sparse history accepted')
"""
    completed = subprocess.run([sys.executable, "-B", "-c", script, str(path)],
                               capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr


def test_large_contiguous_sequence_ids_remain_valid(tmp_path):
    first = 10**20
    rows = [publisher_revision(first, diff_base=None,
                               diff_base_reason="earlier_revisions_not_published"),
            publisher_revision(first + 1)]
    loaded = wiki_loader.load_release(release_files(tmp_path, rows))
    assert [r.revision_id for r in loaded.revisions] == [r["rev_id"] for r in rows]
    assert loaded.revisions[1].parent_id == loaded.revisions[0].revision_id
    assert loaded.source_manifest["pages_with_earlier_unpublished_revisions"] == 1


def supplement_bytes(encoding="utf-8"):
    return json.dumps({
        "recovered": "synthetic", "source": "Security regression fixture",
        "pages": [{"wiki": "syntheticwiki", "name": "Sandbox", "revisions": [
            {"seq": 1, "time": "2020-01-01T00:00:00Z", "added": ["café", "line two"]},
        ]}],
    }, ensure_ascii=False).encode(encoding)


def write_supplement(tmp_path, raw, form):
    if form == "plain":
        packed = raw
    elif form == "concatenated":
        middle = len(raw) // 2
        packed = gzip.compress(raw[:middle]) + gzip.compress(raw[middle:])
    else:
        packed = gzip.compress(raw)
        if form == "zero_padded":
            packed += b"\0" * 16
    path = tmp_path / ("other-wikis.json" if form == "plain" else "other-wikis.json.gz")
    path.write_bytes(packed)
    return path, packed


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
@pytest.mark.parametrize("form", ["plain", "gzip", "concatenated", "zero_padded"])
def test_exact_supplement_limits_preserve_bytes_and_snippets(tmp_path, monkeypatch, encoding, form):
    raw = supplement_bytes(encoding)
    path, packed = write_supplement(tmp_path, raw, form)
    monkeypatch.setattr(wiki_loader, "_MAX_SUPPLEMENT_INPUT_BYTES", len(packed))
    monkeypatch.setattr(wiki_loader, "_MAX_EXPANDED_BYTES", len(raw))
    revisions, provenance = wiki_loader._load_other_wikis(path)
    assert len(revisions) == 1
    assert revisions[0].text == "café\nline two"
    assert revisions[0].text_kind == "added_line_snippet"
    assert revisions[0].record_sha256 == hashlib.sha256(raw).hexdigest()
    assert provenance["supplied_file"] == {
        "name": path.name, "bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest(),
    }
    assert provenance["decoded_file"] == {
        "name": "other-wikis.json", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


@pytest.mark.parametrize("form", ["plain", "gzip", "concatenated", "zero_padded"])
def test_release_rejects_cumulative_supplement_expansion_before_parsing(tmp_path, monkeypatch, form):
    limit = 4096  # Above the tiny main release's expanded size.
    raw = supplement_bytes()
    raw += b" " * (limit + 1 - len(raw))
    path, _ = write_supplement(tmp_path, raw, form)
    monkeypatch.setattr(wiki_loader, "_MAX_EXPANDED_BYTES", limit)
    monkeypatch.setattr(wiki_loader, "_MAX_SUPPLEMENT_INPUT_BYTES", limit * 2)
    with pytest.raises(ValueError, match="Expanded supplement exceeds the bounded size limit"):
        wiki_loader.load_release(release_files(tmp_path), path)


@pytest.mark.parametrize("form", ["plain", "gzip", "concatenated", "zero_padded"])
def test_release_rejects_oversized_packed_supplement(tmp_path, monkeypatch, form):
    path, packed = write_supplement(tmp_path, supplement_bytes(), form)
    monkeypatch.setattr(wiki_loader, "_MAX_SUPPLEMENT_INPUT_BYTES", len(packed) - 1)
    with pytest.raises(ValueError, match="Supplement input exceeds the bounded size limit"):
        wiki_loader.load_release(release_files(tmp_path), path)


@pytest.mark.parametrize("damage", ["truncated", "crc", "trailing_junk"])
def test_invalid_gzip_is_never_accepted_as_a_partial_supplement(tmp_path, damage):
    packed = gzip.compress(supplement_bytes())
    if damage == "truncated":
        packed = packed[:-1]
    elif damage == "crc":
        packed = packed[:-8] + bytes([packed[-8] ^ 1]) + packed[-7:]
    else:
        packed += b"not a gzip member"
    path = tmp_path / "other-wikis.json.gz"
    path.write_bytes(packed)
    with pytest.raises((gzip.BadGzipFile, EOFError)):
        wiki_loader.load_release(release_files(tmp_path), path)
