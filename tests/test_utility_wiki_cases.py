"""Mechanical case/label checks using invented wiki text, not new field findings."""

import copy
import hashlib
from dataclasses import replace

import pytest

from tracebench.investigator_utility.wiki_cases import build_wiki_cases, validate_wiki_gold
from tracebench.wiki_loader import LoadedWiki
from tracebench.wiki_model import Revision


def revision(identifier, page, minute, text, parent=None, **kwargs):
    return Revision(
        site="DSE", page=page, revision_id=identifier,
        timestamp=f"2026-01-01T00:{minute:02}:00Z", author="unverified-handle",
        text=text, parent_id=parent, is_creation=parent is None,
        source_file="invented.jsonl", source_line=minute,
        record_sha256=hashlib.sha256(identifier.encode()).hexdigest(), **kwargs,
    )


def corpus():
    revisions = []
    for category in ("inserted", "inherited"):
        for index in range(3):
            page = f"Target_{category}_{index}"
            identifier = f"{category}_{index}"
            title = f"AlphaPage_{identifier}"
            before = "Opening paragraph." if category == "inserted" else f"See {title}."
            after = before + (f" {title}." if category == "inserted" else " Updated.")
            revisions += [revision("source_" + identifier, title, 1, "Source material."),
                          revision(identifier + "_before", page, 10, before),
                          revision(identifier + "_after", page, 20, after,
                                   parent=identifier + "_before")]
    return LoadedWiki(tuple(revisions), {"source_kind": "synthetic_fixture"}, ())


def build(loaded=None, review=None, **kwargs):
    kwargs.setdefault("evaluation_per_stratum", 1)
    kwargs.setdefault("development_per_stratum", 1)
    return build_wiki_cases(loaded or corpus(), review or {"categories": {}}, **kwargs)


def test_selection_has_fixed_counts_distinct_pages_and_independent_splits():
    cases, gold, manifest = build()
    assert len(cases) == len(gold) == 4
    assert [case["split"] for case in cases].count("development") == 2
    assert [case["split"] for case in cases].count("evaluation") == 2
    assert len({case["cluster_id"] for case in cases}) == 4
    assert len({row["target_page"] for row in manifest["selected"]}) == 4
    endpoint_pages = [tuple(page) for row in manifest["selected"] for page in row["endpoint_pages"]]
    assert len(endpoint_pages) == len(set(endpoint_pages)) == 8
    assert not manifest["shortages"]
    assert "not an assertion" in manifest["known_prior_exposure"]


def test_selection_reproducible_under_input_reordering():
    original = corpus()
    reversed_corpus = replace(original, revisions=tuple(reversed(original.revisions)))
    assert build(original) == build(reversed_corpus)


def test_public_schema_omits_gold_and_classification_fields():
    cases, _, _ = build()
    expected = {"schema_version", "case_id", "subset", "split", "cluster_id",
                "records", "assumptions", "claims"}
    forbidden = {"status", "certificate", "gold", "validation", "stratum", "evidence"}

    def inspect(value):
        if isinstance(value, dict):
            assert not (set(value) & forbidden)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    for case in cases:
        assert set(case) == expected
        inspect(case)


def test_all_full_record_text_and_source_locators_are_retained():
    loaded = corpus()
    cases, _, manifest = build(loaded)
    by_id = {record.revision_id: record for record in loaded.revisions}
    for case, selected in zip(cases, manifest["selected"], strict=True):
        assert sum(len(record["text"]) for record in case["records"]) == selected["full_text_characters"]
        for record in case["records"]:
            source = by_id[record["revision_id"]]
            assert record["text"] == source.text
            assert record["source_file"] == source.source_file
            assert record["record_sha256"] == source.record_sha256
        scope = next(item for item in case["assumptions"] if item["id"] == "window_scope")
        assert scope["parameters"]["complete_incident_history"] is False
        assert scope["parameters"]["included_record_ids"] == [r["id"] for r in case["records"]]


