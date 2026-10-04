"""Finite-model logic, temporal independence and certificate tests; no policy evaluation."""
import copy
from fractions import Fraction

import pytest

from tracebench.evidence_acquisition import Model
from tracebench.evidence_acquisition.generator import generate_problem, generate_split
from tracebench.evidence_acquisition.model import indices


def query(model, record_id):
    return next(qid for qid, q in model.queries.items() if q["record_id"] == record_id)


def history(model, **records):
    return [{"query_id": query(model, record), "outcome_id": outcome}
            for record, outcome in records.items()]


def test_split_bounds_uniformity_reproducibility_and_no_realized_world():
    for split, count in (("development", 4), ("evaluation", 40)):
        problems = generate_split(split)
        assert len(problems) == count
        for problem in problems:
            assert problem == generate_problem(problem["seed"])
            model = Model(problem)
            assert 0 < len(model.worlds) <= 64
            assert 0 < len(model.queries) <= 8
            assert set(model.priors) == {Fraction(1, len(model.worlds))}
            assert set(q["cost"] for q in model.queries.values()) <= {1, 2, 4}
            assert all(len(q["outcomes"]) == 2 for q in model.queries.values())
            assert "actual_world_id" not in problem
            assert model.verify_certificate(model.certificate([]))


def test_not_queried_nonoccurrence_and_nonretention_are_distinct():
    model = Model(generate_problem(94100))
    missing = model.compatible(history(model, record_context_0="missing"))
    assert model.compatible([]) == model.full_state
    assert missing != model.full_state
    assert {model.claim_values[i] for i in indices(missing)} == {False, True}
    nonoccurrence = [i for i in indices(missing) if "context_0" not in model.worlds[i]["occurring_event_ids"]]
    nonretention = [i for i in indices(missing) if "context_0" in model.worlds[i]["occurring_event_ids"]]
    assert nonoccurrence and nonretention
    assert model.queries[query(model, "record_context_0")]["outcomes"]["missing"]["kind"] == "lookup_empty"


def test_downstream_positive_context_survives_missing_upstream_record():
    model = Model(generate_problem(94100))
    observations = history(model, record_context_0="present", record_request_0="missing")
    state = model.compatible(observations)
    assert state and model.terminal(state) == "established"
    assert all("request_0" in model.worlds[i]["occurring_event_ids"] for i in indices(state))
    assert model.verify_certificate(model.certificate(observations))


def test_negative_requires_absence_and_correct_scope_completeness():
    model = Model(generate_problem(94210))
    absent = history(model, record_context_0="missing")
    wrong = absent + history(model, wrong_complete="present")
    correct = absent + history(model, complete_0="present")
    assert model.terminal(model.compatible(absent)) is None
    assert model.terminal(model.compatible(wrong)) is None
    assert model.terminal(model.compatible(history(model, complete_0="present"))) is None
    assert model.terminal(model.compatible(correct)) == "ruled_out"
    assert model.verify_certificate(model.certificate(correct))


def test_inconsistent_history_is_not_vacuous_entailment():
    model = Model(generate_problem(94100))
    contradiction = history(model, record_context_0="missing") + history(model, record_context_0="present")
    assert model.compatible(contradiction) == 0
    cert = model.certificate(contradiction)
    assert cert["status"] == "inconsistent"
    assert cert["exhaustive_compatible_hypotheses"] == []
    assert model.verify_certificate(cert)
    with pytest.raises(ValueError, match="contradicts"):
        model.certificate(contradiction, "established")


def test_global_ambiguity_covers_every_signature_cell():
    model = Model(generate_problem(94230))
    assert model.terminal(model.full_state) == "archive_irreducible"
    cert = model.certificate([])
    assert len(cert["all_remaining_signature_cells"]) == len(model.signature_cells) > 1
    assert model.verify_certificate(cert)
    cert["all_remaining_signature_cells"].pop()
    assert not model.verify_certificate(cert)


def test_one_mixed_cell_does_not_prove_global_irreducibility():
    model = Model(generate_problem(94231))
    assert set(model.tau) == {"archive_irreducible", "ruled_out"}
    assert model.terminal(model.full_state) is None
    cert = model.certificate([])
    assert cert["status"] == "unresolved_pending"
    assert len(cert["opposite_claim_witnesses"]) == 2
    with pytest.raises(ValueError, match="contradicts"):
        model.certificate([], "archive_irreducible")
    mixed = next(cell for cell in model.signature_cells.values()
                 if len({model.claim_values[i] for i in indices(cell)}) == 2)
    assert len({model.answers[i] for i in indices(mixed)}) == 1
    assert {model.worlds[i]["source_mechanism"] for i in indices(mixed)} == {"shared_input", "direct"}


def test_no_source_use_label_lookup_exists():
    for seed in (94230, 94231):
        model = Model(generate_problem(seed))
        assert all(q["kind"] in {"context_receipt", "request_receipt", "delivery_receipt",
                                 "completeness", "archive_record"} for q in model.queries.values())
        for cell in model.signature_cells.values():
            if any(model.claim_values[i] for i in indices(cell)):
                assert {model.claim_values[i] for i in indices(cell)} == {False, True}


