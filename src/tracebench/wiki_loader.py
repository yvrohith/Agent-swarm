"""Pinned synthetic fixtures and the inspected explorer-schema-2 public export.

This does not upgrade posted text or save/probe metadata to read receipts.
No input content is evaluated, rendered, or fetched. All source locators refer
to bytes of the caller-supplied pinned JSONL file.
"""

import gzip
import hashlib
import json
import math
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .wiki_model import Revision

PARSER_VERSION = "tracebench-wiki-fixture-v1"
RECORD_FIELDS = {
    "site", "page", "revision_id", "timestamp", "author", "text", "parent_id",
    "is_creation", "flags",
}
REQUIRED_FIELDS = {"site", "page", "revision_id", "timestamp", "author", "text"}


@dataclass(frozen=True)
class LoadedWiki:
    revisions: tuple[Revision, ...]
    source_manifest: dict
    telemetry_inventory: tuple[dict, ...]
    auxiliary_revisions: tuple[Revision, ...] = ()


def _unavailable(kind: str, meaning: str) -> dict:
    return {
        "evidence_type": kind, "availability": "unavailable",
        "provenance": "No authenticated records of this type in the synthetic fixture contract",
        "meaning": meaning, "linkage_reliability": "unknown",
        "completeness_assurance": "none; absence of a type is not an empty complete stream",
        "restrictions": "Do not infer negative events or verified source selection from absence",
    }


def fixture_inventory() -> tuple[dict, ...]:
    return (
        {
            "evidence_type": "revision_snapshots", "availability": "available_synthetic_only",
            "provenance": "Pinned, explicitly synthetic JSONL fixture",
            "meaning": "Recorded page contents, not necessarily newly authored text",
            "linkage_reliability": "Explicit fixture page/revision/parent identifiers; checked locally",
            "completeness_assurance": "No claim about any public corpus; missing fixture parents flagged",
            "restrictions": "No publisher schema or real-data continuity has been verified",
        },
        {
            "evidence_type": "observed_handles", "availability": "available_or_missing_by_record",
            "provenance": "Synthetic author fields, with missing/redacted cases",
            "meaning": "A posted handle is not stable run identity",
            "linkage_reliability": "Exact observed string only",
            "completeness_assurance": "none",
            "restrictions": "Do not identify owners, equate handles with runs, or repair redactions",
        },
        _unavailable("stable_run_identity", "Stable identity remains unresolved"),
        _unavailable("server_requests", "A posted assertion of reading is not a server request log"),
        _unavailable("authenticated_delivery", "A request does not establish successful delivery"),
        _unavailable("authenticated_context", "A delivery does not establish context insertion"),
        _unavailable("source_selection", "Direct realized source selection is unobserved"),
        _unavailable("publisher_events", "No publisher event schema was inspected; event types unknown"),
    )


