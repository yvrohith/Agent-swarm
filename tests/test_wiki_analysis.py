"""Synthetic-only tests of observable extraction, not incident/source-use labels."""

import copy
import hashlib
from dataclasses import replace

import pytest

from tracebench.wiki_analysis import analyze_references, parse_timestamp, verify_evidence
from tracebench.wiki_model import Revision


def revision(identifier, page, minute, text, *, parent=None, author="handle-b", site="DSE",
             creation=None, flags=()):
    """Construct explicitly synthetic records with fixture source links."""
    return Revision(
        site=site, page=page, revision_id=identifier,
        timestamp=f"2026-01-01T00:{minute:02}:00Z" if minute is not None else None,
        author=author, text=text, parent_id=parent,
        is_creation=parent is None if creation is None else creation,
        source_file="synthetic-fixture.jsonl", source_line=minute or 99,
        record_sha256=hashlib.sha256(repr((identifier, page, text)).encode()).hexdigest(),
        flags=flags,
    )


def source():
    return revision("s1", "AlphaPage", 1, "A synthetic source.", author="handle-a")


def audit_for(analysis, identifier):
    return next(a for a in analysis["revision_audit"] if a["target"]["revision_id"] == identifier)


def pair_for(analysis, identifier, title="AlphaPage"):
    return next(p for p in analysis["pairs"]
                if p["target"]["revision_id"] == identifier and p["referenced_page"] == title)


def analyze(*records):
    result = analyze_references(tuple(records))
    verify_evidence(tuple(records), result)
    return result


def test_unchanged_snapshot_is_inherited_and_duplicate_not_new_insertion():
    initial = revision("t1", "TargetPage", 2, "See AlphaPage.")
    duplicate = revision("t2", "TargetPage", 3, initial.text, parent="t1")
    result = analyze(source(), initial, duplicate)
    assert result["counts"]["naive_snapshot_pairs"] == 2
    assert result["counts"]["inserted_reference_pairs"] == 1
    assert result["counts"]["inherited_only_pairs"] == 1
    assert result["counts"]["naive_snapshot_occurrences"] == 2
    assert result["counts"]["eligible_snapshot_occurrences"] == 2
    assert result["counts"]["inherited_reference_occurrences"] == 1
    assert pair_for(result, "t2")["status"] == "inherited_only"
    assert "duplicate_snapshot" in audit_for(result, "t2")["flags"]


def test_new_insertion_retains_exact_occurrences_and_collapses_only_pairs():
    initial = revision("t1", "TargetPage", 2, "A note.")
    changed = revision("t2", "TargetPage", 3, "A note. AlphaPage and AlphaPage.", parent="t1")
    result = analyze(source(), initial, changed)
    pair = pair_for(result, "t2")
    assert len(pair["inserted_spans"]) == 2
    assert result["counts"]["inserted_reference_pairs"] == 1
    assert result["counts"]["inserted_reference_occurrences"] == 2
    assert result["counts"]["naive_snapshot_occurrences"] == 2
    assert result["counts"]["eligible_snapshot_occurrences"] == 2
    assert result["counts"]["target_revisions_with_inserted_reference"] == 1
    assert [span["start"] for span in pair["inserted_spans"]] == [8, 22]


def test_replacement_line_keeps_unchanged_reference_inherited():
    initial = revision("t1", "TargetPage", 2, "The first statement mentions AlphaPage.")
    changed = revision("t2", "TargetPage", 3, "The revised statement mentions AlphaPage.", parent="t1")
    result = analyze(source(), initial, changed)
    pair = pair_for(result, "t2")
    assert pair["status"] == "inherited_only"
    assert not pair["inserted_spans"]
    assert audit_for(result, "t2")["inserted_character_spans"]


