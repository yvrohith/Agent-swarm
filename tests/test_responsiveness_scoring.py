"""Two-sided evidence responsiveness, strict IDs, and fixed clustered units."""

import copy
import hashlib
import itertools
import json

import pytest

from tracebench.evidence_responsiveness.common import ROLES
from tracebench.evidence_responsiveness.scoring import (
    PRIMARY_METRICS,
    constant_baselines,
    score_families,
    score_variant,
    select_examples,
    summarize,
)
from tracebench.investigator_utility.scoring import STATUSES


def fixtures(family_id="f1", *, subset="receipt", cluster=None, split="evaluation",
             statuses=("established", "established", "unresolved")):
    family = {
        "family_id": family_id, "subset": subset, "split": split,
        "cluster_id": cluster or family_id, "motif": "test motif",
        "variants": {role: f"opaque-{family_id}-{index}" for index, role in enumerate(ROLES)},
    }
    cases, golds = [], []
    for role, status in zip(ROLES, statuses, strict=True):
        case_id = family["variants"][role]
        cases.append({
            "schema_version": 1, "case_id": case_id, "subset": subset,
            "split": split, "cluster_id": family["cluster_id"],
            "records": [{"id": "r1", "text": "Evidence quoted as data."}],
            "assumptions": [{"id": "a1", "text": "Declared contract."}],
            "claims": [{"id": "q0", "text": "The primary claim."}],
        })
        golds.append({"case_id": case_id, "claims": [
            {"id": "q0", "status": status, "certificate": {"kind": "test"}},
        ], "validation": {"valid": True}})
    return cases, golds, family


def response(case, status, *, evidence=None):
    return {"case_id": case["case_id"], "answers": [{
        "claim_id": "q0", "status": status,
        "evidence_ids": ["r1", "a1"] if evidence is None else evidence,
        "reason": "A brief justification from the declared record and assumption.",
    }]}


def rows_for(cases, golds, *, statuses=None, model="m"):
    statuses = statuses or [gold["claims"][0]["status"] for gold in golds]
    return [score_variant(case, gold, response(case, status), model)
            for case, gold, status in zip(cases, golds, statuses, strict=True)]


@pytest.mark.parametrize("statuses", list(itertools.product(STATUSES, repeat=3)))
def test_paired_correctness_requires_both_correct_statuses_not_merely_change(statuses):
    cases, golds, family = fixtures()
    scored = score_families(rows_for(cases, golds, statuses=statuses), [family])[0]
    base, irrelevant, decisive = statuses
    metrics = scored["metrics"]
    assert metrics["decisive_pair_correct"] == (base == "established" and decisive == "unresolved")
    assert metrics["invariant_pair_correct"] == (base == irrelevant == "established")
    assert metrics["whole_family_correct"] == (statuses == ("established", "established", "unresolved"))
    assert metrics["incorrect_stability_decisive"] == (base == decisive)
    assert metrics["incorrect_change_irrelevant"] == (base != irrelevant)


@pytest.mark.parametrize("subset", ["receipt", "wiki_derived"])
def test_private_subset_adapter_preserves_public_identity_and_inputs(subset):
    cases, golds, _ = fixtures(subset=subset)
    before = copy.deepcopy((cases, golds))
    score = score_variant(cases[0], golds[0], json.dumps(response(cases[0], "established")), "m")
    assert (cases, golds) == before
    assert score["subset"] == subset
    assert score["status_correct"] and score["strict_correct"]
    assert score["valid_evidence_ids"] == ["a1", "r1"]


@pytest.mark.parametrize("bad", [None, "", "No answer.", "```json\n{}\n```", [], 4,
                                 {"case_id": "wrong", "answers": []}])
def test_invalid_and_missing_completions_keep_all_pair_denominators(bad):
    cases, golds, family = fixtures()
    rows = rows_for(cases, golds)
    rows[0] = score_variant(cases[0], golds[0], bad, "m")
    family_rows = score_families(rows, [family])
    assert all(not family_rows[0]["metrics"][metric] for metric in PRIMARY_METRICS)
    summary = summarize(family_rows, resamples=20)["groups"][0]
    assert all(summary["metrics"][metric]["denominator"] == 1 for metric in PRIMARY_METRICS)
    assert summary["diagnostics"]["invalid"] == {"numerator": 1, "denominator": 3, "value": 1 / 3}
    assert summary["observed_decisive_pairs"] == summary["observed_invariant_pairs"] == 0


