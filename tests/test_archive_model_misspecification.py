"""Loss-closure correctness on four saved development inputs and tiny restrictions.

No evaluation cases are loaded. Restrictions below select explicit physical
conditions; they are unit fixtures, not additional research cases.
"""

import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

from tracebench.evidence_acquisition.model import Model, canonical, indices
from tracebench.evidence_acquisition.policies import ChargedLookup, run_policy

ROOT = Path(__file__).resolve().parents[1]


def load_module(name):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.archive_model_misspecification.{name}")
    finally:
        sys.path.remove(str(ROOT))


@pytest.fixture(scope="module")
def expanded():
    return load_module("expanded")


@pytest.fixture(scope="module")
def reference():
    return load_module("reference")


@pytest.fixture(scope="module")
def analysis():
    return load_module("analysis")


@pytest.fixture(scope="module")
def development():
    path = ROOT / "studies/evidence_acquisition/development_problems.json"
    problems = json.loads(path.read_text())
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    assert all(p["split"] == "development" for p in problems)
    return problems


def restrict(problem, predicate):
    problem = copy.deepcopy(problem)
    problem["worlds"] = [world for world in problem["worlds"] if predicate(world)]
    assert problem["worlds"]
    problem["prior"] = [f"1/{len(problem['worlds'])}"] * len(problem["worlds"])
    Model(problem)
    return problem


def full_history(model, signature):
    return [{"query_id": qid, "outcome_id": outcome}
            for qid, outcome in zip(model.query_ids, signature, strict=True)]


def nominal_claim_status(model, history):
    values = {model.claim_values[i] for i in indices(model.compatible(history))}
    return ("model_conflict" if not values else "established" if values == {True}
            else "ruled_out" if values == {False} else "unresolved")


@pytest.mark.parametrize("index", range(4))
def test_zero_loss_parity_embedding_and_nested_physical_support(expanded, reference, development, index):
    problem = development[index]
    snapshot = copy.deepcopy(problem)
    nominal = Model(problem)
    previous_support = set()
    for k in (0, 1, 2):
        model = expanded.ExpandedModel(problem, k)
        bodies = {canonical(reference.physical(world)) for world in model.worlds}
        assert previous_support <= bodies
        previous_support = bodies
        assert model.stats["no_truncation"]
        assert len(model.worlds) <= 4096 and len(model.signature_cells) <= 256
        by_id = {world["id"]: i for i, world in enumerate(model.worlds)}
        assert len(model.embedding) == len(nominal.worlds)
        for entry in model.embedding:
            n, e = entry["nominal_world_index"], by_id[entry["expanded_world_id"]]
            assert entry["nominal_world_id"] == nominal.worlds[n]["id"]
            assert nominal.answers[n] == model.answers[e]
            assert nominal.claim_values[n] == model.claim_values[e]
        for signature in nominal.signature_cells:
            history = full_history(model, signature)
            old, new = nominal_claim_status(nominal, history), model.claim_status(history)
            assert new in {old, "unresolved"}
            if k == 0:
                assert new == old
                assert model.terminal_status(history) == nominal.terminal(nominal.compatible(history))
        if k == 0:
            assert set(model.signature_cells) == set(nominal.signature_cells)
            assert model.verify_certificate(model.certificate([]))
            assert nominal.verify_certificate(nominal.certificate([]))
    assert problem == snapshot