@pytest.mark.parametrize("before", ["Read AlphaPoge.", "Read AlphaPge."])
def test_one_changed_title_character_establishes_an_inserted_literal_occurrence(before):
    initial = revision("t1", "TargetPage", 2, before)
    changed = revision("t2", "TargetPage", 3, "Read AlphaPage.", parent="t1")
    result = analyze(source(), initial, changed)
    pair = pair_for(result, "t2")

    # The frozen rule requires any changed title character, not an entirely new title.
    assert audit_for(result, "t2")["inserted_character_spans"] == [[11, 12]]
    assert [(s["start"], s["end"]) for s in pair["inserted_spans"]] == [(5, 14)]
    assert pair["status"] == "inserted"
    assert not pair["inherited_spans"] and not pair["ambiguous_spans"]
    assert result["counts"]["inserted_reference_occurrences"] == 1
    assert pair["evidence"]["exposure"] == "unknown"
    assert pair["evidence"]["source_use"] == "unobserved"


def test_repeated_identical_passages_follow_deterministic_alignment_not_copy_identity():
    repeated = "AlphaPage repeated. "
    initial = revision("t1", "TargetPage", 2, repeated * 2)
    changed = revision("t2", "TargetPage", 3, repeated * 3, parent="t1")
    result = analyze(source(), initial, changed)
    pair = pair_for(result, "t2")

    # Identical copies have no observable identity: alignment retains the prefix.
    assert [(s["start"], s["end"]) for s in pair["inherited_spans"]] == [(0, 9), (20, 29)]
    assert [(s["start"], s["end"]) for s in pair["inserted_spans"]] == [(40, 49)]
    assert audit_for(result, "t2")["inserted_character_spans"] == [[40, 60]]
    assert pair["status"] == "inserted" and not pair["ambiguous_spans"]
    counts = result["counts"]
    assert counts["naive_snapshot_pairs"] == counts["inserted_reference_pairs"] == 2
    assert counts["naive_snapshot_occurrences"] == 5
    assert counts["inserted_reference_occurrences"] == 3
    assert counts["inherited_reference_occurrences"] == 2


def test_moved_passage_can_align_as_insertion_without_new_authorship_or_use():
    passage = "AlphaPage section.\n"
    retained = "Long retained material goes here without any edits.\n"
    initial = revision("t1", "TargetPage", 2, passage + retained)
    changed = revision("t2", "TargetPage", 3, retained + passage, parent="t1")
    result = analyze(source(), initial, changed)
    pair = pair_for(result, "t2")

    # SequenceMatcher retains the longer block and represents the move as delete/insert.
    assert passage in initial.text and passage in changed.text
    assert audit_for(result, "t2")["inserted_character_spans"] == [
        [len(retained), len(changed.text)]
    ]
    assert [(s["start"], s["end"]) for s in pair["inserted_spans"]] == [
        (len(retained), len(retained) + len("AlphaPage"))
    ]
    assert pair["status"] == "inserted" and not pair["inherited_spans"]
    assert pair["evidence"]["exposure"] == "unknown"
    assert pair["evidence"]["source_use"] == "unobserved"


def test_mixed_inherited_and_boundary_ambiguous_pair_keeps_distinct_counter_scopes():
    initial = revision("t1", "TargetPage", 2, "AlphaPage xAlphaPage")
    changed = revision("t2", "TargetPage", 3, "AlphaPage AlphaPage", parent="t1")
    result = analyze(source(), initial, changed)
    pair = pair_for(result, "t2")

    assert audit_for(result, "t2")["eligible"]
    assert pair["status"] == "excluded_or_ambiguous"
    assert [(s["start"], s["end"]) for s in pair["inherited_spans"]] == [(0, 9)]
    assert [(s["start"], s["end"]) for s in pair["ambiguous_spans"]] == [(10, 19)]
    assert not pair["inserted_spans"]
    counts = result["counts"]
    assert counts["naive_snapshot_occurrences"] == 3
    assert counts["eligible_snapshot_occurrences"] == 1
    assert counts["inserted_reference_occurrences"] == 1
    # This counter includes resolved inherited spans inside otherwise ambiguous pairs.
    assert counts["inherited_reference_occurrences"] == 1
    assert counts["ambiguous_reference_occurrences"] == 1
    assert counts["eligible_snapshot_pairs"] == counts["inserted_reference_pairs"] == 1
    assert counts["excluded_or_ambiguous_pairs"] == 1


