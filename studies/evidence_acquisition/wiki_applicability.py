"""Four metadata-selected local wiki lookups; descriptive, never finite-world inference."""

import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from tracebench.wiki_analysis import (
    DEFAULT_EXCLUDED_TITLES,
    _pattern,
    _strictly_before,
    analyze_references,
)
from tracebench.wiki_loader import load_release

ROOT = Path(__file__).resolve().parents[2]
SALT = "wiki-acquisition-metadata-only-v1"
RULE = (
    "From DSE metadata only, rank eligible target revision identities by SHA256 of "
    "[salt,slot_kind,site,page,revision_id]. Select two distinct histories having exactly "
    "two retained revisions: a declared creation followed by its explicit child. Then "
    "select two distinct histories whose first retained revision is a declared missing-"
    "predecessor noncreation. For each target, choose a different nonnavigation source "
    "page with a strictly earlier timestamp interval, ranked by SHA256 of "
    "[salt,source,site,page]; choose its earliest strictly earlier revision as metadata "
    "evidence. Never inspect text, reference matches, gold, or retrieval outcomes for selection."
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pin(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locator(record):
    return {key: getattr(record, key) for key in (
        "site", "page", "revision_id", "timestamp", "parent_id", "is_creation",
        "source_file", "source_line", "record_sha256", "timestamp_uncertainty_seconds")}


def metadata_only(revisions):
    # Loader validates full release bytes, but selection receives no body or author.
    return tuple(replace(r, text=None, author=None) for r in revisions)


def select(metadata):
    if any(r.text is not None or r.author is not None for r in metadata):
        raise ValueError("Selection accepts metadata only")
    pages = defaultdict(list)
    for r in metadata:
        if r.site == "dse" and r.text_kind == "full_revision":
            pages[(r.site, r.page)].append(r)
    candidates = {"connected_two_revision_history": [], "published_history_gap": []}
    for history in pages.values():
        by_id = {r.revision_id: r for r in history}
        if len(history) == 2:
            for target in history:
                parent = by_id.get(target.parent_id)
                if parent and parent.is_creation and parent.parent_id is None and not target.is_creation:
                    candidates["connected_two_revision_history"].append(target)
        gaps = [r for r in history if not r.is_creation and r.parent_id is None
                and "missing_predecessor" in r.flags]
        candidates["published_history_gap"].extend(gaps)
    chosen, used = [], set()
    for kind, possibilities in candidates.items():
        picked = 0
        for target in sorted(possibilities, key=lambda r: pin([SALT, kind, r.site, r.page, r.revision_id])):
            if (target.site, target.page) in used:
                continue
            source_pages = [key for key, history in pages.items()
                            if key != (target.site, target.page)
                            and key[1] not in DEFAULT_EXCLUDED_TITLES
                            and any(_strictly_before(r, target) for r in history)]
            if not source_pages:
                continue  # Timestamp/title metadata eligibility, never an outcome filter.
            source_page = min(source_pages, key=lambda key: pin([SALT, "source", *key]))
            source = min((r for r in pages[source_page] if _strictly_before(r, target)),
                         key=lambda r: (r.timestamp, r.revision_id))
            chosen.append({"slot_kind": kind, "target": locator(target),
                           "parent_id": target.parent_id, "referenced_title": source.page,
                           "source_title_metadata": locator(source)})
            used.add((target.site, target.page))
            picked += 1
            if picked == 2:
                break
        if picked != 2:
            raise ValueError("Fewer than two metadata-eligible histories in a fixed slot; no outcome fallback")
    return chosen


def assess(target, page_records, source_metadata):
    """Use the unchanged classifier on the selected history and title metadata."""
    if source_metadata.text is not None:
        raise ValueError("Unretrieved source text must remain absent")
    analysis = analyze_references(tuple(page_records) + (source_metadata,), target_site=target.site)
    audit = next(a for a in analysis["revision_audit"]
                 if a["target"]["revision_id"] == target.revision_id
                 and a["target"]["site"] == target.site)
    title = source_metadata.page
    pair = next((p for p in analysis["pairs"]
                 if p["pair_key"] == [target.site, target.revision_id, title]), None)
    matches = [[m.start(), m.end()] for m in _pattern(title).finditer(target.text or "")]
    if not matches:
        status, basis = "ruled_out", "No bounded literal title in the retrieved target; no predecessor assumption required"
    elif pair is not None and pair["status"] == "inserted":
        status, basis = "established", "Unchanged classifier finds at least one inserted literal title span"
    elif pair is not None and pair["status"] == "inherited_only":
        status, basis = "ruled_out", "Every target literal match is inherited under the unchanged alignment rule"
    else:
        status, basis = "insufficient_data", "History/extraction exclusions or ambiguous spans prevent a fixed-rule classification"
    return {"status": status, "basis": basis, "target_matches": matches,
            "comparison_eligible": audit["eligible"], "flags": audit["flags"],
            "exclusion_reasons": audit["exclusion_reasons"],
            "pair_status": pair["status"] if pair else "no_target_literal_match",
            "inserted_spans": [[x["start"], x["end"]] for x in pair["inserted_spans"]] if pair else [],
            "inherited_spans": [[x["start"], x["end"]] for x in pair["inherited_spans"]] if pair else [],
            "ambiguous_spans": [[x["start"], x["end"]] for x in pair["ambiguous_spans"]] if pair else [],
            "gap_is_not_empty_predecessor": "missing_predecessor" in audit["exclusion_reasons"]}


def main():
    directory = Path(__file__).resolve().parent
    output_path = directory / "wiki_applicability.json"
    selection_path = ROOT / "artifacts/evidence-acquisition/wiki-applicability-selection.json"
    if output_path.exists() or selection_path.exists():
        raise ValueError("Refuse to overwrite fixed selection or completed descriptive results")
    source_manifest_path = ROOT / "studies/wiki_case_study/source_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text())
    archive = ROOT / source_manifest["archive"]["local_path"]
    if file_pin(archive) != source_manifest["archive"]["sha256"]:
        raise ValueError("Local archive differs from existing publisher-source integrity pin")
    loaded = load_release(archive)  # Validates export checksums; no network or census.
    metadata = metadata_only(loaded.revisions)
    choices = select(metadata)
    inputs = [archive, source_manifest_path, ROOT / "src/tracebench/wiki_loader.py",
              ROOT / "src/tracebench/wiki_analysis.py", ROOT / "src/tracebench/wiki_model.py"]
    selection = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "selection_rule": RULE,
                 "metadata_inventory_sha256": pin([locator(r) for r in metadata]),
                 "selected": choices,
                 "input_sha256": {str(p.relative_to(ROOT)): file_pin(p) for p in inputs},
                 "script_sha256": file_pin(Path(__file__)),
                 "body_access_during_selection": False,
                 "loader_note": "Existing pinned loader decoded/validated archive integrity; selection received metadata-only projections"}
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    with selection_path.open("x") as handle:
        json.dump(selection, handle, indent=2, sort_keys=True)
        handle.write("\n")
    # Selection has been retained before any example's acquisition/classification.
    actual = {(r.site, r.revision_id): r for r in loaded.revisions}
    by_metadata = {(r.site, r.revision_id): r for r in metadata}
    examples = []
    for choice in choices:
        queries = []

        def fetch(site, revision_id):
            record = actual.get((site, revision_id))
            queries.append({"site": site, "revision_id": revision_id,
                            "outcome": "retained_record" if record else "no_retained_record",
                            "record_sha256": record.record_sha256 if record else None,
                            "decoded_text_utf8_sha256": hashlib.sha256(record.text.encode()).hexdigest() if record else None,
                            "decoded_text_utf8_bytes": len(record.text.encode()) if record else 0})
            return record

        target = fetch(choice["target"]["site"], choice["target"]["revision_id"])
        fetched = {target.revision_id: target}
        if choice["parent_id"] is not None:
            parent = fetch(target.site, choice["parent_id"])
            if parent is not None:
                fetched[parent.revision_id] = parent
        page = [fetched.get(r.revision_id, r) for r in metadata
                if r.site == target.site and r.page == target.page]
        source = by_metadata[(choice["source_title_metadata"]["site"],
                              choice["source_title_metadata"]["revision_id"])]
        examples.append({**choice, "retrievals": queries, "retrieval_count": len(queries),
                         "parent_retrieval": "performed" if choice["parent_id"] is not None else
                         "not_issued: publisher supplies no retained predecessor pointer; history gap preserved",
                         "claim": "Target contains at least one inserted bounded literal occurrence of the referenced title under the existing rule",
                         **assess(target, page, source)})
    output = {"study_role": "secondary descriptive existing-wiki applicability, separate from finite experiment",
              "selection": selection, "selection_log": str(selection_path.relative_to(ROOT)),
              "selection_log_sha256": file_pin(selection_path),
              "completed_at_utc": datetime.now(timezone.utc).isoformat(),
              "examples": examples, "histories": len(examples),
              "retrievals": sum(e["retrieval_count"] for e in examples),
              "full_text_copied": False, "census_rerun": False,
              "claim_scope": "Case-sensitive bounded literal titles and unchanged SequenceMatcher insertion/inheritance rule; not authorship, exposure, or source use",
              "limitations": [
                  "Titles and target histories were selected mechanically from metadata; no efficiency advantage was tested or claimed.",
                  "Initial metadata reveals parent availability; gap slots require no invented empty predecessor.",
                  "No target match can rule out insertion without resolving a missing-history comparison; these are distinct facts.",
                  "No synthetic prior, finite natural-language world set, optimality claim or archive-irreducibility conclusion is applied to wiki text.",
                  "Integrity pins do not independently authenticate publisher truth or complete the published history.",
                  "Full raw texts remain only in the already local ignored pinned archive; no new text package was created."],
              "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0"}
    with output_path.open("x") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"histories": len(examples), "retrievals": output["retrievals"],
                      "outcomes": [{"slot": e["slot_kind"], "status": e["status"],
                                    "matches": len(e["target_matches"]),
                                    "comparison_eligible": e["comparison_eligible"]} for e in examples]}, indent=2))


if __name__ == "__main__":
    main()