@pytest.mark.parametrize("index", range(4))
def test_only_unique_queried_noninitial_context_records_disappear(expanded, reference, development, index):
    problem = development[index]
    model = expanded.ExpandedModel(problem, 2)
    records = {r["id"]: r for r in problem["record_catalog"]}
    queries = problem["queries"]
    queried = {q["record_id"] for q in queries}
    initial = set(problem["initial_record_ids"])
    for i, world in enumerate(model.worlds):
        retained = set(world["retained_record_ids"])
        assert initial <= retained
        for rid in retained:
            assert records[rid]["authenticated"] is True
            if records[rid]["kind"].endswith("_receipt"):
                assert records[rid]["event_id"] in world["occurring_event_ids"]
        assert reference.claim_value(problem, world) == model.claim_values[i]
        for origin in world["provenance"]:
            parent = problem["worlds"][origin["parent_world_index"]]
            omitted = set(origin["omitted_record_ids"])
            assert parent["id"] == origin["parent_world_id"]
            assert len(omitted) <= 2 and not omitted & initial
            assert omitted <= queried & set(parent["retained_record_ids"])
            assert all(records[r]["kind"] == "context_receipt" for r in omitted)
            assert retained == set(parent["retained_record_ids"]) - omitted
            expected = reference.physical(parent, retained)
            assert reference.physical(world) == expected
            assert reference.claim_value(problem, parent) == reference.claim_value(problem, world)
            assert origin["affected_query_ids"] == sorted(q["id"] for q in queries if q["record_id"] in omitted)
        # Two actions referring to one physical receipt are not two omission units.
        for j, query in enumerate(queries):
            assert model.answers[i][j] == ("present" if query["record_id"] in retained else "missing")
            for other, alias in enumerate(queries):
                if alias["record_id"] == query["record_id"]:
                    assert model.answers[i][j] == model.answers[i][other]
    assert model.problem["initial_evidence"] == problem["initial_evidence"]
    assert model.problem["record_catalog"] == problem["record_catalog"]
    assert list(model.queries.values()) == problem["queries"]


@pytest.mark.parametrize("index", range(4))
def test_separate_physical_reconstruction_agrees_on_support_and_histories(expanded, reference, development, index):
    problem = development[index]
    for k in (0, 1, 2):
        model = expanded.ExpandedModel(problem, k)
        independent = reference.reconstruct(problem, k)
        assert {canonical(reference.physical(w)) for w in model.worlds} == {
            canonical(reference.physical(w)) for w in independent["worlds"]}
        assert len(model.worlds) == independent["physical_world_count"]
        assert model.stats["generated_world_count"] == independent["generated_candidates"]
        by_id = {w["id"]: w for w in independent["worlds"]}
        for world in model.worlds:
            for actual, expected in zip(world["provenance"], by_id[world["id"]]["origins"], strict=True):
                for field in expected:
                    if field == "violated_nominal_completeness":
                        assert sorted(map(canonical, actual[field])) == sorted(map(canonical, expected[field]))
                    else:
                        assert actual[field] == expected[field]
        histories = [[]]
        for signature in model.signature_cells:
            full = full_history(model, signature)
            histories.extend([full, full[:1], full[::2]])
        for history in histories:
            check = reference.inspect_history(problem, independent["worlds"], history)
            assert check["claim_status"] == model.claim_status(history)
            assert check["terminal_status"] == model.terminal_status(history)
            assert check["compatible_world_ids"] == sorted(
                model.worlds[i]["id"] for i in indices(model.compatible(history)))


def test_initial_context_receipt_is_not_eligible_even_with_query_aliases(expanded, development):
    problem = restrict(development[0], lambda w: "record_context_0" in w["retained_record_ids"])
    problem["initial_record_ids"].append("record_context_0")
    records = {r["id"]: r for r in problem["record_catalog"]}
    problem["initial_evidence"] = [records[rid] for rid in problem["initial_record_ids"]]
    Model(problem)
    model = expanded.ExpandedModel(problem, 2)
    assert len([q for q in problem["queries"] if q["record_id"] == "record_context_0"]) == 2
    assert all("record_context_0" in w["retained_record_ids"] for w in model.worlds)
    assert all(not o["omitted_record_ids"] for w in model.worlds for o in w["provenance"])


def test_positive_context_evidence_establishes_exposure_but_not_source_use(expanded, development):
    for index in (0, 2, 3):
        model = expanded.ExpandedModel(development[index], 2)
        queries = [q for q in model.queries.values() if q["kind"] == "context_receipt"]
        history = [{"query_id": q["id"], "outcome_id": "present"} for q in queries]
        assert model.compatible(history)
        expected = "unresolved" if index == 3 else "established"
        assert model.claim_status(history) == expected
        # The untouched bytes are evidence of an occurring context event,
        # without a source-selection verdict added to the observation.
        for row in history:
            payload = model.queries[row["query_id"]]["outcomes"]["present"]
            assert payload["authenticated"] is True and payload["kind"] == "context_receipt"
            assert "selected_source_ids" not in payload


