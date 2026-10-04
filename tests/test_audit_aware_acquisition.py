"""Paid audit ordering on saved development cases and explicit tiny archives.

No evaluation problem or new evaluation-policy outcome is loaded here.
"""

import copy
import gzip
import importlib
import inspect
import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from tracebench.evidence_acquisition.model import Model, canonical, pin

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("no_audit", "cost_order", "constant_first", "closure_informed")
BUDGETS = (0, 25, 50, 100)


def study_module(study, name):
    sys.path.insert(0, str(ROOT))
    try:
        return importlib.import_module(f"studies.{study}.{name}")
    finally:
        sys.path.remove(str(ROOT))


@pytest.fixture(scope="module")
def auditing():
    return study_module("audit_aware_acquisition", "auditing")


@pytest.fixture(scope="module")
def driver():
    return study_module("audit_aware_acquisition", "analysis")


@pytest.fixture(scope="module")
def expanded():
    return study_module("archive_model_misspecification", "expanded")


@pytest.fixture(scope="module")
def nominal_study():
    return study_module("archive_model_misspecification", "analysis")


@pytest.fixture(scope="module")
def development():
    problems = json.loads((ROOT / "studies/evidence_acquisition/development_problems.json").read_text())
    assert [p["seed"] for p in problems] == list(range(94100, 94104))
    assert all(p["split"] == "development" for p in problems)
    path = ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz"
    cells = json.loads(gzip.decompress(path.read_bytes()))
    assert {(c["problem_id"], c["k"]) for c in cells} == {
        (p["problem_id"], k) for p in problems for k in (0, 1, 2)}
    return problems, {(c["problem_id"], c["k"]): c for c in cells}


def tiny_correlated(problem):
    """Two separate receipts for one occurring event, with one catalogue alias.

    Nominally both receipts are retained or both are missing. The exposure
    claim is true in both worlds. Omitting one physical copy creates a new
    signature and a genuine two-query contradiction after a nonconstant test.
    """
    problem = copy.deepcopy(problem)
    context = next(r for r in problem["record_catalog"] if r["id"] == "record_context_0")
    second = {**copy.deepcopy(context), "id": "unit_context_copy"}
    problem["record_catalog"].append(second)
    worlds = []
    for retained in (False, True):
        world = copy.deepcopy(next(w for w in problem["worlds"]
                                   if "context_0" in w["occurring_event_ids"]
                                   and ("record_context_0" in w["retained_record_ids"]) == retained))
        if retained:
            world["retained_record_ids"].append(second["id"])
        world["id"] = f"unit_world_{retained}"
        worlds.append(world)
    problem["worlds"], problem["prior"] = worlds, ["1/2", "1/2"]
    queries = []
    for qid, record, cost in (("q_a", context, 1), ("q_b", second, 2), ("q_c_alias_b", second, 4)):
        queries.append({"id": qid, "record_id": record["id"], "kind": record["kind"],
                        "scope": copy.deepcopy(record["scope"]), "cost": cost,
                        "outcomes": {"present": copy.deepcopy(record),
                                     "missing": {"kind": "lookup_empty", "scope": copy.deepcopy(record["scope"])}}})
    problem["queries"] = queries
    Model(problem)
    return problem


def tiny_with_expensive_constant(problem):
    problem = tiny_correlated(problem)
    marker = next(r for r in problem["record_catalog"] if r["id"] == "initial_marker")
    problem["queries"] = [problem["queries"][0], {
        "id": "q_expensive_constant", "record_id": marker["id"], "kind": marker["kind"],
        "scope": copy.deepcopy(marker["scope"]), "cost": 4,
        "outcomes": {"present": copy.deepcopy(marker),
                     "missing": {"kind": "lookup_empty", "scope": copy.deepcopy(marker["scope"])}}}]
    Model(problem)
    return problem


def baseline_from_nominal(nominal, signature, nominal_study):
    baseline = nominal_study.nominal_acquire(nominal, signature)
    certificate = baseline["certificate"]
    baseline["certificate"] = pin(certificate)
    assert nominal.verify_certificate(certificate)
    return baseline


