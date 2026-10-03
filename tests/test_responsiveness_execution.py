"""Local transport fixtures test accounting without manufacturing study outputs."""

import hashlib
import json
from decimal import Decimal

import pytest

from tracebench.evidence_responsiveness.execution import (
    CALL_DIRECTORY,
    HISTORICAL_LEDGER,
    ExecutionBlocked,
    TransportFailure,
    cumulative_preflight,
    run_requests,
)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY", "unit-test-only-secret")
    historical = tmp_path / HISTORICAL_LEDGER
    historical.parent.mkdir(parents=True)
    (historical.parent / ".execution.lock").touch()
    events = [
        {"event": "study", "models_hash": "historical-fixture"},
        {"event": "attempt_reserved", "attempt_id": "prior-known", "attempt_key": "old-known",
         "attempt_number": 1, "reserved_usd": "2", "split": "evaluation"},
        {"event": "attempt_completed", "attempt_id": "prior-known", "attempt_key": "old-known",
         "charged_usd": "1", "provider_reported_actual_cost_usd": "1", "usage_cost_usd": "1",
         "split": "evaluation"},
        {"event": "attempt_reserved", "attempt_id": "prior-unknown", "attempt_key": "old-unknown",
         "attempt_number": 1, "reserved_usd": "0.5", "split": "evaluation"},
        {"event": "attempt_completed", "attempt_id": "prior-unknown", "attempt_key": "old-unknown",
         "charged_usd": "0.5", "usage_cost_usd": None, "split": "evaluation"},
    ]
    historical.write_text("".join(json.dumps(e) + "\n" for e in events))
    save(tmp_path / "studies/evidence_responsiveness/preservation.json", {
        "historical_ledger": {"path": HISTORICAL_LEDGER,
                              "sha256": hashlib.sha256(historical.read_bytes()).hexdigest()}})
    model = {
        "provider": "openrouter", "model_id": "test-only-model", "family": "test-only-family",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions", "api_key_env": "OPENROUTER_KEY",
        "context_tokens": 100000, "max_output_tokens": 100,
        "input_usd_per_million": "1", "output_usd_per_million": "2",
        "pricing_source": "https://openrouter.ai/api/v1/models",
        "pricing_verified_at": "2026-10-03T00:00:00Z", "pricing_evidence_sha256": "a" * 64,
        "limits_source": "https://openrouter.ai/docs/api-reference/parameters",
        "limits_evidence_sha256": "b" * 64, "authorized": True, "verified_limits": True,
        "input_token_bound": "utf8_bytes_plus_4096", "decoding": {},
        "reasoning": "included_in_output_cap", "request_usd": "0",
        "provider_routing": {"only": ["test-route"], "allow_fallbacks": False,
                             "require_parameters": True, "max_price": {"prompt": 1, "completion": 2}},
    }
    save(tmp_path / "studies/investigator_utility/openrouter_v1/config.json", {"models": [model]})
    requests = [{"attempt_key": f"responsiveness-{split}-{i}", "case_id": f"opaque-{split}-{i}",
                 "model_id": model["model_id"], "split": split,
                 "system": "Use only this evidence and return JSON.", "user": "Quoted evidence."}
                for split, count in (("development", 6), ("evaluation", 36)) for i in range(count)]
    return tmp_path, model, requests