def test_own_page_title_is_excluded():
    initial = revision("s1", "AlphaPage", 1, "AlphaPage exists.")
    changed = revision("s2", "AlphaPage", 2, "AlphaPage exists. AlphaPage again.", parent="s1")
    result = analyze(initial, changed)
    assert result["pairs"] == []
    assert result["counts"]["naive_snapshot_pairs"] == 0


@pytest.mark.parametrize("parent,creation,expected", [
    (None, False, "missing_predecessor"),
    ("unavailable", False, "missing_predecessor"),
    ("s1", False, "wrong_page_predecessor"),
])
def test_missing_or_wrong_predecessor_excludes_attribution(parent, creation, expected):
    target = revision("t1", "TargetPage", 2, "AlphaPage", parent=parent, creation=creation)
    result = analyze(source(), target)
    assert result["counts"]["naive_snapshot_pairs"] == 1
    assert result["counts"]["inserted_reference_pairs"] == 0
    assert expected in pair_for(result, "t1")["exclusion_reasons"]
    assert result["counts"]["excluded_or_ambiguous_pairs"] == 1


def test_restoration_of_nonimmediate_snapshot_excluded_from_new_authorship():
    first = revision("t1", "TargetPage", 2, "AlphaPage")
    removal = revision("t2", "TargetPage", 3, "No references.", parent="t1")
    restoration = revision("t3", "TargetPage", 4, "AlphaPage", parent="t2")
    result = analyze(source(), first, removal, restoration)
    pair = pair_for(result, "t3")
    assert pair["status"] == "excluded_or_ambiguous"
    assert "restoration_of_earlier_snapshot" in pair["flags"]
    assert "restoration_not_new_authorship" in pair["exclusion_reasons"]
    assert result["counts"]["naive_snapshot_pairs"] == 2
    assert result["counts"]["inserted_reference_pairs"] == 1


def test_source_timestamp_tie_without_prior_source_is_ambiguous():
    target = revision("t1", "TargetPage", 1, "AlphaPage")
    result = analyze(source(), target)
    pair = pair_for(result, "t1")
    assert not pair["source_order_eligible"]
    assert "source_page_timestamp_tie" in pair["flags"]
    assert result["counts"]["naive_snapshot_pairs"] == 0
    assert result["counts"]["excluded_source_order_pairs"] == 1
    assert pair["source_revisions"] == []


def test_source_tie_does_not_override_strict_earlier_evidence():
    later_source = revision("s2", "AlphaPage", 2, "Updated source.", parent="s1")
    target = revision("t1", "TargetPage", 2, "AlphaPage")
    result = analyze(source(), later_source, target)
    pair = pair_for(result, "t1")
    assert pair["status"] == "inserted"
    assert [r["revision_id"] for r in pair["source_revisions"]] == ["s1"]
    assert "source_page_timestamp_tie" in pair["flags"]


def test_tied_same_page_revisions_are_not_arbitrarily_ordered():
    first = revision("t1", "TargetPage", 2, "No references.")
    changed = revision("t2", "TargetPage", 2, "AlphaPage", parent="t1")
    result = analyze(source(), first, changed)
    assert pair_for(result, "t2")["status"] == "excluded_or_ambiguous"
    assert "tied_same_page_timestamp" in audit_for(result, "t2")["flags"]


def test_tied_predecessors_are_not_arbitrarily_selected():
    first = revision("t1", "TargetPage", 2, "One.")
    second = revision("t2", "TargetPage", 2, "Two.", creation=False)
    target = revision("t3", "TargetPage", 3, "AlphaPage", parent="t1")
    result = analyze(source(), first, second, target)
    assert "tied_predecessor_timestamp" in pair_for(result, "t3")["flags"]
    assert pair_for(result, "t3")["status"] == "excluded_or_ambiguous"


