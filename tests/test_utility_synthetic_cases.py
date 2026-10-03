"""Mechanistic finite-world certificates for the utility reasoning fixtures."""

from copy import deepcopy

import pytest

from tracebench.investigator_utility.synthetic_cases import (
    InconsistentEvidenceError,
    build_synthetic_cases,
    enumerate_compatible_worlds,
    validate_synthetic_gold,
)


@pytest.fixture
def study():
    return build_synthetic_cases()


def statuses(gold):
    return [claim["status"] for claim in gold["claims"]]


def test_fixed_counts_split_clusters_and_reproducibility(study):
    cases, gold, manifest = study
    assert study == build_synthetic_cases()
    assert len(cases) == len(gold) == 10
    assert sum(case["split"] == "evaluation" for case in cases) == 8
    assert sum(case["split"] == "development" for case in cases) == 2
    assert len({case["cluster_id"] for case in cases}) == len(cases)
    assert manifest["evaluation_cases"] == 8
    assert all(len(case["claims"]) == 4 for case in cases)
    assert all(set(claim) == {"id", "text"} for case in cases for claim in case["claims"])


@pytest.mark.parametrize("index", range(10))
def test_gold_certificates_reenumerate_and_partition_all_worlds(study, index):
    cases, labels, _ = study
    case, gold = cases[index], labels[index]
    validate_synthetic_gold(case, gold)
    worlds = enumerate_compatible_worlds(case)
    all_ids = {world["world_id"] for world in worlds}
    assert worlds == gold["validation"]["compatible_worlds"]
    assert len(worlds) > 0
    for claim in gold["claims"]:
        certificate = claim["certificate"]
        true_ids, false_ids = map(set, (certificate["true_world_ids"],
                                       certificate["false_world_ids"]))
        assert true_ids | false_ids == all_ids
        assert not true_ids & false_ids
        examples = certificate["disagreeing_constructions"]
        if claim["status"] == "unresolved":
            assert len(examples) == 2
            assert examples[0] in worlds and examples[1] in worlds
            assert examples[0]["world_id"] in true_ids
            assert examples[1]["world_id"] in false_ids
        else:
            assert not examples


def test_surviving_authentic_context_establishes_missing_upstream_events(study):
    cases, gold, _ = study
    assert [row["kind"] for row in cases[2]["records"]][3:] == ["context"]
    assert statuses(gold[2]) == ["established"] * 3 + ["unresolved"]


def test_delivery_without_context_record_remains_unknown_without_complete_logging(study):
    _, gold, _ = study
    assert statuses(gold[3]) == ["established", "established", "unresolved", "unresolved"]
    assert statuses(gold[4]) == ["established", "established", "ruled_out", "ruled_out"]


def test_complete_delivery_logs_distinguish_real_nondelivery_from_missing_record(study):
    _, gold, _ = study
    assert statuses(gold[5]) == ["established", "ruled_out", "ruled_out", "ruled_out"]
    assert statuses(gold[2])[1] == "established"


def test_source_and_shared_mechanisms_really_generate_identical_visible_output(study):
    cases, labels, _ = study
    case, gold = cases[6], labels[6]
    assert statuses(gold) == ["established", "established", "established", "unresolved"]
    use_certificate = gold["claims"][3]["certificate"]
    yes, no = use_certificate["disagreeing_constructions"]
    assert yes["scopes"] == no["scopes"]
    assert yes["source_selected"] is True and no["source_selected"] is False
    assert yes["construction"]["mechanism"] == "copy_source_payload"
    assert no["construction"]["mechanism"] == "fill_shared_scaffold"
    source, shared, target = case["records"][:3]
    assert yes["construction"]["input_record_id"] == source["id"]
    assert no["construction"]["input_record_id"] == shared["id"]
    source_rendered = "Result: " + source["body"] + "."
    scaffold_rendered = "Result: " + shared["scaffold"].format(topic=shared["topic"]) + "."
    assert source_rendered == scaffold_rendered == target["body"]
    assert yes["construction"]["output_text"] == no["construction"]["output_text"]


def test_incompatible_output_mechanism_is_rejected_not_just_label_toggled(study):
    cases, _, _ = study
    changed_source = deepcopy(cases[6])
    changed_source["records"][0]["body"] = "An incompatible payload"
    worlds = enumerate_compatible_worlds(changed_source)
    assert worlds and all(not world["source_selected"] for world in worlds)
    changed_shared = deepcopy(cases[6])
    changed_shared["records"][1]["topic"] = "An incompatible scaffold input"
    worlds = enumerate_compatible_worlds(changed_shared)
    assert worlds and all(world["source_selected"] for world in worlds)


def test_all_missing_request_records_with_relevant_complete_scope_rule_out_chain(study):
    _, labels, _ = study
    assert statuses(labels[7]) == ["ruled_out"] * 4