def test_previously_reviewed_target_page_excludes_every_other_revision_of_page():
    review = {"categories": {"inserted": [{"candidate": {
        "target": {"site": "DSE", "page": "Target_inserted_0"},
        "referenced_page": "AnUnrelatedPage",
    }}]}}
    _, _, manifest = build(review=review)
    assert "Target_inserted_0" not in {row["target_page"] for row in manifest["selected"]}
    assert ["DSE", "Target_inserted_0"] in manifest["excluded_pages"]


def test_previously_reviewed_reference_page_is_excluded_even_for_new_targets():
    review = {"categories": {"inserted": [{"candidate": {
        "target": {"site": "DSE", "page": "SomePriorTarget"},
        "referenced_page": f"AlphaPage_{category}_{index}",
    }} for category in ("inserted", "inherited") for index in range(3)]}}
    cases, gold, manifest = build(review=review)
    assert cases == gold == []
    assert len(manifest["shortages"]) == 4
    assert manifest["exclusion_counts_first_applicable_reason"]["previously_reviewed_target_or_source_page"]


def test_oversize_windows_record_shortage_without_silent_truncation():
    cases, gold, manifest = build(max_text_chars=1)
    assert cases == gold == []
    assert len(manifest["shortages"]) == 4
    assert manifest["exclusion_counts_first_applicable_reason"]["complete_record_text_exceeds_frozen_character_limit"]


@pytest.mark.parametrize("setting", [
    {"development_per_stratum": 2}, {"evaluation_per_stratum": 9},
    {"max_text_chars": 24001}, {"max_text_chars": -1}, {"evaluation_per_stratum": True},
])
def test_bounds_cannot_silently_expand_the_study(setting):
    with pytest.raises(ValueError, match="bounded|nonnegative"):
        build(**setting)


def test_each_case_has_two_answerable_and_two_genuinely_unresolved_claims():
    cases, labels, _ = build()
    for case, gold in zip(cases, labels, strict=True):
        claims = {claim["id"]: claim for claim in gold["claims"]}
        assert {claims[name]["status"] for name in ("literal_inserted", "literal_inherited")} == {
            "established", "ruled_out",
        }
        for name in ("exposure", "source_use"):
            assert claims[name]["status"] == "unresolved"
            worlds = claims[name]["certificate"]["compatible_constructions"]
            assert {(w["exposure"], w["source_use"]) for w in worlds} == {
                (False, False), (True, False), (True, True),
            }
        assert validate_wiki_gold(case, gold)["validated"]


def test_validator_does_not_rerun_or_trust_original_extraction(monkeypatch):
    cases, labels, _ = build()

    def unavailable(*args, **kwargs):
        raise AssertionError("Original extraction must not be called by the separate check")

    monkeypatch.setattr("tracebench.investigator_utility.wiki_cases.analyze_references", unavailable)
    assert validate_wiki_gold(cases[0], labels[0])["validated"]


@pytest.mark.parametrize("mutation", ["status", "offset", "opcode", "classification"])
def test_evaluator_certificate_tampering_is_detected(mutation):
    cases, labels, _ = build()
    gold = copy.deepcopy(labels[0])
    claim = gold["claims"][0]
    if mutation == "status":
        claim["status"] = "unresolved"
    elif mutation == "offset":
        claim["certificate"]["target_offsets"] = [[1000, 1009]]
    elif mutation == "opcode":
        claim["certificate"]["opcode_check"]["opcodes"] = []
    else:
        claim["certificate"]["all_match_classifications"]["inherited"] = [[1000, 1009]]
    with pytest.raises(ValueError, match="extraction"):
        validate_wiki_gold(cases[0], gold)


def test_text_tampering_is_detected_before_label_check():
    cases, labels, _ = build()
    case = copy.deepcopy(cases[0])
    case["records"][0]["text"] += " A change."
    with pytest.raises(ValueError, match="digest"):
        validate_wiki_gold(case, labels[0])


