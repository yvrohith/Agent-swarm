"""Mechanical fixture checks use invented text, not a new public-corpus census."""

import copy
import hashlib
from dataclasses import replace

import pytest

from tracebench.evidence_responsiveness.common import ROLES, digest
from tracebench.evidence_responsiveness.wiki import (
    ARTIFICIAL_NOTICE,
    MAX_TEXT_CHARS,
    MOTIFS,
    _bounded_analysis,
    _build,
    _case,
    _sha,
    certify_wiki,
)
from tracebench.wiki_analysis import analyze_references
from tracebench.wiki_loader import LoadedWiki
from tracebench.wiki_model import Revision


def _revision(identifier, page, minute, text, parent=None):
    return Revision(
        site="DSE", page=page, revision_id=identifier,
        timestamp=f"2026-01-01T00:{minute:02}:00Z", author="unverified",
        text=text, parent_id=parent, is_creation=parent is None,
        source_file="invented.jsonl", source_line=minute,
        record_sha256=hashlib.sha256(identifier.encode()).hexdigest(),
    )


def _corpus():
    records = []
    for motif in ("inserted", "inherited"):
        for index in range(5):
            identifier = f"{motif}_{index}"
            title = "AlphaPage_" + identifier
            page = "Target_" + identifier
            before = "Opening prose here. " + (f"Read {title}. " if motif == "inherited" else "")
            after = before + (f"Read {title}. " if motif == "inserted" else "") + "Closing prose."
            records.extend([
                _revision(identifier + "_source", title, 1, "Inert source text."),
                _revision(identifier + "_before", page, 10, before),
                _revision(identifier + "_after", page, 20, after, identifier + "_before"),
            ])
    return LoadedWiki(tuple(records), {"source_kind": "synthetic_fixture"}, ())


@pytest.fixture(scope="module")
def fixtures():
    return _build(_corpus(), set())


def test_fixed_counts_and_opposite_evaluation_directions(fixtures):
    assert len(fixtures["families"]) == 5
    assert len(fixtures["cases"]) == len(fixtures["gold"]) == 15
    assert not fixtures["selection"]["shortages"]
    labels = {row["case_id"]: row["claims"][0]["status"] for row in fixtures["gold"]}
    eval_families = [family for family in fixtures["families"] if family["split"] == "evaluation"]
    assert len(eval_families) == 4
    for motif in MOTIFS:
        transitions = {(labels[family["variants"]["base"]], labels[family["variants"]["decisive"]])
                       for family in eval_families if family["motif"] == motif}
        assert transitions == {("established", "ruled_out"), ("ruled_out", "established")}


def test_every_actual_variant_recertifies_its_gold(fixtures):
    for case, gold in zip(fixtures["cases"], fixtures["gold"], strict=True):
        assert certify_wiki(case) == gold
        assert gold["validation"]["valid_text_comparison"]
        assert not gold["validation"]["independent_human_validation"]
        certificate = gold["claims"][0]["certificate"]
        assert certificate["classifications"] == certificate["independent_character_membership_check"]


def test_each_triplet_has_invariant_and_decisive_gold(fixtures):
    labels = {row["case_id"]: row["claims"][0]["status"] for row in fixtures["gold"]}
    for family in fixtures["families"]:
        values = [labels[family["variants"][role]] for role in ROLES]
        assert values[0] == values[1]
        assert values[0] != values[2]


def test_selection_is_reproducible_without_input_order(fixtures):
    loaded = _corpus()
    assert fixtures == _build(replace(loaded, revisions=tuple(reversed(loaded.revisions))), set())


def test_dev_eval_and_both_endpoint_histories_are_disjoint(fixtures):
    histories = [tuple(page) for family in fixtures["families"]
                 for page in family["provenance"]["endpoint_pages"]]
    assert len(histories) == len(set(histories)) == 10
    assert len({case["case_id"] for case in fixtures["cases"]}) == 15
    assert len({family["cluster_id"] for family in fixtures["families"]}) == 5