def load_fixture(revisions_path: Path, manifest_path: Path) -> LoadedWiki:
    """Load only the documented synthetic schema and verify its exact byte pin.

    Real releases use the separate inspected ``load_release`` adapter, rather
    than silently treating fixture conventions as public corpus facts.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("source_kind") != "synthetic_fixture"
            or manifest.get("schema_version") != PARSER_VERSION):
        raise ValueError("Only explicitly synthetic fixture schema is supported; "
                         "a publisher export requires schema/provenance inspection")
    raw = revisions_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    expected = manifest.get("revision_file", {})
    if (expected.get("name") != revisions_path.name
            or expected.get("sha256") != digest or expected.get("bytes") != len(raw)):
        raise ValueError("Revision file name, byte length, or SHA-256 does not match its manifest")
    revisions, seen = [], set()
    for line_number, raw_line in enumerate(raw.splitlines(keepends=True), 1):
        if not raw_line.strip():
            raise ValueError(f"Blank JSONL record at line {line_number}; no silent exclusions")
        try:
            record = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid UTF-8 JSON record at line {line_number}") from error
        if (not isinstance(record, dict) or not REQUIRED_FIELDS <= record.keys()
                or not record.keys() <= RECORD_FIELDS):
            raise ValueError(f"Unsupported revision schema at line {line_number}")
        for field in ("site", "page", "revision_id"):
            if not isinstance(record[field], str) or not record[field]:
                raise ValueError(f"{field} must be a nonempty string at line {line_number}")
        for field in ("timestamp", "author", "text", "parent_id"):
            if record.get(field) is not None and not isinstance(record[field], str):
                raise ValueError(f"{field} must be a string or null at line {line_number}")
        if type(record.get("is_creation", False)) is not bool:
            raise ValueError(f"is_creation must be boolean at line {line_number}")
        flags = record.get("flags", [])
        if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
            raise ValueError(f"flags must be a list of strings at line {line_number}")
        identity = (record["site"], record["page"], record["revision_id"])
        if identity in seen:
            raise ValueError(f"Duplicate revision identity at line {line_number}")
        seen.add(identity)
        record["flags"] = tuple(flags)
        revisions.append(Revision(
            **record, source_file=revisions_path.name, source_line=line_number,
            record_sha256=hashlib.sha256(raw_line).hexdigest(),
        ))
    if expected.get("records") != len(revisions):
        raise ValueError("Parsed record count does not match the selected fixture manifest")
    observed = {
        "parser_version": PARSER_VERSION, "revision_file": expected,
        "source_kind": "synthetic_fixture", "publisher_origin_authenticated": False,
        "sha256_meaning": "Local integrity pin, not publisher authentication or completeness",
        "records": len(revisions), "sites": dict(sorted(Counter(r.site for r in revisions).items())),
        "pages": len({(r.site, r.page) for r in revisions}),
        "authors_missing_or_empty": sum(not r.author for r in revisions),
        "publisher_events_inspected": False, "publisher_checksums": None,
        "input_manifest": manifest,
    }
    return LoadedWiki(tuple(revisions), observed, fixture_inventory())


RELEASE_PARSER_VERSION = "tracebench-wiki-explorer-schema-2-v1"
_RELEASE_FILES = {"pages.jsonl", "revisions.jsonl", "events.jsonl", "labels.jsonl", "manifest.json"}
_MAX_EXPANDED_BYTES = 128 * 1024 * 1024


def release_inventory() -> tuple[dict, ...]:
    """Capabilities of the inspected release, without fabricating complete streams."""
    unavailable = []
    for kind, meaning in (
        ("stable_run_identity", "Observed labels do not identify stable runs or owners"),
        ("authenticated_delivery", "Save/probe success is not delivery of a source page to a target"),
        ("authenticated_context", "No authenticated source-page context-entry receipts supplied"),
        ("source_selection", "Direct realized source selection is unobserved"),
    ):
        entry = _unavailable(kind, meaning)
        entry["provenance"] = "Inspected explorer-schema-2 manifest, revisions, labels and events"
        unavailable.append(entry)
    return (
        {
            "evidence_type": "revision_snapshots", "availability": "available_with_history_gaps",
            "provenance": "Checksum-verified revisions.jsonl and pages.jsonl",
            "meaning": "Stored revision contents with explicit same-page diff bases",
            "linkage_reliability": "Publisher page/revision IDs and previous logical sequence checked",
            "completeness_assurance": "Published write-date cut only; earlier unpublished rows flagged",
            "restrictions": "Snapshots contain inherited text; a held revision is not proof of new authorship",
        },
        {
            "evidence_type": "observed_handles", "availability": "available_or_missing_by_record",
            "provenance": "Publisher label fields retained verbatim, including blanks and redactions",
            "meaning": "Observed posted handles only",
            "linkage_reliability": "Exact string comparison; IP prefixes are not identities",
            "completeness_assurance": "No stable identity assurance",
            "restrictions": "Do not infer owners or equate handles with runs",
        },
        {
            "evidence_type": "server_requests", "availability": "limited_save_and_probe_metadata",
            "provenance": "Revision request_time/action metadata and publisher probe/save events",
            "meaning": "Limited server evidence about saves and probes, not source-page reading",
            "linkage_reliability": "Save links use revision_ref; probes lack target source-read linkage",
            "completeness_assurance": "No complete general read-request stream; raw request logs not included",
            "restrictions": "Candidate source-read requests remain unavailable; posted read claims unverified",
        },
        {
            "evidence_type": "publisher_events", "availability": "available_selected_event_populations",
            "provenance": "Checksum-verified events.jsonl; save, delete, revert, probe schemas inspected",
            "meaning": "Overlapping publisher populations, not independent incident counts",
            "linkage_reliability": "Save revision references checked; recreation links may be derived",
            "completeness_assurance": "Population-specific release coverage only",
            "restrictions": "Do not add populations to estimate incidents or interpret omissions as non-events",
        },
        *unavailable,
    )


def _jsonl_records(data: bytes, name: str) -> list[tuple[dict, int, str]]:
    records = []
    for line_number, line in enumerate(data.splitlines(keepends=True), 1):
        if not line.strip():
            raise ValueError(f"Blank JSONL record in {name}:{line_number}")
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid JSON in {name}:{line_number}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object in {name}:{line_number}")
        records.append((value, line_number, hashlib.sha256(line).hexdigest()))
    return records


def _string(record: dict, field: str, *, nullable: bool = False) -> str | None:
    value = record.get(field)
    if nullable and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Publisher field {field} must be a string")
    return value


def _release_bytes(archive_path: Path) -> tuple[dict[str, bytes], dict]:
    """Read named archive members directly; never extract arbitrary archive paths."""
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or set(names) != _RELEASE_FILES | {"SHA256SUMS"}:
            raise ValueError("Unexpected or duplicate archive members for explorer-schema-2")
        if sum(item.file_size for item in archive.infolist()) > _MAX_EXPANDED_BYTES:
            raise ValueError("Release exceeds the bounded expanded-size limit")
        contents = {name: archive.read(name) for name in names}
    checksums = {}
    for line in contents["SHA256SUMS"].decode("ascii").splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.removeprefix("*")
        if name in checksums or name not in _RELEASE_FILES:
            raise ValueError("Unexpected or duplicate checksum entry")
        if hashlib.sha256(contents[name]).hexdigest() != digest:
            raise ValueError(f"Publisher SHA-256 mismatch for {name}")
        checksums[name] = digest
    if checksums.keys() != _RELEASE_FILES:
        raise ValueError("Publisher checksums do not cover every release file")
    return contents, checksums


def _body(record: dict) -> str:
    # explorer-schema-2 JSON stores source bytes via Latin-1 regardless of the
    # declared display encoding. Encoding the JSON body directly as UTF-8 breaks
    # every non-ASCII UTF-8 source hash in the inspected release.
    body = _string(record, "body")
    codec = {"ascii": "ascii", "utf8": "utf-8", "latin1": "latin-1"}.get(record.get("body_encoding"))
    if codec is None:
        raise ValueError("Unsupported publisher body encoding")
    try:
        source_bytes = body.encode("latin-1")
        decoded = source_bytes.decode(codec)
    except UnicodeError as error:
        raise ValueError("Publisher body cannot round-trip its declared encoding") from error
    if (len(source_bytes) != record.get("body_len")
            or hashlib.sha256(source_bytes).hexdigest() != record.get("body_sha256")):
        raise ValueError("Publisher body byte length or SHA-256 mismatch")
    return decoded


def _count_matches(actual: int, declared: dict, description: str) -> None:
    if not isinstance(declared, dict) or declared.get("value") != actual:
        raise ValueError(f"Publisher manifest count mismatch: {description}")


def load_release(archive_path: Path, other_wikis_path: Path | None = None) -> LoadedWiki:
    """Load the inspected public ZIP; checksums establish integrity, not complete history.

    This is separate from the synthetic Observation contract. No empty request or
    context arrays, stable run IDs, exposure edges or source-use labels are created.
    Optional other-wiki added-line snippets remain a separate, partial collection.
    """
    contents, checksums = _release_bytes(archive_path)
    manifest = json.loads(contents["manifest.json"])
    if manifest.get("tool_versions", {}).get("exporter") != "explorer-schema-2":
        raise ValueError("Unsupported publisher exporter version; schema inspection required")
    tables = {name: _jsonl_records(contents[name + ".jsonl"], name + ".jsonl")
              for name in ("pages", "revisions", "events", "labels")}
    for name in ("pages", "revisions", "labels"):
        _count_matches(len(tables[name]), manifest.get("counts", {}).get(name), name)
    page_records = {(r["wiki"], r["name"]): r for r, _, _ in tables["pages"]}
    if len(page_records) != len(tables["pages"]):
        raise ValueError("Duplicate publisher page identity")
    revisions, raw_by_id, page_sequences = [], {}, {}
    for record, line, digest in tables["revisions"]:
        for field in ("wiki", "name", "rev_id"):
            if not _string(record, field):
                raise ValueError(f"Publisher {field} must not be empty")
        site, page, revision_id = record["wiki"], record["name"], record["rev_id"]
        seq = record.get("seq")
        if type(seq) is not int or seq < 1:
            raise ValueError("Publisher revision sequence must be a positive integer")
        page_key = _string(record, "page_key")
        if revision_id != f"{page_key}@{seq}":
            raise ValueError("Publisher revision ID disagrees with page/sequence")
        key = (site, page)
        if key not in page_records or revision_id in raw_by_id:
            raise ValueError("Missing publisher page or duplicate revision identity")
        if page_records[key].get("page_key") != page_key:
            raise ValueError("Publisher page key disagrees with revision page key")
        sequences = page_sequences.setdefault(key, set())
        if seq in sequences:
            raise ValueError("Duplicate publisher page sequence")
        sequences.add(seq)
        raw_by_id[revision_id] = record
        uncertainty = record.get("uncertainty_seconds")
        if (type(uncertainty) not in (int, float) or not math.isfinite(uncertainty)
                or uncertainty < 0):
            raise ValueError("Publisher timestamp uncertainty must be finite and nonnegative")
        parent_id = _string(record, "diff_base", nullable=True)
        reason = record.get("diff_base_reason")
        if reason not in (None, "page_created", "earlier_revisions_not_published"):
            raise ValueError("Unsupported publisher diff-base reason")
        creation = reason == "page_created"
        if creation and (seq != 1 or parent_id is not None):
            raise ValueError("Contradictory publisher creation metadata")
        flags = []
        if reason == "earlier_revisions_not_published":
            if seq <= 1 or parent_id is not None:
                raise ValueError("Contradictory publisher earlier-history metadata")
            flags.append("missing_predecessor")
        elif not creation and parent_id != f"{page_key}@{seq - 1}":
            raise ValueError("Publisher diff base is not previous same-page sequence")
        if record.get("relation_type") == "first_recreation_of":
            flags.append("publisher_recreation")
        if record.get("request_action") == "revert":
            flags.append("publisher_revert")
        author = _string(record, "label", nullable=True)
        if author and author.startswith("[") and author.endswith("]"):
            flags.append("redacted_author")
        revisions.append(Revision(
            site=site, page=page, revision_id=revision_id,
            timestamp=_string(record, "time", nullable=True), author=author,
            text=_body(record), parent_id=parent_id, is_creation=creation,
            source_file="revisions.jsonl", source_line=line, record_sha256=digest,
            flags=tuple(flags), timestamp_uncertainty_seconds=uncertainty,
        ))
    for revision in revisions:
        if revision.parent_id is not None and revision.parent_id not in raw_by_id:
            raise ValueError("Publisher diff base points outside supplied revision history")
    for key, page in page_records.items():
        seqs = page_sequences.get(key, set())
        if not seqs or len(seqs) != page.get("n_revs"):
            raise ValueError("Publisher page revision count mismatch")
        if seqs != set(range(min(seqs), max(seqs) + 1)) or min(seqs) - 1 != page.get("n_revs_before"):
            raise ValueError("Publisher logical history is not contiguous within the declared cut")
    by_wiki = Counter(revision.site for revision in revisions)
    for wiki, n_revisions in by_wiki.items():
        declared = manifest.get("per_wiki", {}).get(wiki, {})
        _count_matches(n_revisions, declared.get("revisions"), f"{wiki} revisions")
        _count_matches(sum(key[0] == wiki for key in page_records), declared.get("pages"), f"{wiki} pages")
        if "body_bytes" in declared:
            _count_matches(sum(r["body_len"] for r in raw_by_id.values() if r["wiki"] == wiki),
                           declared["body_bytes"], f"{wiki} body bytes")
    if set(manifest.get("per_wiki", {})) != set(by_wiki):
        raise ValueError("Publisher per-wiki population mismatch")
    event_counts = Counter(record.get("event_type") for record, _, _ in tables["events"])
    if not event_counts.keys() <= {"save", "delete", "revert", "probe"}:
        raise ValueError("Unknown publisher event type")
    event_ids = [record.get("event_id") for record, _, _ in tables["events"]]
    if len(set(event_ids)) != len(event_ids) or any(not isinstance(x, str) for x in event_ids):
        raise ValueError("Missing or duplicate publisher event IDs")
    for kind in ("save", "delete", "revert", "probe"):
        _count_matches(event_counts[kind], manifest.get("population_counts", {}).get(kind), f"{kind} events")
    save_refs = [r.get("revision_ref") for r, _, _ in tables["events"] if r["event_type"] == "save"]
    if len(set(save_refs)) != len(save_refs) or set(save_refs) != set(raw_by_id):
        raise ValueError("Publisher save events do not match held revisions one-to-one")
    labels = [_string(r, "label") for r, _, _ in tables["labels"]]
    if len(set(labels)) != len(labels) or set(labels) != {r.author or "" for r in revisions}:
        raise ValueError("Publisher labels do not match revision labels")
    total_body_bytes = sum(r["body_len"] for r in raw_by_id.values())
    _count_matches(total_body_bytes, manifest.get("body_bytes", {}).get("total"), "body bytes")
    encoding_counts = dict(Counter(r["body_encoding"] for r in raw_by_id.values()))
    if "body_encoding" in manifest and manifest["body_encoding"].get("values") != encoding_counts:
        raise ValueError("Publisher body encoding counts do not match revision records")
    archive_bytes = archive_path.read_bytes()
    timestamps = sorted(r.timestamp for r in revisions if r.timestamp is not None)
    observed = {
        "parser_version": RELEASE_PARSER_VERSION, "source_kind": "publisher_export",
        "archive": {"name": archive_path.name, "bytes": len(archive_bytes),
                    "sha256": hashlib.sha256(archive_bytes).hexdigest()},
        "publisher_checksums": checksums, "internal_checksums_verified": True,
        "sha256_meaning": "Release integrity only; HTTPS acquisition provenance is recorded separately",
        "records": len(revisions), "pages": len(page_records), "sites": dict(sorted(by_wiki.items())),
        "labels": len(labels), "authors_missing_or_empty": sum(not r.author for r in revisions),
        "event_rows": len(tables["events"]), "event_type_counts": dict(sorted(event_counts.items())),
        "event_population_warning": manifest.get("population_counts", {}).get("never_sum"),
        "time_range": {"min": timestamps[0] if timestamps else None, "max": timestamps[-1] if timestamps else None},
        "pages_with_earlier_unpublished_revisions": sum(p["n_revs_before"] > 0 for p in page_records.values()),
        "body_bytes": total_body_bytes, "body_encoding_counts": encoding_counts,
        "body_hashes_verified": len(revisions),
        "text_decoding": "JSON body -> Latin-1 source bytes -> declared ascii/utf8/latin1 decode; no normalization",
        "offset_convention": "Python Unicode code points in decoded text",
        "publisher_cut": manifest.get("cut"), "publisher_generated_at": manifest.get("generated_at"),
        "publisher_database_sha256": manifest.get("db_sha256"),
        "publisher_checks_reported": manifest.get("checks", []),
        "publisher_events_inspected": True,
    }
    auxiliary, supplemental = _load_other_wikis(other_wikis_path) if other_wikis_path else ((), None)
    observed["other_wikis"] = supplemental
    return LoadedWiki(tuple(revisions), observed, release_inventory(), auxiliary)


def _load_other_wikis(path: Path) -> tuple[tuple[Revision, ...], dict]:
    """Preserve recovered added lines as snippets, never reconstruct snapshots."""
    packed = path.read_bytes()
    raw = gzip.decompress(packed) if path.suffix == ".gz" else packed
    value = json.loads(raw)
    if not isinstance(value, dict) or not {"recovered", "source", "pages"} <= value.keys():
        raise ValueError("Unsupported recovered other-wiki schema")
    digest = hashlib.sha256(raw).hexdigest()
    records, seen, pages = [], set(), set()
    for page_index, page in enumerate(value["pages"]):
        site, name = _string(page, "wiki"), _string(page, "name")
        if site in {"dse", "dorfwiki", "probier", "fractal"}:
            raise ValueError("Supplemental snippets cannot masquerade as full-snapshot release sites")
        key = (site, name)
        if key in pages:
            raise ValueError("Duplicate supplemental page identity")
        pages.add(key)
        for revision_index, row in enumerate(page["revisions"]):
            seq = row.get("seq")
            if type(seq) is not int or seq < 1 or (key, seq) in seen:
                raise ValueError("Invalid or duplicate supplemental sequence")
            seen.add((key, seq))
            added = row.get("added")
            if not isinstance(added, list) or any(not isinstance(line, str) for line in added):
                raise ValueError("Supplemental added lines must be strings")
            records.append(Revision(
                site=site, page=name, revision_id=f"{site}~{name}@{seq}:added",
                timestamp=_string(row, "time", nullable=True), author=None,
                text="\n".join(added), source_file="other-wikis.json", source_line=0,
                record_sha256=digest, flags=("partial_added_lines_only", "timestamp_uncertainty_unknown"),
                timestamp_uncertainty_seconds=None,
                source_json_pointer=f"/pages/{page_index}/revisions/{revision_index}/added",
                text_kind="added_line_snippet",
            ))
    return tuple(records), {
        "supplied_file": {"name": path.name, "bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest()},
        "decoded_file": {"name": "other-wikis.json", "bytes": len(raw), "sha256": digest},
        "pages": len(pages), "revision_snippets": len(records), "recovered": value["recovered"],
        "publisher_provenance": value["source"],
        "interpretation": "Added-line text only; removed lines are not indexed; no full bodies, labels or predecessor reconstruction",
        "time_uncertainty": "Not supplied; no strict temporal claim without an uncertainty bound",
        "locator_hash_scope": "record_sha256 pins entire decoded JSON file; source_json_pointer locates added-line array",
        "completeness_assurance": "Partial recovered rendering; absence of a match is not absence from those sites",
    }
