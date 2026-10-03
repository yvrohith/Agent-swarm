"""The triplet relationships follow from each supplied receipt contract."""

from collections import Counter
from copy import deepcopy

import pytest

from tracebench.evidence_responsiveness.common import ROLES, canonical, digest
from tracebench.evidence_responsiveness.receipts import (
    MOTIFS,
    PUBLIC_FIELDS,
    _oracle_case,
    _settings,
    build_receipt_families,
    certify_receipt,
)
from tracebench.investigator_utility import synthetic_cases as oracle


@pytest.fixture(scope="module")
def study():
    return build_receipt_families()


def _status(gold):
    return gold["claims"][0]["status"]


def test_fixed_counts_determinism_and_independent_split_instances(study):
    assert study == build_receipt_families()
    assert len(study["cases"]) == len(study["gold"]) == 27
    assert Counter(f["split"] for f in study["families"]) == {"evaluation": 8, "development": 1}
    assert Counter(f["motif"] for f in study["families"] if f["split"] == "evaluation") == {
        motif: 2 for motif in MOTIFS}
    assert len({c["case_id"] for c in study["cases"]}) == 27
    assert len({f["cluster_id"] for f in study["families"]}) == 9
    sources = {}
    bodies = {}
    for family in study["families"]:
        case = next(c for c in study["cases"] if c["case_id"] == family["variants"]["base"])
        sources[family["family_id"]] = _settings(case)["target_scope"]["source_id"]
        bodies[family["family_id"]] = next(r["body"] for r in case["records"]
                                             if r["kind"] == "source_write")
    assert len(set(sources.values())) == len(set(bodies.values())) == 9


@pytest.mark.parametrize("index", range(27))
def test_every_actual_variant_reenumerates_and_certifies_world_partition(study, index):
    case, gold = study["cases"][index], study["gold"][index]
    assert certify_receipt(case) == gold
    worlds = oracle.enumerate_compatible_worlds(_oracle_case(case))
    assert worlds == gold["validation"]["compatible_worlds"]
    assert worlds
    assert gold["validation"]["public_case_sha256"] == digest({k: case[k] for k in PUBLIC_FIELDS})
    certificate = gold["claims"][0]["certificate"]
    yes, no = set(certificate["true_world_ids"]), set(certificate["false_world_ids"])
    assert yes | no == {w["world_id"] for w in worlds}
    assert not yes & no
    if _status(gold) == "established":
        assert yes and not no
    elif _status(gold) == "ruled_out":
        assert no and not yes
    else:
        true, false = certificate["disagreeing_constructions"]
        assert true in worlds and false in worlds
        assert true["world_id"] in yes and false["world_id"] in no
        assert true["scopes"] != false["scopes"]
        assert true["construction"]["output_text"] == false["construction"]["output_text"]
    # All relevant source/shared outputs coincide; exposure never establishes use.
    if _status(gold) != "ruled_out":
        assert {w["source_selected"] for w in worlds} == {False, True}
        assert {w["construction"]["mechanism"] for w in worlds} == {
            "copy_source_payload", "fill_shared_scaffold"}


@pytest.mark.parametrize("index", range(9))
def test_family_relationships_and_expected_balanced_direction(study, index):
    family = study["families"][index]
    labels = {g["case_id"]: g for g in study["gold"]}
    actual = [_status(labels[family["variants"][role]]) for role in ROLES]
    definite = ("ruled_out" if family["motif"].startswith("completeness") else "established")
    relevant = family["provenance"]["instance"] % 2 == 0
    assert actual == ([definite, definite, "unresolved"] if relevant
                      else ["unresolved", "unresolved", definite])


def test_adapter_changes_queries_and_private_schema_only_not_public_evidence(study):
    for case in study["cases"]:
        adapted = _oracle_case(case)
        assert canonical(adapted["records"]) == canonical(case["records"])
        assert canonical(adapted["assumptions"]) == canonical(case["assumptions"])
        assert set(k for k in adapted if adapted[k] != case[k]) == {"subset", "claims"}
        assert adapted["claims"][2]["text"] == case["claims"][0]["text"]


