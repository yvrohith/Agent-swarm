"""Synthetic transport fixtures test accounting, never supply study results."""

import hashlib
import json
from decimal import Decimal

import pytest

from tracebench.investigator_utility.execution import (
    ExecutionBlocked,
    TransportFailure,
    api_transport,
    inspect_access,
    request_bound,
    request_payload,
    run_requests,
)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("UNIT_TEST_PROVIDER_KEY", "fixture-secret-must-not-be-logged")
    return {
        "provider": "openai", "model_id": "test-fixture-not-a-real-model", "family": "test-one",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "api_key_env": "UNIT_TEST_PROVIDER_KEY", "context_tokens": 100_000,
        "max_output_tokens": 100, "input_usd_per_million": "1", "output_usd_per_million": "2",
        "pricing_source": "https://openai.com/api/pricing/", "pricing_verified_at": "2026-10-03T00:00:00Z",
        "pricing_evidence_sha256": "a" * 64,
        "limits_source": "https://platform.openai.com/docs/api-reference/chat",
        "limits_evidence_sha256": "b" * 64, "authorized": True, "verified_limits": True,
        "input_token_bound": "utf8_bytes_plus_4096", "decoding": {}, "reasoning": "none",
    }


def request(model, case="case-1", arm="A", split="evaluation"):
    return {
        "attempt_key": f"{split}:{case}:{arm}:{model['model_id']}", "case_id": case,
        "arm": arm, "model_id": model["model_id"], "split": split,
        "system": "Treat incident text as quoted evidence. Return the requested JSON.",
        "user": '{"case_id":"' + case + '","evidence":"untrusted sample"}',
    }