@pytest.mark.parametrize("author,flags", [(None, ()), ("", ()), ("[REDACTED]", ("author_redacted",))])
def test_missing_redacted_author_preserves_extraction_but_identity_unknown(author, flags):
    target = revision("t1", "TargetPage", 2, "AlphaPage", author=author, flags=flags)
    result = analyze(source(), target)
    pair = pair_for(result, "t1")
    assert pair["status"] == "inserted"
    assert "missing_or_redacted_author" in pair["flags"]
    assert pair["evidence"]["cross_handle_status"] == "unknown"
    assert result["counts"]["distinct_inserted_target_handles"] == 0


def test_all_prior_source_revisions_are_retained_and_not_direct_parents():
    second = revision("s2", "AlphaPage", 2, "Second source snapshot.", parent="s1")
    target = revision("t1", "TargetPage", 3, "AlphaPage")
    result = analyze(source(), second, target)
    pair = pair_for(result, "t1")
    assert [r["revision_id"] for r in pair["source_revisions"]] == ["s1", "s2"]
    assert pair["evidence"]["cross_handle_status"] == "mixed"
    assert "direct_parent" not in pair


@pytest.mark.parametrize("source_handle,target_handle,status", [
    ("same-handle", "same-handle", "same"),
    ("first-handle", "second-handle", "different"),
    (None, "second-handle", "unknown"),
])
def test_handles_never_become_stable_run_identities(source_handle, target_handle, status):
    original = replace(source(), author=source_handle)
    target = revision("t1", "TargetPage", 2, "AlphaPage", author=target_handle)
    evidence = pair_for(analyze(original, target), "t1")["evidence"]
    assert evidence["cross_handle_status"] == status
    assert evidence["stable_identity"] == "unresolved"


def test_receipt_streams_unavailable_and_posted_read_claim_not_exposure():
    target = revision("t1", "TargetPage", 2, "I read AlphaPage and used it to write this.")
    pair = pair_for(analyze(source(), target), "t1")
    evidence = pair["evidence"]
    assert evidence["literal_reference"] == "observed"
    assert evidence["newly_inserted_reference"] is True
    assert evidence["request_evidence"] == "unavailable_for_source_reference"
    assert evidence["authenticated_delivery_evidence"] == "unavailable"
    assert evidence["authenticated_context_evidence"] == "unavailable"
    assert evidence["exposure"] == "unknown"
    assert evidence["source_use"] == "unobserved"
    assert all(key not in pair for key in ("requests", "deliveries", "contexts", "truth"))


def test_boundary_only_new_reference_is_ambiguous_not_inherited():
    initial = revision("t1", "TargetPage", 2, "xAlphaPage")
    target = revision("t2", "TargetPage", 3, "AlphaPage", parent="t1")
    result = analyze(source(), initial, target)
    pair = pair_for(result, "t2")
    assert pair["status"] == "excluded_or_ambiguous"
    assert len(pair["ambiguous_spans"]) == 1
    assert not pair["inherited_spans"] and not pair["inserted_spans"]
    assert result["counts"]["ambiguous_reference_occurrences"] == 1


def test_literal_unicode_case_sensitive_boundaries_and_no_regex_execution():
    title = "Über+Page"
    original = revision("s1", title, 1, "Source.")
    target = revision("t1", "TargetPage", 2,
                      "Über+Page; über+Page; Über+Pages; xÜber+Page; [Über+Page].")
    result = analyze(original, target)
    pair = pair_for(result, "t1", title)
    assert len(pair["inserted_spans"]) == 2
    assert all(span["matched_text"] == title for span in pair["inserted_spans"])


def test_does_not_normalize_canonically_equivalent_unicode():
    original = revision("s1", "CaféPage", 1, "Source.")
    target = revision("t1", "TargetPage", 2, "Cafe\u0301Page")
    result = analyze(original, target)
    assert result["pairs"] == []


def test_excluded_navigation_titles_are_recorded_and_not_matched():
    navigation = revision("s1", "HomePage", 1, "Navigation.")
    target = revision("t1", "TargetPage", 2, "HomePage")
    result = analyze(navigation, target)
    assert result["pairs"] == []
    assert "HomePage" in result["excluded_titles"]