def test_source_order_contradiction_is_excluded_by_validator():
    cases, labels, _ = build()
    case = copy.deepcopy(cases[0])
    case["records"][2]["timestamp"] = "2026-01-01T00:59:00Z"
    with pytest.raises(ValueError, match="precede"):
        validate_wiki_gold(case, labels[0])


def test_wrong_page_predecessor_is_rejected():
    cases, labels, _ = build()
    case = copy.deepcopy(cases[0])
    case["records"][0]["page"] = "DifferentPage"
    with pytest.raises(ValueError, match="predecessor"):
        validate_wiki_gold(case, labels[0])


def test_gold_constructions_must_allow_disagreement_and_require_exposure_for_use():
    cases, labels, _ = build()
    gold = copy.deepcopy(labels[0])
    gold["claims"][2]["certificate"]["compatible_constructions"][1]["exposure"] = False
    with pytest.raises(ValueError, match="compatible"):
        validate_wiki_gold(cases[0], gold)


def test_partial_title_character_edit_uses_the_frozen_character_rule():
    loaded = LoadedWiki((
        revision("s", "AlphaPage", 1, "Source."),
        revision("b", "Target", 10, "Read AlphaPoge."),
        revision("a", "Target", 20, "Read AlphaPage.", parent="b"),
    ), {}, ())
    cases, gold, _ = build(loaded, development_per_stratum=0)
    assert len(cases) == 1
    assert gold[0]["claims"][0]["status"] == "established"
    assert gold[0]["claims"][0]["certificate"]["target_offsets"] == [[5, 14]]
    assert validate_wiki_gold(cases[0], gold[0])["validated"]


def test_boundary_only_change_is_not_selected_as_an_unambiguous_window():
    loaded = LoadedWiki((
        revision("s", "AlphaPage", 1, "Source."),
        revision("b", "Target", 10, "xAlphaPage"),
        revision("a", "Target", 20, "AlphaPage", parent="b"),
    ), {}, ())
    cases, _, manifest = build(loaded, development_per_stratum=0)
    assert not cases
    assert manifest["shortages"]


def test_every_strictly_earlier_source_revision_is_retained():
    loaded = LoadedWiki((
        revision("source", "AlphaPage", 1, "Source material."),
        revision("source2", "AlphaPage", 5, "Other source content.", parent="source"),
        revision("b", "Target", 10, "Read a page."),
        revision("a", "Target", 20, "Read AlphaPage.", parent="b"),
    ), {}, ())
    cases, _, _ = build(loaded, development_per_stratum=0)
    assert len(cases) == 1
    sources = [record for record in cases[0]["records"] if record["kind"] == "wiki_source"]
    assert [record["revision_id"] for record in sources] == ["source", "source2"]
    assert [record["text"] for record in sources] == ["Source material.", "Other source content."]


def test_shared_source_page_history_cannot_cross_cases_or_splits():
    loaded = LoadedWiki((
        revision("source", "AlphaPage", 1, "Source."),
        revision("a0", "TargetA", 10, "Before."),
        revision("a1", "TargetA", 20, "Before. AlphaPage.", parent="a0"),
        revision("b0", "TargetB", 10, "Before. AlphaPage."),
        revision("b1", "TargetB", 20, "Before. AlphaPage. Updated.", parent="b0"),
    ), {}, ())
    cases, _, manifest = build(loaded)
    assert len(cases) == 1
    assert cases[0]["split"] == "development"
    assert manifest["shortages"]


@pytest.mark.parametrize("field,value", [
    ("context_time", "2026-01-01T00:59:00Z"),
    ("context_source_record_id", "record_1"),
    ("selected_source_record_id", "record_1"),
    ("observed_record_sha256", "0" * 64),
    ("target_text_sha256", "0" * 64),
])
def test_compatible_constructions_preserve_actual_observations_and_feasible_events(field, value):
    cases, labels, _ = build()
    gold = copy.deepcopy(labels[0])
    gold["claims"][2]["certificate"]["compatible_constructions"][1][field] = value
    with pytest.raises(ValueError, match="[Cc]ompatible"):
        validate_wiki_gold(cases[0], gold)
