"""Synthetic transport fixtures exercise routing and accounting, not model outcomes."""

import json
import urllib.error
from decimal import Decimal

import pytest

from tracebench.investigator_utility.execution import (
    ExecutionBlocked,
    TransportFailure,
    _NoRedirect,
    api_transport,
    inspect_access,
    request_bound,
    request_payload,
    run_requests,
    schedule_preflight,
)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("UNIT_TEST_ROUTER_KEY", "fixture-secret-do-not-log")
    return {
        "provider": "openrouter", "model_id": "fixture-family/not-a-real-model",
        "family": "fixture-family", "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "api_key_env": "UNIT_TEST_ROUTER_KEY", "context_tokens": 100_000,
        "max_output_tokens": 100, "input_usd_per_million": "1", "output_usd_per_million": "2",
        "pricing_source": "https://openrouter.ai/docs/fixture-pricing",
        "pricing_verified_at": "2026-10-03T00:00:00Z", "pricing_evidence_sha256": "a" * 64,
        "limits_source": "https://openrouter.ai/docs/fixture-limits",
        "limits_evidence_sha256": "b" * 64, "authorized": True, "verified_limits": True,
        "input_token_bound": "utf8_bytes_plus_4096", "decoding": {},
        "reasoning": "included_in_output_cap", "request_usd": "0",
        "provider_routing": {"only": ["test-provider"], "allow_fallbacks": False,
                             "require_parameters": True, "max_price": {"prompt": 1, "completion": 2}},
    }


def request(model, case="case-1", arm="A", split="evaluation"):
    return {"attempt_key": f"{split}:{case}:{arm}:{model['model_id']}", "case_id": case,
            "arm": arm, "model_id": model["model_id"], "split": split,
            "system": "Return the requested JSON using only supplied evidence.",
            "user": "Untrusted fixture evidence; no study data."}


def full_schedule(models):
    return [request(model, f"{split}-{index}", arm, split)
            for split, count in (("development", 4), ("evaluation", 24))
            for index in range(count) for model in models for arm in ("A", "B", "C")]


def response(*_args, cost=0.00004):
    return {"choices": [{"message": {"content": "malformed but final"},
                         "finish_reason": "length"}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 20,
                      "completion_tokens_details": {"reasoning_tokens": 15}, "cost": cost}}


def events(path):
    return [json.loads(line) for line in (path / "attempts.jsonl").read_text().splitlines()]


def test_router_payload_caps_total_output_and_preserves_default_reasoning(model):
    payload = request_payload(request(model), model)
    assert set(payload) == {"model", "messages", "max_tokens", "stream", "provider"}
    assert payload["max_tokens"] == model["max_output_tokens"]
    assert payload["provider"] == model["provider_routing"]
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    assert "thinking" not in payload and "reasoning" not in payload and "tools" not in payload
    bound, reserve = request_bound(payload, model)
    assert reserve == (Decimal(bound) + Decimal(200)) / Decimal(1_000_000)


@pytest.mark.parametrize("source", [
    "https://openrouter.ai.evil.invalid/pricing", "https://evil.openrouter.ai/pricing",
    "http://openrouter.ai/pricing", "https://openrouter.ai@evil.invalid/pricing",
    "https://user:password@openrouter.ai/pricing", "https://openrouter.ai:444/pricing",
    "https://platform.claude.com.evil.invalid/docs", "https://evil.claude.com/docs",
])
def test_router_documentation_hosts_are_narrow_and_parsed(model, source):
    model["pricing_source"] = source
    assert inspect_access([model])["blockers"]


@pytest.mark.parametrize("source", [
    "https://openrouter.ai/docs", "https://developers.openai.com/api/docs/models/example",
    "https://platform.claude.com/docs/en/models/example",
])
def test_verified_official_documentation_host_can_be_configured(model, source):
    model["limits_source"] = source
    assert not inspect_access([model])["blockers"]