def test_initial_completeness_assertion_survives_as_authentic_not_current_guarantee(expanded, development):
    problem = development[2]
    assert {"complete_0", "complete_1"} <= set(problem["initial_record_ids"])
    model = expanded.ExpandedModel(problem, 2)
    origins = [o for w in model.worlds for o in w["provenance"] if o["omitted_record_ids"]]
    assert any(o["violated_retained_assertion_ids"] for o in origins)
    for origin in origins:
        for row in origin["applicable_retained_assertions"]:
            assert row["initial_assertion_ids"] == row["assertion_ids"]
            assert row["initial_assertion_ids"]
    assert model.problem["initial_evidence"] == problem["initial_evidence"]


@pytest.mark.parametrize("index", range(3))
def test_wrong_source_recipient_or_time_completeness_is_not_applicable(expanded, development, index):
    model = expanded.ExpandedModel(development[index], 2)
    nonempty = [o for w in model.worlds for o in w["provenance"] if o["omitted_record_ids"]]
    assert nonempty
    for origin in nonempty:
        assert "wrong_complete" not in origin["violated_retained_assertion_ids"]
        for applicability in origin["applicable_retained_assertions"]:
            assert "wrong_complete" not in applicability["assertion_ids"]


def test_wrong_scope_declaration_does_not_make_missing_context_negative_evidence(expanded, development):
    model = expanded.ExpandedModel(development[0], 1)
    history = [{"query_id": q["id"], "outcome_id": "present" if q["kind"] == "completeness" else "missing"}
               for q in model.queries.values() if q["kind"] in {"completeness", "context_receipt"}]
    assert model.claim_status(history) == "unresolved"
    assert {model.claim_values[i] for i in indices(model.compatible(history))} == {False, True}


def test_scope_guarantee_without_retained_assertion_is_support_only_loss(expanded, development):
    problem = restrict(development[1], lambda w: {"record_context_0", "complete_0"} <= set(w["retained_record_ids"]))
    problem["worlds"] = problem["worlds"][:1]
    problem["prior"] = ["1"]
    problem["worlds"][0]["retained_record_ids"].remove("complete_0")
    Model(problem)
    model = expanded.ExpandedModel(problem, 1)
    origin = next(o for w in model.worlds for o in w["provenance"] if o["omitted_record_ids"] == ["record_context_0"])
    assert origin["violated_nominal_completeness"]
    assert not origin["violated_retained_assertion_ids"]
    assert origin["support_only_omitted_record_ids"] == ["record_context_0"]
    assert origin["applicable_retained_assertions"][0]["assertion_ids"] == []


def test_original_authoritative_validator_still_rejects_post_loss_snapshot(expanded, development):
    problem = restrict(development[1], lambda w: {"record_context_0", "complete_0"} <= set(w["retained_record_ids"]))
    problem["worlds"] = problem["worlds"][:1]
    problem["prior"] = ["1"]
    broken = copy.deepcopy(problem)
    broken["worlds"][0]["retained_record_ids"].remove("record_context_0")
    with pytest.raises(ValueError, match="complete logging dropped a relevant receipt"):
        Model(broken)
    model = expanded.ExpandedModel(problem, 1)
    origin = next(o for w in model.worlds for o in w["provenance"] if o["omitted_record_ids"] == ["record_context_0"])
    assert "complete_0" in origin["violated_retained_assertion_ids"]
    assert "do not guarantee completeness" in model.contract["completeness_assumption_change"]
    assert model.problem["record_catalog"] == problem["record_catalog"]


def test_empty_compatibility_is_model_conflict_not_vacuous_certainty(expanded, development):
    problem = restrict(development[0], lambda w: "record_context_0" in w["retained_record_ids"])
    zero, one = expanded.ExpandedModel(problem, 0), expanded.ExpandedModel(problem, 1)
    qid = next(q["id"] for q in problem["queries"] if q["record_id"] == "record_context_0")
    history = [{"query_id": qid, "outcome_id": "missing"}]
    assert zero.compatible(history) == 0
    assert zero.claim_status(history) == zero.terminal_status(history) == "model_conflict"
    cert = zero.certificate(history)
    assert cert["compatible_world_count"] == 0
    assert cert["exhaustive_compatible_hypotheses"] == [] and zero.verify_certificate(cert)
    assert one.compatible(history) and one.claim_status(history) == "established"


