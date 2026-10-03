"""Local, deterministic descriptive audit; never a source-use evaluation."""

import hashlib
import html
import json
from collections import Counter
from pathlib import Path

from .wiki_analysis import analyze_references, verify_evidence
from .wiki_loader import LoadedWiki


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _selection_key(pair: dict) -> tuple[str, str]:
    identity = json.dumps(pair["pair_key"], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(identity.encode()).hexdigest(), identity


def select_review(analysis: dict) -> dict:
    """Frozen hash selection, independent of convenience or hidden source use."""
    categories = {}
    audits = {(a["target"]["site"], a["target"]["revision_id"]): a
              for a in analysis["revision_audit"]}
    for status in ("inserted", "inherited_only"):
        eligible = sorted((p for p in analysis["pairs"] if p["status"] == status),
                          key=_selection_key)
        categories[status] = [{
            "selection_sha256": _selection_key(pair)[0],
            "candidate": pair,
            "target_attribution": audits[(pair["target"]["site"], pair["target"]["revision_id"])],
            "automated_check": "record locators, offsets, excerpts and time conditions verified",
            "ai_assisted_review": None,
            "human_review": {"reviewer": None, "date": None, "extraction_correct": None,
                             "notes": None},
        } for pair in eligible[:10]]
    return {
        "selection_rule": "first 10 per status by SHA256 compact UTF-8 JSON pair_key, then key",
        "review_scope": "observable extraction correctness only; source use remains unobserved",
        "independent_human_validation": False,
        "categories": categories,
    }


def _compact_review(review: dict) -> dict:
    """Retain links to all possible sources but avoid redistributing earlier text."""
    # The candidate itself keeps the target's small excerpts for extraction review.
    # Prior occurrences need only locators and offsets, not repeated body excerpts.
    compact = json.loads(_json(review))
    for entries in compact["categories"].values():
        for entry in entries:
            for occurrence in entry["candidate"]["prior_name_occurrences_all_supplied_sites"]:
                for span in occurrence["spans"]:
                    span.pop("excerpt", None)
    return compact


def _safe(value) -> str:
    return html.escape(str(value), quote=True)


def _report(result: dict, review: dict, cards: list[dict]) -> str:
    c = result["counts"]
    synthetic = result["source_kind"] == "synthetic_fixture"
    lines = [
        "# " + ("Synthetic fixture validation" if synthetic else "Public-wiki reference audit"),
        "",
        ("**SYNTHETIC FIXTURE ONLY. These are not public-incident measurements.**" if synthetic
         else "Exploratory, review-informed census of one pinned public export. "
              "True source use is unobserved."),
        "",
        "The descriptive target is newly inserted literal page-name references. It is separate "
        "from the simulator's direct, realized cross-run source selection. A reference may "
        "address a page without showing that its writer read it.",
        "",
        "## Counts and exclusions",
        "",
        "Pairs identify a target revision and referenced page title; repeated mentions count "
        "separately only as occurrences. Handles are observed labels, not runs.",
        "",
        "| Measurement | Count |", "| --- | ---: |",
    ]
    for key, value in c.items():
        if isinstance(value, int):
            lines.append(f"| {key.replace('_', ' ')} | {value:,} |")
    lines += ["", "The naive snapshot count already requires earlier source-page evidence but "
              "ignores target attribution eligibility. The eligible snapshot count isolates "
              "the comparison after those checks. Inherited-only content and excluded history "
              "are different reasons for a smaller inserted count; this is not a false-positive "
              "source-use rate.", "",
              f"Eligible snapshot pairs comprise **{c['inserted_reference_pairs']:,} inserted** "
              f"and **{c['inherited_only_pairs']:,} inherited-only** pairs. There are "
              f"**{c['excluded_or_ambiguous_pairs']:,} excluded/ambiguous** raw pairs. "
              "Reason counts below overlap.", ""]
    lines += ["Frozen generic/navigation exclusions: "
              + ", ".join(f"<code>{_safe(title)}</code>" for title in result["excluded_titles"])
              + ". Present in the target site's supplied title set: "
              + (", ".join(f"<code>{_safe(title)}</code>"
                           for title in result["excluded_titles_present"]) or "none") + ".",
              "", "Inserted-pair cross-handle statuses: "
              + ", ".join(f"{status}={count:,}" for status, count
                          in result["inserted_pair_cross_handle_counts"].items())
              + ". All have unresolved stable run identity, unknown exposure and unobserved use.", ""]
    for key in ("revision_exclusion_reasons", "revision_flags", "pair_exclusion_reasons"):
        lines += [f"### {key.replace('_', ' ').capitalize()}", "",
                  "| Reason | Count |", "| --- | ---: |"]
        lines += [f"| {_safe(reason)} | {number:,} |" for reason, number in c[key].items()]
        if not c[key]:
            lines.append("| None | 0 |")
        lines.append("")
    lines += ["## Evidence capabilities", "",
              "| Evidence type | Availability | Meaning and limits |",
              "| --- | --- | --- |"]
    for item in result["telemetry_inventory"]:
        lines.append(f"| {_safe(item['evidence_type'])} | {_safe(item['availability'])} | "
                     f"{_safe(item['meaning'])} {_safe(item['completeness_assurance'])} |")
    lines += ["", "Absent telemetry types are not empty complete streams. An absent record in "
              "an available stream also cannot establish that an event did not occur. Save or "
              "probe records do not establish a candidate source-page read; a posted assertion "
              "of reading is unverified. Exposure remains unknown, while source use remains "
              "unobserved even if exposure were later established.", "",
              "## Frozen extraction review", "",
              f"The sheet contains {len(review['categories']['inserted'])} inserted and "
              f"{len(review['categories']['inherited_only'])} inherited-only pairs selected by "
              "the frozen hash rule. All candidate locators, excerpts, offsets and eligible "
              "time conditions were checked mechanically before output. Human-review fields "
              "are blank; these checks are not independent human validation. See "
              "`review_sheet.json` for the selected cases and any separately labeled AI review.",
              "", "## Source-linked evidence cards", ""]
    for card in cards:
        target = card["target"]
        spans = card["inserted_spans"] if card["status"] == "inserted" else card["inherited_spans"]
        span = spans[0]
        lines += [f"### {_safe(card['status'])}: <code>{_safe(card['referenced_page'])}</code>", "",
                  f"Target <code>{_safe(target['revision_id'])}</code>, "
                  f"page <code>{_safe(target['page'])}</code>, "
                  f"time <code>{_safe(target['timestamp'])}</code>, "
                  f"observed handle <code>{_safe(target['observed_handle'])}</code>.", "",
                  f"Pinned record: <code>{_safe(target['source_file'])}</code>, "
                  f"line {target['source_line']}; SHA-256 "
                  f"<code>{target['record_sha256']}</code>. Title span "
                  f"[{span['start']}, {span['end']}); excerpt span "
                  f"[{span['context_start']}, {span['context_end']}).", "",
                  f"<pre>{_safe(span['excerpt'])}</pre>", "",
                  f"All {len(card['source_revisions'])} strictly earlier source-page revisions "
                  "are retained in `evidence_cards.json`; none is designated a direct source.", ""]
        if card["source_revisions"]:
            source = card["source_revisions"][0]
            lines += [f"First chronological source-page locator: "
                      f"<code>{_safe(source['revision_id'])}</code>, "
                      f"<code>{_safe(source['timestamp'])}</code>, "
                      f"<code>{_safe(source['source_file'])}</code> line {source['source_line']}.", ""]
        lines += [f"Cross-handle status: **{card['evidence']['cross_handle_status']}**; stable "
                  "identity unresolved; source-read request, authenticated delivery and context "
                  "evidence unavailable; exposure unknown; source use unobserved.", ""]
    lines += ["## Interpretation and limits", "",
              "The snapshot-to-insertion comparison measures sensitivity to attribution of "
              "cumulative text. It does not measure copying, collusion, exposure or causal use. "
              "Diff and evidence invariants are unit-test consequences, not discoveries. "
              "Character alignment is deterministic but not unique; partial history, conservative "
              "timestamp intervals, excluded recreations/restorations, quoted text, title "
              "collisions and alternative sources limit interpretation. First observed in this "
              "export is not global origin. Redacted handles do not support run reconstruction.", "",
              "This census has no sampling interval and no real-data precision, recall or theta. "
              "Raw files remain ignored. Source URLs, publisher checksums and retrieval provenance "
              "are in `../source_manifest.json`; frozen rules are in `../ANALYSIS.md`. "
              "`manifest.json` pins the rules, code and local outputs. Original synthetic and "
              "missing-receipt artifacts are preserved separately.", ""]
    return "\n".join(lines)


def run_loaded_study(loaded: LoadedWiki, protocol: Path, output: Path, *, target_site: str) -> dict:
    """Run after protocol freeze. Refuse to replace existing artifacts."""
    if not protocol.is_file():
        raise ValueError("A saved, frozen analysis protocol is required")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory is not empty; choose a fresh directory")
    protocol_hash = hashlib.sha256(protocol.read_bytes()).hexdigest()
    revisions = loaded.revisions + loaded.auxiliary_revisions
    analysis = analyze_references(revisions, target_site=target_site)
    verify_evidence(revisions, analysis)
    review = _compact_review(select_review(analysis))
    selected = review["categories"]["inserted"][:2] + review["categories"]["inherited_only"][:1]
    cards = [entry["candidate"] | {"target_attribution": entry["target_attribution"]}
             for entry in selected]
    result = {
        "study_type": "exploratory_descriptive_reference_audit",
        "source_kind": loaded.source_manifest["source_kind"],
        "counts": analysis["counts"], "settings": analysis["analysis_settings"],
        "excluded_titles": analysis["excluded_titles"],
        "excluded_titles_present": sorted({r.page for r in loaded.revisions if r.site == target_site}
                                          & set(analysis["excluded_titles"])),
        "inserted_pair_cross_handle_counts": dict(sorted(Counter(
            p["evidence"]["cross_handle_status"] for p in analysis["pairs"]
            if p["status"] == "inserted"
        ).items())),
        "telemetry_inventory": loaded.telemetry_inventory,
        "input_validation": loaded.source_manifest,
        "analysis_protocol_sha256": protocol_hash,
        "mechanical_verification": "all candidates checked; not independent human review",
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (("counts.json", result), ("review_sheet.json", review),
                        ("evidence_cards.json", cards)):
        (output / name).write_text(_json(value), encoding="utf-8")
    (output / "REPORT.md").write_text(_report(result, review, cards), encoding="utf-8")
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())}
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(Path(__file__).parent.glob("wiki_*.py"))}
    (output / "manifest.json").write_text(_json({
        "algorithm": "sha256", "files": files, "analysis_protocol_sha256": protocol_hash,
        "analysis_source_files": sources, "schema_version": 1,
    }), encoding="utf-8")
    return result