def selector_for(auditing, nominal, arm, design):
    return auditing.AuditSelector(nominal, arm,
                                  design_signatures=design if arm == "closure_informed" else None)


def run_audit(auditing, nominal, signature, baseline, arm, budget, design):
    selector = selector_for(auditing, nominal, arm, design)
    lookup = auditing.PassiveAuditArchive(nominal, signature, baseline["history"])
    permitted = {key: baseline[key] for key in (
        "history", "cost", "query_count", "returned_bytes", "status", "certificate", "certificate_valid")}
    return auditing.audit(nominal, permitted, lookup, selector, budget)


def test_selector_interfaces_exclude_realization_and_only_take_paid_history(auditing):
    allowed = {"nominal", "arm", "design_signatures"}
    assert set(inspect.signature(auditing.AuditSelector).parameters) == allowed
    assert set(inspect.signature(auditing.AuditSelector.choose).parameters) == {"self", "history"}
    assert set(inspect.signature(auditing.AuditSelector.detection_scores).parameters) == {"self", "history"}


def test_constant_first_fallback_creates_later_constant_expectation(auditing, expanded, development):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    selector = auditing.AuditSelector(nominal, "constant_first")
    assert nominal.terminal(nominal.full_state) == "established"
    assert all(len(nominal.partition(nominal.full_state, qid)) == 2 for qid in nominal.query_ids)
    assert selector.choose([]) == "q_a"  # Nonconstant fallback, despite terminal claim.
    history = [{"query_id": "q_a", "outcome_id": "missing"}]
    assert selector.choose(history) == "q_b"
    assert set(nominal.partition(nominal.compatible(history), "q_b")) == {"missing"}
    # The actual allowed omission is not exposed to the selector.
    model = expanded.ExpandedModel(problem, 1)
    assert ("missing", "present", "present") in model.signature_cells
    assert nominal.compatible(history + [{"query_id": "q_b", "outcome_id": "present"}]) == 0


def test_closure_scores_count_distinct_signatures_and_recompute_on_history(auditing, expanded, development):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    selector = auditing.AuditSelector(nominal, "closure_informed", design_signatures=design)
    assert set(selector.detection_scores([]).values()) == {Fraction(0)}
    assert selector.choose([]) == "q_a"
    history = [{"query_id": "q_a", "outcome_id": "missing"}]
    expected = {"q_b": Fraction(1, 2), "q_c_alias_b": Fraction(1, 4)}
    assert selector.detection_scores(history) == expected
    repeated = auditing.AuditSelector(nominal, "closure_informed", design_signatures=design * 7)
    assert repeated.detection_scores(history) == expected
    assert repeated.choose(history) == selector.choose(history) == "q_b"


def test_closure_scores_ignore_world_multiplicity_truth_and_traversal(auditing, expanded, development):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    changed = copy.deepcopy(problem)
    changed["claim"]["kind"] = "source_use"  # Same archive, all claims now false.
    duplicate = copy.deepcopy(changed["worlds"][0])
    duplicate["id"] = "extra_nominal_parent"
    changed["worlds"] = [*reversed(changed["worlds"]), duplicate]
    changed["prior"] = ["1/3"] * 3
    other = Model(changed)
    assert set(nominal.answers) == set(other.answers)
    assert set(nominal.claim_values) == {True} and set(other.claim_values) == {False}
    one = auditing.AuditSelector(nominal, "closure_informed", design_signatures=design)
    two = auditing.AuditSelector(other, "closure_informed", design_signatures=tuple(reversed(design)))
    histories = [[], *[[{"query_id": "q_a", "outcome_id": outcome}] for outcome in ("missing", "present")]]
    first = {canonical(h): (one.choose(h), one.detection_scores(h)) for h in histories}
    second = {canonical(h): (two.choose(h), two.detection_scores(h)) for h in reversed(histories)}
    assert first == second