@pytest.mark.parametrize("changes", [
    {"only": []}, {"only": ["one", "two"]}, {"allow_fallbacks": True},
    {"require_parameters": False}, {"sort": "price"},
    {"max_price": {"prompt": 2, "completion": 2}},
    {"max_price": {"prompt": "1", "completion": 2}},
    {"max_price": {"prompt": 1, "completion": 2, "request": 0}},
])
def test_unbounded_or_different_router_contract_is_rejected(model, changes):
    model["provider_routing"].update(changes)
    assert inspect_access([model])["blockers"]


def test_router_requires_verified_zero_request_charge(model):
    del model["request_usd"]
    assert inspect_access([model])["blockers"]
    model["request_usd"] = "0.01"
    assert inspect_access([model])["blockers"]


def test_api_network_boundary_rejects_unapproved_endpoint_before_reading_key(model, monkeypatch):
    model["endpoint"] = "https://unapproved.invalid/chat/completions"
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: pytest.fail("network opened"))
    with pytest.raises(ExecutionBlocked, match="endpoints"):
        api_transport(model, {}, "fixture-secret")


def test_router_bearer_and_redirect_blocking(model, monkeypatch):
    class Opener:
        def open(self, req, timeout):
            assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
            assert req.get_header("Authorization") == "Bearer fixture-secret"
            assert req.get_header("X-api-key") is None
            assert timeout == 120
            raise urllib.error.HTTPError(req.full_url, 302, "redirect", {}, None)

    def build(handler):
        assert handler is _NoRedirect
        assert handler().redirect_request(None, None, 302, "redirect", {},
                                        "https://unapproved.invalid/") is None
        return Opener()

    monkeypatch.setattr("urllib.request.build_opener", build)
    with pytest.raises(TransportFailure) as caught:
        api_transport(model, request_payload(request(model), model), "fixture-secret")
    assert caught.value.code == "http_302" and not caught.value.retryable


def test_router_reported_charge_separate_from_priced_usage_and_output_is_final(model, tmp_path):
    calls = []

    def invoke(*args):
        calls.append(args)
        return response()

    first = run_requests([request(model)], [model], tmp_path, transport=invoke)
    second = run_requests([request(model)], [model], tmp_path, transport=invoke)
    assert first == second and len(calls) == 1
    assert first["known_usage_cost_usd"] == "0.00007"
    assert first["charged_or_reserved_usd"] == "0.00004"
    assert first["actual_total_cost_usd"] == "0.00004"
    assert first["provider_reported_actual_cost_usd"] == "0.00004"
    assert first["unknown_actual_cost_attempts"] == 0
    saved = json.loads(next((tmp_path / "responses").glob("*.json")).read_text())
    assert saved["completion_text"] == "malformed but final"
    assert all("fixture-secret" not in file.read_text() for file in tmp_path.rglob("*.json*"))


@pytest.mark.parametrize("cost", [None, "NaN", -1, True, "invalid"])
def test_unknown_or_invalid_actual_charge_keeps_conservative_usage_estimate(model, tmp_path, cost):
    result = run_requests([request(model)], [model], tmp_path,
                          transport=lambda *_: response(cost=cost))
    assert result["completed_calls"] == 1
    assert result["actual_total_cost_usd"] is None
    assert result["unknown_actual_cost_attempts"] == 1
    assert result["charged_or_reserved_usd"] == result["known_usage_cost_usd"] == "0.00007"


def test_overbound_reported_charge_halts_persistently_before_next_request(model, tmp_path):
    result = run_requests([request(model), request(model, arm="B")], [model], tmp_path,
                          transport=lambda *_: response(cost="1"))
    assert result["attempts"] == 1 and result["status"] == "blocked"
    assert result["actual_total_cost_usd"] == result["charged_or_reserved_usd"] == "1"
    assert events(tmp_path)[-1]["event"] == "execution_halted"
    resumed = run_requests([request(model, arm="B")], [model], tmp_path, transport=response)
    assert resumed["attempts"] == 1 and resumed["status"] == "blocked"


