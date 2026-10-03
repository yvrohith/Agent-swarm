"""Controlled, full-text wiki fixtures; edits are never historical observations.

The completed census and matching rule are imported without mutation. Original
bytes and transformation maps belong only to evaluator-side provenance.
"""

import base64
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path

from ..investigator_utility.wiki_cases import _review_pages
from ..wiki_analysis import (
    DEFAULT_EXCLUDED_TITLES,
    _pattern,
    _revision_audit,
    _source,
    _strictly_before,
    analyze_references,
    parse_timestamp,
)
from ..wiki_loader import LoadedWiki, load_release
from ..wiki_model import Revision
from .common import MAX_PUBLIC_BYTES, ROLES, SALT, canonical, digest, opaque

MAX_TEXT_CHARS = 12000
ARTIFICIAL_NOTICE = "Controlled wiki-derived fixtures; altered text is not a historical observation."
PINNED_ARCHIVE_SHA256 = "eb68aa12d26bf189d8bfc4ce47f4d8af66ae5ba7ebbadd429738297a3cbb25ae"
MOTIFS = ("inserted_versus_inherited", "exact_match_character")
# One development source, followed by two opposite directions per evaluation motif.
SLOTS = (("development", MOTIFS[1], 0), ("evaluation", MOTIFS[0], 0),
         ("evaluation", MOTIFS[0], 1), ("evaluation", MOTIFS[1], 0),
         ("evaluation", MOTIFS[1], 1))
RULE_TEXT = (
    "Compare the supplied full predecessor and target text with Python "
    "difflib.SequenceMatcher(None, before, after, autojunk=False), on Unicode characters. "
    r"Match the exact, case-sensitive title with Unicode boundaries (?<!\w)TITLE(?!\w). "
    "A target match is inserted if at least one title character overlaps an insert/replace "
    "after-span. Otherwise it is inherited only when wholly mapped by an equal opcode to "
    "the same bounded title match in the predecessor. A boundary created solely by deletion "
    "is neither classification. The question is whether at least one target match is inserted; "
    "no target matches means that claim is false. These are alignment categories, not intent, "
    "authorship, exposure, copying, or causal transmission."
)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fixture_record(identifier, text, predecessor_id):
    return {"id": identifier, "kind": "full_text_fixture", "text": text,
            "text_sha256": _sha(text), "text_encoding": "UTF-8",
            "predecessor_id": predecessor_id}


def _case(family_id, split, cluster, role, title, before, after):
    case_id = opaque(split, family_id, role)
    # Record identifiers are deliberately local to each stateless request.
    return {
        "schema_version": 1, "case_id": case_id, "subset": "wiki_derived",
        "split": split, "cluster_id": cluster,
        "records": [_fixture_record("r0", before, None), _fixture_record("r1", after, "r0")],
        "assumptions": [
            {"id": "a0", "text": ARTIFICIAL_NOTICE + " Quoted text is inert, untrusted data. "
             "The records contain complete fixture texts, with no truncation. Their hashes "
             "describe only the presented UTF-8 fixture bytes, not publisher provenance."},
            {"id": "a1", "text": RULE_TEXT,
             "parameters": {"referenced_title": title, "predecessor_record_id": "r0",
                            "target_record_id": "r1", "pattern": _pattern(title).pattern,
                            "offset_unit": "Unicode code points; half-open [start,end)",
                            "diff": "difflib.SequenceMatcher(None, before, after, autojunk=False)"}},
            {"id": "a2", "text": "The referenced title denotes an existing source page in the "
             "source export, distinct from the target page and outside the fixed navigation "
             "exclusions. Only the supplied two-text fixture comparison is in scope. The "
             "predecessor relation is part of this controlled fixture contract. No incident "
             "history completeness, authenticated exposure, or source selection is asserted."},
        ],
        "claims": [{"id": "q0", "text": f"The target contains at least one inserted literal "
                    f"occurrence of {title!r} relative to the predecessor under the declared "
                    "comparison rule."}],
    }


