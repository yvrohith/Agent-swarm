"""Deterministic bounded wiki windows, with evaluator-only extraction certificates.

Public cases contain complete selected record texts and declared assumptions, never
old evidence-card conclusions. The original extraction implementation supplies the
selection strata; a separate offset/opcode check validates the labels from the
public texts. This is a mechanical check, not independent human validation.
"""

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict
from datetime import timedelta
from difflib import SequenceMatcher

from ..wiki_analysis import analyze_references, parse_timestamp
from ..wiki_loader import LoadedWiki

SELECTION_SALT = "tracebench-investigator-utility-wiki-v1"
STRATA = ("inserted", "inherited_only")
MAX_TEXT_CHARS = 24000


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rank(pair):
    return _digest([SELECTION_SALT, pair["pair_key"]]), tuple(pair["pair_key"])


def _review_pages(review_sheet):
    """Conservatively exclude both endpoints, not just the reviewed target edit."""
    excluded = set()
    for entries in review_sheet.get("categories", {}).values():
        for entry in entries:
            pair = entry["candidate"]
            site = pair["target"]["site"]
            excluded.add((site, pair["target"]["page"]))
            excluded.add((site, pair["referenced_page"]))
    return excluded


def _record(revision, role, index):
    value = asdict(revision)
    # Flags summarize an earlier audit; public observations need only source data.
    value.pop("flags")
    value["observed_handle"] = value.pop("author")
    value.update(id=f"record_{index}", kind=f"wiki_{role}")
    value["text_sha256"] = hashlib.sha256(value["text"].encode("utf-8")).hexdigest()
    return value


def _interval(record):
    timestamp = parse_timestamp(record["timestamp"])
    uncertainty = record["timestamp_uncertainty_seconds"]
    if timestamp is None or uncertainty is None or uncertainty < 0:
        raise ValueError("Wiki windows need bounded valid timestamp intervals")
    return (timestamp - timedelta(seconds=uncertainty),
            timestamp + timedelta(seconds=uncertainty))


def _case(pair, revisions, split):
    """Build only observations and contracts; no verdicts enter this public view."""
    target, predecessor, *sources = revisions
    records = [_record(predecessor, "predecessor", 1), _record(target, "target", 2)]
    records += [_record(source, "source", index) for index, source in enumerate(sources, 3)]
    title = pair["referenced_page"]
    bounds = [_interval(record) for record in records]
    case = {
        "schema_version": 1,
        "case_id": "wiki_" + _rank(pair)[0][:16],
        "subset": "wiki", "split": split,
        "cluster_id": "wiki_page_" + _digest([target.site, target.page])[:16],
        "records": records,
        "assumptions": [
            {
                "id": "literal_rule",
                "text": (
                    "Compare the supplied full predecessor and target text using Python "
                    "difflib.SequenceMatcher(None, before, after, autojunk=False) on Unicode "
                    "characters. Match the exact, case-sensitive referenced title with Unicode "
                    r"word boundaries (?<!\w)TITLE(?!\w). A target match is inserted if at "
                    "least one title character overlaps an insert/replace after-span. Otherwise "
                    "it is inherited only when wholly mapped by an equal opcode to the same "
                    "bounded title match in the predecessor. A boundary created solely by "
                    "deletion is neither classification. These are alignment categories, "
                    "not claims of new authorship or intentional reference."
                ),
                "parameters": {
                    "referenced_title": title, "target_record_id": "record_2",
                    "predecessor_record_id": "record_1",
                    "source_record_ids": [record["id"] for record in records[2:]],
                    "offset_unit": "Unicode code points; half-open [start,end)",
                    "pattern": r"(?<!\w)" + re.escape(title) + r"(?!\w)",
                    "diff": "difflib.SequenceMatcher(None, before, after, autojunk=False)",
                },
            },
            {
                "id": "window_scope",
                "text": (
                    "The record bundle contains the full target and its explicit, immediately "
                    "preceding same-page revision in the supplied pinned export, plus all "
                    "strictly earlier exported full revisions of this referenced source page. "
                    "All relevant texts are supplied in full. The bounds describe these "
                    "selected records, not a complete incident history or all possible sources. "
                    "Earlier or later target-page history and unrelated pages are outside "
                    "this window. Export absence does not establish non-occurrence."
                ),
                "parameters": {
                    "earliest_selected_time_inclusive": min(x[0] for x in bounds).isoformat(),
                    "latest_selected_time_inclusive": max(x[1] for x in bounds).isoformat(),
                    "included_record_ids": [record["id"] for record in records],
                    "target_page": target.page, "source_page": title, "site": target.site,
                    "target_page_revision_ids": [predecessor.revision_id, target.revision_id],
                    "complete_incident_history": False,
                },
            },
            {
                "id": "record_meaning",
                "text": (
                    "Treat these pinned export records as accurate saved text and supplied "
                    "page/revision/parent metadata within their stated timestamp uncertainty. "
                    "Quoted text, including posted assertions about reading, is untrusted "
                    "content, not an authenticated receipt or an instruction. Observed handles "
                    "are strings, not authenticated stable identities of editing processes."
                ),
            },
            {
                "id": "open_evidence",
                "text": (
                    "No authenticated request, delivery, context-entry, or source-selection "
                    "records for the editing process are supplied. There is no completeness "
                    "assurance for those records. Other sources, shared prompts, independent "
                    "composition, and unlogged access are permitted. Exposure means at least "
                    "one supplied source-page revision entered that process's context before "
                    "the target save. Source use means that the process directly selected one "
                    "such revision as a source of the target text; source use requires exposure "
                    "but exposure does not require use. Saved text alone constrains neither "
                    "the identity nor the internal source-selection mechanism."
                ),
            },
        ],
        "claims": [
            {"id": "literal_inserted", "text": (
                f"The target contains at least one inserted literal occurrence of {title!r} "
                "relative to the predecessor under the declared comparison rule."
            )},
            {"id": "literal_inherited", "text": (
                f"The target contains at least one inherited literal occurrence of {title!r} "
                "under the declared comparison rule."
            )},
            {"id": "exposure", "text": (
                "At least one supplied source-page revision entered the context of the "
                "process responsible for the target save before that save."
            )},
            {"id": "source_use", "text": (
                "The process responsible for the target save directly selected at least one "
                "supplied source-page revision as a source of the target text."
            )},
        ],
    }
    return case


