import copy

import pytest

from tracebench.evidence_responsiveness import __main__ as cli
from tracebench.evidence_responsiveness.common import file_hash, write
from tracebench.evidence_responsiveness.receipts import build_receipt_families
from tracebench.evidence_responsiveness.wiki import _case, certify_wiki


@pytest.fixture(scope="module")
def full_design():
    bundle = build_receipt_families()
    for i in range(5):
        split = "development" if i == 0 else "evaluation"
        family = {"family_id": f"wiki-{i}", "cluster_id": f"history-{i}",
                  "subset": "wiki_derived", "split": split, "variants": {}, "motif": "test"}
        for role in ("base", "irrelevant", "decisive"):
            before = "A quiet note." if role != "decisive" else "A quiet note. AlphaPage."
            after = "A quiet note. AlphaPage." + (" Additional note." if role == "irrelevant" else "")
            case = _case(family["family_id"], split, family["cluster_id"], role,
                         "AlphaPage", before, after)
            family["variants"][role] = case["case_id"]
            bundle["cases"].append(case)
            bundle["gold"].append(certify_wiki(case))
        bundle["families"].append(family)
    return bundle


def test_full_design_requires_every_certified_variant(full_design):
    result = cli.validate(full_design["cases"], full_design["gold"], full_design["families"])
    assert result["certificates_reproduced"] == 42
    assert result["relationship_checks"] == 14
    assert result["constant_baselines_pass"]


def test_certificate_changed_after_selection_is_rejected(full_design):
    gold = copy.deepcopy(full_design["gold"])
    gold[0]["claims"][0]["status"] = "invented"
    with pytest.raises(ValueError, match="Certificate"):
        cli.validate(full_design["cases"], gold, full_design["families"])


def test_cannot_drop_family_or_reuse_a_variant(full_design):
    with pytest.raises(ValueError, match="strata"):
        cli.validate(full_design["cases"], full_design["gold"], full_design["families"][:-1])
    families = copy.deepcopy(full_design["families"])
    families[0]["variants"]["decisive"] = families[0]["variants"]["base"]
    with pytest.raises(ValueError, match="relationship"):
        cli.validate(full_design["cases"], full_design["gold"], families)


@pytest.mark.parametrize("changed", ["result.json", "raw-response.json"])
def test_preservation_rejects_result_or_prior_response_mutation(tmp_path, monkeypatch, changed):
    study = tmp_path / "study"
    study.mkdir()
    for name in ("result.json", "raw-response.json"):
        (tmp_path / name).write_text("unchanged")
    write(study / "preservation.json", {"baseline_commit": "original",
          "tracked_sha256": {"result.json": file_hash(tmp_path / "result.json")},
          "historical_raw_sha256": {"raw-response.json": file_hash(tmp_path / "raw-response.json")}})
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(cli, "STUDY", study)
    assert cli.preservation()["all_match"]
    (tmp_path / changed).write_text("changed")
    with pytest.raises(ValueError, match="Preserved files differ"):
        cli.preservation()


def test_presentation_changes_are_explicit_and_require_actual_results(tmp_path, monkeypatch):
    study = tmp_path / 'study'
    study.mkdir()
    (tmp_path / 'README.md').write_text('baseline')
    write(study / 'preservation.json', {
        'baseline_commit': 'original',
        'tracked_sha256': {'README.md': file_hash(tmp_path / 'README.md')},
        'historical_raw_sha256': {}, 'presentation_only_paths': ['README.md']})
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'STUDY', study)
    (tmp_path / 'README.md').write_text('actual result link')
    with pytest.raises(ValueError, match='actual study results'):
        cli.preservation()
    (study / 'results').mkdir()
    (study / 'results/REPORT.md').write_text('results')
    result = cli.preservation()
    assert result['scientific_all_match'] and result['historical_raw_all_match']
    assert not result['all_match']
    assert result['changed_presentation_paths'] == ['README.md']


@pytest.mark.parametrize('condition', ['clean', 'stale', 'early_evaluation'])
def test_freeze_binds_development_snapshot_to_live_ledger(tmp_path, monkeypatch, condition):
    import json

    monkeypatch.setattr(cli, 'RAW', tmp_path)
    (tmp_path / 'calls').mkdir()
    ledger = tmp_path / 'calls/attempts.jsonl'
    ledger.write_text(json.dumps({'event': 'study'}) + '\n')
    development = {'ledger_sha256': file_hash(ledger), 'development_completed': 12,
                   'evaluation_completed': 0}
    if condition != 'clean':
        with ledger.open('a') as stream:
            stream.write(json.dumps({'event': 'attempt_reserved', 'split': 'evaluation'}) + '\n')
        if condition == 'early_evaluation':
            development['ledger_sha256'] = file_hash(ledger)
        with pytest.raises(ValueError, match='live ledger|attempted before'):
            cli.verify_development_snapshot({'models': [{}, {}]}, development)
    else:
        cli.verify_development_snapshot({'models': [{}, {}]}, development)