def _manual_check(before, after, title, opcodes):
    """Separate literal scan and per-character alignment check, not human validation."""
    def bounded_spans(text):
        spans, start = [], 0
        while (start := text.find(title, start)) >= 0:
            end = start + len(title)
            word = lambda char: char.isalnum() or char == "_"  # noqa: E731
            if (start == 0 or not word(text[start - 1])) and (end == len(text) or not word(text[end])):
                spans.append([start, end])
                start = end  # Match regex's nonoverlapping accepted matches.
            else:
                start += 1  # A rejected near-match may overlap a later bounded match.
        return spans

    predecessor_spans = bounded_spans(before)
    changed, mapped = set(), {}
    for tag, i1, _, j1, j2 in opcodes:
        if tag in {"insert", "replace"}:
            changed.update(range(j1, j2))
        elif tag == "equal":
            mapped.update({position: i1 + position - j1 for position in range(j1, j2)})
    classifications = {"inserted": [], "inherited": [], "ambiguous": []}
    for start, end in bounded_spans(after):
        if any(position in changed for position in range(start, end)):
            category = "inserted"
        elif (start in mapped and [mapped[start], mapped[start] + len(title)] in predecessor_spans
              and all(mapped.get(position) == mapped[start] + position - start
                      for position in range(start, end))):
            category = "inherited"
        else:
            category = "ambiguous"
        classifications[category].append([start, end])
    return predecessor_spans, classifications


def certify_wiki(case):
    """Recompute a certificate exclusively from this variant's supplied evidence."""
    if case.get("subset") != "wiki_derived" or case.get("schema_version") != 1:
        raise ValueError("Wrong controlled wiki fixture schema")
    records = {record["id"]: record for record in case["records"]}
    assumptions = {item["id"]: item for item in case["assumptions"]}
    if len(records) != 2 or len(records) != len(case["records"]):
        raise ValueError("Exactly two uniquely identified full fixture texts are required")
    if (set(assumptions) != {"a0", "a1", "a2"}
            or not assumptions["a0"]["text"].startswith(ARTIFICIAL_NOTICE)
            or assumptions["a1"]["text"] != RULE_TEXT):
        raise ValueError("Controlled fixture notice or exact comparison rule missing")
    parameters = assumptions["a1"]["parameters"]
    title = parameters["referenced_title"]
    if not title or title in DEFAULT_EXCLUDED_TITLES or parameters["pattern"] != _pattern(title).pattern:
        raise ValueError("Invalid referenced title or matching rule")
    contract = _case("unused", "evaluation", "unused", "base", title, "", "")
    if case["assumptions"] != contract["assumptions"]:
        raise ValueError("Exact material assumptions or comparison parameters changed")
    if case["claims"] != contract["claims"]:
        raise ValueError("Primary claim differs from the declared title comparison")
    before_record, target = records[parameters["predecessor_record_id"]], records[parameters["target_record_id"]]
    if target["predecessor_id"] != before_record["id"] or before_record["predecessor_id"] is not None:
        raise ValueError("Inconsistent fixture predecessor")
    for record in records.values():
        if (record.get("kind") != "full_text_fixture" or not isinstance(record.get("text"), str)
                or record.get("text_encoding") != "UTF-8"
                or record.get("text_sha256") != _sha(record["text"])):
            raise ValueError("Invalid full fixture text or byte hash")
    before, after = before_record["text"], target["text"]
    if len(before) + len(after) > MAX_TEXT_CHARS:
        raise ValueError("Full-text comparison exceeds fixed character bound")
    # Apply the existing census implementation to this exact, declared comparison.
    # The private scaffold supplies only mechanical IDs/times and the explicit
    # title-existence assumption; it supplies no additional comparison text.
    fixture_page = "comparison_" + digest(title)[:16]
    revisions = (
        Revision("DSE", title, "s", "2026-01-01T00:00:00Z", "fixture", "", is_creation=True),
        Revision("DSE", fixture_page, "p", "2026-01-01T00:01:00Z", "fixture", before, is_creation=True),
        Revision("DSE", fixture_page, "t", "2026-01-01T00:02:00Z", "fixture", after, parent_id="p"),
    )
    analysis = analyze_references(revisions)
    pair = next((pair for pair in analysis["pairs"] if pair["pair_key"] == ["DSE", "t", title]), None)
    classifications = {name: [[span["start"], span["end"]] for span in pair[name + "_spans"]]
                       if pair else [] for name in ("inserted", "inherited", "ambiguous")}
    opcodes = [list(row) for row in SequenceMatcher(None, before, after, autojunk=False).get_opcodes()]
    predecessor_spans, independent = _manual_check(before, after, title, opcodes)
    if classifications != independent:
        raise ValueError("Frozen extraction disagrees with separate character-membership check")
    target_spans = [[match.start(), match.end()] for match in _pattern(title).finditer(after)]
    certificate = {
        "method": "unchanged census classifier plus separate character-membership check",
        "predecessor_text_sha256": _sha(before), "target_text_sha256": _sha(after),
        "predecessor_matches": predecessor_spans, "target_matches": target_spans,
        "opcodes": opcodes, "qualifying_spans": classifications["inserted"],
        "classifications": classifications, "independent_character_membership_check": independent,
        "independence_limit": "Both checks share Python SequenceMatcher alignment; no human validation.",
        "offset_unit": "Unicode code points; half-open [start,end)",
    }
    return {"case_id": case["case_id"], "claims": [{"id": "q0",
            "status": "established" if classifications["inserted"] else "ruled_out",
            "certificate": certificate}],
            "validation": {"public_case_sha256": digest(case), "valid_text_comparison": True,
                           "mechanical_check": True, "independent_human_validation": False}}