@pytest.mark.parametrize("evidence,status_ok,support_ok,citation_error", [
    ([], True, False, False), (["a1"], True, True, False),
    (["r1", "made-up"], True, False, True), (["made-up"], True, False, True),
    (["r1", "r1"], True, True, False), ("r1", False, False, True),
])
def test_status_and_strict_mechanical_support_are_separate(evidence, status_ok, support_ok,
                                                          citation_error):
    cases, golds, family = fixtures()
    rows = rows_for(cases, golds)
    rows[0] = score_variant(cases[0], golds[0],
                            response(cases[0], "established", evidence=evidence), "m")
    row = rows[0]
    assert row["status_correct"] == status_ok
    assert row["strict_correct"] == support_ok
    assert row["citation_error"] == citation_error
    metrics = score_families(rows, [family])[0]["metrics"]
    assert metrics["whole_family_correct"] == status_ok
    assert metrics["strict_whole_family_correct"] == support_ok


@pytest.mark.parametrize("finish_reason,refused", [("content_filter", False), ("refusal", False),
                                                  ("stop", True)])
def test_refusal_metadata_never_receives_success_even_if_content_is_valid(finish_reason, refused):
    cases, golds, family = fixtures()
    rows = rows_for(cases, golds)
    rows[2] = score_variant(cases[2], golds[2], response(cases[2], "unresolved"), "m",
                            finish_reason, refused=refused)
    assert rows[2]["schema_valid"]
    assert rows[2]["refused"]
    assert not rows[2]["status_correct"]
    family_row = score_families(rows, [family])[0]
    assert not family_row["metrics"]["decisive_pair_correct"]
    assert not family_row["observed_decisive_pair"]
    assert family_row["metrics"]["invariant_pair_correct"]


@pytest.mark.parametrize("finish_reason", ["length", "max_tokens"])
def test_truncated_completions_fail_even_when_returned_json_is_valid(finish_reason):
    cases, golds, family = fixtures()
    rows = rows_for(cases, golds)
    rows[0] = score_variant(cases[0], golds[0], response(cases[0], "established"), "m",
                            finish_reason)
    assert rows[0]["schema_valid"] and rows[0]["truncated"]
    assert not rows[0]["completion_valid"]
    assert not rows[0]["status_correct"] and not rows[0]["strict_correct"]
    scored = score_families(rows, [family])
    assert all(not scored[0]["metrics"][metric] for metric in PRIMARY_METRICS)
    group = summarize(scored, resamples=20)["groups"][0]
    assert group["diagnostics"]["truncated"]["numerator"] == 1
    for metric in ("incorrect_stability_decisive", "incorrect_change_irrelevant"):
        assert group["metrics"][metric]["mean"] is None
        assert group["metrics"][metric]["denominator"] == 0


def test_invalid_pairs_do_not_dilute_conditional_behavior_rates():
    cases1, golds1, first = fixtures("f1")
    cases2, golds2, second = fixtures("f2")
    # The only observable pair is incorrectly stable on decisive evidence and
    # incorrectly changes on irrelevant evidence. An absent base is not a pass.
    rows = rows_for(cases1, golds1, statuses=("established", "ruled_out", "established"))
    rows.extend(rows_for(cases2, golds2))
    rows[3] = score_variant(cases2[0], golds2[0], None, "m")
    group = summarize(score_families(rows, [first, second]), resamples=20)["groups"][0]
    for metric in ("incorrect_stability_decisive", "incorrect_change_irrelevant"):
        assert group["metrics"][metric]["mean"] == 1
        assert group["metrics"][metric]["denominator"] == 1
        assert group["metrics"][metric]["numerator"] == 1
    for metric in PRIMARY_METRICS:
        assert group["metrics"][metric]["denominator"] == 2
        assert group["metrics"][f"strict_{metric}"]["denominator"] == 2


@pytest.mark.parametrize("alteration", ["duplicate_json", "extra_field", "wrong_claim",
                                       "empty_reason", "overlong_reason", "duplicate_claim"])