def test_opposite_witness_alone_does_not_prove_archive_irreducibility(expanded, development):
    model = expanded.ExpandedModel(development[0], 1)
    cert = model.certificate([])
    assert cert["claim_status"] == "unresolved"
    assert len(cert["opposite_claim_witnesses"]) == 2
    assert cert["terminal_status"] == "unresolved_pending"
    assert "all_remaining_signature_cells" not in cert
    assert any(model.claim_status(full_history(model, s)) == "established" for s in model.signature_cells)
    false_irreducible = copy.deepcopy(cert)
    false_irreducible["terminal_status"] = "archive_irreducible"
    assert not model.verify_certificate(false_irreducible)


def test_irreducibility_certificate_covers_every_remaining_signature(expanded, development):
    problem = restrict(development[3], lambda w: "context_0" in w["occurring_event_ids"])
    model = expanded.ExpandedModel(problem, 1)
    cert = model.certificate([])
    assert cert["claim_status"] == "unresolved" and cert["terminal_status"] == "archive_irreducible"
    coverage = cert["all_remaining_signature_cells"]
    assert len(coverage) == len(model.signature_cells) > 1
    assert model.verify_certificate(cert)
    for cell in coverage:
        signature = tuple(cell["complete_query_signature"])
        selected = [i for i, w in enumerate(model.worlds) if w["id"] in cell["opposite_claim_witnesses"]]
        assert {model.claim_values[i] for i in selected} == {False, True}
        assert {model.answers[i] for i in selected} == {signature}
    incomplete = copy.deepcopy(cert)
    incomplete["all_remaining_signature_cells"].pop()
    assert not model.verify_certificate(incomplete)


def test_nominal_certificate_can_remain_valid_while_expanded_support_weakens(expanded, reference, development):
    model = expanded.ExpandedModel(development[1], 1)
    witness = next(w for s in model.nominal.signature_cells
                   if (w := model.comparison_witness(s)) is not None)
    assert witness["witness_kind"] == "same_signature_opposite_claim"
    assert model.nominal.verify_certificate(witness["nominal_certificate"])
    assert witness["nominal_certificate"]["status"] in {"established", "ruled_out"}
    assert witness["expanded_certificate"]["claim_status"] == "unresolved"
    assert model.verify_comparison_witness(witness)
    left = next(w for w in model.nominal.worlds if w["id"] == witness["nominal_world_id"])
    right = next(w for w in model.worlds if w["id"] == witness["expanded_world_id"])
    assert reference.check_same_signature_opposites(model.problem, left, right) == len(model.query_ids)
    tampered = copy.deepcopy(witness)
    tampered["full_signature"][-1] = "missing" if tampered["full_signature"][-1] == "present" else "present"
    assert not model.verify_comparison_witness(tampered)


def test_certificate_contract_cannot_be_relabelled_by_hash_substitution(expanded, development):
    model = expanded.ExpandedModel(development[2], 1)
    cert = model.certificate([])
    assert model.verify_certificate(cert)
    changed = copy.deepcopy(cert)
    changed["contract"]["completeness_assumption_change"] = "authoritative completeness"
    assert not model.verify_certificate(changed)
    changed = copy.deepcopy(cert)
    changed["k"] = 0
    assert not model.verify_certificate(changed)
    transplanted = model.nominal.certificate([])
    for name in ("contract_id", "contract_pin", "model_pin", "support_pin", "k"):
        transplanted[name] = cert[name]
    assert not model.verify_certificate(transplanted)
    assert not model.nominal.verify_certificate(cert)


def test_world_query_renaming_and_order_preserve_physical_inference(expanded, reference, development):
    original = expanded.ExpandedModel(development[0], 1)
    renamed = copy.deepcopy(development[0])
    renamed["worlds"].reverse()
    renamed["prior"].reverse()
    for i, world in enumerate(renamed["worlds"]):
        world["id"] = f"opaque_world_{i:03}"
    mapping = {q["id"]: f"opaque_action_{i:03}" for i, q in enumerate(renamed["queries"])}
    renamed["queries"].reverse()
    for query in renamed["queries"]:
        query["id"] = mapping[query["id"]]
    changed = expanded.ExpandedModel(renamed, 1)
    assert {canonical(reference.physical(w)) for w in changed.worlds} == {
        canonical(reference.physical(w)) for w in original.worlds}
    for signature in original.signature_cells:
        history = full_history(original, signature)[::2]
        renamed_history = [{"query_id": mapping[r["query_id"]], "outcome_id": r["outcome_id"]} for r in history]
        assert original.claim_status(history) == changed.claim_status(renamed_history)
        assert original.terminal_status(history) == changed.terminal_status(renamed_history)
        assert {original.worlds[i]["id"] for i in indices(original.compatible(history))} == {
            changed.worlds[i]["id"] for i in indices(changed.compatible(renamed_history))}


