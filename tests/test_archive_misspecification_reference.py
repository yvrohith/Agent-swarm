"""Development-only physical and certificate checks for the independent path."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from studies.archive_model_misspecification.analysis import analyze_cell

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / f"studies/archive_model_misspecification/{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


reference = module("reference")
expanded = module("expanded")
DEVELOPMENT = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())


@pytest.mark.parametrize("index", range(4))
def test_independent_closure_provenance_and_full_certificates_on_development(index):
    problem = DEVELOPMENT[index]
    previous = set()
    for k in (0, 1, 2):
        model = expanded.ExpandedModel(problem, k)
        rebuilt = reference.verify_expansion(problem, k, model.to_dict())
        current = {reference.canonical(reference.physical(w)) for w in rebuilt["worlds"]}
        assert previous <= current
        previous = current
        for signature in model.signature_cells:
            history = [{"query_id": qid, "outcome_id": outcome}
                       for qid, outcome in zip(model.query_ids, signature, strict=True)]
            result = reference.inspect_history(problem, rebuilt["worlds"], history)
            assert result["claim_status"] == model.claim_status(history)
            assert result["terminal_status"] == model.terminal_status(history)
            reference.verify_expanded_certificate(problem, k, model.certificate(history), rebuilt)


def test_alias_omission_changes_every_lookup_of_one_physical_record():
    problem = copy.deepcopy(DEVELOPMENT[0])
    context = next(q for q in problem["queries"] if q["kind"] == "context_receipt")
    alias = copy.deepcopy(context)
    alias["id"] = "alias_context"
    problem["queries"].append(alias)
    rebuilt = reference.reconstruct(problem, 1)
    positions = [i for i, q in enumerate(problem["queries"]) if q["record_id"] == context["record_id"]]
    for world in rebuilt["worlds"]:
        signature = reference.full_signature(problem, world)
        assert signature[positions[0]] == signature[positions[1]]
        for origin in world["origins"]:
            if context["record_id"] in origin["omitted_record_ids"]:
                assert {context["id"], alias["id"]} <= set(origin["affected_query_ids"])


@pytest.mark.parametrize("tamper", ["events", "retained", "origin", "answers", "contract"])
def test_saved_expansion_tampering_is_detected(tamper):
    problem = DEVELOPMENT[0]
    saved = expanded.ExpandedModel(problem, 1).to_dict()
    if tamper == "events":
        saved["worlds"][0]["occurring_event_ids"] = []
    elif tamper == "retained":
        saved["worlds"][0]["retained_record_ids"] = []
    elif tamper == "origin":
        saved["worlds"][0]["provenance"][0]["omitted_record_ids"] = ["invented"]
    elif tamper == "answers":
        saved["answers"][0][0] = "invented"
    else:
        saved["contract"]["completeness_assumption_change"] = "completeness still reliable"
    with pytest.raises(ValueError):
        reference.verify_expansion(problem, 1, saved)


def test_nominal_certificate_cannot_be_relabelled_by_changing_only_hashes():
    problem = DEVELOPMENT[0]
    model = expanded.ExpandedModel(problem, 1)
    rebuilt = reference.reconstruct(problem, 1)
    cert = model.nominal.certificate([])
    cert.update(reference._pins(problem, 1, rebuilt))
    with pytest.raises((ValueError, KeyError)):
        reference.verify_expanded_certificate(problem, 1, cert, rebuilt)


def tiny_support():
    problem = {
        "claim": {"kind": "any_context_exposure", "source_ids": ["s"], "recipient": "r",
                  "window": [0, 10], "target_write_id": "target"},
        "event_catalog": [{"id": "event", "kind": "context", "source_id": "s", "recipient": "r", "time": 5}],
        "queries": [{"id": "q0", "record_id": "receipt"}, {"id": "q1", "record_id": "other"}],
    }
    def world(name, truth, retained):
        return {"id": name, "occurring_event_ids": ["event"] if truth else [],
                "retained_record_ids": retained, "selected_source_ids": [], "source_mechanism": "shared_input",
                "recipient_writes": [{"id": "target", "time": 10, "recipient": "r"}]}
    return problem, [world("false", False, []), world("true", True, []), world("new", False, ["other"])]


def test_empty_compatibility_is_conflict_not_vacuous_certainty():
    problem, worlds = tiny_support()
    status = reference.inspect_history(problem, worlds, [{"query_id": "q0", "outcome_id": "present"}])
    assert status["claim_status"] == status["terminal_status"] == "model_conflict"


def test_one_opposite_pair_does_not_establish_partial_history_irreducibility():
    problem, worlds = tiny_support()
    old = reference.inspect_history(problem, worlds[:2], [])
    new = reference.inspect_history(problem, worlds, [])
    assert old["claim_status"] == new["claim_status"] == "unresolved"
    assert old["terminal_status"] == "archive_irreducible"
    assert new["terminal_status"] == "unresolved_pending"
    retained_cell = reference.inspect_history(problem, worlds, [{"query_id": "q1", "outcome_id": "missing"}])
    assert retained_cell["terminal_status"] == "archive_irreducible"


def test_same_signature_witness_check_includes_unqueried_actions():
    problem, worlds = tiny_support()
    assert reference.check_same_signature_opposites(problem, worlds[0], worlds[1]) == 2
    with pytest.raises(ValueError, match="catalogue action"):
        reference.check_same_signature_opposites(problem, worlds[1], worlds[2])


def test_claim_is_derived_from_scope_and_source_use_not_record_loss_or_labels():
    problem, worlds = tiny_support()
    positive = copy.deepcopy(worlds[1])
    positive["claim_value"] = False
    assert reference.claim_value(problem, positive)
    problem["claim"]["recipient"] = "wrong_recipient"
    assert not reference.claim_value(problem, positive)
    problem["claim"]["recipient"] = "r"
    problem["claim"]["window"] = [6, 10]
    assert not reference.claim_value(problem, positive)
    problem["claim"]["window"] = [0, 10]
    problem["claim"]["kind"] = "source_use"
    assert not reference.claim_value(problem, positive)
    positive["selected_source_ids"] = ["s"]
    assert reference.claim_value(problem, positive)


@pytest.fixture(scope="module")
def development_cell():
    problem = DEVELOPMENT[1]
    return problem, analyze_cell(problem, 1)


def test_saved_census_and_paid_policy_histories_verify_independently(development_cell):
    problem, cell = development_cell
    checked = reference.verify_cell(problem, 1, cell)
    assert checked["verified"] and checked["signature_rows"] == len(cell["signature_rows"])
    assert checked["policy_histories"] == checked["signature_rows"]
    assert checked["counterexamples"] == cell["counts"]["lost_definite"]
    assert checked["nominal_conflicts"] == cell["counts"]["new_signatures"]


@pytest.mark.parametrize("tamper", ["population", "transition", "cost", "outcome", "counterexample", "denominator"])
def test_saved_conclusions_witnesses_and_accounting_cannot_override_reference(development_cell, tamper):
    problem, original = development_cell
    cell = copy.deepcopy(original)
    row = cell["signature_rows"][0]
    if tamper == "population":
        row["population"] = "new" if row["population"] == "original" else "original"
    elif tamper == "transition":
        row["transition"] = "invented_transition"
    elif tamper == "cost":
        row["policy"]["cost"] += 1
    elif tamper == "outcome":
        item = next(r["policy"]["history"][0] for r in cell["signature_rows"] if r["policy"]["history"])
        item["outcome_id"] = "missing" if item["outcome_id"] == "present" else "present"
    elif tamper == "counterexample":
        witness = next(r["counterexample"] for r in cell["signature_rows"] if r["counterexample"])
        witness["expanded_claim_value"] = witness["nominal_claim_value"]
    else:
        cell["counts"]["original_signatures"] -= 1
    with pytest.raises(ValueError):
        reference.verify_cell(problem, 1, cell)


def test_failed_cell_is_visible_as_unverified_not_silently_omitted():
    problem = DEVELOPMENT[0]
    cell = {"problem_id": problem["problem_id"], "stratum": problem["stratum"],
            "subtype": problem["subtype"], "k": 1, "status": "unavailable", "census_status": "unavailable",
            "failure": {"kind": "declared_cap"}}
    result = reference.verify_cell(problem, 1, cell)
    assert not result["verified"] and result["failure"] == cell["failure"]