def response(*_args):
    return {"choices": [{"message": {"content": "malformed but final"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "cost": "0.000007"}}


def ledger(root):
    return [json.loads(line) for line in (root / CALL_DIRECTORY / "attempts.jsonl").read_text().splitlines()]


def run_one(setup, **kwargs):
    root, model, requests = setup
    return run_requests(requests[:1], [model], root, all_requests=requests,
                        transport=kwargs.pop("transport", response), **kwargs)


def test_preflight_carries_known_cost_and_unresolved_reservation_read_only(setup):
    root, model, requests = setup
    old = (root / HISTORICAL_LEDGER).read_bytes()
    result = cumulative_preflight(requests, [model], root)
    assert result["request_count"] == 42
    assert result["development_requests"] == 6 and result["evaluation_requests"] == 36
    assert result["historical_charged_or_reserved_usd"] == "1.5"
    assert result["cumulative_known_actual_usd"] == "1"
    assert result["cumulative_unknown_actual_attempts"] == 1
    assert result["remaining_retry_attempts"] == 4
    assert not (root / CALL_DIRECTORY).exists()
    assert (root / HISTORICAL_LEDGER).read_bytes() == old


def test_whole_schedule_budget_checked_before_first_request(setup):
    root, model, requests = setup
    save(root / "studies/evidence_responsiveness/config.json", {"budget_usd": "1.6"})
    with pytest.raises(ExecutionBlocked, match="complete cumulative schedule"):
        run_one(setup)
    assert not (root / CALL_DIRECTORY / "attempts.jsonl").exists()


def test_cumulative_ceiling_cannot_be_raised_above_twenty_five(setup):
    root, model, requests = setup
    save(root / "studies/evidence_responsiveness/config.json", {"budget_usd": "1000"})
    assert cumulative_preflight(requests, [model], root)["budget_usd"] == "25"


@pytest.mark.parametrize("limits", [
    {"cumulative_budget_usd": "1.6"},
    {"cumulative_budget_usd": "25", "budget_usd": "1.6"},
    {"cumulative_budget_usd": "1.6", "budget_usd": "25"},
])
def test_stricter_cumulative_or_workspace_cap_is_used(setup, limits):
    root, model, requests = setup
    save(root / "studies/evidence_responsiveness/config.json", limits)
    with pytest.raises(ExecutionBlocked, match="cap is 1.6"):
        cumulative_preflight(requests, [model], root)


def test_full_schedule_registration_precedes_call_and_old_bytes_unchanged(setup):
    root, model, requests = setup
    old = (root / HISTORICAL_LEDGER).read_bytes()

    def transport(*_args):
        events = ledger(root)
        assert sum(e["event"] == "request" for e in events) == 42
        assert events[-1]["event"] == "attempt_reserved"
        assert len(list((root / CALL_DIRECTORY / "requests").glob("*.json"))) == 42
        return response()

    result = run_one(setup, transport=transport)
    assert result["attempts"] == 1
    assert result["cumulative_charged_or_reserved_usd"] == "1.500007"
    assert (root / HISTORICAL_LEDGER).read_bytes() == old
    assert all("unit-test-only-secret" not in p.read_text()
               for p in (root / CALL_DIRECTORY).rglob("*.json*"))


def test_completed_invalid_response_is_final_and_resume_does_not_call(setup):
    root, model, requests = setup
    first = run_one(setup)

    def forbidden(*_args):
        raise AssertionError("completed response was retried")

    resumed = run_requests(requests[:1], [model], root, transport=forbidden)
    assert first == resumed
    raw = json.loads(next((root / CALL_DIRECTORY / "responses").glob("*.json")).read_text())
    assert raw["completion_text"] == "malformed but final"


def test_missing_metadata_reserves_entire_attempt_and_missing_key_preserves_cost(setup, monkeypatch):
    root, model, requests = setup
    result = run_one(setup, transport=lambda *_: {"choices": []})
    reserved = next(e["reserved_usd"] for e in ledger(root) if e["event"] == "attempt_reserved")
    assert Decimal(result["cumulative_charged_or_reserved_usd"]) == Decimal("1.5") + Decimal(reserved)
    assert result["cumulative_unknown_actual_attempts"] == 2
    monkeypatch.delenv("OPENROUTER_KEY")
    blocked = run_requests(requests[1:2], [model], root)
    assert blocked["attempts"] == 1
    assert blocked["cumulative_charged_or_reserved_usd"] == result["cumulative_charged_or_reserved_usd"]
    assert "OPENROUTER_KEY" in blocked["blockers"][0]


def test_usage_without_actual_cost_keeps_full_reservation_across_resume(setup):
    root, model, requests = setup
    result = run_one(setup, transport=lambda *_: {
        "choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 2}})
    reserved = next(e["reserved_usd"] for e in ledger(root) if e["event"] == "attempt_reserved")
    assert Decimal(result["charged_or_reserved_usd"]) == Decimal(reserved)
    assert result["known_usage_cost_usd"] == "0.000007"
    assert Decimal(result["cumulative_unresolved_reservation_usd"]) == Decimal("0.5") + Decimal(reserved)
    assert result["cumulative_unknown_actual_attempts"] == 2
    resumed = run_requests(requests[:1], [model], root, transport=response)
    assert resumed == result


def test_only_supported_credential_name_accepted(setup):
    root, model, requests = setup
    model["api_key_env"] = "OPENROUTER_API_KEY"
    with pytest.raises(ExecutionBlocked, match="OPENROUTER_KEY only"):
        cumulative_preflight(requests, [model], root)


def test_alternate_path_and_unregistered_followup_cannot_reset_cost(setup):
    root, model, requests = setup
    with pytest.raises(ExecutionBlocked, match="alternate ledger"):
        cumulative_preflight(requests, [model], root, root / "different-calls")
    other = root / "artifacts/other-study/attempts.jsonl"
    other.parent.mkdir(parents=True)
    other.write_text("")
    with pytest.raises(ExecutionBlocked, match="unregistered study ledger"):
        cumulative_preflight(requests, [model], root)


def test_changed_historical_ledger_fails_instead_of_resetting(setup):
    root, model, requests = setup
    with (root / HISTORICAL_LEDGER).open("a") as handle:
        handle.write("\n")
    with pytest.raises(ExecutionBlocked, match="historical ledger changed"):
        cumulative_preflight(requests, [model], root)


def test_changed_model_or_request_fails_resume(setup):
    root, model, requests = setup
    run_one(setup)
    changed = {**model, "max_output_tokens": 99}
    with pytest.raises(ExecutionBlocked, match="contract changed"):
        run_requests(requests[1:2], [changed], root)
    modified = [{**r, "user": "changed"} if i == 0 else r for i, r in enumerate(requests)]
    with pytest.raises(ExecutionBlocked, match="contract changed"):
        run_requests(modified[:1], [model], root, all_requests=modified)
    with pytest.raises(ExecutionBlocked, match="exact part"):
        run_requests([{**requests[1], "user": "changed"}], [model], root)


def test_entire_schedule_required_and_duplicate_subset_rejected(setup):
    root, model, requests = setup
    with pytest.raises(ExecutionBlocked, match="entire development/evaluation"):
        run_requests(requests[:1], [model], root)
    with pytest.raises(ExecutionBlocked, match="duplicate subset"):
        run_requests([requests[0], requests[0]], [model], root, all_requests=requests)


@pytest.mark.parametrize("change", ["missing_evaluation", "extra_development", "duplicate", "private"])
def test_invalid_full_schedule_cannot_register(setup, change):
    root, model, requests = setup
    if change == "missing_evaluation":
        requests = requests[:-1]
    elif change == "extra_development":
        requests = requests + [{**requests[0], "attempt_key": "extra", "case_id": "extra"}]
    elif change == "duplicate":
        requests = requests + [requests[0]]
    else:
        requests = [{**requests[0], "gold": "established"}] + requests[1:]
    with pytest.raises(ExecutionBlocked):
        cumulative_preflight(requests, [model], root)


def test_transport_retry_limit_is_four_across_all_new_requests(setup):
    root, model, requests = setup

    def failure(*_args):
        raise TransportFailure("timeout", retryable=True)

    first = run_one(setup, transport=failure)
    assert first["attempts"] == 5 and first["additional_retry_attempts"] == 4
    second = run_requests(requests[1:2], [model], root, transport=failure)
    assert second["attempts"] == 6 and second["additional_retry_attempts"] == 4
    assert second["completed_calls"] == 0


def test_historical_retry_usage_reduces_new_retry_allowance(setup):
    root, model, requests = setup
    path = root / HISTORICAL_LEDGER
    data = [json.loads(line) for line in path.read_text().splitlines()]
    for i in range(10):
        data.append({"event": "attempt_reserved", "attempt_id": f"old-retry-{i}",
                     "attempt_key": "old-key", "attempt_number": i + 2, "reserved_usd": "0.001"})
    path.write_text("".join(json.dumps(e) + "\n" for e in data))
    save(root / "studies/evidence_responsiveness/preservation.json", {
        "historical_ledger": {"path": HISTORICAL_LEDGER,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}})
    result = cumulative_preflight(requests, [model], root)
    assert result["remaining_retry_attempts"] == 2


@pytest.mark.parametrize("configured,used,expected", [(1, 0, 1), (4, 1, 1), (0, 0, 0)])
def test_stricter_new_and_historical_retry_limits_apply(setup, configured, used, expected):
    root, model, requests = setup
    path = root / HISTORICAL_LEDGER
    data = [json.loads(line) for line in path.read_text().splitlines()]
    data[0]["limits"] = {"retry_attempts": 2}
    for index in range(used):
        data.append({"event": "attempt_reserved", "attempt_id": f"old-retry-{index}",
                     "attempt_key": "old-key", "attempt_number": index + 2, "reserved_usd": "0.001"})
    path.write_text("".join(json.dumps(e) + "\n" for e in data))
    save(root / "studies/evidence_responsiveness/preservation.json", {
        "historical_ledger": {"path": HISTORICAL_LEDGER,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}})
    save(root / "studies/evidence_responsiveness/config.json", {"transport_retry_limit": configured})
    assert cumulative_preflight(requests, [model], root)["remaining_retry_attempts"] == expected

    def failure(*_args):
        raise TransportFailure("timeout", retryable=True)

    result = run_one(setup, transport=failure)
    assert result["additional_retry_attempts"] == expected
    assert result["attempts"] == 1 + expected


def test_nontransport_and_secret_exception_are_not_retried(setup):
    root, model, requests = setup

    def failure(*_args):
        raise RuntimeError("unit-test-only-secret")

    result = run_one(setup, transport=failure)
    assert result["attempts"] == 1
    assert ledger(root)[-1]["error"] == "unexpected_adapter_error"
    assert "unit-test-only-secret" not in (root / CALL_DIRECTORY / "attempts.jsonl").read_text()
    assert run_requests(requests[:1], [model], root, transport=response)["attempts"] == 1


def test_interrupted_attempt_stays_reserved_without_automatic_retry(setup):
    root, model, requests = setup
    run_one(setup)
    data = ledger(root)
    assert data[-1]["event"] == "attempt_completed"
    (root / CALL_DIRECTORY / "attempts.jsonl").write_text("".join(json.dumps(e) + "\n" for e in data[:-1]))
    result = run_requests(requests[:1], [model], root, transport=response)
    assert result["attempts"] == 1 and result["completed_calls"] == 0
    assert "Unsettled" in result["blockers"][0]


def test_provider_bound_violation_persists_across_resume(setup):
    root, model, requests = setup
    result = run_one(setup, transport=lambda *_: {
        "usage": {"prompt_tokens": 3, "completion_tokens": 101, "cost": "0.1"}})
    assert result["status"] == "blocked"
    with pytest.raises(ExecutionBlocked, match="halted this follow-up"):
        run_requests(requests[1:2], [model], root, transport=response)
    assert sum(e["event"] == "attempt_reserved" for e in ledger(root)) == 1


def test_two_model_design_has_84_unique_requests(setup):
    root, first, requests = setup
    second = {**first, "model_id": "second-test-only-model", "family": "second-test-family"}
    models = [first, second]
    save(root / "studies/investigator_utility/openrouter_v1/config.json", {"models": models})
    all_requests = requests + [{**r, "attempt_key": "second-" + r["attempt_key"],
                                "model_id": second["model_id"]} for r in requests]
    result = cumulative_preflight(all_requests, models, root)
    assert result["request_count"] == 84
    assert result["development_requests"] == 12 and result["evaluation_requests"] == 72