def test_same_paid_history_has_same_action_across_k_hidden_archive_and_visit_order(auditing, expanded, development):
    problems, cells = development
    for problem in problems:
        nominal = Model(problem)
        fixed_design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
        visits = [(k, row) for k in (0, 1, 2)
                  for row in cells[problem["problem_id"], k]["signature_rows"]]
        for arm in ARMS:
            selector = selector_for(auditing, nominal, arm, fixed_design)
            observed = {}
            for _, row in visits + list(reversed(visits)):
                history = copy.deepcopy(row["policy"]["history"])
                original = copy.deepcopy(history)
                action = selector.choose(history)
                assert history == original
                assert observed.setdefault(canonical(history), action) == action
            fresh = selector_for(auditing, nominal, arm, tuple(reversed(fixed_design)))
            assert all(fresh.choose(json.loads(history)) == action for history, action in observed.items())


def test_distinct_design_scores_match_direct_counting_on_development(auditing, expanded, development):
    problems, cells = development
    for problem in problems:
        nominal = Model(problem)
        design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
        selector = selector_for(auditing, nominal, "closure_informed", design)
        for row in cells[problem["problem_id"], 1]["signature_rows"]:
            history = row["policy"]["history"]
            seen = {h["query_id"]: h["outcome_id"] for h in history}
            possible = {s for s in design if all(s[nominal.query_ids.index(q)] == out for q, out in seen.items())}
            expected = {}
            for position, qid in enumerate(nominal.query_ids):
                if qid not in seen:
                    contradictions = sum(not nominal.compatible(history + [{"query_id": qid, "outcome_id": s[position]}])
                                         for s in possible)
                    expected[qid] = Fraction(contradictions, nominal.queries[qid]["cost"])
            assert selector.detection_scores(history) == expected


def test_zero_budget_and_no_audit_preserve_saved_histories_accounting_and_certificates(auditing, expanded, development):
    problems, cells = development
    for problem in problems:
        nominal = Model(problem)
        design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
        for k in (0, 1, 2):
            cell = cells[problem["problem_id"], k]
            for row in cell["signature_rows"]:
                baseline = row["policy"]
                certificate = cell["certificates"][baseline["certificate"]]
                assert nominal.verify_certificate(certificate)
                assert pin(nominal.certificate(baseline["history"])) == baseline["certificate"]
                for arm, budget in [*((arm, 0) for arm in ARMS), *(("no_audit", b) for b in (25, 50, 100))]:
                    result = run_audit(auditing, nominal, row["outcomes"], baseline, arm, budget, design)
                    assert result["history"] == result["base_history"] == baseline["history"]
                    assert result["baseline_certificate"] == baseline["certificate"]
                    assert result["audit_history"] == [] and result["first_conflict"] is None
                    assert result["status"] == "no_conflict_observed"
                    assert result["added_cost"] == result["added_query_count"] == result["added_returned_bytes"] == 0
                    assert result["base_cost"] == result["total_cost"] == baseline["cost"]
                    assert result["base_returned_bytes"] == result["total_returned_bytes"] == baseline["returned_bytes"]


def test_first_conflict_stops_before_remaining_alias_spend(auditing, expanded, development, nominal_study):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    signature = ("missing", "present", "present")
    model = expanded.ExpandedModel(problem, 2)
    baseline = baseline_from_nominal(nominal, signature, nominal_study)
    assert baseline["history"] == [] and baseline["status"] == "established"
    for arm in ARMS[1:]:
        selector = selector_for(auditing, nominal, arm, tuple(model.signature_cells))
        archive = auditing.PassiveAuditArchive(nominal, signature)
        selected = []
        choose = selector.choose

        def checked_choice(history):
            assert nominal.compatible(history), "No action may be selected after first conflict"
            selected.append(copy.deepcopy(history))
            return choose(history)

        selector.choose = checked_choice
        result = auditing.audit(nominal, baseline, archive, selector, 100)
        assert len(selected) == 2
        assert result["status"] == "nominal_model_conflict"
        assert result["proposal_withheld"] and result["original_proposal"] == "established"
        assert result["first_conflict"] == {
            "added_query_index": 2, "added_cost": 3, "total_cost": 3,
            "query_id": "q_b", "outcome_id": "present", "nominal_outcomes_before": ["missing"]}
        assert result["added_cost"] == archive.cost == 3
        assert result["coverage"]["remaining_actions"] == 1
        assert "q_c_alias_b" not in {h["query_id"] for h in result["history"]}
        cert = nominal.certificate(result["history"])
        assert cert["status"] == "inconsistent" and nominal.verify_certificate(cert)
        # An alarm concerns nominal archive compatibility, not falsity of exposure.
        assert model.claim_status(result["history"]) == "established"