def test_unchanged_strict_response_parser_rejects_without_repair(alteration):
    cases, golds, _ = fixtures()
    output = response(cases[0], "established")
    if alteration == "duplicate_json":
        output = '{"case_id":"x","case_id":"x","answers":[]}'
    elif alteration == "extra_field":
        output["answers"][0]["confidence"] = 1
    elif alteration == "wrong_claim":
        output["answers"][0]["claim_id"] = "gold_established"
    elif alteration == "empty_reason":
        output["answers"][0]["reason"] = "  "
    elif alteration == "overlong_reason":
        output["answers"][0]["reason"] = "x" * 401
    elif alteration == "duplicate_claim":
        output["answers"].append(copy.deepcopy(output["answers"][0]))
    scored = score_variant(cases[0], golds[0], output, "m")
    assert not scored["schema_valid"]
    assert not scored["status_correct"]
    assert not scored["strict_correct"]


def test_missing_rows_and_fully_missing_model_are_explicit_failures():
    cases, golds, family = fixtures()
    rows = rows_for(cases, golds)[:2]
    result = score_families(rows, [family], model_ids=["m", "missing-model"])
    observed, missing_model = result
    assert observed["missing_score_rows"] == ["decisive"]
    assert observed["metrics"]["invariant_pair_correct"]
    assert not observed["metrics"]["decisive_pair_correct"]
    assert missing_model["missing_score_rows"] == list(ROLES)
    summary = summarize(result, resamples=20)
    for group in summary["groups"]:
        assert group["n_families"] == 1 and group["n_variants"] == 3
        assert group["metrics"]["decisive_pair_correct"]["denominator"] == 1
    assert summary["groups"][1]["diagnostics"]["missing"]["numerator"] == 3
    with pytest.raises(ValueError, match="model_ids required"):
        score_families([], [family])


def test_omitted_whole_family_not_dropped_from_fixed_universe():
    c1, g1, f1 = fixtures("f1")
    _, _, f2 = fixtures("f2")
    result = score_families(rows_for(c1, g1), [f1, f2])
    group = summarize(result, resamples=40)["groups"][0]
    assert group["n_families"] == 2
    assert group["metrics"]["whole_family_correct"]["mean"] == 0.5
    assert group["diagnostics"]["missing"]["numerator"] == 3


@pytest.mark.parametrize("alteration", ["duplicate_row", "duplicate_family", "duplicate_case",
                                       "unknown_case", "wrong_cluster", "wrong_split",
                                       "wrong_subset", "gold_changed"])
def test_pairing_rejects_corrupted_identity_or_duplicate_observations(alteration):
    cases, golds, family = fixtures()
    rows, families = rows_for(cases, golds), [family]
    if alteration == "duplicate_row":
        rows.append(copy.deepcopy(rows[0]))
    elif alteration == "duplicate_family":
        families.append(copy.deepcopy(family))
    elif alteration == "duplicate_case":
        family["variants"]["decisive"] = family["variants"]["base"]
    elif alteration == "unknown_case":
        rows[0]["case_id"] = "unknown"
    elif alteration == "wrong_cluster":
        rows[0]["cluster_id"] = "other"
    elif alteration == "wrong_split":
        rows[0]["split"] = "development"
    elif alteration == "wrong_subset":
        rows[0]["subset"] = "wiki_derived"
    elif alteration == "gold_changed":
        changed = {**rows[0], "model_id": "other-model", "gold_status": "unresolved"}
        rows.append(changed)
    with pytest.raises(ValueError):
        score_families(rows, families)


@pytest.mark.parametrize("role,replacement", [("irrelevant", "unresolved"),
                                             ("decisive", "established")])
def test_pairing_checks_gold_invariance_and_decisive_relationships(role, replacement):
    cases, golds, family = fixtures()
    rows = rows_for(cases, golds)
    rows[ROLES.index(role)]["gold_status"] = replacement
    with pytest.raises(ValueError, match="pair has"):
        score_families(rows, [family])