def test_anthropic_default_thinking_is_bounded_and_extracted_without_leaking(model, tmp_path):
    model.update({"provider": "anthropic", "endpoint": "https://api.anthropic.com/v1/messages",
                  "pricing_source": "https://platform.claude.com/docs/en/about-claude/pricing",
                  "limits_source": "https://platform.claude.com/docs/en/build-with-claude/thinking"})
    payload = request_payload(request(model), model)
    assert payload["max_tokens"] == 100 and "thinking" not in payload
    result = run_requests([request(model)], [model], tmp_path, transport=lambda *_: {
        "content": [{"type": "thinking", "thinking": "private internal fixture"},
                    {"type": "text", "text": "answer"}],
        "usage": {"input_tokens": 10, "output_tokens": 90},
    })
    assert result["known_usage_cost_usd"] == "0.00019"
    saved = json.loads(next((tmp_path / "responses").glob("*.json")).read_text())
    assert saved["completion_text"] == "answer"


def test_full_schedule_includes_development_evaluation_and_global_retry_reserve(model, monkeypatch):
    monkeypatch.delenv("UNIT_TEST_ROUTER_KEY")  # Arithmetic does not require credentials.
    schedule = full_schedule([model])
    result = schedule_preflight(schedule, [model])
    reserves = [request_bound(request_payload(r, model), model)[1] for r in schedule]
    assert result["development_requests"] == 12 and result["evaluation_requests"] == 72
    assert Decimal(result["total_schedule_bound_usd"]) == sum(reserves) + 12 * max(reserves)
    assert len(result["requests"]) == 84


def test_full_schedule_two_models_and_budget_rejection_before_artifacts(model, tmp_path):
    second = {**model, "model_id": "different/model", "family": "different"}
    models = [model, second]
    schedule = full_schedule(models)
    result = schedule_preflight(schedule, models)
    assert result["development_requests"] == 24 and result["evaluation_requests"] == 144
    with pytest.raises(ExecutionBlocked, match="full schedule including retry reserve"):
        schedule_preflight(schedule, models, {"budget_usd": "0.01"})
    assert list(tmp_path.iterdir()) == []


def test_full_schedule_never_drops_cases_or_arms_to_fit(model):
    with pytest.raises(ExecutionBlocked, match="full schedule"):
        schedule_preflight(full_schedule([model])[:-1], [model])


def test_preflight_preserves_actual_past_cost_and_only_reserves_pending_requests(model, tmp_path):
    schedule = full_schedule([model])
    run_requests(schedule[:1], [model], tmp_path, transport=response)
    result = schedule_preflight(schedule, [model], existing_events=events(tmp_path))
    remaining = sum(request_bound(request_payload(r, model), model)[1] for r in schedule[1:])
    assert result["prior_charged_or_reserved_usd"] == "0.00004"
    assert Decimal(result["remaining_request_reservations_usd"]) == remaining
    assert Decimal(result["total_schedule_bound_usd"]) == (
        remaining + Decimal("0.00004") + Decimal(result["retry_reservation_usd"]))


def test_preflight_deducts_consumed_retries_and_keeps_failure_reservations(model, tmp_path):
    calls = []

    def invoke(*args):
        calls.append(args)
        if len(calls) == 1:
            raise TransportFailure("http_503", retryable=True)
        return response()

    schedule = full_schedule([model])
    run_requests(schedule[:1], [model], tmp_path, transport=invoke)
    result = schedule_preflight(schedule, [model], existing_events=events(tmp_path))
    reserve = request_bound(request_payload(schedule[0], model), model)[1]
    assert result["remaining_retry_attempts"] == 11
    assert Decimal(result["prior_charged_or_reserved_usd"]) == reserve + Decimal("0.00004")
    assert Decimal(result["retry_reservation_usd"]) == 11 * Decimal(
        result["maximum_attempt_reservation_usd"])
