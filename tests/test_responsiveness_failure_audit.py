"""Only diagnostic logic is new; frozen acceptance is never relaxed."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    'failure_audit', Path(__file__).resolve().parents[1]
    / 'studies/evidence_responsiveness/offline_failure_audit/audit.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
VALID = {'case_id': 'test', 'answers': [{'claim_id': 'q0', 'status': 'established',
                                     'evidence_ids': ['r0'], 'reason': 'Recorded.'}]}
SCORE = {'completion_valid': True, 'schema_errors': [], 'response_errors': []}


@pytest.mark.parametrize(('text', 'subtype'), [
    (json.dumps(VALID), 'whole_json'),
    ('```json\n' + json.dumps(VALID) + '\n```', 'sole_markdown_fence_single_json_value'),
    ('A JSON array is written [].\n```json\n' + json.dumps(VALID) + '\n```',
     'surrounding_prose_single_json_value'),
    ('Here is the requested object:\n' + json.dumps(VALID), 'surrounding_prose_single_json_value'),
    (json.dumps(VALID) + '\nCorrection:\n' + json.dumps(VALID), 'multiple_or_ambiguous_json_values'),
    ('{"case_id":"a","case_id":"b","answers":[]}', 'duplicate_json_keys'),
    ('{"case_id":', 'malformed_json'),
])
def test_whole_response_diagnostic_does_not_select_or_repair(text, subtype):
    before = text
    kind, value = audit.diagnostic_json(text)
    assert kind == subtype
    assert text == before
    if kind in {'multiple_or_ambiguous_json_values', 'duplicate_json_keys', 'malformed_json'}:
        assert value is None


@pytest.mark.parametrize(('final', 'refusal', 'expected'), [
    (None, True, 'provider_refusal_or_filter'),
    ('', False, 'empty_final_without_refusal'),
    ('not JSON', False, 'serialization_violation'),
    (json.dumps(VALID), False, 'accepted'),
])
def test_primary_precedence_does_not_double_count_cascades(final, refusal, expected):
    result = audit.classify(final, SCORE, refusal=refusal)
    assert result['primary_cause'] == expected
    assert result['actual_final_empty'] == (final is None or final == '')


def test_nonempty_malformed_output_is_not_absent_final():
    score = {**SCORE, 'completion_valid': False,
             'schema_errors': ['answers_not_list', 'wrong_case_id', 'missing_claim'],
             'response_errors': ['malformed_json', 'missing_response']}
    result = audit.classify('Here is JSON: ' + json.dumps(VALID), score)
    assert result['primary_cause'] == 'serialization_violation'
    assert not result['actual_final_empty']


def test_object_answers_ambiguity_is_distinct_from_serialization():
    value = copy.deepcopy(VALID)
    value['answers'] = value['answers'][0]
    score = {**SCORE, 'completion_valid': False, 'schema_errors': ['answers_not_list']}
    result = audit.classify(json.dumps(value), score)
    assert result['subtype'] == 'object_valued_answers'
    assert result['attribution'] == 'prompt_underspecification'


@pytest.mark.parametrize(('change', 'errors', 'primary', 'flag'), [
    ('replace_id', ['unknown_claim_id', 'missing_claim'], 'case_or_claim_identity_violation',
     'id_instead_of_claim_id'),
    ('extra_id', ['invalid_answer_fields'], 'answer_field_or_value_violation',
     'extra_id_alongside_claim_id'),
])
def test_explicit_field_violations(change, errors, primary, flag):
    value = copy.deepcopy(VALID)
    value['answers'][0]['id'] = 'q0'
    if change == 'replace_id':
        del value['answers'][0]['claim_id']
    score = {**SCORE, 'completion_valid': False, 'schema_errors': errors}
    result = audit.classify(json.dumps(value), score)
    assert result['primary_cause'] == primary
    assert flag in result['secondary_flags']


def test_refusal_takes_precedence_over_adapter_defect():
    assert audit.classify('', SCORE, refusal=True, extraction_defect=True)['primary_cause'] == 'provider_refusal_or_filter'


def test_final_projection_never_inspects_or_exports_private_fields(monkeypatch):
    class Forbidden:
        def __str__(self):
            pytest.fail('Private reasoning inspected')

    saved = {'completion_text': 'final', 'raw_response': {
        'model': 'model', 'provider': 'provider', 'private_account': Forbidden(),
        'choices': [{'finish_reason': 'stop', 'message': {'content': 'final',
            'reasoning': Forbidden(), 'reasoning_details': Forbidden()}}]}}
    monkeypatch.setattr(audit, 'read', lambda _: saved)
    result = audit.final_projection(Path('unused'))
    assert result['final_content'] == result['saved_completion_text'] == result['adapter_extracted']
    assert set(result) == {'final_content', 'saved_completion_text', 'adapter_extracted',
                           'finish_reason', 'refusal', 'response_model', 'provider'}
    assert 'private' not in json.dumps(result)


def test_request_difference_preserves_id_text_and_derived_hash_distinctions():
    base = {'case_id': 'a', 'records': [{'text': 'abc', 'text_sha256': 'old'}], 'assumptions': []}
    variant = {'case_id': 'b', 'records': [{'text': 'adc', 'text_sha256': 'new'}], 'assumptions': []}
    differences = audit.field_differences(base, variant)
    assert {d['path'] for d in differences} == {'/case_id', '/records/0/text', '/records/0/text_sha256'}
    assert all(set(d) == {'path', 'before_sha256', 'after_sha256'} for d in differences)
