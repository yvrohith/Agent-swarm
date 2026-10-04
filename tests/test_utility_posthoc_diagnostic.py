"""Retrospective transforms are narrow; never choose a favorable answer."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from tracebench.investigator_utility.scoring import score_response

SPEC = importlib.util.spec_from_file_location(
    "utility_diagnostic", Path(__file__).resolve().parents[1]
    / "studies/review_remediation/utility_diagnostic.py")
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)
VALID = {"case_id": "example", "answers": [{"claim_id": "q0", "status": "established",
                                         "evidence_ids": ["r0"], "reason": "Recorded."}]}
CASE = {"case_id": "example", "subset": "synthetic", "cluster_id": "cluster",
        "claims": [{"id": "q0"}], "records": [{"id": "r0"}]}
GOLD = {"case_id": "example", "claims": [{"id": "q0", "status": "established"}]}


def claim(value):
    return score_response(CASE, GOLD, value)["claims"][0]


def test_unchanged_json_retains_exact_visible_string():
    text = json.dumps(VALID, indent=2)
    result, transforms, blockers, spans = diagnostic.normalize(text, {"q0"})
    assert result == text and not transforms and not blockers and not spans


def test_unique_fenced_object_ignores_numeric_arrays_and_nested_answers():
    text = "Window [10,20].\n```json\n" + json.dumps(VALID) + "\n```"
    value, transforms, blockers, spans = diagnostic.normalize(text, {"q0"})
    assert value == VALID and not blockers
    assert len(spans) == 1 and transforms[0]["operation"] == "extract_unique_response_object"


@pytest.mark.parametrize("second_status", ["established", "ruled_out"])
def test_two_objects_remain_ambiguous_even_when_statuses_agree(second_status):
    second = copy.deepcopy(VALID)
    second["answers"][0]["status"] = second_status
    text = json.dumps(VALID) + "\nCorrection:\n" + json.dumps(second)
    value, transforms, blockers, spans = diagnostic.normalize(text, {"q0"})
    assert value == text and not transforms and blockers == ["multiple_candidates"]
    assert len(spans) == 2 and not claim(value)["schema_valid"]


@pytest.mark.parametrize("text", [
    '[{"case_id":"example","answers":[]}]',
    '{"case_id":"example","case_id":"wrong","answers":[]}',
])
def test_invalid_root_or_duplicate_keys_are_not_repaired(text):
    value, transforms, _, _ = diagnostic.normalize(text, {"q0"})
    assert value == text and not transforms and not claim(value)["schema_valid"]


@pytest.mark.parametrize("mode", ["rename", "remove_agreeing"])
def test_expected_id_mapping(mode):
    source = copy.deepcopy(VALID)
    source["answers"][0]["id"] = "q0"
    if mode == "rename":
        del source["answers"][0]["claim_id"]
    value, transforms, blockers, _ = diagnostic.normalize(json.dumps(source), {"q0"})
    assert value == VALID and not blockers and len(transforms) == 1
    assert claim(value)["status_correct"]


@pytest.mark.parametrize("mode", ["conflict", "nonmember", "other_extra"])
def test_conflicting_nonmember_or_unrelated_extra_fields_stay_invalid(mode):
    source = copy.deepcopy(VALID)
    if mode == "conflict":
        source["answers"][0]["id"] = "q1"
    elif mode == "nonmember":
        source["answers"][0]["id"] = source["answers"][0].pop("claim_id")
        source["answers"][0]["id"] = "unknown"
    else:
        source["answers"][0]["unrelated"] = True
    text = json.dumps(source)
    value, transforms, _, _ = diagnostic.normalize(text, {"q0", "q1"})
    assert value == text and not transforms and not claim(value)["schema_valid"]


def test_duplicate_claims_created_by_mapping_remain_invalid():
    source = copy.deepcopy(VALID)
    source["answers"].append({"id": "q0", "status": "established", "evidence_ids": [], "reason": "Again."})
    value, _, _, _ = diagnostic.normalize(json.dumps(source), {"q0"})
    assert "duplicate_claim" in claim(value)["schema_errors"]


def test_unknown_citation_and_wrong_status_never_repaired():
    source = copy.deepcopy(VALID)
    source["answers"][0].update(id="q0", evidence_ids=["missing"], status="ruled_out")
    value, _, _, _ = diagnostic.normalize(json.dumps(source), {"q0"})
    scored = claim(value)
    assert scored["schema_valid"] and not scored["citation_valid"] and not scored["status_correct"]
    assert value["answers"][0]["evidence_ids"] == ["missing"]


@pytest.mark.parametrize("flag", ["refused", "truncated"])
def test_provider_failure_cannot_become_accepted(flag):
    value, transforms, blockers, _ = diagnostic.normalize(json.dumps(VALID), {"q0"}, **{flag: True})
    assert value is None and not transforms and blockers and not claim(value)["schema_valid"]


def test_case_means_are_not_pooled_claim_ratios():
    one = score_response(CASE, GOLD, VALID)
    two = copy.deepcopy(one)
    metric = "warranted_answer_accuracy"
    one["metrics"][metric] = {"numerator": 1, "denominator": 1, "value": 1.0}
    two["metrics"][metric] = {"numerator": 0, "denominator": 3, "value": 0.0}
    result = diagnostic.summarize([one, two])
    assert result["case_means"][metric]["value"] == 0.5
    assert result["pooled_claim_metrics"][metric] == {"numerator": 1, "denominator": 4}