def _extraction_check(case):
    """Derive exact match membership without using original pair/audit outputs."""
    if set(case) != {"schema_version", "case_id", "subset", "split", "cluster_id",
                     "records", "assumptions", "claims"}:
        raise ValueError("Unexpected public wiki case fields")
    records = {record["id"]: record for record in case["records"]}
    if len(records) != len(case["records"]):
        raise ValueError("Duplicate public record ID")
    assumptions = {item["id"]: item for item in case["assumptions"]}
    parameters = assumptions["literal_rule"]["parameters"]
    before_record = records[parameters["predecessor_record_id"]]
    target = records[parameters["target_record_id"]]
    if (target["parent_id"] != before_record["revision_id"]
            or (target["site"], target["page"]) != (before_record["site"], before_record["page"])
            or _interval(before_record)[1] >= _interval(target)[0]):
        raise ValueError("Inconsistent predecessor contract")
    sources = [records[identifier] for identifier in parameters["source_record_ids"]]
    if not sources or len(sources) + 2 != len(records):
        raise ValueError("Missing or undeclared source records")
    title = parameters["referenced_title"]
    for source in sources:
        if ((source["site"], source["page"]) != (target["site"], title)
                or _interval(source)[1] >= _interval(target)[0]):
            raise ValueError("Source does not strictly precede target")
    for record in records.values():
        if (record["text_kind"] != "full_revision" or not isinstance(record["text"], str)
                or record["text_sha256"] != hashlib.sha256(record["text"].encode()).hexdigest()):
            raise ValueError("Full record text or its byte digest is invalid")
    before, after = before_record["text"], target["text"]
    pattern = re.compile(r"(?<!\w)" + re.escape(title) + r"(?!\w)")
    if parameters["pattern"] != pattern.pattern:
        raise ValueError("Literal matching contract changed")
    old_spans = {(match.start(), match.end()) for match in pattern.finditer(before)}
    opcodes = SequenceMatcher(None, before, after, autojunk=False).get_opcodes()
    output = {"inserted": [], "inherited": [], "ambiguous": []}
    for match in pattern.finditer(after):
        start, end = match.span()
        changed = any(tag in {"insert", "replace"} and max(start, j1) < min(end, j2)
                      for tag, _, _, j1, j2 in opcodes)
        inherited = False
        if not changed:
            for tag, i1, _, j1, j2 in opcodes:
                if tag == "equal" and j1 <= start and end <= j2:
                    old_start = i1 + start - j1
                    inherited = (old_start, old_start + len(title)) in old_spans
                    break
        category = "inserted" if changed else "inherited" if inherited else "ambiguous"
        output[category].append([start, end])
    output["opcodes"] = [list(opcode) for opcode in opcodes]
    output["target_text_sha256"] = target["text_sha256"]
    output["predecessor_text_sha256"] = before_record["text_sha256"]
    return output