def test_cross_site_titles_do_not_supply_same_site_page_evidence():
    other_site_source = replace(source(), site="OTHER")
    target = revision("t1", "TargetPage", 2, "AlphaPage")
    result = analyze(other_site_source, target)
    assert result["pairs"] == []
    assert result["counts"]["target_revisions"] == 1


def test_all_site_prior_occurrences_indexed_separately_from_same_site_sources():
    other = revision("o1", "SomePage", 2, "AlphaPage", site="OTHER")
    target = revision("t1", "TargetPage", 3, "AlphaPage")
    pair = pair_for(analyze(source(), other, target), "t1")
    assert [r["revision_id"] for r in pair["source_revisions"]] == ["s1"]
    occurrences = pair["prior_name_occurrences_all_supplied_sites"]
    assert [o["record"]["revision_id"] for o in occurrences] == ["o1"]
    assert occurrences[0]["record"]["site"] == "OTHER"


@pytest.mark.parametrize("timestamp", [None, "2026-01-01T00:02:00", "not-a-date",
                                       "2026-02-30T00:02:00Z"])
def test_unknown_timestamp_target_excluded_without_invented_order(timestamp):
    target = replace(revision("t1", "TargetPage", 2, "AlphaPage"), timestamp=timestamp)
    result = analyze(source(), target)
    pair = pair_for(result, "t1")
    assert pair["status"] == "excluded_or_ambiguous"
    assert "unknown_target_timestamp" in pair["exclusion_reasons"]
    assert not pair["source_revisions"]


def test_timezone_offsets_compared_as_instants_without_rewriting_source():
    original = replace(source(), timestamp="2026-01-01T01:01:00+01:00")
    target = revision("t1", "TargetPage", 2, "AlphaPage")
    pair = pair_for(analyze(original, target), "t1")
    assert pair["status"] == "inserted"
    assert pair["source_revisions"][0]["timestamp"] == original.timestamp
    assert parse_timestamp(original.timestamp) == parse_timestamp("2026-01-01T00:01:00Z")


def test_nonadjacent_parent_is_excluded_even_when_earlier():
    first = revision("t1", "TargetPage", 2, "One.")
    second = revision("t2", "TargetPage", 3, "Two.", parent="t1")
    target = revision("t3", "TargetPage", 4, "AlphaPage", parent="t1")
    pair = pair_for(analyze(source(), first, second, target), "t3")
    assert "nonadjacent_predecessor" in pair["exclusion_reasons"]
    assert pair["status"] == "excluded_or_ambiguous"


def test_unknown_same_page_chronology_prevents_predecessor_assurance():
    unknown = revision("t0", "TargetPage", None, "Unknown date.")
    target = revision("t1", "TargetPage", 2, "AlphaPage", parent="t0")
    pair = pair_for(analyze(source(), unknown, target), "t1")
    assert "ambiguous_predecessor_order" in pair["exclusion_reasons"]


def test_late_creation_metadata_is_not_used_as_empty_predecessor():
    first = revision("t1", "TargetPage", 2, "Some text.")
    target = revision("t2", "TargetPage", 3, "AlphaPage")
    pair = pair_for(analyze(source(), first, target), "t2")
    assert "contradictory_creation_metadata" in pair["exclusion_reasons"]


def test_missing_text_and_missing_parent_text_remain_explicit_exclusions():
    first = revision("t1", "TargetPage", 2, None)
    target = revision("t2", "TargetPage", 3, "AlphaPage", parent="t1")
    result = analyze(source(), first, target)
    assert "missing_text" in audit_for(result, "t1")["exclusion_reasons"]
    assert "missing_predecessor_text" in pair_for(result, "t2")["exclusion_reasons"]