@pytest.mark.parametrize("scope_dimension", ["source_id", "run_id", "window"])
def test_completeness_cannot_be_extrapolated_to_other_source_run_or_window(study, scope_dimension):
    cases, _, _ = study
    changed = deepcopy(cases[4])
    context_assumption = next(
        a for a in changed["assumptions"]
        if a.get("parameters", {}).get("channel") == "context"
    )
    context_assumption["parameters"][scope_dimension] = (
        [20, 30] if scope_dimension == "window" else "another_value"
    )
    p = context_assumption["parameters"]
    context_assumption["text"] = (
        f"The context channel is complete for source {p['source_id']}, "
        f"run {p['run_id']}, within inclusive interval {p['window']}."
    )
    worlds = enumerate_compatible_worlds(changed)
    assert {world["source_selected"] for world in worlds} == {False, True}
    assert {bool(world["scopes"][0]["events"][-1]["kind"] == "context")
            for world in worlds} == {False, True}


def test_fixed_irrelevant_scope_cases_have_unresolved_claims(study):
    _, labels, _ = study
    assert statuses(labels[8]) == ["unresolved"] * 4
    assert statuses(labels[9]) == ["established", "established", "unresolved", "unresolved"]


@pytest.mark.parametrize("problem", ["contradictory_completeness", "no_rendering_mechanism"])
def test_inconsistent_evidence_is_excluded_not_vacuously_established(study, problem):
    cases, _, _ = study
    changed = deepcopy(cases[2])
    if problem == "contradictory_completeness":
        assumption = deepcopy(changed["assumptions"][-1])
        assumption["id"] = "a99"
        assumption["parameters"]["channel"] = "delivery"
        assumption["text"] = assumption["text"].replace("context channel", "delivery channel")
        changed["assumptions"].append(assumption)
    else:
        changed["records"][2]["body"] = "Neither declared mechanism produces this"
    with pytest.raises(InconsistentEvidenceError, match="No compatible world"):
        enumerate_compatible_worlds(changed)


@pytest.mark.parametrize("field", ["status", "worlds", "construction"])
def test_tampered_verdict_or_certificate_fails_reenumeration(study, field):
    cases, labels, _ = study
    tampered = deepcopy(labels[6])
    if field == "status":
        tampered["claims"][-1]["status"] = "established"
    elif field == "worlds":
        tampered["validation"]["compatible_worlds"].pop()
    else:
        tampered["claims"][-1]["certificate"]["disagreeing_constructions"][0][
            "construction"]["output_text"] = "Invented output"
    with pytest.raises(ValueError, match="differs from finite re-enumeration"):
        validate_synthetic_gold(cases[6], tampered)


def test_public_view_contains_no_evaluator_fields_and_gold_mutation_cannot_change_it(study):
    cases, gold, _ = study
    public_copy = deepcopy(cases)
    gold[0]["claims"][0]["status"] = "a changed hidden verdict"
    gold[0]["validation"]["compatible_worlds"][0]["source_selected"] = "not a public value"
    assert cases == public_copy

    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    assert not {"status", "certificate", "source_selected", "truth", "gold",
                "validation", "verdict", "answers"} & set(keys(cases))


def test_evaluation_has_both_definite_classes_but_no_established_source_use(study):
    cases, labels, _ = study
    evaluation = [gold for case, gold in zip(cases, labels, strict=True)
                  if case["split"] == "evaluation"]
    assert {claim["status"] for gold in evaluation for claim in gold["claims"]} == {
        "established", "ruled_out", "unresolved"}
    assert all(gold["claims"][-1]["status"] != "established" for gold in evaluation)
    assert sum(claim["status"] != "unresolved" for gold in evaluation
               for claim in gold["claims"]) == 22


@pytest.mark.parametrize("index", [1, 2])
def test_authentication_and_logging_rules_cannot_be_assumed_when_withheld(study, index):
    cases, _, _ = study
    changed = deepcopy(cases[2])
    changed["assumptions"].pop(index)
    with pytest.raises(ValueError, match="assumption must be"):
        enumerate_compatible_worlds(changed)


def test_contradictory_human_readable_and_structured_scope_is_rejected(study):
    cases, _, _ = study
    changed = deepcopy(cases[2])
    changed["assumptions"][-1]["text"] = "All delivery logs are complete everywhere."
    with pytest.raises(ValueError, match="Invalid scoped completeness"):
        enumerate_compatible_worlds(changed)


@pytest.mark.parametrize("interval,expected", [([0, 3], {False, True}),
                                               ([4, 4], {False}),
                                               ([5, 10], {False, True})])
def test_completeness_covers_only_event_timestamps_in_its_inclusive_interval(
        study, interval, expected):
    cases, _, _ = study
    changed = deepcopy(cases[4])
    declaration = changed["assumptions"][-1]
    declaration["parameters"]["window"] = interval
    p = declaration["parameters"]
    declaration["text"] = (f"The context channel is complete for source {p['source_id']}, "
                           f"run {p['run_id']}, within inclusive interval {interval}.")
    assert {world["source_selected"] for world in enumerate_compatible_worlds(changed)} == expected


def test_altered_mechanistic_contract_is_not_silently_ignored(study):
    cases, _, _ = study
    changed = deepcopy(cases[6])
    changed["assumptions"][0]["text"] = "Every output must use its source record."
    with pytest.raises(ValueError, match="supported semantics"):
        enumerate_compatible_worlds(changed)