def _gold(case, pair):
    original_spans = {
        name: [[span["start"], span["end"]] for span in pair[name + "_spans"]]
        for name in ("inserted", "inherited", "ambiguous")
    }
    checked = _extraction_check(case)
    if any(checked[name] != spans for name, spans in original_spans.items()):
        raise ValueError("Separate offset check disagrees with the frozen wiki extraction")
    source = case["records"][2]
    target = case["records"][1]
    low, high = _interval(source)[1], _interval(target)[0]
    access_time = (low + (high - low) / 2).isoformat()
    witness = [
        {
            "name": "independent_composition",
            "mechanism": (
                "The editing process never accesses the supplied source revisions. An external "
                "prompt or independent composition yields exactly the supplied target text; "
                "the existing before/after snapshots and handles are saved as recorded. No "
                "receipt is emitted in the supplied bundle. This satisfies open_evidence, "
                "record_meaning and every literal observation."
            ),
            "exposure": False, "source_use": False,
        },
        {
            "name": "unlogged_context_and_selection",
            "mechanism": (
                "Before the target save the editing process reads one strictly earlier "
                "supplied source revision through an unlogged channel, receives it in context "
                "and selects it as a source while producing exactly the supplied target text. "
                "A permitted source-dependent composition rule maps that source content and "
                "other inputs to the observed text, with a different output possible for "
                "different source content. The same snapshots, handles and "
                "timestamps are saved. Incomplete receipt logging and unobserved internal "
                "selection make this consistent with all supplied observations."
            ),
            "exposure": True, "source_use": True,
        },
        {
            "name": "unlogged_unused_exposure",
            "mechanism": (
                "The editing process receives a strictly earlier source revision in an "
                "unlogged context channel, ignores it and composes the recorded target from "
                "an external prompt. The same saved records remain unchanged. This satisfies "
                "the source-use-requires-exposure implication without equating exposure to use."
            ),
            "exposure": True, "source_use": False,
        },
    ]
    for world in witness:
        world["observed_record_sha256"] = _digest(case["records"])
        world["target_text_sha256"] = target["text_sha256"]
        world["context_source_record_id"] = source["id"] if world["exposure"] else None
        world["context_time"] = access_time if world["exposure"] else None
        world["selected_source_record_id"] = source["id"] if world["source_use"] else None
    claims = []
    for name in ("inserted", "inherited"):
        claims.append({
            "id": "literal_" + name,
            "status": "established" if original_spans[name] else "ruled_out",
            "certificate": {
                "contract": "literal_rule", "method": "exhaustive_bounded_title_matches",
                "target_offsets": original_spans[name],
                "all_match_classifications": original_spans,
                "opcode_check": checked,
                "scope": "literal alignment only; no authorship or intention claim",
            },
        })
    for name in ("exposure", "source_use"):
        claims.append({
            "id": name, "status": "unresolved",
            "certificate": {"contract": "open_evidence", "compatible_constructions": witness},
        })
    return {
        "case_id": case["case_id"], "claims": claims,
        "validation": {
            "public_case_sha256": _digest(case),
            "method": "original extraction plus separate regex/opcode/offset derivation",
            "mechanical_check": True, "independent_human_validation": False,
            "nonempty_compatible_set": True,
        },
    }