def test_count_partitions_and_separate_pair_target_and_handle_units():
    other = revision("s2", "BetaPage", 1, "Another source.")
    first = revision("t1", "TargetPage", 2, "AlphaPage AlphaPage BetaPage")
    duplicate = revision("t2", "TargetPage", 3, first.text, parent="t1")
    result = analyze(source(), other, first, duplicate)
    count = result["counts"]
    assert count["naive_snapshot_pairs"] == 4
    assert count["inserted_reference_pairs"] == 2
    assert count["inserted_reference_occurrences"] == 3
    assert count["target_revisions_with_snapshot_match"] == 2
    assert count["target_revisions_with_inserted_reference"] == 1
    assert count["distinct_inserted_target_handles"] == 1
    assert count["eligible_snapshot_pairs"] == count["inserted_reference_pairs"] + count["inherited_only_pairs"]
    assert count["raw_snapshot_pairs_before_source_check"] == count["eligible_snapshot_pairs"] + count["excluded_or_ambiguous_pairs"]
    assert count["raw_snapshot_pairs_before_source_check"] == count["naive_snapshot_pairs"] + count["excluded_source_order_pairs"]


def test_input_order_does_not_change_results_or_offsets():
    first = revision("t1", "TargetPage", 2, "One.")
    target = revision("t2", "TargetPage", 3, "AlphaPage", parent="t1")
    assert analyze(source(), first, target) == analyze(target, source(), first)


def test_duplicate_revision_ids_within_site_rejected():
    with pytest.raises(ValueError, match="unique within a site"):
        analyze(source(), replace(source(), page="OtherPage"))


def test_same_revision_id_across_sites_allowed():
    result = analyze(source(), replace(source(), site="OTHER"))
    assert result["counts"]["total_input_revisions"] == 2
    assert result["counts"]["target_revisions"] == 1


def test_inert_markup_and_urls_never_executed_or_treated_as_receipts():
    target = revision("t1", "TargetPage", 2,
                      '<script>fetch("https://example.invalid/AlphaPage")</script>')
    pair = pair_for(analyze(source(), target), "t1")
    assert pair["inserted_spans"][0]["excerpt"].startswith("<script>")
    assert pair["evidence"]["exposure"] == "unknown"


@pytest.mark.parametrize("field", ["excerpt", "start", "source_hash", "source_timestamp"])
def test_evidence_verification_detects_corrupted_offsets_or_links(field):
    target = revision("t1", "TargetPage", 2, "Read AlphaPage.")
    records = (source(), target)
    result = copy.deepcopy(analyze(*records))
    pair = result["pairs"][0]
    if field == "excerpt":
        pair["snapshot_spans"][0]["excerpt"] = "Wrong excerpt."
    elif field == "start":
        pair["snapshot_spans"][0]["start"] += 1
    elif field == "source_hash":
        pair["source_revisions"][0]["record_sha256"] = "0" * 64
    else:
        pair["source_revisions"][0]["timestamp"] = target.timestamp
    with pytest.raises(AssertionError):
        verify_evidence(records, result)


def test_long_excerpts_capped_and_unicode_codepoint_offsets_resolve():
    target = revision("t1", "TargetPage", 2, "🦔 " + "a " * 200 + "AlphaPage " + "b " * 200)
    pair = pair_for(analyze(source(), target), "t1")
    span = pair["inserted_spans"][0]
    assert span["start"] == 402
    assert len(span["excerpt"]) <= 160
    assert target.text[span["start"]:span["end"]] == "AlphaPage"


def test_empty_target_site_reports_zero_observations_without_groundtruth_metrics():
    result = analyze(replace(source(), site="OTHER"))
    assert result["counts"]["target_revisions"] == 0
    assert result["pairs"] == []
    assert not {"precision", "recall", "theta", "coverage"} & result["counts"].keys()


@pytest.mark.parametrize("seconds,expected", [(1, False), (2, False), (3, True)])
def test_timestamp_uncertainty_requires_strict_interval_separation(seconds, expected):
    original = replace(source(), timestamp="2026-01-01T00:00:00Z",
                       timestamp_uncertainty_seconds=1)
    target = replace(revision("t1", "TargetPage", 2, "AlphaPage"),
                     timestamp=f"2026-01-01T00:00:{seconds:02}Z",
                     timestamp_uncertainty_seconds=1)
    pair = pair_for(analyze(original, target), "t1")
    assert pair["source_order_eligible"] is expected
    assert (pair["status"] == "inserted") is expected
    if not expected:
        assert "overlapping_source_timestamp_intervals" in pair["flags"]