def test_complementarity_no_single_initial_lookup_settles_everything():
    model = Model(generate_problem(94220))
    for qid in model.queries:
        assert all(model.terminal(cell) is None for cell in model.partition(model.full_state, qid).values())
    joint = history(model, record_context_0="present", record_context_1="present")
    assert model.terminal(model.compatible(joint)) == "established"
    assert model.verify_certificate(model.certificate(joint))


def test_irrelevant_and_duplicate_records_are_explicitly_dependent():
    model = Model(generate_problem(94100))
    duplicates = [qid for qid, q in model.queries.items() if q["record_id"] == "record_context_0"]
    assert len(duplicates) == 2
    positions = [model.query_ids.index(qid) for qid in duplicates]
    assert all(row[positions[0]] == row[positions[1]] for row in model.answers)
    irrelevant = query(model, "nuisance")
    for cell in model.partition(model.full_state, irrelevant).values():
        assert 0 < cell.bit_count() < len(model.worlds)
        assert model.terminal(cell) is None
        assert model.mass(cell) == Fraction(1, 2)


@pytest.mark.parametrize("field", ["model_pin", "assumptions_pin", "initial_evidence_pin"])
def test_certificate_rejects_pin_tampering(field):
    model = Model(generate_problem(94100))
    cert = model.certificate(history(model, record_context_0="present"))
    cert[field] = "0" * 64
    assert not model.verify_certificate(cert)


@pytest.mark.parametrize("change", ["record", "scope", "claim", "history", "initial", "witness"])
def test_certificate_rejects_payload_and_claim_tampering(change):
    model = Model(generate_problem(94100))
    cert = model.certificate(history(model, record_context_0="present"))
    if change == "record":
        cert["acquired_evidence"][0]["time"] += 1
    elif change == "scope":
        cert["acquired_evidence"][0]["scope"]["recipient"] = "other"
    elif change == "claim":
        cert["claim"]["kind"] = "source_use"
    elif change == "history":
        cert["history"][0]["outcome_id"] = "missing"
    elif change == "initial":
        cert["initial_evidence"] = []
    else:
        cert["exhaustive_compatible_hypotheses"].pop()
    assert not model.verify_certificate(cert)


def test_checker_rebuilds_classes_and_does_not_trust_cached_policy_state():
    model = Model(generate_problem(94100))
    cert = model.certificate(history(model, record_context_0="present"))
    model.tau = ("ruled_out",) * len(model.worlds)
    model.claim_values = (False,) * len(model.worlds)
    assert model.verify_certificate(cert)


def test_positive_priors_change_mass_never_compatibility_or_claim_classes():
    problem = generate_problem(94100)
    uniform = Model(problem)
    n = len(problem["worlds"])
    denominator = n * (n + 1) // 2
    problem["prior"] = [str(Fraction(i + 1, denominator)) for i in range(n)]
    weighted = Model(problem)
    observations = history(uniform, record_context_0="present")
    assert uniform.compatible(observations) == weighted.compatible(observations)
    assert uniform.tau == weighted.tau
    assert uniform.mass(1) != weighted.mass(1)
    problem["prior"][0] = "0"
    with pytest.raises(ValueError, match="prior"):
        Model(problem)


@pytest.mark.parametrize("change", ["timestamp", "parent", "first_availability", "receipt", "scope", "complete", "future_complete"])
def test_temporal_and_authenticity_contract_fails_closed(change):
    problem = generate_problem(94210)
    if change == "timestamp":
        problem["event_catalog"][2]["time"] = 9
    elif change == "parent":
        world = next(w for w in problem["worlds"] if "context_0" in w["occurring_event_ids"])
        world["occurring_event_ids"].remove("delivery_0")
    elif change == "first_availability":
        world = next(w for w in problem["worlds"] if "context_0" in w["occurring_event_ids"])
        world["recipient_writes"][1]["context_sources"] = []
    elif change == "receipt":
        world = next(w for w in problem["worlds"] if "context_0" not in w["occurring_event_ids"])
        world["retained_record_ids"].append("record_context_0")
    elif change == "scope":
        problem["queries"][0]["scope"]["recipient"] = "other"
    elif change == "complete":
        world = next(w for w in problem["worlds"] if "complete_0" in w["retained_record_ids"]
                     and "record_context_0" in w["retained_record_ids"])
        world["retained_record_ids"].remove("record_context_0")
    else:
        record = next(r for r in problem["record_catalog"] if r["id"] == "complete_0")
        record["time"] = 25
    with pytest.raises(ValueError):
        Model(problem)


def test_fingerprints_identify_cost_only_repetitions():
    problems = generate_split("evaluation")
    assert len({p["structural_fingerprint"] for p in problems}) == 40
    assert len({p["unweighted_structure_fingerprint"] for p in problems}) < 40
    assert all(not p["selection"]["policy_outcomes_consulted"] for p in problems)


def test_unknown_query_and_zero_or_negative_states_reject_invalid_contracts():
    model = Model(generate_problem(94100))
    with pytest.raises(ValueError):
        model.compatible([{"query_id": "unknown", "outcome_id": "missing"}])
    with pytest.raises(ValueError):
        model.mass(-1)
    with pytest.raises(ValueError):
        model.terminal(model.full_state + 1)
    problem = copy.deepcopy(model.problem)
    problem["queries"][0]["cost"] = 0
    with pytest.raises(ValueError, match="cost"):
        Model(problem)