def validate_wiki_gold(case, gold):
    """Reject mismatched statuses/certificates using only supplied record texts."""
    checked = _extraction_check(case)
    if gold["case_id"] != case["case_id"] or gold["validation"]["public_case_sha256"] != _digest(case):
        raise ValueError("Gold case identity or public-case digest mismatch")
    expected_ids = {claim["id"] for claim in case["claims"]}
    claims = {claim["id"]: claim for claim in gold["claims"]}
    if set(claims) != expected_ids or len(claims) != len(gold["claims"]):
        raise ValueError("Gold claims differ from public claims")
    for category in ("inserted", "inherited"):
        claim = claims["literal_" + category]
        expected = "established" if checked[category] else "ruled_out"
        certificate = claim["certificate"]
        if (claim["status"] != expected or certificate["target_offsets"] != checked[category]
                or certificate["opcode_check"] != checked):
            raise ValueError("Wiki extraction gold failed independent offset validation")
        for name in ("inserted", "inherited", "ambiguous"):
            if certificate["all_match_classifications"][name] != checked[name]:
                raise ValueError("Wiki extraction classification certificate mismatch")
    for category in ("exposure", "source_use"):
        claim = claims[category]
        worlds = claim["certificate"]["compatible_constructions"]
        values = {world[category] for world in worlds}
        if (claim["status"] != "unresolved" or values != {False, True}
                or any(world["source_use"] and not world["exposure"] for world in worlds)
                or any(not world.get("mechanism") for world in worlds)):
            raise ValueError("Unresolved claim lacks compatible disagreement constructions")
        records = {record["id"]: record for record in case["records"]}
        source_ids = {record["id"] for record in case["records"] if record["kind"] == "wiki_source"}
        target = next(record for record in case["records"] if record["kind"] == "wiki_target")
        for world in worlds:
            if (world["observed_record_sha256"] != _digest(case["records"])
                    or world["target_text_sha256"] != target["text_sha256"]):
                raise ValueError("Compatible construction changes the observations")
            source_id = world["context_source_record_id"]
            if world["exposure"]:
                time = parse_timestamp(world["context_time"])
                if (source_id not in source_ids or time is None
                        or not _interval(records[source_id])[1] < time < _interval(target)[0]):
                    raise ValueError("Compatible exposure construction has invalid timing or source")
            elif source_id is not None or world["context_time"] is not None:
                raise ValueError("Compatible non-exposure construction includes source context")
            selected = world["selected_source_record_id"]
            if (world["source_use"] and selected != source_id) or (not world["source_use"] and selected is not None):
                raise ValueError("Compatible source-selection construction violates the contract")
    return {"case_id": case["case_id"], "validated": True,
            "independent_human_validation": False,
            "target_occurrences_checked": sum(len(checked[name]) for name in ("inserted", "inherited", "ambiguous"))}


