"""No-inference integration checks for the whole-study budget gate."""

import copy

import pytest

from tracebench.investigator_utility import __main__ as cli
from tracebench.investigator_utility.execution import ExecutionBlocked
from tracebench.investigator_utility.study import read_json, write_json
from tracebench.investigator_utility.synthetic_cases import build_synthetic_cases


def setup_cases(tmp_path, monkeypatch):
    cases, golds, manifest = build_synthetic_cases()
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    write_json(prepared / "public_cases.json", cases)
    write_json(prepared / "gold.json", golds)
    write_json(prepared / "selection.json", manifest)
    config = read_json(cli.STUDY / "config.json")
    config["models"] = [{"model_id": "unit-test-model"}]
    ledger_dir = tmp_path / "calls"
    ledger_dir.mkdir()
    monkeypatch.setattr(cli, "_ledger_path", lambda _: ledger_dir)
    return prepared, config, ledger_dir


def test_budget_gate_includes_development_and_evaluation_not_only_next_split(tmp_path, monkeypatch):
    prepared, config, ledger_dir = setup_cases(tmp_path, monkeypatch)
    (ledger_dir / "attempts.jsonl").write_text('{"event":"test-prior-reservation"}\n')
    captured = []

    def check(requests, models, limits, *, existing_events):
        captured.append((requests, models, limits, existing_events))
        return {"status": "ready", "total_schedule_bound_usd": "1"}

    monkeypatch.setattr(cli, "schedule_preflight", check)
    result = cli.whole_schedule_preflight(prepared, config)
    requests, models, limits, events = captured[0]
    assert sum(r["split"] == "development" for r in requests) == 6
    assert sum(r["split"] == "evaluation" for r in requests) == 24
    assert {r["arm"] for r in requests} == {"A", "B", "C"}
    assert models == config["models"] and limits["budget_usd"] == "25.00"
    assert events == [{"event": "test-prior-reservation"}]
    assert result["status"] == "ready"


def test_development_never_calls_transport_when_entire_plan_is_over_budget(tmp_path, monkeypatch):
    prepared, config, _ = setup_cases(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(cli, "validate_prepared", lambda *args: {})
    monkeypatch.setattr(cli, "run_requests", lambda *args: calls.append(args))

    def over_budget(*args, **kwargs):
        raise ExecutionBlocked("Entire frozen schedule plus retries exceeds the cap")

    monkeypatch.setattr(cli, "schedule_preflight", over_budget)
    output = tmp_path / "development"
    with pytest.raises(ExecutionBlocked, match="Entire frozen schedule"):
        cli.develop(prepared, config, output)
    assert calls == [] and not output.exists()


def test_unconfigured_model_does_not_create_fake_cost_bound(tmp_path, monkeypatch):
    prepared, config, _ = setup_cases(tmp_path, monkeypatch)
    empty = copy.deepcopy(config)
    empty["models"] = []
    result = cli.whole_schedule_preflight(prepared, empty)
    assert result["status"] == "blocked"
    assert "total_schedule_bound_usd" not in result