def test_safety_caps_fail_without_silently_truncating_support(expanded, development):
    with pytest.raises(ValueError, match="support not truncated"):
        expanded.ExpandedModel(development[0], 1, world_cap=1)
    with pytest.raises(ValueError, match="support not truncated"):
        expanded.ExpandedModel(development[0], 1, signature_cap=1)


@pytest.mark.parametrize("index", range(4))
def test_zero_loss_exact_policy_paths_costs_and_certificates_match_original(analysis, development, index):
    nominal = Model(development[index])
    planner = analysis.CappedPlanner(nominal, "exact_optimal", state_cap=100_000)
    original_planner = analysis.CappedPlanner(nominal, "exact_optimal", state_cap=100_000)
    for signature in nominal.signature_cells:
        expected = run_policy(nominal, "exact_optimal", ChargedLookup(nominal, signature), planner=original_planner)
        actual = analysis.nominal_acquire(nominal, signature, planner=planner)
        for field in ("history", "cost", "query_count", "returned_bytes", "status", "certificate"):
            assert actual[field] == expected[field]
        assert actual["certificate_valid"] and actual["failure"] is None


def test_planner_gets_only_nominal_model_and_paid_history(analysis, expanded, development):
    model = expanded.ExpandedModel(development[1], 2)
    nominal = model.nominal

    class RecordingPlanner(analysis.CappedPlanner):
        def __init__(self):
            super().__init__(nominal, "exact_optimal", state_cap=100_000)
            self.decisions = {}
            self.seen = []

        def choose(self, history):
            assert self.model is nominal and isinstance(self.model, Model)
            assert not hasattr(self.model, "embedding")
            assert not hasattr(self.model, "contract")
            assert all(set(row) == {"query_id", "outcome_id"} for row in history)
            assert self.model.compatible(history)  # Never plan after a contradiction.
            before = copy.deepcopy(history)
            action = super().choose(history)
            assert history == before
            if action is not None:
                # The frozen exact planner discards constant queries. With
                # this binary catalogue, both admissible answers therefore
                # leave nominal support: detection cannot be manufactured by
                # treating a skipped constant answer as observed.
                children = self.model.partition(self.model.compatible(history), action)
                assert set(children) == {"present", "missing"} and all(children.values())
            key = canonical(history)
            assert self.decisions.setdefault(key, action) == action
            self.seen.append(before)
            return action

    planner = RecordingPlanner()
    for signature in model.signature_cells:
        result = analysis.nominal_acquire(nominal, signature, planner=planner)
        assert planner.seen[-1] == result["history"]
        assert result["cost"] == sum(nominal.queries[row["query_id"]]["cost"] for row in result["history"])
        assert result["returned_bytes"] == sum(len(canonical(
            nominal.queries[row["query_id"]]["outcomes"][row["outcome_id"]])) for row in result["history"])
        answers = dict(zip(nominal.query_ids, signature, strict=True))
        assert all(row["outcome_id"] == answers[row["query_id"]] for row in result["history"])


def test_nominal_constant_action_skipped_is_not_free_observation(analysis, expanded, development):
    problem = restrict(development[0], lambda w: "record_context_0" in w["retained_record_ids"])
    model = expanded.ExpandedModel(problem, 1)
    novel = next(s for s in model.signature_cells if s not in model.nominal.signature_cells)
    assert model.nominal.compatible(full_history(model, novel)) == 0
    result = analysis.nominal_acquire(model.nominal, novel)
    assert result["status"] == "established"
    assert result["history"] == []
    assert result["cost"] == result["query_count"] == result["returned_bytes"] == 0
    assert result["certificate_valid"]
    assert result["claim_status"] == model.claim_status([]) == "established"
    # Exhaustive retrieval contradicts the nominal archive, but its exact
    # policy's zero-cost stopping certificate contains no receipt observation.
    witness = model.comparison_witness(novel)
    assert witness["witness_kind"] == "nominal_incompatible_full_history"
    assert witness["nominal_certificate"]["status"] == "inconsistent"
    assert model.verify_comparison_witness(witness)