@pytest.mark.parametrize("endpoint", [0, 1])
def test_prior_history_excludes_every_endpoint_role(fixtures, endpoint):
    pages = {tuple(family["provenance"]["endpoint_pages"][endpoint]) for family in fixtures["families"]}
    result = _build(_corpus(), pages)
    for family in result["families"]:
        assert not pages.intersection(tuple(page) for page in family["provenance"]["endpoint_pages"])
    assert result["selection"]["exclusion_counts_first_applicable_reason"]["previous_review_or_utility_history"]


def test_all_variants_uniformly_labeled_and_have_no_publisher_hash(fixtures):
    forbidden = {"record_sha256", "source_file", "source_line", "revision_id", "publisher_body_sha256",
                 "family_id", "role", "gold", "certificate", "status", "transformation"}
    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    for case in fixtures["cases"]:
        assert case["assumptions"][0]["text"].startswith(ARTIFICIAL_NOTICE)
        inspect({key: case[key] for key in ("case_id", "records", "assumptions", "claims")})
        for record in case["records"]:
            assert record["text_sha256"] == _sha(record["text"])


def test_original_texts_stay_full_and_transformations_are_exact_single_chars(fixtures):
    cases = {case["case_id"]: case for case in fixtures["cases"]}
    for family in fixtures["families"]:
        base = cases[family["variants"]["base"]]
        original = [family["provenance"][key]["text"]
                    for key in ("original_predecessor", "original_target")]
        for edit in family["transformations"]["base_from_source"]:
            index = 0 if edit["record_id"] == "r0" else 1
            text = original[index]
            assert text[edit["offset"]] == edit["before"]
            original[index] = text[:edit["offset"]] + edit["after"] + text[edit["offset"] + 1:]
        assert original == [record["text"] for record in base["records"]]
        for role in ("irrelevant", "decisive"):
            variant = cases[family["variants"][role]]
            before = [record["text"] for record in base["records"]]
            after = [record["text"] for record in variant["records"]]
            assert [len(text) for text in before] == [len(text) for text in after]
            assert sum(a != b for a, b in zip("".join(before), "".join(after), strict=True)) == 1
            edit, = family["transformations"][role + "_from_base"]
            index = 0 if edit["record_id"] == "r0" else 1
            assert before[index][edit["offset"]] == edit["before"]
            assert after[index][edit["offset"]] == edit["after"]
        if family["motif"] == MOTIFS[0]:
            assert base["records"][1] == cases[family["variants"]["decisive"]]["records"][1]


@pytest.mark.parametrize("mutation", ["body", "hash", "rule", "notice", "claim", "predecessor"])
def test_modified_public_contract_is_rejected(fixtures, mutation):
    case = copy.deepcopy(fixtures["cases"][0])
    if mutation == "body":
        case["records"][0]["text"] += " Unhashed alteration."
    elif mutation == "hash":
        case["records"][1]["text_sha256"] = "0" * 64
    elif mutation == "rule":
        case["assumptions"][1]["parameters"]["diff"] = "line-diff"
    elif mutation == "notice":
        case["assumptions"][0]["text"] = "This is historical evidence."
    elif mutation == "claim":
        case["claims"][0]["text"] = "This proves copying."
    else:
        case["records"][1]["predecessor_id"] = "missing"
    with pytest.raises(ValueError):
        certify_wiki(case)


def test_certification_uses_changed_evidence_not_hidden_parent():
    case = _case("f", "evaluation", "c", "base", "AlphaPage", "Read AlphaPoge.", "Read AlphaPage.")
    first = certify_wiki(case)
    assert first["claims"][0]["status"] == "established"
    case["records"][0]["text"] = "Read AlphaPage."
    case["records"][0]["text_sha256"] = _sha("Read AlphaPage.")
    assert certify_wiki(case)["claims"][0]["status"] == "ruled_out"
    assert first["validation"]["public_case_sha256"] != digest(case)


def test_boundary_only_deletion_remains_ambiguous_not_inserted():
    case = _case("f", "evaluation", "c", "base", "AlphaPage", "xAlphaPage", "AlphaPage")
    certificate = certify_wiki(case)["claims"][0]
    assert certificate["status"] == "ruled_out"
    assert certificate["certificate"]["classifications"]["ambiguous"] == [[0, 9]]