def test_empty_lookup_cost_floor_and_unaffordable_next_action_do_not_rerank(auditing, expanded, development, nominal_study):
    problem = tiny_with_expensive_constant(development[0][0])
    nominal = Model(problem)
    signature = ("missing", "present")
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    baseline = baseline_from_nominal(nominal, signature, nominal_study)
    cheap = run_audit(auditing, nominal, signature, baseline, "cost_order", 25, design)
    assert cheap["residual_cost"] == 5 and cheap["audit_budget"] == 1
    assert cheap["audit_history"] == [{"query_id": "q_a", "outcome_id": "missing"}]
    assert cheap["added_cost"] == 1
    payload = nominal.queries["q_a"]["outcomes"]["missing"]
    assert payload["kind"] == "lookup_empty"
    assert cheap["added_returned_bytes"] == len(canonical(payload)) > 0
    assert cheap["termination_reason"] == "next_action_unaffordable"
    constant = run_audit(auditing, nominal, signature, baseline, "constant_first", 50, design)
    assert constant["audit_budget"] == 2
    assert constant["next_query"] == "q_expensive_constant"
    assert constant["audit_history"] == [] and constant["added_cost"] == 0
    assert nominal.queries["q_a"]["cost"] <= constant["audit_budget"]
    assert constant["termination_reason"] == "next_action_unaffordable"


def test_budget_limited_runs_equal_fixed_full_trajectory_prefixes(auditing, expanded, development, nominal_study):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    for signature in design:
        baseline = baseline_from_nominal(nominal, signature, nominal_study)
        for arm in ARMS:
            full = run_audit(auditing, nominal, signature, baseline, arm, 100, design)
            for budget in BUDGETS:
                limited = run_audit(auditing, nominal, signature, baseline, arm, budget, design)
                allowance = full["residual_cost"] * budget // 100
                prefix, cost = [], 0
                for row in full["audit_history"]:
                    price = nominal.queries[row["query_id"]]["cost"]
                    if cost + price > allowance:
                        break
                    prefix.append(row)
                    cost += price
                assert limited["audit_history"] == prefix
                assert limited["added_cost"] == cost <= allowance
                assert limited["history"] == baseline["history"] + prefix
                assert limited["total_cost"] == baseline["cost"] + cost


def test_full_audits_detect_all_development_new_signatures_and_never_originals(auditing, expanded, development):
    problems, cells = development
    conflicts, originals = 0, 0
    for problem in problems:
        nominal = Model(problem)
        design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
        paths = {}
        for k in (0, 1, 2):
            for row in cells[problem["problem_id"], k]["signature_rows"]:
                signature = tuple(row["outcomes"])
                original = signature in nominal.signature_cells
                for arm in ARMS[1:]:
                    result = run_audit(auditing, nominal, signature, row["policy"], arm, 100, design)
                    assert (result["status"] == "nominal_model_conflict") is (not original)
                    if original:
                        assert result["coverage"]["complete"]
                        assert result["termination_reason"] == "catalogue_exhausted"
                        originals += 1
                    else:
                        assert result["first_conflict"] is not None and not nominal.compatible(result["history"])
                        conflicts += 1
                    path = (result["history"], result["added_cost"], result["added_returned_bytes"])
                    assert paths.setdefault((signature, arm), path) == path
    assert conflicts > 0 and originals > 0