def test_parent_uncertainty_overlap_prevents_insertion_attribution():
    first = replace(revision("t1", "TargetPage", 2, "No reference."),
                    timestamp="2026-01-01T00:02:00Z", timestamp_uncertainty_seconds=1)
    target = replace(revision("t2", "TargetPage", 3, "AlphaPage", parent="t1"),
                     timestamp="2026-01-01T00:02:01Z", timestamp_uncertainty_seconds=1)
    pair = pair_for(analyze(source(), first, target), "t2")
    assert pair["source_order_eligible"]
    assert pair["status"] == "excluded_or_ambiguous"
    assert "overlapping_same_page_timestamp_intervals" in pair["flags"]


@pytest.mark.parametrize("flag", ["publisher_recreation", "publisher_revert"])
def test_publisher_recreation_or_revert_excluded_even_without_full_snapshot_repeat(flag):
    target = revision("t1", "TargetPage", 2, "AlphaPage", flags=(flag,))
    pair = pair_for(analyze(source(), target), "t1")
    assert pair["source_order_eligible"]
    assert pair["status"] == "excluded_or_ambiguous"
    assert "publisher_recreation_or_revert_not_new_authorship" in pair["exclusion_reasons"]


def test_added_line_snippets_never_become_targets_or_sourcepage_history():
    snippet = replace(revision("aux1", "AlphaPage", 1, "OtherPage"),
                      text_kind="added_line_snippet", timestamp_uncertainty_seconds=None,
                      source_json_pointer="/pages/0/revisions/0/added")
    other = revision("other1", "OtherPage", 2, "Source.")
    target = revision("t1", "TargetPage", 3, "AlphaPage")
    result = analyze(snippet, other, target)
    assert result["counts"]["target_revisions"] == 2
    assert result["pairs"] == []
    assert all(a["target"]["revision_id"] != "aux1" for a in result["revision_audit"])


def test_unknown_uncertainty_snippet_occurrence_has_explicit_nominal_only_status():
    snippet = replace(revision("aux1", "OtherPage", 2, "AlphaPage", site="OTHER"),
                      text_kind="added_line_snippet", timestamp_uncertainty_seconds=None,
                      source_json_pointer="/pages/0/revisions/0/added")
    target = revision("t1", "TargetPage", 3, "AlphaPage")
    pair = pair_for(analyze(source(), snippet, target), "t1")
    occurrence = pair["prior_name_occurrences_all_supplied_sites"][0]
    assert occurrence["record"]["source_json_pointer"] == "/pages/0/revisions/0/added"
    assert occurrence["temporal_status"] == "nominal_earlier_uncertainty_unknown"
    assert [s["revision_id"] for s in pair["source_revisions"]] == ["s1"]


@pytest.mark.parametrize("uncertainty", [-1, float("nan"), float("inf"), "1"])
def test_invalid_timestamp_uncertainty_rejected(uncertainty):
    with pytest.raises(ValueError, match="uncertainty"):
        analyze(replace(source(), timestamp_uncertainty_seconds=uncertainty))


@pytest.mark.parametrize("timestamp", ["2026-01-01T01:01:00+01:99",
                                       "2026-01-01T01:01:00.1234567Z"])
def test_invalid_zone_or_submicrosecond_precision_not_silently_normalized(timestamp):
    assert parse_timestamp(timestamp) is None


def test_partial_snippet_cannot_supply_complete_predecessor():
    partial = replace(revision("t1", "TargetPage", 2, "Old snippet."),
                      text_kind="added_line_snippet")
    target = revision("t2", "TargetPage", 3, "AlphaPage", parent="t1")
    pair = pair_for(analyze(source(), partial, target), "t2")
    assert pair["status"] == "excluded_or_ambiguous"
    assert "partial_predecessor_text" in pair["exclusion_reasons"]