def test_query_selection_does_not_affect_world_enumeration(study, monkeypatch):
    # The existing public entry point validates its historical query template.
    # After that validation, query descriptions have no role in the enumerator.
    # Keep its validated contract/evidence fixed while varying only query lists.
    case = _oracle_case(study["cases"][2])
    checked_settings = oracle._contract(case)
    expected = oracle.enumerate_compatible_worlds(case)
    monkeypatch.setattr(oracle, "_contract", lambda _: checked_settings)
    for queries in ([], [{"id": "q0", "text": "An unrelated query"}], case["claims"][:1]):
        changed = deepcopy(case)
        changed["claims"] = queries
        assert oracle.enumerate_compatible_worlds(changed) == expected


def test_scope_identity_and_timestamped_records_are_consistent(study):
    for case in study["cases"]:
        settings = _settings(case)
        scopes = settings["scopes"]
        assert len(scopes) == len({oracle._scope_key(s) for s in scopes}) == 3
        assert scopes[0]["source_id"] == scopes[1]["source_id"]
        assert scopes[0]["run_id"] != scopes[1]["run_id"]
        assert scopes[0]["source_id"] != scopes[2]["source_id"]
        assert scopes[0]["run_id"] == scopes[2]["run_id"]
        for row in case["records"]:
            if row["kind"] in oracle.CHANNELS:
                assert oracle._scope_key(row) in {oracle._scope_key(s) for s in scopes}
                assert row["timestamp"] == oracle._event_time(row, row["kind"])
        for assumption in case["assumptions"]:
            p = assumption.get("parameters", {})
            if p.get("type") == "complete_logging":
                assert (p["source_id"], p["run_id"]) in {
                    (s["source_id"], s["run_id"]) for s in scopes}
                assert assumption["text"] == oracle._completeness_text(p["channel"], p)


def test_nuisance_transformations_retain_evidence_content_or_biject_identifiers(study):
    cases = {c["case_id"]: c for c in study["cases"]}
    for family in study["families"]:
        base = cases[family["variants"]["base"]]
        control = cases[family["variants"]["irrelevant"]]
        transform = family["transformations"]["irrelevant"]
        if "identifier_bijection" in transform:
            mapping = transform["identifier_bijection"]
            assert len(set(mapping.values())) == len(mapping)
            original = canonical({k: base[k] for k in PUBLIC_FIELDS if k != "case_id"})
            for before, after in mapping.items():
                original = original.replace(before, after)
            assert original == canonical({k: control[k] for k in PUBLIC_FIELDS if k != "case_id"})
        else:
            assert control["records"] == base["records"][::-1]
            assert control["assumptions"] == base["assumptions"]
            assert control["claims"] == base["claims"]


@pytest.mark.parametrize("problem", ["incompatible_output", "contradictory_logging", "wrong_query"])
def test_contradictions_and_unsupported_primary_queries_are_rejected(study, problem):
    case = deepcopy(study["cases"][0])
    if problem == "incompatible_output":
        next(r for r in case["records"] if r["kind"] == "target_write")["body"] = "No mechanism renders this"
    elif problem == "contradictory_logging":
        scope = deepcopy(_settings(case)["target_scope"])
        case["assumptions"].append({
            "id": "a99", "text": oracle._completeness_text("delivery", scope),
            "parameters": {"type": "complete_logging", "channel": "delivery", **scope}})
    else:
        case["claims"][0]["text"] = "Source use is established."
    with pytest.raises(ValueError):
        certify_receipt(case)


def test_evaluator_only_metadata_cannot_affect_certification(study):
    case = deepcopy(study["cases"][0])
    original = certify_receipt(case)
    case.update({"split": "not transmitted", "cluster_id": "not transmitted"})
    revised = certify_receipt(case)
    assert revised["claims"] == original["claims"]
    assert revised["validation"]["compatible_worlds"] == original["validation"]["compatible_worlds"]
    assert revised["validation"]["public_case_sha256"] == original["validation"]["public_case_sha256"]


def test_public_payload_has_no_roles_motifs_or_evaluator_labels(study):
    forbidden = {"status", "certificate", "gold", "validation", "source_selected",
                 "variants", "transformations", "family_id", "cluster_id", "split", "motif"}

    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    for case in study["cases"]:
        public = {k: case[k] for k in PUBLIC_FIELDS}
        assert not forbidden & set(keys(public))
        assert case["claims"][0]["id"] == "q0"
        assert all(motif not in canonical(public) for motif in MOTIFS)
        assert all(role not in case["case_id"] for role in ROLES)