def test_physical_aliases_agree_remain_charged_and_do_not_add_logical_evidence(auditing, expanded, development, nominal_study):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    signature = ("present", "present", "present")
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    baseline = baseline_from_nominal(nominal, signature, nominal_study)
    result = run_audit(auditing, nominal, signature, baseline, "cost_order", 100, design)
    assert result["added_cost"] == 7 and result["added_query_count"] == 3
    assert result["coverage"]["added_alias_queries"] == 1
    assert result["coverage"]["distinct_record_ids_queried"] == 2
    assert nominal.compatible(result["history"][:2]) == nominal.compatible(result["history"])
    archive = auditing.PassiveAuditArchive(nominal, signature, result["history"][:1])
    with pytest.raises(ValueError, match="repeated paid audit lookup"):
        archive("q_a")
    with pytest.raises(ValueError, match="physical aliases"):
        auditing.PassiveAuditArchive(nominal, ("missing", "present", "missing"))


def test_complete_indistinguishable_counterexample_survives_all_audit_arms(auditing, expanded, development):
    problems, cells = development
    problem = problems[1]
    cell = cells[problem["problem_id"], 1]
    row = next(row for row in cell["signature_rows"] if row["transition"] == "definite_to_unresolved")
    model = expanded.ExpandedModel(problem, 1)
    nominal = model.nominal
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    witness = model.comparison_witness(row["outcomes"])
    assert witness["witness_kind"] == "same_signature_opposite_claim"
    assert model.verify_comparison_witness(witness)
    for arm in ARMS[1:]:
        result = run_audit(auditing, nominal, row["outcomes"], row["policy"], arm, 100, design)
        assert result["status"] == "no_conflict_observed" and result["coverage"]["complete"]
        assert model.claim_status(result["history"]) == "unresolved"
        assert model.terminal_status(result["history"]) == "archive_irreducible"
        assert model.verify_certificate(model.certificate(result["history"]))


def test_incomplete_design_envelope_cannot_silently_become_a_successful_alarm(auditing, development, nominal_study):
    nominal = Model(tiny_correlated(development[0][0]))
    signature = ("missing", "present", "present")
    baseline = baseline_from_nominal(nominal, signature, nominal_study)
    # Deliberately invalid fixture: includes nominal support but lacks a
    # permitted loss signature. Production D must always receive k=2 closure.
    selector = auditing.AuditSelector(nominal, "closure_informed", design_signatures=nominal.signature_cells)
    archive = auditing.PassiveAuditArchive(nominal, signature)
    with pytest.raises(ValueError, match="empty fixed k=2 design-envelope compatibility"):
        auditing.audit(nominal, baseline, archive, selector, 100)


def test_invalid_inputs_caps_and_unverified_certificate_references_fail(auditing, expanded, development, nominal_study):
    problem = tiny_correlated(development[0][0])
    nominal = Model(problem)
    signature = ("present", "present", "present")
    baseline = baseline_from_nominal(nominal, signature, nominal_study)
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    for bad_budget in (True, -1, 1, 101):
        with pytest.raises(ValueError, match="budget outside"):
            run_audit(auditing, nominal, signature, baseline, "cost_order", bad_budget, design)
    with pytest.raises(ValueError, match="nominal-only auditor"):
        auditing.AuditSelector(nominal, "constant_first", design_signatures=design)
    with pytest.raises(ValueError, match="requires fixed design signatures"):
        auditing.AuditSelector(nominal, "closure_informed")
    with pytest.raises(ValueError, match="omits nominal support"):
        auditing.AuditSelector(nominal, "closure_informed", design_signatures=design[:1])
    with pytest.raises(ValueError, match="unknown audit arm"):
        auditing.AuditSelector(nominal, "tuned_audit")
    with pytest.raises(TypeError):
        auditing.AuditSelector(nominal, "cost_order", actual_k=1)
    oversized = copy.deepcopy(nominal)
    oversized.queries = {f"invalid_{i}": copy.deepcopy(nominal.queries["q_a"]) for i in range(9)}
    with pytest.raises(ValueError, match="catalogue exceeds frozen bounds"):
        auditing.AuditSelector(oversized, "cost_order")
    for key, value in (("certificate_valid", False), ("certificate", "not-a-certificate"), ("cost", 123)):
        damaged = {**baseline, key: value}
        with pytest.raises(ValueError):
            run_audit(auditing, nominal, signature, damaged, "cost_order", 100, design)
    invalid_cert = nominal.certificate(baseline["history"])
    invalid_cert["status"] = "ruled_out"
    damaged = {**baseline, "certificate": invalid_cert}
    with pytest.raises(ValueError, match="invalid original nominal certificate"):
        run_audit(auditing, nominal, signature, damaged, "cost_order", 100, design)
    missing = copy.deepcopy(baseline)
    missing.pop("certificate")
    with pytest.raises(KeyError):
        run_audit(auditing, nominal, signature, missing, "cost_order", 100, design)


