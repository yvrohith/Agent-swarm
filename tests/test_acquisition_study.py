"""Study-level weighting, frozen-input boundary, and overwrite protection."""
import json
from fractions import Fraction

import pytest

from tracebench.evidence_acquisition import study
from tracebench.evidence_acquisition.generator import generate_problem


def test_aggregation_keeps_problem_and_signature_denominators_separate():
    problem = generate_problem(94103)
    config = {'policies': ['read_all', 'schema_aware', 'world_entropy', 'pair_cut', 'exact_optimal'],
              'budget_percentages': [0, 100]}
    result = study.evaluate([problem], config)
    summary = study.summarize(result)
    assert summary['problems'] == 1
    assert summary['policy_budget_rows'] == 10
    assert summary['certificate_failures'] == 0
    for row in result['per_problem_policy_budget']:
        assert sum(Fraction(row['expected'][s]['exact']) for s in study.STATES) == 1
        if row['budget_percent'] == 0:
            assert row['expected']['cost']['exact'] == '0'
        else:
            assert row['expected']['budget_exhausted_unresolved']['exact'] == '0'
    assert all(x['ratio'] is not None for x in summary['optimal_comparisons'])


def test_frozen_dependency_tampering_and_missing_file_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'ROOT', tmp_path)
    monkeypatch.setattr(study, 'STUDY', tmp_path)
    dependency = tmp_path / 'input.json'
    dependency.write_text('{"claim":true}')
    monkeypatch.setattr(study, 'freeze_paths', lambda: [dependency])
    (tmp_path / 'freeze.json').write_text(json.dumps({
        'files_sha256': {'input.json': study.digest(dependency)}}))
    study.verify_freeze()
    dependency.write_text('{"claim":false}')
    with pytest.raises(ValueError, match='freeze mismatch'):
        study.verify_freeze()
    dependency.unlink()
    with pytest.raises(FileNotFoundError):
        study.verify_freeze()


def test_results_never_overwrite_existing_files(tmp_path):
    path = tmp_path / 'result.json'
    study.write_new(path, {'first': True})
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        study.write_new(path, {'first': False})
    assert path.read_bytes() == before


def test_missing_freeze_dependency_is_not_silently_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'ROOT', tmp_path)
    monkeypatch.setattr(study, 'STUDY', tmp_path)
    monkeypatch.setattr(study, 'freeze_paths', lambda: [tmp_path / 'required.json'])
    (tmp_path / 'freeze.json').write_text(json.dumps({'files_sha256': {}}))
    with pytest.raises(ValueError, match='dependency closure'):
        study.verify_freeze()


def test_mislabeled_problem_schedule_rejected():
    problem = generate_problem(94100)
    expected = [(94100, 'positive_receipt', 'development')]
    study.validate_inputs([problem], 1, expected)
    problem['split'] = 'evaluation'
    with pytest.raises(ValueError, match='identities'):
        study.validate_inputs([problem], 1, expected)