def _build_from_analysis(
    loaded: LoadedWiki, review_sheet: dict, analysis: dict, *, evaluation_per_stratum=8,
    development_per_stratum=1, max_text_chars=MAX_TEXT_CHARS,
):
    """Return public cases, evaluator-only gold, and a reproducible selection manifest.

    Every endpoint page history appears in at most one case across both splits.
    Eligibility and strata use the existing rule before any investigator outcomes.
    A shortage is recorded, not repaired by relaxing eligibility or replacing cases.
    """
    for value in (evaluation_per_stratum, development_per_stratum, max_text_chars):
        if type(value) is not int or value < 0:
            raise ValueError("Selection bounds must be nonnegative integers")
    if development_per_stratum > 1 or evaluation_per_stratum > 8 or max_text_chars > MAX_TEXT_CHARS:
        raise ValueError("Selection exceeds the bounded wiki study limits")
    revisions = loaded.revisions
    site = "dse" if any(revision.site == "dse" for revision in revisions) else "DSE"
    by_id = {(revision.site, revision.revision_id): revision for revision in revisions}
    audits = {(audit["target"]["site"], audit["target"]["revision_id"]): audit
              for audit in analysis["revision_audit"]}
    excluded_pages = _review_pages(review_sheet)
    candidates = {category: [] for category in STRATA}
    exclusions = Counter()
    for pair in analysis["pairs"]:
        if pair["status"] not in STRATA:
            exclusions["frozen_extraction_excluded_or_ambiguous"] += 1
            continue
        target = by_id[tuple(pair["pair_key"][:2])]
        audit = audits[(target.site, target.revision_id)]
        if (target.site, target.page) in excluded_pages or (target.site, pair["referenced_page"]) in excluded_pages:
            exclusions["previously_reviewed_target_or_source_page"] += 1
            continue
        if audit["predecessor"] is None:
            exclusions["no_actual_predecessor_for_two_snapshot_task"] += 1
            continue
        predecessor = by_id[(target.site, audit["predecessor"]["revision_id"])]
        sources = [by_id[(source["site"], source["revision_id"])]
                   for source in pair["source_revisions"]]
        selected_records = [target, predecessor, *sources]
        if any(record.text is None for record in selected_records) or pair["ambiguous_spans"]:
            exclusions["missing_full_text_or_ambiguous_match"] += 1
            continue
        chars = sum(len(record.text) for record in selected_records)
        if chars > max_text_chars:
            exclusions["complete_record_text_exceeds_frozen_character_limit"] += 1
            continue
        candidates[pair["status"]].append((pair, selected_records, chars))
    public, gold, selected, shortages = [], [], [], []
    used_pages = set()
    for stratum in STRATA:
        ranked = sorted(candidates[stratum], key=lambda item: _rank(item[0]))
        for split, requested in (("development", development_per_stratum),
                                 ("evaluation", evaluation_per_stratum)):
            obtained = 0
            for pair, selected_records, chars in ranked:
                target = selected_records[0]
                endpoint_pages = {(target.site, target.page),
                                  (target.site, pair["referenced_page"])}
                if endpoint_pages & used_pages:
                    continue
                if obtained >= requested:
                    break
                case = _case(pair, selected_records, split)
                case_gold = _gold(case, pair)
                validate_wiki_gold(case, case_gold)
                public.append(case)
                gold.append(case_gold)
                used_pages.update(endpoint_pages)
                obtained += 1
                selected.append({
                    "case_id": case["case_id"], "split": split, "stratum": stratum,
                    "cluster_id": case["cluster_id"], "pair_key": pair["pair_key"],
                    "target_page": target.page, "source_page": pair["referenced_page"],
                    "endpoint_pages": [list(page) for page in sorted(endpoint_pages)],
                    "selection_sha256": _rank(pair)[0], "full_text_characters": chars,
                    "public_case_sha256": _digest(case),
                })
            if obtained != requested:
                shortages.append({"stratum": stratum, "split": split,
                                  "requested": requested, "obtained": obtained})
    manifest = {
        "schema_version": 1, "selection_salt": SELECTION_SALT, "target_site": site,
        "rule": (
            "Use original eligible literal pairs with a real predecessor, no ambiguous "
            "matches, and all full predecessor/target/strict-prior-source text within the "
            "frozen character bound. Exclude both endpoint pages from every old review pair. "
            "Process inserted then inherited_only; rank each by SHA256 of compact sorted-key "
            "JSON [salt,pair_key], then pair_key. Take development then evaluation per stratum, "
            "skipping any target or source page history previously chosen in either role "
            "across both strata and splits."
        ),
        "max_full_text_characters": max_text_chars,
        "requested_evaluation_per_stratum": evaluation_per_stratum,
        "requested_development_per_stratum": development_per_stratum,
        "candidate_pairs_by_stratum": {key: len(value) for key, value in candidates.items()},
        "excluded_pages": [list(page) for page in sorted(excluded_pages)],
        "exclusion_counts_first_applicable_reason": dict(sorted(exclusions.items())),
        "selected": selected, "shortages": shortages,
        "known_prior_exposure": (
            "The authors previously computed corpus-wide extraction and AI-assisted checks "
            "of a 20-pair review sheet. Every target and referenced page in that sheet is "
            "excluded, including other revisions of those pages. This is not an assertion "
            "of unseen pages for every author or uncontaminated model evaluation data. "
            "The public corpus and its earlier report were already available."
        ),
        "validation": "Mechanical extraction/offset checks; no independent human validation",
    }
    return public, gold, manifest


def build_wiki_cases(
    loaded: LoadedWiki, review_sheet: dict, *, evaluation_per_stratum=8,
    development_per_stratum=1, max_text_chars=MAX_TEXT_CHARS,
):
    """Select from the unchanged full-corpus extractor, then certify public views."""
    for value in (evaluation_per_stratum, development_per_stratum, max_text_chars):
        if type(value) is not int or value < 0:
            raise ValueError("Selection bounds must be nonnegative integers")
    if development_per_stratum > 1 or evaluation_per_stratum > 8 or max_text_chars > MAX_TEXT_CHARS:
        raise ValueError("Selection exceeds the bounded wiki study limits")
    site = "dse" if any(revision.site == "dse" for revision in loaded.revisions) else "DSE"
    analysis = analyze_references(loaded.revisions, target_site=site)
    return _build_from_analysis(
        loaded, review_sheet, analysis, evaluation_per_stratum=evaluation_per_stratum,
        development_per_stratum=development_per_stratum, max_text_chars=max_text_chars,
    )