def test_tampered_paid_payload_and_repeated_history_do_not_pass(auditing, development, nominal_study):
    nominal = Model(tiny_correlated(development[0][0]))
    signature = ("present", "present", "present")
    baseline = baseline_from_nominal(nominal, signature, nominal_study)
    selector = auditing.AuditSelector(nominal, "cost_order")
    archive = auditing.PassiveAuditArchive(nominal, signature)

    def corrupted_lookup(qid):
        result = archive(qid)
        result["canonical_bytes"] += 1
        return result

    with pytest.raises(ValueError, match="payload/accounting mismatch"):
        auditing.audit(nominal, baseline, corrupted_lookup, selector, 100)
    repeated = [{"query_id": "q_a", "outcome_id": "present"}] * 2
    with pytest.raises(ValueError, match="more than once"):
        selector.choose(repeated)


def test_zero_residual_budget_keeps_all_coincident_conditions(auditing, expanded, development, nominal_study):
    problem = copy.deepcopy(development[0][0])
    problem["queries"] = [next(q for q in problem["queries"] if q["record_id"] == "record_context_0")]
    nominal = Model(problem)
    design = tuple(expanded.ExpandedModel(problem, 2).signature_cells)
    for signature in nominal.signature_cells:
        baseline = baseline_from_nominal(nominal, signature, nominal_study)
        assert len(baseline["history"]) == 1
        for arm in ARMS:
            for budget in BUDGETS:
                result = run_audit(auditing, nominal, signature, baseline, arm, budget, design)
                assert result["residual_cost"] == result["audit_budget"] == result["added_cost"] == 0
                assert result["history"] == baseline["history"] and result["coverage"]["complete"]


def test_alarm_withdrawal_is_separate_from_restoration_and_from_claim_falsity(driver):
    # No alarm by itself repairs an unsupported proposal.
    withdrawn = driver.classify_support("ruled_out", "unresolved", "unresolved_pending",
                                        "unresolved", "archive_irreducible", True, "archive_irreducible")
    assert withdrawn["withdrawn_definite"] and not withdrawn["warrant_restored"]
    assert withdrawn["disposition"] == "definite_proposal_withdrawn"
    opposite = driver.classify_support("ruled_out", "unresolved", "unresolved_pending",
                                       "established", "established", True, "established")
    assert opposite["withdrawn_definite"] and not opposite["warrant_restored"]
    # The evaluator can separately establish the original proposition after
    # an alarm. Withdrawal is still the auditor's action, not its proof.
    same = driver.classify_support("ruled_out", "unresolved", "unresolved_pending",
                                   "ruled_out", "ruled_out", True, "ruled_out")
    assert same["withdrawn_definite"] and same["warrant_restored"]
    assert not same["unwithdrawn_warrant_restored"]
    assert same["disposition"] == "definite_proposal_withdrawn"
    restored = driver.classify_support("ruled_out", "unresolved", "unresolved_pending",
                                       "ruled_out", "ruled_out", False, "ruled_out")
    assert restored["warrant_restored"] and restored["unwithdrawn_warrant_restored"]
    assert not restored["withdrawn_definite"]
    assert restored["disposition"] == "definite_warrant_restored"