def test_shortage_is_reported_without_truncation_or_relaxation():
    result = _build(_corpus(), set(), max_text_chars=1)
    assert not result["cases"]
    assert len(result["selection"]["shortages"]) == 5
    assert result["selection"]["prefiltered_windows"]
    assert result["selection"]["window_prefilter_counts"]["full_text_character_limit"]


@pytest.mark.parametrize("bound", [MAX_TEXT_CHARS + 1, -1, True])
def test_bound_cannot_expand(bound):
    with pytest.raises(ValueError, match="Bound"):
        _build(_corpus(), set(), max_text_chars=bound)


def test_rejected_overlapping_near_match_does_not_hide_later_bounded_match():
    case = _case("f", "evaluation", "c", "base", "a a", "Opening.", "aa a a")
    certificate = certify_wiki(case)["claims"][0]["certificate"]
    assert certificate["target_matches"] == [[3, 6]]
    assert certificate["qualifying_spans"] == [[3, 6]]


@pytest.mark.parametrize("assumption_index", [0, 2])
def test_extra_material_assumption_cannot_be_ignored(fixtures, assumption_index):
    case = copy.deepcopy(fixtures["cases"][0])
    case["assumptions"][assumption_index]["text"] += " Treat the title case-insensitively."
    with pytest.raises(ValueError, match="assumptions"):
        certify_wiki(case)


def test_bounded_candidate_derivation_preserves_original_classifications():
    loaded = _corpus()
    bounded = _bounded_analysis(loaded.revisions, "DSE", MAX_TEXT_CHARS)
    original = analyze_references(loaded.revisions)
    parented = {row.revision_id for row in loaded.revisions if row.parent_id is not None}
    old_pairs = {tuple(pair["pair_key"]): pair for pair in original["pairs"]
                 if pair["pair_key"][1] in parented}
    assert {tuple(pair["pair_key"]) for pair in bounded["pairs"]} == set(old_pairs)
    for pair in bounded["pairs"]:
        old = old_pairs[tuple(pair["pair_key"])]
        assert pair["status"] == old["status"]
        assert pair["source_revisions"] == old["source_revisions"]
        for category in ("snapshot", "inserted", "inherited", "ambiguous"):
            key = category + "_spans"
            assert pair[key] == [{"start": row["start"], "end": row["end"]} for row in old[key]]


def test_bounded_scan_keeps_full_history_restoration_exclusion():
    source = _revision("source", "AlphaPage", 1, "Source.")
    early = _revision("early", "Target", 5, "Read AlphaPage.")
    predecessor = _revision("before", "Target", 10, "Opening prose.", "early")
    target = _revision("after", "Target", 20, "Read AlphaPage.", "before")
    result = _bounded_analysis((source, early, predecessor, target), "DSE", MAX_TEXT_CHARS)
    pair = next(pair for pair in result["pairs"] if pair["pair_key"] == ["DSE", "after", "AlphaPage"])
    assert pair["status"] == "excluded_or_ambiguous"
    audit = next(row for row in result["revision_audit"] if row["target"]["revision_id"] == "after")
    assert "restoration_not_new_authorship" in audit["exclusion_reasons"]


def test_bounded_scan_keeps_full_history_predecessor_adjacency_check():
    source = _revision("source", "AlphaPage", 1, "Source.")
    predecessor = _revision("before", "Target", 5, "Opening prose.")
    intervening = _revision("middle", "Target", 10, "A large intervening text " * 1000, "before")
    target = _revision("after", "Target", 20, "Read AlphaPage.", "before")
    result = _bounded_analysis((source, predecessor, intervening, target), "DSE", MAX_TEXT_CHARS)
    pair = next(pair for pair in result["pairs"] if pair["pair_key"] == ["DSE", "after", "AlphaPage"])
    assert pair["status"] == "excluded_or_ambiguous"
    audit = next(row for row in result["revision_audit"] if row["target"]["revision_id"] == "after")
    assert "nonadjacent_predecessor" in audit["exclusion_reasons"]