def test_constant_statuses_never_pass_decisive_or_whole_family():
    cases, golds, family = fixtures()
    others, other_gold, second = fixtures("f2", subset="wiki_derived",
                                         statuses=("unresolved", "unresolved", "ruled_out"))
    baselines = constant_baselines(cases + others, golds + other_gold, [family, second])
    assert len(baselines["variant_rows"]) == 18
    assert len(baselines["family_rows"]) == 6
    for row in baselines["family_rows"]:
        assert not row["metrics"]["decisive_pair_correct"]
        assert not row["metrics"]["whole_family_correct"]
        assert not row["metrics"]["strict_invariant_pair_correct"]
    assert {g["model_id"] for g in baselines["summary"]["groups"]} == {
        f"always_{status}" for status in STATUSES}
    with pytest.raises(ValueError, match="complete family universe"):
        constant_baselines(cases[:2], golds[:2], [family])


def test_history_cluster_bootstrap_keeps_triplets_and_shared_families_together():
    rows, families = [], []
    for family_id in ("f1", "f2", "f3"):
        cases, golds, family = fixtures(family_id, cluster="same-history")
        families.append(family)
        statuses = ("established", "established", "unresolved") if family_id == "f1" else STATUSES
        rows.extend(rows_for(cases, golds, statuses=statuses))
    scored = score_families(rows, families)
    summary = summarize(scored, resamples=50)["groups"][0]
    metric = summary["metrics"]["whole_family_correct"]
    assert summary["n_variants"] == 9
    assert metric["n_families"] == 3
    assert metric["n_clusters"] == 1
    assert metric["mean"] == 1 / 3
    assert metric["ci_low"] is None and metric["ci_high"] is None


def test_bootstrap_is_reproducible_order_independent_and_separates_models_substrates_splits():
    rows, families = [], []
    for subset, split, index in itertools.product(("receipt", "wiki_derived"),
                                                 ("development", "evaluation"), range(3)):
        cases, golds, family = fixtures(f"{subset}-{split}-{index}", subset=subset, split=split)
        families.append(family)
        for model in ("m1", "m2"):
            rows.extend(rows_for(cases, golds, model=model,
                                 statuses=STATUSES if index == 0 else None))
    scored = score_families(rows, families)
    first = summarize(scored, resamples=100)
    assert first == summarize(list(reversed(scored)), resamples=100)
    assert len(first["groups"]) == 8
    for group in first["groups"]:
        assert group["n_families"] == group["n_clusters"] == 3
        assert group["n_variants"] == 9
        assert group["metrics"]["whole_family_correct"]["mean"] == 2 / 3
    with pytest.raises(ValueError, match="duplicate"):
        summarize(scored + [scored[0]])


@pytest.mark.parametrize("resamples", [0, -1, True, 2.5])
def test_bootstrap_rejects_invalid_resampling_count(resamples):
    with pytest.raises(ValueError, match="positive integer"):
        summarize([], resamples=resamples)


def test_all_pass_retained_and_examples_explicitly_absent():
    rows, families = [], []
    for family_id in ("f1", "f2"):
        cases, golds, family = fixtures(family_id)
        families.append(family)
        rows.extend(rows_for(cases, golds))
    scored = score_families(rows, families)
    summary = summarize(scored, resamples=100)["groups"][0]
    for metric in PRIMARY_METRICS:
        assert summary["metrics"][metric]["mean"] == 1
        assert summary["metrics"][metric]["ci_low"] == 1
        assert summary["metrics"][metric]["ci_high"] == 1
    examples = select_examples(scored)
    assert len(examples) == 2
    assert all(example["selection"] is None and example["absence"] for example in examples)


def test_examples_use_frozen_hash_order_not_most_dramatic_failure():
    rows, families = [], []
    for family_id in ("f1", "f2", "f3"):
        cases, golds, family = fixtures(family_id)
        families.append(family)
        rows.extend(rows_for(cases, golds, statuses=("ruled_out",) * 3))
    scored = score_families(rows, families)
    expected = min(scored, key=lambda row: hashlib.sha256(
        row["variants"]["base"]["case_id"].encode()).hexdigest())["family_id"]
    examples = select_examples(scored)
    assert {example["selection"]["family_id"] for example in examples} == {expected}
    assert examples == select_examples(list(reversed(scored)))
    with pytest.raises(ValueError, match="duplicate"):
        select_examples(scored + [scored[0]])