def _change(text, offset):
    old = text[offset]
    # Fixed same-length mutation; no normalization, truncation, or word-boundary edit.
    new = "Q" if old != "Q" else "Z"
    return text[:offset] + new + text[offset + 1:], {"offset": offset, "before": old, "after": new}


def _nuisance(text, span):
    # Nearest alphabetic character outside the title and its immediate boundaries,
    # within a frozen 80-character radius; ties prefer the lower offset.
    start, end = span
    eligible = [index for index, char in enumerate(text)
                if char.isalpha() and (start - 80 <= index < start - 1 or end + 1 <= index < end + 80)]
    if not eligible:
        raise ValueError("no_nearby_nuisance_character")
    index = min(eligible, key=lambda index: (min(abs(index - start), abs(index - end)), index))
    return _change(text, index)


def _make_family(pair, predecessor, target, split, motif, direction):
    title = pair["referenced_page"]
    before, after = predecessor.text, target.text
    source_span = (pair["inherited_spans"] if motif == MOTIFS[0] else pair["inserted_spans"])[0]
    span = [source_span["start"], source_span["end"]]
    if motif == MOTIFS[0]:
        occurrence = next(_pattern(title).finditer(before))
        changed, edit = _change(before, occurrence.start() + len(title) // 2)
        original, modified, changed_record = (before, after), (changed, after), "r0"
    else:
        changed, edit = _change(after, span[0] + len(title) // 2)
        original, modified, changed_record = (before, after), (before, changed), "r1"
    # Direction 0 starts with source snapshots; direction 1 starts with their one-character edit.
    base, decisive = (original, modified) if direction == 0 else (modified, original)
    nuisance, nuisance_edit = _nuisance(base[1], span)
    family_id = "f_" + digest([SALT, split, motif, pair["pair_key"]])[:24]
    cluster = "history_" + digest([target.site, target.page])[:24]
    versions = {"base": base, "irrelevant": (base[0], nuisance), "decisive": decisive}
    cases = [_case(family_id, split, cluster, role, title, *versions[role]) for role in ROLES]
    gold = [certify_wiki(case) for case in cases]
    statuses = [row["claims"][0]["status"] for row in gold]
    if statuses[0] != statuses[1] or statuses[0] == statuses[2]:
        raise ValueError("transformation_failed_certified_relationship")
    if any(row["claims"][0]["certificate"]["classifications"]["ambiguous"] for row in gold):
        raise ValueError("ambiguous_transformed_match")
    if any(len(canonical({key: case[key] for key in ("case_id", "records", "assumptions", "claims")}).encode())
           > MAX_PUBLIC_BYTES for case in cases):
        raise ValueError("serialized_public_evidence_exceeds_fixed_limit")
    decisive_edit = edit if direction == 0 else {"offset": edit["offset"], "before": edit["after"], "after": edit["before"]}
    family = {
        "family_id": family_id, "subset": "wiki_derived", "split": split, "cluster_id": cluster,
        "motif": motif, "variants": {role: case["case_id"] for role, case in zip(ROLES, cases, strict=True)},
        "transformations": {
            "base_from_source": [] if direction == 0 else [{"record_id": changed_record, **edit}],
            "irrelevant_from_base": [{"record_id": "r1", **nuisance_edit}],
            "decisive_from_base": [{"record_id": changed_record, **decisive_edit}],
            "mechanical_updates": "Recompute fixture UTF-8 hashes and unrelated opaque case IDs.",
            "semantic_change": "Change predecessor literal-title presence while retaining target and claim."
            if motif == MOTIFS[0] else "Create or remove a target literal title with one character.",
        },
        "provenance": {"pair_key": pair["pair_key"],
                       "endpoint_pages": [[target.site, target.page], [target.site, title]],
                       "original_predecessor": asdict(predecessor), "original_target": asdict(target),
                       "title_source_revisions": pair["source_revisions"],
                       "original_text_utf8_sha256": [_sha(before), _sha(after)],
                       "source_role": "Source material only; presented copies are controlled fixtures."},
    }
    return cases, gold, family



def _bounded_analysis(revisions, site, max_text_chars):
    """Apply existing rules after the fixed window bound, without a new census.

    The unchanged predecessor audit receives every revision of the page and the
    full by-ID/time maps. Thus earlier restoration, adjacency and timestamp checks
    retain their old scope. Only costly, irrelevant unbounded text comparisons
    and the old census's all-site prior-occurrence report are omitted here.
    """
    by_id = {(row.site, row.revision_id): row for row in revisions}
    times = {key: parse_timestamp(row.timestamp) for key, row in by_id.items()}
    pages = defaultdict(list)
    for row in revisions:
        if row.text_kind == "full_revision":
            pages[(row.site, row.page)].append(row)
    titles = sorted(page for title_site, page in pages
                    if title_site == site and page and page not in DEFAULT_EXCLUDED_TITLES)
    patterns = {title: _pattern(title) for title in titles}
    audits, pairs, prefilter = [], [], []
    for target in sorted((row for row in revisions if row.site == site and row.text_kind == "full_revision"),
                         key=lambda row: (row.page, row.revision_id)):
        parent = by_id.get((site, target.parent_id))
        reason = None
        if parent is None:
            reason = "no_full_actual_predecessor"
        elif parent.text is None or target.text is None:
            reason = "missing_full_text"
        elif len(parent.text) + len(target.text) > max_text_chars:
            reason = "full_text_character_limit"
        if reason:
            prefilter.append({"revision_key": [site, target.revision_id], "reason": reason})
            continue
        audit, predecessor, opcodes = _revision_audit(
            target, pages[(site, target.page)], by_id, times,
        )
        audits.append(audit)
        for title in titles:
            if title == target.page or title not in target.text:
                continue
            pattern = patterns[title]
            matches = list(pattern.finditer(target.text))
            if not matches:
                continue
            sources = sorted((source for source in pages[(site, title)] if _strictly_before(source, target)),
                             key=lambda row: (times[(row.site, row.revision_id)], row.revision_id))
            classifications = {"inserted": [], "inherited": [], "ambiguous": []}
            for match in matches:
                if not audit["eligible"] or not sources:
                    continue
                start, end = match.span()
                if any(start < right and left < end for left, right in audit["inserted_character_spans"]):
                    category = "inserted"
                else:
                    inherited = False
                    for tag, i1, _, j1, j2 in opcodes:
                        if tag == "equal" and j1 <= start and end <= j2:
                            old_start = i1 + start - j1
                            inherited = any(old.span() == (old_start, old_start + len(title))
                                            for old in pattern.finditer(predecessor.text))
                            break
                    category = "inherited" if inherited else "ambiguous"
                classifications[category].append({"start": start, "end": end})
            status = "excluded_or_ambiguous"
            if audit["eligible"] and sources:
                if classifications["inserted"]:
                    status = "inserted"
                elif classifications["inherited"] and not classifications["ambiguous"]:
                    status = "inherited_only"
            pairs.append({"pair_key": [site, target.revision_id, title], "referenced_page": title,
                          "status": status, "snapshot_spans": [
                              {"start": match.start(), "end": match.end()} for match in matches],
                          **{name + "_spans": spans for name, spans in classifications.items()},
                          "source_revisions": [_source(source) for source in sources]})
    return {"pairs": pairs, "revision_audit": audits, "prefiltered_windows": prefilter}


def _build(loaded: LoadedWiki, excluded_pages, *, max_text_chars=MAX_TEXT_CHARS):
    """Fixed design, with every rejected candidate and first applicable reason retained."""
    if type(max_text_chars) is not int or not 0 <= max_text_chars <= MAX_TEXT_CHARS:
        raise ValueError("Bound must not exceed fixed full-text character limit")
    site = "dse" if any(row.site == "dse" for row in loaded.revisions) else "DSE"
    analysis = _bounded_analysis(loaded.revisions, site, max_text_chars)
    by_id = {(row.site, row.revision_id): row for row in loaded.revisions}
    audits = {(row["target"]["site"], row["target"]["revision_id"]): row for row in analysis["revision_audit"]}
    candidates, rejected, counts = {motif: [] for motif in MOTIFS}, [], Counter()
    def reject(pair, reason):
        rejected.append({"pair_key": pair["pair_key"], "reason": reason})
        counts[reason] += 1

    for pair in analysis["pairs"]:
        target = by_id[tuple(pair["pair_key"][:2])]
        endpoints = {(target.site, target.page), (target.site, pair["referenced_page"])}
        audit = audits[(target.site, target.revision_id)]
        if pair["status"] not in {"inserted", "inherited_only"} or pair["ambiguous_spans"]:
            reject(pair, "frozen_extraction_excluded_or_ambiguous")
            continue
        if endpoints & excluded_pages:
            reject(pair, "previous_review_or_utility_history")
            continue
        if audit["predecessor"] is None:
            reject(pair, "no_full_actual_predecessor")
            continue
        predecessor = by_id[(target.site, audit["predecessor"]["revision_id"])]
        if predecessor.text is None or target.text is None:
            reject(pair, "missing_full_text")
            continue
        if len(predecessor.text) + len(target.text) > max_text_chars:
            reject(pair, "full_text_character_limit")
            continue
        pattern = _pattern(pair["referenced_page"])
        old_matches = list(pattern.finditer(predecessor.text))
        if (len(pair["snapshot_spans"]) != 1 or len(pair["referenced_page"]) < 3
                or (pair["status"] == "inherited_only" and len(old_matches) != 1)
                or (pair["status"] == "inserted" and old_matches)):
            reject(pair, "not_single_unambiguous_title_window")
            continue
        motif = MOTIFS[0] if pair["status"] == "inherited_only" else MOTIFS[1]
        candidates[motif].append((pair, predecessor, target))
    for entries in candidates.values():
        entries.sort(key=lambda row: (digest([SALT, "wiki", row[0]["pair_key"]]), row[0]["pair_key"]))
    cases, gold, families, selected, shortages, used_pages = [], [], [], [], [], set()
    transformation_rejections = set()
    transformation_checks = []
    for split, motif, direction in SLOTS:
        eligible = None
        for entry in candidates[motif]:
            pair, predecessor, target = entry
            endpoints = {(target.site, target.page), (target.site, pair["referenced_page"])}
            if endpoints & used_pages or tuple(pair["pair_key"]) in transformation_rejections:
                continue
            try:
                # Check both fixed directions before taking the first ranked eligible
                # window. Later ranked candidates need not be transformed to select it.
                for check_direction in (0, 1):
                    _make_family(pair, predecessor, target, "evaluation", motif, check_direction)
            except ValueError as error:
                reject(pair, str(error))
                transformation_rejections.add(tuple(pair["pair_key"]))
                continue
            transformation_checks.append(pair["pair_key"])
            eligible = entry
            break
        if eligible is None:
            shortages.append({"split": split, "motif": motif, "direction": direction})
            continue
        pair, predecessor, target = eligible
        triplet, labels, family = _make_family(pair, predecessor, target, split, motif, direction)
        endpoints = {(target.site, target.page), (target.site, pair["referenced_page"])}
        used_pages.update(endpoints)
        cases.extend(triplet)
        gold.extend(labels)
        families.append(family)
        selected.append({"family_id": family["family_id"], "split": split, "motif": motif,
                         "direction": direction, "pair_key": pair["pair_key"],
                         "endpoint_pages": sorted([list(page) for page in endpoints]),
                         "selection_sha256": digest([SALT, "wiki", pair["pair_key"]])})
    return {"cases": cases, "gold": gold, "families": families, "selection": {
        "selection_salt": SALT, "max_full_text_characters": max_text_chars,
        "max_public_bytes": MAX_PUBLIC_BYTES, "fixed_navigation_exclusions": list(DEFAULT_EXCLUDED_TITLES),
        "input_revisions": len(loaded.revisions), "candidate_pairs": len(analysis["pairs"]),
        "candidate_pair_scope": "Only actual predecessor/target windows within the fixed character bound; not a corpus census.",
        "prefiltered_windows": analysis["prefiltered_windows"],
        "window_prefilter_counts": dict(sorted(Counter(row["reason"] for row in analysis["prefiltered_windows"]).items())),
        "structurally_eligible_by_motif": {key: len(value) for key, value in candidates.items()},
        "transformation_certified_candidates": transformation_checks,
        "excluded_pages": sorted([list(page) for page in excluded_pages]),
        "exclusion_counts_first_applicable_reason": dict(sorted(counts.items())),
        "rejected_candidates": rejected, "selected": selected, "shortages": shortages,
        "selection_rule": "Rank SHA256 compact sorted-key JSON [new salt, wiki, pair_key]. "
        "Use fixed dev/stratum/direction slots; exclude all earlier review and utility endpoint "
        "histories; no endpoint history may recur across families/splits. In rank order require both "
        "directions to pass exact certificates before selection; record rejected candidates and "
        "stop at the first eligible unused history per slot. Unreached candidates are not "
        "transformation-certified. No model outcomes are read.",
        "known_prior_exposure": "The public corpus and completed census were previously available; "
        "page exclusions do not establish uncontaminated model training data.",
    }}


def build_wiki_families(root: Path):
    """Load the pinned local ZIP without regenerating or editing any corpus file."""
    root = Path(root)
    archive = root / "data/raw/wiki/full-wiki-logs.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PINNED_ARCHIVE_SHA256:
        raise ValueError("The existing wiki archive does not match the frozen publisher pin")
    review_path = root / "studies/wiki_case_study/results/review_sheet.json"
    excluded = _review_pages(json.loads(review_path.read_text()))
    selection_paths = [root / "studies/investigator_utility/frozen/selection.json",
                       root / "studies/investigator_utility/openrouter_v1/frozen/selection.json"]
    for path in selection_paths:
        prior = json.loads(path.read_text())["wiki"]
        excluded.update(tuple(page) for row in prior["selected"] for page in row["endpoint_pages"])
        excluded.update(tuple(page) for page in prior["excluded_pages"])
    result = _build(load_release(archive), excluded)
    result["selection"]["source_archive_sha256"] = PINNED_ARCHIVE_SHA256
    result["selection"]["exclusion_manifest_sha256"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [review_path, *selection_paths]
    }
    with zipfile.ZipFile(archive) as handle:
        name = next(name for name in handle.namelist() if Path(name).name == "revisions.jsonl")
        lines = handle.read(name).splitlines(keepends=True)
    for family in result["families"]:
        for field in ("original_predecessor", "original_target"):
            source = family["provenance"][field]
            raw_line = lines[source["source_line"] - 1]
            if hashlib.sha256(raw_line).hexdigest() != source["record_sha256"]:
                raise ValueError("Original publisher line differs from its loader hash")
            raw = json.loads(raw_line)
            body = raw["body"].encode("latin-1")
            if hashlib.sha256(body).hexdigest() != raw["body_sha256"]:
                raise ValueError("Original publisher body hash mismatch")
            source["original_jsonl_bytes_base64"] = base64.b64encode(raw_line).decode("ascii")
            source["original_body_bytes_base64"] = base64.b64encode(body).decode("ascii")
            source["publisher_body_sha256"] = raw["body_sha256"]
            source["publisher_body_encoding"] = raw["body_encoding"]
    return result