def test_unresolved_pending_and_archive_irreducibility_remain_distinct(driver):
    pending = driver.classify_support("archive_irreducible", "unresolved", "unresolved_pending",
                                      "unresolved", "unresolved_pending", False, "archive_irreducible")
    assert pending["irreducibility_overstrong"]
    assert not pending["irreducibility_warranted_at_start"] and not pending["irreducibility_warranted_at_end"]
    assert pending["residual_full_archive_ambiguity"]
    warranted = driver.classify_support("archive_irreducible", "unresolved", "unresolved_pending",
                                        "unresolved", "archive_irreducible", False, "archive_irreducible")
    assert warranted["irreducibility_warranted_at_end"] and not warranted["irreducibility_overstrong"]
    assert warranted["disposition"] == "irreducibility_warranted"
    with pytest.raises(ValueError, match="removed an already warranted"):
        driver.classify_support("established", "established", "established",
                                "unresolved", "unresolved_pending", False, "archive_irreducible")


def test_certificate_cache_separates_contracts_and_rejects_wrong_retained_pin(driver, expanded, development):
    problem = development[0][0]
    nominal = Model(problem)
    models = [nominal, expanded.ExpandedModel(problem, 0), expanded.ExpandedModel(problem, 1)]
    cache = driver.CertificateCache()
    references = [cache.get(model, []) for model in models]
    assert len(set(references)) == 3
    verified = cache.stats()["distinct_certificates_verified"]
    assert [cache.get(model, []) for model in models] == references
    assert cache.stats()["distinct_certificates_verified"] == verified
    for model, key in zip(models, references, strict=True):
        assert model.verify_certificate(cache.certificates[key])
    wrong = copy.deepcopy(cache.certificates[references[0]])
    wrong["status"] = "established"
    with pytest.raises(ValueError, match="Saved baseline certificate differs"):
        cache.get(nominal, [], expected=wrong)


def test_driver_projects_only_nominal_baseline_and_uses_one_fixed_k2_envelope(driver, development, monkeypatch):
    problems, saved = development
    problem = problems[1]
    conditions = [saved[problem["problem_id"], k] for k in (0, 1, 2)]
    design = {tuple(row["outcomes"]) for row in conditions[2]["signature_rows"]}
    allowed = {"history", "cost", "query_count", "returned_bytes", "status", "certificate", "certificate_valid"}
    seen_design = []
    original_selector, original_audit = driver.AuditSelector, driver.audit

    def selecting(nominal, arm, design_signatures=None):
        if arm == "closure_informed":
            assert set(map(tuple, design_signatures)) == design
            seen_design.append(tuple(design_signatures))
        else:
            assert design_signatures is None
        return original_selector(nominal, arm, design_signatures=design_signatures)

    def checking(nominal, baseline, lookup, selector, budget):
        assert set(baseline) == allowed
        return original_audit(nominal, baseline, lookup, selector, budget)

    monkeypatch.setattr(driver, "AuditSelector", selecting)
    monkeypatch.setattr(driver, "audit", checking)
    result = driver.analyze_problem(problem, conditions)
    assert len(seen_design) == 1
    assert len(result["cells"]) == 48
    assert all(cell["status"] == "completed" for cell in result["cells"])
    assert len(result["runs"]) == sum(len(c["signature_rows"]) for c in conditions) * 16


def test_missing_corrupt_or_relabelled_baseline_certificate_keeps_condition_unavailable(driver, development):
    problems, saved = development
    problem = problems[0]
    for mode in ("missing", "corrupt", "relabelled"):
        conditions = copy.deepcopy([saved[problem["problem_id"], k] for k in (0, 1, 2)])
        affected = conditions[1]
        baseline = affected["signature_rows"][0]["policy"]
        key = baseline["certificate"]
        if mode == "missing":
            affected["certificates"].pop(key)
        elif mode == "corrupt":
            affected["certificates"][key]["status"] = "established"
        else:
            replacement = "0" * 64
            assert replacement != key
            affected["certificates"][replacement] = copy.deepcopy(affected["certificates"][key])
            baseline["certificate"] = replacement
        result = driver.analyze_problem(problem, conditions)
        assert len(result["cells"]) == 48
        assert all(c["status"] == ("unavailable" if c["k"] == 1 else "completed") for c in result["cells"])
        assert all(c["completed_signatures"] == 0 and c["failure"] for c in result["cells"] if c["k"] == 1)
        assert {r["k"] for r in result["runs"]} == {0, 2}