def test_passive_archive_charges_once_and_preserves_empty_payload_semantics(analysis, expanded, development):
    model = expanded.ExpandedModel(development[2], 1)
    signature = next(s for s in model.signature_cells if "missing" in s)
    qid = model.query_ids[signature.index("missing")]
    archive = analysis.PassiveArchive(model.nominal, signature)
    assert archive.history == [] and archive.cost == archive.returned_bytes == 0
    row = archive(qid)
    payload = model.queries[qid]["outcomes"]["missing"]
    assert row == {"query_id": qid, "outcome_id": "missing"}
    assert payload["kind"] == "lookup_empty" and "event_occurred" not in payload
    assert archive.cost == model.queries[qid]["cost"]
    assert archive.returned_bytes == len(canonical(payload)) > 0
    with pytest.raises(ValueError, match="repeated paid lookup"):
        archive(qid)
    assert archive.history == [row]
    with pytest.raises(ValueError, match="unknown outcome"):
        analysis.PassiveArchive(model.nominal, ("forged",) * len(model.query_ids))


@pytest.fixture
def isolated_freeze(analysis, monkeypatch, tmp_path):
    study = tmp_path / "study"
    study.mkdir()
    config = study / "config.json"
    config.write_bytes((ROOT / "studies/archive_model_misspecification/config.json").read_bytes())
    source = study / "source.py"
    source.write_text('"""Non-executed dependency-hash unit fixture."""\n')
    checks = [study / name for name in (
        "baseline_verification.json", "development_checks.json", "pre_freeze_checks.json")]
    for path in checks:
        path.write_text(json.dumps({"status": "passed", "evaluation_policy_outcomes_observed": 0}))
    monkeypatch.setattr(analysis, "ROOT", tmp_path)
    monkeypatch.setattr(analysis, "STUDY", study)
    monkeypatch.setattr(analysis, "dependencies", lambda: [config, source, *checks])
    monkeypatch.setattr(analysis, "verify_preservation", lambda: {"tracked_files": 0, "local_files": 0})
    return study


@pytest.mark.parametrize("name", ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"))
def test_freeze_refuses_failed_required_checks(analysis, isolated_freeze, name):
    (isolated_freeze / name).write_text(json.dumps({"status": "failed", "evaluation_policy_outcomes_observed": 0}))
    with pytest.raises(ValueError, match="Required pre-freeze check has not passed"):
        analysis.freeze()
    assert not (isolated_freeze / "freeze.json").exists()


@pytest.mark.parametrize("observed", (None, 1))
def test_freeze_requires_explicit_zero_evaluation_outcomes(analysis, isolated_freeze, observed):
    (isolated_freeze / "pre_freeze_checks.json").write_text(
        json.dumps({"status": "passed", "evaluation_policy_outcomes_observed": observed}))
    with pytest.raises(ValueError, match="Evaluation already observed or pre-freeze chronology missing"):
        analysis.freeze()
    assert not (isolated_freeze / "freeze.json").exists()


@pytest.mark.parametrize("filename", ("config.json", "source.py"))
def test_frozen_code_and_config_tampering_is_rejected(analysis, isolated_freeze, filename):
    assert analysis.freeze()["status"] == "frozen"
    assert analysis.verify_freeze() == 5
    path = isolated_freeze / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="Frozen computational input changed"):
        analysis.verify_freeze()


def test_freeze_dependency_set_and_overwrite_are_checked(analysis, isolated_freeze):
    analysis.freeze()
    path = isolated_freeze / "freeze.json"
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        analysis.freeze()
    assert path.read_bytes() == original
    incomplete = json.loads(original)
    incomplete["files_sha256"].pop("study/source.py")
    path.write_text(json.dumps(incomplete))
    with pytest.raises(ValueError, match="Incomplete frozen computational dependency closure"):
        analysis.verify_freeze()


def test_existing_run_output_is_refused_before_loading_any_cases(analysis, isolated_freeze, monkeypatch):
    analysis.freeze()
    output = isolated_freeze / "results"
    output.mkdir()
    marker = output / "untouched.txt"
    marker.write_text("historical output")
    monkeypatch.setattr(analysis, "analyze_cell", lambda *a, **kw: pytest.fail("No policy should execute"))
    # No development or evaluation input is present in this temporary tree.
    # Directory refusal must therefore happen before trying to read either.
    with pytest.raises(FileExistsError):
        analysis.execute(output)
    assert marker.read_text() == "historical output"
    assert list(output.iterdir()) == [marker]
