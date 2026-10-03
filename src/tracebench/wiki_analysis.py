"""Descriptive literal-page-reference audit, separate from source-use evaluation.

No run identities, receipts, exposure, or source-use labels are reconstructed.
Input content is inert text. The canonical format is tested with synthetic data;
using it with a public release requires separate schema and provenance inspection.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from .wiki_model import Revision

DEFAULT_EXCLUDED_TITLES = (
    "HomePage", "RecentChanges", "SandBox", "WikiSandBox", "Help", "Index", "FrontPage",
)
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)\Z"
)


def parse_timestamp(value: str | None) -> datetime | None:
    """Accept explicit timezone-aware ISO timestamps only; never invent a zone."""
    if value is None or not _TIMESTAMP.fullmatch(value):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result if result.tzinfo is not None else None


def _key(revision: Revision) -> tuple[str, str]:
    return revision.site, revision.revision_id


def _source(revision: Revision) -> dict:
    return {
        "site": revision.site, "page": revision.page, "revision_id": revision.revision_id,
        "timestamp": revision.timestamp, "observed_handle": revision.author,
        "source_file": revision.source_file, "source_line": revision.source_line,
        "record_sha256": revision.record_sha256,
        "timestamp_uncertainty_seconds": revision.timestamp_uncertainty_seconds,
        "source_json_pointer": revision.source_json_pointer, "text_kind": revision.text_kind,
    }


def _bounds(revision: Revision):
    timestamp = parse_timestamp(revision.timestamp)
    uncertainty = revision.timestamp_uncertainty_seconds
    if timestamp is None or uncertainty is None:
        return None
    return (timestamp - timedelta(seconds=uncertainty),
            timestamp + timedelta(seconds=uncertainty))


def _strictly_before(source: Revision, target: Revision) -> bool:
    source_bounds, target_bounds = _bounds(source), _bounds(target)
    return bool(source_bounds and target_bounds and source_bounds[1] < target_bounds[0])


def _overlapping(left: Revision, right: Revision) -> bool:
    a, b = _bounds(left), _bounds(right)
    return bool(a and b and a[0] <= b[1] and b[0] <= a[1])


def _pattern(title: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(title) + r"(?!\w)")


def _span(text: str, start: int, end: int) -> dict:
    # A maximum 160-code-point excerpt; long titles keep their full separate span.
    left = max(0, start - 40)
    right = min(len(text), max(end, start + 80), left + 160)
    return {"start": start, "end": end, "matched_text": text[start:end],
            "context_start": left, "context_end": right, "excerpt": text[left:right]}


def _revision_audit(revision, page_revisions, by_id, times):
    flags = set(revision.flags)
    blockers = set()
    if revision.timestamp_uncertainty_seconds is None:
        flags.add("unknown_timestamp_uncertainty")
        blockers.add("ambiguous_predecessor_order")
    if "publisher_recreation" in flags or "publisher_revert" in flags:
        blockers.add("publisher_recreation_or_revert_not_new_authorship")
    timestamp = times[_key(revision)]
    if timestamp is None:
        flags.add("missing_timestamp" if revision.timestamp is None else "invalid_timestamp")
        blockers.add("unknown_target_timestamp")
    if revision.text is None:
        flags.add("missing_text")
        blockers.add("missing_text")
    if not revision.author or any("author" in flag and "redact" in flag for flag in flags):
        flags.add("missing_or_redacted_author")
    others = [r for r in page_revisions if r != revision]
    if any(_bounds(r) is None for r in others):
        flags.add("undated_same_page_revision")
        blockers.add("ambiguous_predecessor_order")
    if timestamp is not None and any(times[_key(r)] == timestamp for r in others):
        flags.add("tied_same_page_timestamp")
        blockers.add("ambiguous_predecessor_order")
    if any(_overlapping(r, revision) for r in others):
        flags.add("overlapping_same_page_timestamp_intervals")
        blockers.add("ambiguous_predecessor_order")
    earlier = [r for r in others if _strictly_before(r, revision)]
    parent = None
    if revision.parent_id is not None:
        parent = by_id.get((revision.site, revision.parent_id))
        if parent is None:
            flags.add("missing_predecessor")
            blockers.add("missing_predecessor")
        elif parent.page != revision.page:
            flags.add("wrong_page_predecessor")
            blockers.add("wrong_page_predecessor")
        elif parent.text_kind != "full_revision":
            flags.add("partial_predecessor_text")
            blockers.add("partial_predecessor_text")
        elif not _strictly_before(parent, revision):
            flags.add("nonpreceding_or_undated_predecessor")
            blockers.add("ambiguous_predecessor_order")
        elif earlier:
            latest_time = max(times[_key(r)] for r in earlier)
            latest = [r for r in earlier if times[_key(r)] == latest_time]
            if len(latest) != 1:
                flags.add("tied_predecessor_timestamp")
                blockers.add("ambiguous_predecessor_order")
            elif _key(latest[0]) != _key(parent):
                flags.add("nonadjacent_predecessor")
                blockers.add("nonadjacent_predecessor")
            elif any(r != parent and not _strictly_before(r, parent) for r in earlier):
                flags.add("ambiguous_latest_predecessor_interval")
                blockers.add("ambiguous_predecessor_order")
        if parent is not None and parent.text is None:
            flags.add("missing_predecessor_text")
            blockers.add("missing_predecessor_text")
        if revision.is_creation:
            flags.add("creation_with_predecessor")
            blockers.add("contradictory_creation_metadata")
    elif not revision.is_creation:
        flags.add("missing_predecessor")
        blockers.add("missing_predecessor")
    elif earlier:
        flags.add("creation_after_existing_revision")
        blockers.add("contradictory_creation_metadata")
    if parent is not None and parent.page == revision.page and revision.text is not None:
        if revision.text == parent.text:
            flags.add("duplicate_snapshot")
        elif any(r.text == revision.text for r in earlier if r != parent):
            flags.add("restoration_of_earlier_snapshot")
            blockers.add("restoration_not_new_authorship")
    before = parent.text if parent is not None and parent.text is not None else ""
    after = revision.text or ""
    if blockers:
        opcodes = []
    elif before == after:
        opcodes = [("equal", 0, len(before), 0, len(after))]
    elif not before:
        opcodes = [("insert", 0, 0, 0, len(after))]
    else:
        opcodes = SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    added = [[j1, j2] for tag, _, _, j1, j2 in opcodes if tag in ("insert", "replace")
             and j2 > j1] if not blockers else []
    audit = {"target": _source(revision), "eligible": not blockers,
             "flags": sorted(flags), "exclusion_reasons": sorted(blockers),
             "predecessor": _source(parent) if parent is not None else None,
             "inserted_character_spans": added}
    return audit, parent, opcodes


def _handle_status(target: Revision, sources: list[Revision]) -> str:
    def known(revision):
        return bool(revision.author) and not any(
            "author" in flag and "redact" in flag for flag in revision.flags
        )
    if not known(target) or any(not known(source) for source in sources):
        return "unknown"
    comparison = {source.author == target.author for source in sources}
    return "mixed" if len(comparison) > 1 else "same" if True in comparison else "different"


def analyze_references(
    revisions: tuple[Revision, ...], *, target_site: str = "DSE",
    excluded_titles: tuple[str, ...] = DEFAULT_EXCLUDED_TITLES,
) -> dict:
    """Audit fixed literal reference candidates, not true source-use edges.

    A pair is (target site, target revision ID, referenced same-site page title).
    Repeated occurrences collapse only for pair counts; occurrence spans remain.
    The naive count requires strict earlier source-page evidence but ignores target
    predecessor eligibility. Eligible snapshot pairs additionally pass attribution
    eligibility, allowing an extraction-only comparison apart from exclusions.
    """
    if not isinstance(revisions, tuple) or any(not isinstance(r, Revision) for r in revisions):
        raise TypeError("revisions must be a tuple of Revision observations")
    by_id = {_key(revision): revision for revision in revisions}
    if len(by_id) != len(revisions):
        raise ValueError("revision IDs must be unique within a site")
    for revision in revisions:
        uncertainty = revision.timestamp_uncertainty_seconds
        if uncertainty is not None and (not isinstance(uncertainty, (int, float))
                                        or uncertainty < 0 or uncertainty != uncertainty
                                        or uncertainty == float("inf")):
            raise ValueError("timestamp uncertainty must be finite nonnegative seconds or None")
    times = {_key(revision): parse_timestamp(revision.timestamp) for revision in revisions}
    pages = defaultdict(list)
    for revision in revisions:
        if revision.text_kind == "full_revision":
            pages[(revision.site, revision.page)].append(revision)
    targets = sorted((r for r in revisions if r.site == target_site and r.text_kind == "full_revision"),
                     key=lambda r: (r.page, r.revision_id))
    titles = sorted(page for site, page in pages if site == target_site and page
                    and page not in excluded_titles)
    patterns = {title: _pattern(title) for title in titles}
    pairs, audits = [], []
    # Index all supplied sites for earlier literal occurrences only. These do not
    # become source-page evidence and are not an origin/completeness assurance.
    occurrences = defaultdict(list)
    record_matches = defaultdict(dict)
    for revision in sorted(revisions, key=lambda r: (r.site, r.page, r.revision_id)):
        if revision.text is None:
            continue
        for title, pattern in patterns.items():
            if title not in revision.text:  # Exact necessary prefilter; matching rule unchanged.
                continue
            matches = list(pattern.finditer(revision.text))
            if matches:
                spans = [_span(revision.text, m.start(), m.end()) for m in matches]
                record_matches[_key(revision)][title] = matches
                occurrences[title].append((revision, spans))
    for target in targets:
        audit, parent, opcodes = _revision_audit(
            target, pages[(target.site, target.page)], by_id, times,
        )
        audits.append(audit)
        if target.text is None:
            continue
        target_time = times[_key(target)]
        for title, matches in record_matches[_key(target)].items():
            pattern = patterns[title]
            if title == target.page:
                continue
            sources = [source for source in pages[(target.site, title)]
                       if _strictly_before(source, target)]
            sources.sort(key=lambda r: (times[_key(r)], r.revision_id))
            flags = set(audit["flags"])
            reasons = set(audit["exclusion_reasons"])
            if not sources:
                reasons.add("no_strictly_earlier_same_site_source_page")
            if target_time is not None and any(
                times[_key(source)] == target_time for source in pages[(target.site, title)]
            ):
                flags.add("source_page_timestamp_tie")
            if any(_overlapping(source, target) for source in pages[(target.site, title)]):
                flags.add("overlapping_source_timestamp_intervals")
            if any(times[_key(source)] is None for source in pages[(target.site, title)]):
                flags.add("source_page_has_undated_revision")
            spans, inserted, inherited, ambiguous = [], [], [], []
            for match in matches:
                item = _span(target.text, match.start(), match.end())
                spans.append(item)
                if reasons:
                    continue
                overlaps = any(match.start() < end and start < match.end()
                               for start, end in audit["inserted_character_spans"])
                if overlaps:
                    inserted.append(item)
                    continue
                # An equal character span must also have been a bounded reference
                # before the edit. A deletion can create a boundary without adding
                # title characters; that case is explicitly ambiguous.
                was_bounded = False
                for tag, i1, _, j1, j2 in opcodes:
                    if tag == "equal" and j1 <= match.start() and match.end() <= j2:
                        old_start = i1 + match.start() - j1
                        was_bounded = parent is not None and any(
                            old.start() == old_start and old.end() == old_start + len(title)
                            for old in pattern.finditer(parent.text or "")
                        )
                        break
                (inherited if was_bounded else ambiguous).append(item)
            if ambiguous:
                flags.add("boundary_only_or_unmapped_reference")
            status = "excluded_or_ambiguous"
            if not reasons:
                if inserted:
                    status = "inserted"
                elif inherited and not ambiguous:
                    status = "inherited_only"
                else:
                    reasons.add("boundary_only_or_unmapped_reference")
            prior_occurrences = [
                {"record": _source(record), "spans": record_spans,
                 "temporal_status": "strictly_earlier" if _strictly_before(record, target)
                 else "nominal_earlier_uncertainty_unknown"}
                for record, record_spans in occurrences[title]
                if target_time is not None and times[_key(record)] is not None
                and (_strictly_before(record, target)
                     or (record.timestamp_uncertainty_seconds is None
                         and times[_key(record)] < target_time))
            ]
            pairs.append({
                "pair_key": [target.site, target.revision_id, title],
                "target": _source(target), "referenced_page": title,
                "status": status, "source_order_eligible": bool(sources),
                "flags": sorted(flags), "exclusion_reasons": sorted(reasons),
                "snapshot_spans": spans, "inserted_spans": inserted,
                "inherited_spans": inherited, "ambiguous_spans": ambiguous,
                "source_revisions": [_source(source) for source in sources],
                "prior_name_occurrences_all_supplied_sites": prior_occurrences,
                "evidence": {
                    "literal_reference": "observed", "newly_inserted_reference": bool(inserted),
                    "cross_handle_status": _handle_status(target, sources) if sources else "unknown",
                    "stable_identity": "unresolved", "request_evidence": "unavailable_for_source_reference",
                    "authenticated_delivery_evidence": "unavailable",
                    "authenticated_context_evidence": "unavailable",
                    "exposure": "unknown", "source_use": "unobserved",
                },
            })
    naive = [pair for pair in pairs if pair["source_order_eligible"]]
    inserted_pairs = [pair for pair in pairs if pair["status"] == "inserted"]
    matched_targets = {(p["target"]["site"], p["target"]["revision_id"]) for p in naive}
    inserted_targets = {(p["target"]["site"], p["target"]["revision_id"]) for p in inserted_pairs}
    def handles(selected):
        return {r.author for r in targets if r.author and _key(r) in selected
                and not any("author" in f and "redact" in f for f in r.flags)}
    counts = {
        "total_input_records": len(revisions),
        "total_input_revisions": sum(r.text_kind == "full_revision" for r in revisions),
        "auxiliary_added_line_records": sum(r.text_kind != "full_revision" for r in revisions),
        "target_revisions": len(targets),
        "eligible_target_revisions": sum(a["eligible"] for a in audits),
        "excluded_or_ambiguous_revisions": sum(not a["eligible"] for a in audits),
        "raw_snapshot_pairs_before_source_check": len(pairs),
        "excluded_source_order_pairs": sum(not p["source_order_eligible"] for p in pairs),
        "naive_snapshot_pairs": len(naive),
        "naive_snapshot_occurrences": sum(len(p["snapshot_spans"]) for p in naive),
        "eligible_snapshot_pairs": sum(p["status"] != "excluded_or_ambiguous" for p in pairs),
        "eligible_snapshot_occurrences": sum(len(p["snapshot_spans"]) for p in pairs
                                             if p["status"] != "excluded_or_ambiguous"),
        "inserted_reference_pairs": len(inserted_pairs),
        "inserted_reference_occurrences": sum(len(p["inserted_spans"]) for p in inserted_pairs),
        "target_revisions_with_snapshot_match": len(matched_targets),
        "target_revisions_with_inserted_reference": len(inserted_targets),
        "distinct_observed_handles": len(handles({_key(r) for r in targets})),
        "distinct_snapshot_target_handles": len(handles(matched_targets)),
        "distinct_inserted_target_handles": len(handles(inserted_targets)),
        "inherited_only_pairs": sum(p["status"] == "inherited_only" for p in pairs),
        "inherited_reference_occurrences": sum(len(p["inherited_spans"]) for p in pairs),
        "excluded_or_ambiguous_pairs": sum(p["status"] == "excluded_or_ambiguous" for p in pairs),
        "ambiguous_reference_occurrences": sum(len(p["ambiguous_spans"]) for p in pairs),
        "revision_exclusion_reasons": dict(sorted(Counter(
            reason for a in audits for reason in a["exclusion_reasons"]
        ).items())),
        "revision_flags": dict(sorted(Counter(flag for a in audits for flag in a["flags"]).items())),
        "pair_exclusion_reasons": dict(sorted(Counter(
            reason for p in pairs for reason in p["exclusion_reasons"]
        ).items())),
    }
    return {
        "counts": counts, "pairs": pairs, "revision_audit": audits,
        "excluded_titles": list(excluded_titles),
        "analysis_settings": {
            "target_site": target_site,
            "source_page_scope": "same-site full revisions; all strictly earlier intervals retained",
            "temporal_precedence": "source timestamp plus uncertainty < target timestamp minus uncertainty",
            "partial_records": "added-line snippets indexed for literal occurrences only; never targets/sources",
            "earlier_literal_occurrence_scope": "all supplied sites; no global-origin inference",
            "normalization": "none; case-sensitive exact Unicode strings",
            "matching_rule": r"(?<!\w) escaped literal page title (?!\w)",
            "offset_unit": "Unicode code points; half-open [start,end)",
            "pair_unit": "target site / target revision ID / referenced same-site page title",
            "diff": "difflib.SequenceMatcher characters, autojunk=False; insert/replace spans",
            "first_revision": "eligible only with explicit is_creation=True",
            "predecessor": "explicit same-page parent, strictly earlier and latest unambiguous",
            "restoration": "exact earlier non-immediate snapshot excluded from new attribution",
            "receipt_streams": "unavailable; no complete empty streams are synthesized",
            "stable_identity": "unresolved; handles are not run identities",
            "source_use": "unobserved; reference or posted read claim is not exposure/use",
        },
    }


def verify_evidence(revisions: tuple[Revision, ...], analysis: dict) -> None:
    """Mechanically resolve all output links and offsets; not independent review."""
    by_id = {_key(revision): revision for revision in revisions}
    def resolve(source):
        revision = by_id[(source["site"], source["revision_id"])]
        assert source == _source(revision), "source link does not match pinned record"
        return revision
    def check_span(revision, span):
        assert revision.text is not None
        start, end = span["start"], span["end"]
        assert 0 <= start < end <= len(revision.text)
        assert revision.text[start:end] == span["matched_text"]
        left, right = span["context_start"], span["context_end"]
        assert 0 <= left <= start < right <= len(revision.text)
        assert right - left <= 160
        assert revision.text[left:right] == span["excerpt"]
    for audit in analysis["revision_audit"]:
        target = resolve(audit["target"])
        if audit["predecessor"] is not None:
            parent = resolve(audit["predecessor"])
            if audit["eligible"]:
                assert (parent.site, parent.page) == (target.site, target.page)
                assert _strictly_before(parent, target)
        elif audit["eligible"]:
            assert target.is_creation
    for pair in analysis["pairs"]:
        target = resolve(pair["target"])
        for collection in ("snapshot_spans", "inserted_spans", "inherited_spans", "ambiguous_spans"):
            for span in pair[collection]:
                check_span(target, span)
                assert span["matched_text"] == pair["referenced_page"]
        for source in pair["source_revisions"]:
            revision = resolve(source)
            assert revision.site == target.site and revision.page == pair["referenced_page"]
            assert _strictly_before(revision, target)
        for occurrence in pair["prior_name_occurrences_all_supplied_sites"]:
            revision = resolve(occurrence["record"])
            if occurrence["temporal_status"] == "strictly_earlier":
                assert _strictly_before(revision, target)
            else:
                assert occurrence["temporal_status"] == "nominal_earlier_uncertainty_unknown"
                assert revision.timestamp_uncertainty_seconds is None
                assert parse_timestamp(revision.timestamp) < parse_timestamp(target.timestamp)
            for span in occurrence["spans"]:
                check_span(revision, span)
                assert span["matched_text"] == pair["referenced_page"]
        evidence = pair["evidence"]
        assert evidence["stable_identity"] == "unresolved"
        assert evidence["exposure"] == "unknown" and evidence["source_use"] == "unobserved"
        assert evidence["request_evidence"] == "unavailable_for_source_reference"
        assert all(evidence[field] == "unavailable" for field in (
            "authenticated_delivery_evidence", "authenticated_context_evidence",
        ))