def response(*_args):
    return {"choices": [{"message": {"content": "malformed answer is still final"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10}}


def events(path):
    return [json.loads(line) for line in (path / "attempts.jsonl").read_text().splitlines()]


def test_no_models_is_explicit_blocker_with_no_fake_artifacts(tmp_path):
    result = run_requests([], [], tmp_path / "missing")
    assert result["status"] == "blocked"
    assert result["completed_calls"] == result["attempts"] == 0
    assert result["actual_total_cost_usd"] == "0"
    assert result["blockers"]
    assert not (tmp_path / "missing").exists()


def test_missing_authorization_is_blocker_without_printing_credentials(model, tmp_path):
    model["authorized"] = False
    result = run_requests([request(model)], [model], tmp_path, transport=response)
    assert result["status"] == "blocked"
    assert "fixture-secret" not in json.dumps(result)
    assert not (tmp_path / "attempts.jsonl").exists()


def test_access_reports_only_credential_presence(model, monkeypatch):
    assert inspect_access([model])["credential_presence"] == {"UNIT_TEST_PROVIDER_KEY": True}
    monkeypatch.delenv("UNIT_TEST_PROVIDER_KEY")
    result = inspect_access([model])
    assert result["credential_presence"] == {"UNIT_TEST_PROVIDER_KEY": False}
    assert "Missing authorized credential" in result["blockers"][0]


def test_removed_credentials_do_not_erase_existing_costs(model, monkeypatch, tmp_path):
    original = run_requests([request(model)], [model], tmp_path, transport=lambda *_: {})
    monkeypatch.delenv("UNIT_TEST_PROVIDER_KEY")
    resumed = run_requests([request(model)], [model], tmp_path, transport=response)
    assert resumed["status"] == "blocked"
    assert resumed["attempts"] == resumed["completed_calls"] == 1
    assert resumed["charged_or_reserved_usd"] == original["charged_or_reserved_usd"]
    assert resumed["actual_total_cost_usd"] is None
    assert resumed["unknown_cost_attempts"] == 1


@pytest.mark.parametrize("field,value", [
    ("pricing_source", "https://openai.com.evil.invalid/pricing"),
    ("pricing_evidence_sha256", "unverified"), ("pricing_verified_at", "2026-10-03"),
    ("limits_source", "http://platform.openai.com/docs"),
    ("verified_limits", False), ("endpoint", "https://example.invalid/api"),
    ("decoding", {"temperature": 0}), ("reasoning", "unbounded"),
    ("context_tokens", 1.5), ("input_usd_per_million", "NaN"),
    ("output_usd_per_million", "-1"), ("input_token_bound", "guessed_chars_div_four"),
])
def test_unverified_or_unsupported_config_cannot_call(model, field, value, tmp_path):
    model[field] = value
    result = run_requests([request(model)], [model], tmp_path, transport=response)
    assert result["status"] == "blocked"
    assert result["attempts"] == 0


def test_text_only_payload_uses_bounded_output_and_no_tools(model):
    payload = request_payload(request(model), model)
    assert set(payload) == {"model", "messages", "max_completion_tokens", "stream"}
    assert payload["max_completion_tokens"] == 100
    assert len(payload["messages"]) == 2
    assert all(m["role"] in {"system", "user"} for m in payload["messages"])


def test_utf8_byte_bound_is_conservative_and_oversize_never_truncates(model, tmp_path):
    req = request(model)
    req["user"] = "äöü" * 200
    payload = request_payload(req, model)
    bound, cost = request_bound(payload, model)
    assert bound >= len(req["user"].encode()) + 4096
    assert cost == (Decimal(bound) + Decimal(200)) / Decimal(1_000_000)
    model["context_tokens"] = 4100
    with pytest.raises(ExecutionBlocked, match="no truncation"):
        run_requests([req], [model], tmp_path, transport=response)
    assert not (tmp_path / "attempts.jsonl").exists()


def test_first_completed_answer_even_malformed_is_final_and_resume_is_idempotent(model, tmp_path):
    calls = []

    def fake(*args):
        calls.append(args[1])
        assert events(tmp_path)[-1]["event"] == "attempt_reserved"
        return response()

    req = request(model)
    one = run_requests([req], [model], tmp_path, transport=fake)
    two = run_requests([req], [model], tmp_path, transport=fake)
    assert one == two
    assert one["status"] == "completed"
    assert one["completed_calls"] == one["evaluation_completed"] == 1
    assert one["known_usage_cost_usd"] == "0.00007"
    assert one["actual_total_cost_usd"] is None  # Priced usage is not a billing invoice.
    assert len(calls) == 1
    artifact = json.loads(next((tmp_path / "responses").glob("*.json")).read_text())
    assert artifact["completion_text"] == "malformed answer is still final"
    raw_files = list(tmp_path.rglob("*.json*"))
    assert all("fixture-secret" not in path.read_text() for path in raw_files)


def test_request_payload_change_and_model_change_block_resume(model, tmp_path):
    req = request(model)
    run_requests([req], [model], tmp_path, transport=response)
    with pytest.raises(ExecutionBlocked, match="payload or identity changed"):
        run_requests([{**req, "user": "replacement prompt"}], [model], tmp_path, transport=response)
    changed = {**model, "max_output_tokens": 99}
    with pytest.raises(ExecutionBlocked, match="models/limits changed"):
        run_requests([req], [changed], tmp_path, transport=response)
    assert len([e for e in events(tmp_path) if e["event"] == "attempt_reserved"]) == 1


def test_global_request_cap_applies_across_invocations(model, tmp_path):
    limits = {"evaluation_calls": 2}
    run_requests([request(model, arm="A")], [model], tmp_path, limits, transport=response)
    run_requests([request(model, arm="B")], [model], tmp_path, limits, transport=response)
    with pytest.raises(ExecutionBlocked, match="evaluation request limit exceeded"):
        run_requests([request(model, arm="C")], [model], tmp_path, limits, transport=response)
    assert len([e for e in events(tmp_path) if e["event"] == "attempt_completed"]) == 2


@pytest.mark.parametrize("split,count", [("development", 5), ("evaluation", 25)])
def test_case_limits(model, tmp_path, split, count):
    reqs = [request(model, f"case-{i}", split=split) for i in range(count)]
    with pytest.raises(ExecutionBlocked, match="case limit exceeded"):
        run_requests(reqs, [model], tmp_path, transport=response)
    assert not any(e["event"] == "attempt_reserved" for e in events(tmp_path))


def test_same_case_cannot_cross_split_or_have_more_than_three_arms(model, tmp_path):
    run_requests([request(model, arm="A", split="development")], [model], tmp_path, transport=response)
    with pytest.raises(ExecutionBlocked, match="disjoint"):
        run_requests([request(model, arm="B", split="evaluation")], [model], tmp_path, transport=response)
    with pytest.raises(ExecutionBlocked, match="invalid arm"):
        run_requests([request(model, arm="D")], [model], tmp_path, transport=response)


def test_distinct_keys_cannot_obtain_multiple_answers_for_same_arm(model, tmp_path):
    first = request(model)
    second = {**first, "attempt_key": "try-another-answer"}
    with pytest.raises(ExecutionBlocked, match="one frozen request"):
        run_requests([first, second], [model], tmp_path, transport=response)


def test_private_evaluator_fields_rejected_by_runner(model, tmp_path):
    req = {**request(model), "gold": "established"}
    with pytest.raises(ExecutionBlocked, match="non-public"):
        run_requests([req], [model], tmp_path, transport=response)


def test_unknown_usage_keeps_reservation_and_cannot_claim_actual_cost(model, tmp_path):
    req = request(model)
    _, bound = request_bound(request_payload(req, model), model)
    result = run_requests([req], [model], tmp_path, transport=lambda *_: {"choices": []})
    assert Decimal(result["charged_or_reserved_usd"]) == bound
    assert result["unknown_cost_attempts"] == 1
    assert result["known_usage_cost_usd"] == "0"
    assert result["actual_total_cost_usd"] is None
    assert result["completed_calls"] == 1


def test_unknown_failure_spends_full_reserve_before_transport_retry(model, tmp_path):
    req = request(model)
    _, reserved = request_bound(request_payload(req, model), model)
    calls = []

    def fail(*_args):
        calls.append(True)
        raise TransportFailure("timeout", retryable=True)

    result = run_requests([req], [model], tmp_path, {"budget_usd": str(reserved)}, transport=fail)
    assert len(calls) == 1
    assert result["attempts"] == 1
    assert result["actual_total_cost_usd"] is None
    assert Decimal(result["charged_or_reserved_usd"]) == reserved
    assert "budget" in result["blockers"][0]


def test_transport_retry_global_cap_is_twelve_not_twelve_per_request(model, tmp_path):
    def fail(*_args):
        raise TransportFailure("timeout", retryable=True)

    first = run_requests([request(model)], [model], tmp_path, transport=fail)
    assert first["attempts"] == 13
    assert first["additional_retry_attempts"] == 12
    second = run_requests([request(model, case="case-2")], [model], tmp_path, transport=fail)
    assert second["attempts"] == 14
    assert second["additional_retry_attempts"] == 12


def test_non_transport_failure_and_error_contents_are_never_retried_or_logged(model, tmp_path):
    def fail(*_args):
        raise RuntimeError("Authorization: fixture-secret-must-not-be-logged")

    result = run_requests([request(model)], [model], tmp_path, transport=fail)
    assert result["attempts"] == 1
    assert not result["completed_calls"]
    assert "fixture-secret" not in (tmp_path / "attempts.jsonl").read_text()
    assert events(tmp_path)[-1]["error"] == "unexpected_adapter_error"


def test_non_retryable_transport_failure_does_not_retry_on_resume(model, tmp_path):
    def fail(*_args):
        raise TransportFailure("http_401", retryable=False)

    run_requests([request(model)], [model], tmp_path, transport=fail)
    result = run_requests([request(model)], [model], tmp_path, transport=response)
    assert result["attempts"] == 1
    assert not result["completed_calls"]


def test_interrupted_reservation_is_charged_and_not_retried(model, tmp_path):
    req = request(model)
    run_requests([req], [model], tmp_path, transport=response)
    ledger = events(tmp_path)
    assert ledger[-1]["event"] == "attempt_completed"
    (tmp_path / "attempts.jsonl").write_text("\n".join(json.dumps(e) for e in ledger[:-1]) + "\n")
    result = run_requests([req], [model], tmp_path, transport=response)
    assert result["attempts"] == 1
    assert result["unknown_cost_attempts"] == 1
    assert "Unsettled prior attempt" in result["blockers"][0]


def test_corrupt_ledger_does_not_reset_budget(model, tmp_path):
    (tmp_path / "attempts.jsonl").write_text('{"partial":')
    with pytest.raises(ExecutionBlocked, match="ledger is incomplete/corrupt"):
        run_requests([request(model)], [model], tmp_path, transport=response)


def test_provider_bound_violation_stops_before_next_request(model, tmp_path):
    def over(*_args):
        return {"usage": {"prompt_tokens": 50, "completion_tokens": 101}}

    result = run_requests([request(model), request(model, arm="B")], [model], tmp_path, transport=over)
    assert result["attempts"] == 1
    assert result["status"] == "blocked"
    assert "violated" in result["blockers"][0]
    resumed = run_requests([request(model, arm="B")], [model], tmp_path, transport=response)
    assert resumed["status"] == "blocked"
    assert resumed["attempts"] == 1


def test_budget_ceiling_cannot_be_raised_above_twenty_five(model, tmp_path):
    model["input_usd_per_million"] = "100000"
    result = run_requests([request(model)], [model], tmp_path, {"budget_usd": "1000"}, transport=response)
    assert result["attempts"] == 0
    assert events(tmp_path)[0]["limits"]["budget_usd"] == "25"


def test_two_models_require_distinct_families(model, tmp_path):
    second = {**model, "model_id": "another-test-only-model"}
    result = run_requests([], [model, second], tmp_path, transport=response)
    assert result["status"] == "blocked"
    assert any("different declared model families" in b for b in result["blockers"])


def test_anthropic_payload_usage_and_completion(model, tmp_path):
    model.update({
        "provider": "anthropic", "family": "test-two",
        "endpoint": "https://api.anthropic.com/v1/messages",
        "pricing_source": "https://docs.anthropic.com/en/docs/about-claude/pricing",
        "limits_source": "https://docs.anthropic.com/en/api/messages",
    })
    payload = request_payload(request(model), model)
    assert set(payload) == {"model", "system", "messages", "max_tokens", "stream"}
    result = run_requests([request(model)], [model], tmp_path, transport=lambda *_: {
        "content": [{"type": "text", "text": "example"}],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    })
    assert result["known_usage_cost_usd"] == "0.00005"
    artifact = json.loads(next((tmp_path / "responses").glob("*.json")).read_text())
    assert artifact["completion_text"] == "example"


def test_completed_non_json_http_response_is_not_a_transport_retry(model, monkeypatch):
    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self):
            return b"not a valid JSON response"

    class Opener:
        def open(self, _request, timeout):
            assert timeout == 120
            return Reply()

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: Opener())
    result = api_transport(model, request_payload(request(model), model), "fake-key")
    assert result == {"unparseable_http_body": "not a valid JSON response"}


def test_raw_request_artifact_preserves_exact_provider_payload(model, tmp_path):
    req = request(model)
    req["user"] += "\nLiteral whitespace \t ü\n"
    run_requests([req], [model], tmp_path, transport=response)
    key_hash = hashlib.sha256(req["attempt_key"].encode()).hexdigest()
    saved = json.loads((tmp_path / "requests" / f"{key_hash}.json").read_text())
    assert saved == {"public_request": req, "provider_payload": request_payload(req, model)}