def test_resource_cap_failure_preserves_other_conditions(driver, development, monkeypatch):
    problems, saved = development
    problem = problems[0]
    original = driver.ExpandedModel

    def bounded(problem, k):
        if k == 1:
            raise ValueError("expanded-world safety cap exceeded; support not truncated")
        return original(problem, k)

    monkeypatch.setattr(driver, "ExpandedModel", bounded)
    result = driver.analyze_problem(problem, [saved[problem["problem_id"], k] for k in (0, 1, 2)])
    assert len(result["cells"]) == 48
    assert sum(c["status"] == "unavailable" for c in result["cells"]) == 16
    assert all("safety cap" in c["failure"]["message"] for c in result["cells"] if c["k"] == 1)
    assert all(c["status"] == "completed" for c in result["cells"] if c["k"] != 1)
    assert {r["k"] for r in result["runs"]} == {0, 2}


@pytest.fixture
def isolated_freeze(driver, monkeypatch, tmp_path):
    study = tmp_path / "study"
    study.mkdir()
    config = study / "config.json"
    config.write_bytes((ROOT / "studies/audit_aware_acquisition/config.json").read_bytes())
    source = study / "source.py"
    source.write_text('"""Non-executed dependency-integrity unit fixture."""\n')
    checks = [study / name for name in (
        "baseline_verification.json", "development_checks.json", "pre_freeze_checks.json")]
    for path in checks:
        path.write_text(json.dumps({"status": "passed", "evaluation_audit_outcomes_observed": 0}))
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    monkeypatch.setattr(driver, "STUDY", study)
    monkeypatch.setattr(driver, "dependencies", lambda: [config, source, *checks])
    monkeypatch.setattr(driver, "verify_preservation", lambda: {"tracked_files": 0, "local_files": 0})
    return study


def test_freeze_rejects_failed_checks_and_missing_or_postoutcome_chronology(driver, isolated_freeze):
    passed = json.dumps({"status": "passed", "evaluation_audit_outcomes_observed": 0})
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        path = isolated_freeze / name
        path.write_text(json.dumps({"status": "failed", "evaluation_audit_outcomes_observed": 0}))
        with pytest.raises(ValueError, match="Pre-freeze check has not passed"):
            driver.freeze()
        assert not (isolated_freeze / "freeze.json").exists()
        path.write_text(passed)
    for observed in (None, 1):
        (isolated_freeze / "pre_freeze_checks.json").write_text(
            json.dumps({"status": "passed", "evaluation_audit_outcomes_observed": observed}))
        with pytest.raises(ValueError, match="chronology is not pre-outcome"):
            driver.freeze()
        assert not (isolated_freeze / "freeze.json").exists()


def test_freeze_binds_source_config_and_complete_dependency_set(driver, isolated_freeze):
    assert driver.freeze()["status"] == "frozen"
    assert driver.verify_freeze() == 5
    for name in ("source.py", "config.json"):
        path = isolated_freeze / name
        original = path.read_bytes()
        path.write_bytes(original + b"\n")
        with pytest.raises(ValueError, match="Frozen computational input changed"):
            driver.verify_freeze()
        path.write_bytes(original)
    frozen_path = isolated_freeze / "freeze.json"
    frozen = json.loads(frozen_path.read_text())
    frozen["files_sha256"].pop("study/source.py")
    frozen_path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="dependency closure differs"):
        driver.verify_freeze()


def test_freeze_and_run_refuse_existing_outputs_before_any_case_loading(driver, isolated_freeze, monkeypatch):
    driver.freeze()
    frozen = (isolated_freeze / "freeze.json").read_bytes()
    with pytest.raises(FileExistsError):
        driver.freeze()
    assert (isolated_freeze / "freeze.json").read_bytes() == frozen
    output = isolated_freeze / "results"
    output.mkdir()
    marker = output / "untouched.txt"
    marker.write_text("existing output")
    monkeypatch.setattr(driver, "_inputs", lambda *a, **kw: pytest.fail("No input population may be loaded"))
    with pytest.raises(FileExistsError):
        driver.execute(output)
    assert marker.read_text() == "existing output" and list(output.iterdir()) == [marker]
