"""Bounded, serial, stateless execution; raw artifacts belong in an ignored directory.

Model metadata is deliberately supplied by the frozen study, never guessed here.
The configured byte/framing token bound and API output cap must have been checked
against the provider contract. Usage omitted by a provider is not an actual cost:
its full reservation continues to consume the budget. The injectable transport is
for unit tests; it must not be used to manufacture study observations.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

MILLION = Decimal(1_000_000)
PROVIDERS = {
    "openai": ("https://api.openai.com/v1/chat/completions", "openai.com"),
    "anthropic": ("https://api.anthropic.com/v1/messages", "anthropic.com"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "openrouter.ai"),
}
DOCUMENTATION_HOSTS = {
    "openai": {"openai.com", "platform.openai.com", "developers.openai.com"},
    "anthropic": {"anthropic.com", "docs.anthropic.com", "platform.claude.com"},
    "openrouter": {"openrouter.ai", "developers.openai.com", "platform.claude.com"},
}
REQUIRED_MODEL_FIELDS = {
    "provider", "model_id", "family", "endpoint", "api_key_env", "context_tokens",
    "max_output_tokens", "input_usd_per_million", "output_usd_per_million",
    "pricing_source", "pricing_verified_at", "pricing_evidence_sha256",
    "limits_source", "limits_evidence_sha256", "authorized", "verified_limits",
    "input_token_bound", "decoding", "reasoning",
}


class ExecutionBlocked(ValueError):
    """A preflight/budget condition prevents issuing another request."""


class TransportFailure(Exception):
    """Only this explicit transport classification permits another attempt."""

    def __init__(self, code: str, *, retryable: bool = False):
        # Callers must use a short code, not a raw exception containing headers.
        self.code = code if re.fullmatch(r"[a-zA-Z0-9_:-]{1,80}", code) else "transport_error"
        self.retryable = retryable
        super().__init__(self.code)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _money(value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ExecutionBlocked("invalid monetary amount") from None
    if not number.is_finite() or number < 0:
        raise ExecutionBlocked("monetary amounts must be finite and nonnegative")
    return number


def _integer(value: Any, field: str) -> int:
    if type(value) is not int or value < 1:
        raise ExecutionBlocked(f"{field} must be a positive integer")
    return value


def _official_url(value: str, hosts: set[str]) -> bool:
    try:
        parsed = urlparse(value)
        return (parsed.scheme == "https" and parsed.hostname in hosts
                and parsed.username is None and parsed.password is None
                and parsed.port in {None, 443})
    except (TypeError, ValueError):
        return False


def _validate_model(model: dict) -> None:
    missing = REQUIRED_MODEL_FIELDS - model.keys()
    if missing:
        raise ExecutionBlocked("missing frozen model metadata: " + ", ".join(sorted(missing)))
    provider = model["provider"]
    if provider not in PROVIDERS or model["endpoint"] != PROVIDERS[provider][0]:
        raise ExecutionBlocked("only the explicit official stateless API endpoints are supported")
    if model["authorized"] is not True or model["verified_limits"] is not True:
        raise ExecutionBlocked("authorized access and verified enforceable limits are required")
    for field in ("model_id", "family"):
        if not isinstance(model[field], str) or not model[field].strip():
            raise ExecutionBlocked(f"{field} must be frozen and nonempty")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+", model["api_key_env"]):
        raise ExecutionBlocked("invalid credential environment-variable name")
    _integer(model["context_tokens"], "context_tokens")
    _integer(model["max_output_tokens"], "max_output_tokens")
    _money(model["input_usd_per_million"])
    _money(model["output_usd_per_million"])
    for kind in ("pricing", "limits"):
        if not _official_url(model[kind + "_source"], DOCUMENTATION_HOSTS[provider]):
            raise ExecutionBlocked(f"{kind} must cite official provider documentation")
        if not re.fullmatch(r"[0-9a-f]{64}", model[kind + "_evidence_sha256"]):
            raise ExecutionBlocked(f"{kind} needs a pinned verification artifact")
    try:
        verified = datetime.fromisoformat(model["pricing_verified_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ExecutionBlocked("pricing verification requires an ISO timestamp") from None
    if verified.tzinfo is None:
        raise ExecutionBlocked("pricing verification timestamp needs a timezone")
    if model["input_token_bound"] != "utf8_bytes_plus_4096":
        raise ExecutionBlocked("unsupported input-token upper-bound contract")
    # A deliberately narrow adapter rejects unsupported parameters instead of
    # silently dropping them. A provider's output cap must include reasoning.
    if model["decoding"] != {}:
        raise ExecutionBlocked("this adapter supports provider-default decoding only")
    allowed_reasoning = {"none", "included_in_output_cap"}
    if model["reasoning"] not in allowed_reasoning:
        raise ExecutionBlocked("unbounded or unsupported reasoning settings")
    if provider == "openrouter":
        routing = model.get("provider_routing")
        if (not isinstance(routing, dict) or set(routing) != {
            "only", "allow_fallbacks", "require_parameters", "max_price"
        } or not isinstance(routing["only"], list) or len(routing["only"]) != 1
                or not isinstance(routing["only"][0], str) or not routing["only"][0].strip()
                or routing["allow_fallbacks"] is not False
                or routing["require_parameters"] is not True):
            raise ExecutionBlocked("OpenRouter requires one frozen route and enforced parameters")
        prices = routing["max_price"]
        if not isinstance(prices, dict) or set(prices) != {"prompt", "completion"}:
            raise ExecutionBlocked("OpenRouter requires explicit input/output routing price caps")
        for key, field in (("prompt", "input_usd_per_million"),
                           ("completion", "output_usd_per_million")):
            if type(prices[key]) not in {int, float} or _money(prices[key]) != _money(model[field]):
                raise ExecutionBlocked("routing price caps must match frozen per-million rates")
        # Additional request/image/search fees cannot be inferred from token prices.
        # The selected text-only route must have a verified zero per-request charge.
        if "request_usd" not in model or _money(model["request_usd"]) != 0:
            raise ExecutionBlocked("OpenRouter requires a verified zero per-request charge")


def inspect_access(models: list[dict]) -> dict:
    """Return credential presence and blockers, never environment-variable values."""
    blockers: list[str] = []
    presence: dict[str, bool] = {}
    if not models:
        blockers.append("No frozen authorized models with verified official pricing and limits.")
    if len(models) > 2:
        blockers.append("At most two frozen investigator models are supported.")
    for index, model in enumerate(models):
        try:
            _validate_model(model)
        except ExecutionBlocked as exc:
            blockers.append(f"Model {index}: {exc}")
            continue
        env = model["api_key_env"]
        presence[env] = bool(os.environ.get(env))
        if not presence[env]:
            blockers.append(f"Missing authorized credential environment variable: {env}.")
    if len({m.get("model_id") for m in models}) != len(models):
        blockers.append("Frozen model identifiers must be unique.")
    if len({m.get("family") for m in models}) != len(models):
        blockers.append("Two-model evaluation requires different declared model families.")
    return {"credential_presence": presence, "blockers": blockers}


def request_payload(request: dict, model: dict) -> dict:
    """Build the entire tool-free provider body from the public request only."""
    _validate_model(model)
    if not isinstance(request.get("system"), str) or not isinstance(request.get("user"), str):
        raise ExecutionBlocked("system and user prompts must be text")
    if model["provider"] == "openrouter":
        return {
            "model": model["model_id"],
            "messages": [
                {"role": "system", "content": request["system"]},
                {"role": "user", "content": request["user"]},
            ],
            "max_tokens": model["max_output_tokens"], "stream": False,
            "provider": json.loads(_canonical(model["provider_routing"])),
        }
    if model["provider"] == "openai":
        return {
            "model": model["model_id"],
            "messages": [
                {"role": "system", "content": request["system"]},
                {"role": "user", "content": request["user"]},
            ],
            "max_completion_tokens": model["max_output_tokens"],
            "stream": False,
        }
    return {
        "model": model["model_id"], "system": request["system"],
        "messages": [{"role": "user", "content": request["user"]}],
        "max_tokens": model["max_output_tokens"], "stream": False,
    }


def request_bound(payload: dict, model: dict) -> tuple[int, Decimal]:
    """UTF-8 bytes plus a verified 4096-token allowance for provider framing."""
    input_bound = len(_canonical(payload).encode("utf-8")) + 4096
    output_bound = model["max_output_tokens"]
    if input_bound + output_bound > model["context_tokens"]:
        raise ExecutionBlocked("request exceeds the frozen context bound; no truncation performed")
    cost = (Decimal(input_bound) * _money(model["input_usd_per_million"])
            + Decimal(output_bound) * _money(model["output_usd_per_million"])) / MILLION
    return input_bound, cost


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An endpoint redirect must never forward a credential to another host.
        return None


def api_transport(model: dict, payload: dict, api_key: str) -> dict:
    """One potentially billable attempt, without SDK retries or tool support."""
    _validate_model(model)  # Credential destinations are checked at the network boundary too.
    headers = {"Content-Type": "application/json"}
    if model["provider"] in {"openai", "openrouter"}:
        headers["Authorization"] = "Bearer " + api_key
    else:
        headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    request = urllib.request.Request(
        model["endpoint"], _canonical(payload).encode(), headers, method="POST"
    )
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=120) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise TransportFailure(
            f"http_{exc.code}", retryable=exc.code in {408, 429, 500, 502, 503, 504}
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TransportFailure("connection_failure", retryable=True) from None
    # A completed HTTP response is retained even if its envelope is invalid.
    # It is never classified as a retryable transport failure.
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return {"unparseable_http_body": body.decode("utf-8", errors="replace")}
    return value if isinstance(value, dict) else {"invalid_http_envelope": value}


def _usage(response: dict, model: dict) -> tuple[dict | None, Decimal | None]:
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None, None
    keys = ("prompt_tokens", "completion_tokens") if model["provider"] in {"openai", "openrouter"} else (
        "input_tokens", "output_tokens"
    )
    if any(type(usage.get(key)) is not int or usage[key] < 0 for key in keys):
        return None, None
    # The runner never requests caching; cached input is conservatively charged
    # at the regular rate. Reported cost is thus a priced-usage estimate, not an invoice.
    inputs, outputs = usage[keys[0]], usage[keys[1]]
    cost = (Decimal(inputs) * _money(model["input_usd_per_million"])
            + Decimal(outputs) * _money(model["output_usd_per_million"])) / MILLION
    normalized = {"input_tokens": inputs, "output_tokens": outputs}
    if model["provider"] == "openrouter" and usage.get("cost") is not None:
        try:
            # Only provider-reported generation charges are actual costs here;
            # token-derived costs remain a distinct conservative priced estimate.
            if isinstance(usage["cost"], bool):
                raise ExecutionBlocked("invalid cost")
            actual = _money(usage["cost"])
        except ExecutionBlocked:
            pass  # Invalid cost metadata must not lose a completed response.
        else:
            normalized["provider_reported_actual_cost_usd"] = str(actual)
    return normalized, cost


def _completion(response: dict, provider: str) -> str | None:
    try:
        if provider in {"openai", "openrouter"}:
            content = response["choices"][0]["message"]["content"]
            return content if isinstance(content, str) else None
        parts = response["content"]
        if not isinstance(parts, list):
            return None
        return "".join(p["text"] for p in parts if p.get("type") == "text")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def _append(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical({**event, "timestamp_utc": _now()}) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _save_once(path: Path, value: dict) -> None:
    encoded = (_canonical(value) + "\n").encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ExecutionBlocked("refusing to overwrite an existing request/response artifact")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_text().splitlines()]
    except ValueError:
        raise ExecutionBlocked("ledger is incomplete/corrupt; manual accounting is required") from None


def _account(events: list[dict]) -> dict:
    reservations = {e["attempt_id"]: e for e in events if e["event"] == "attempt_reserved"}
    settled = {e["attempt_id"]: e for e in events if e["event"] in {
        "attempt_completed", "attempt_failed"
    }}
    charged = sum((_money(settled.get(a, {}).get("charged_usd", r["reserved_usd"]))
                   for a, r in reservations.items()), Decimal(0))
    known = sum((_money(e["usage_cost_usd"]) for e in settled.values()
                 if e.get("usage_cost_usd") is not None), Decimal(0))
    unknown = sum(1 for a in reservations if settled.get(a, {}).get("usage_cost_usd") is None)
    actual_costs = [settled.get(a, {}).get("provider_reported_actual_cost_usd")
                    for a in reservations]
    known_actual = sum((_money(cost) for cost in actual_costs if cost is not None), Decimal(0))
    unknown_actual = sum(cost is None for cost in actual_costs)
    return {"attempts": len(reservations), "additional_retry_attempts": sum(
        e["attempt_number"] > 1 for e in reservations.values()
    ), "completed_calls": sum(e["event"] == "attempt_completed" for e in settled.values()),
        "development_completed": sum(e["event"] == "attempt_completed" and e["split"] == "development"
                                     for e in settled.values()),
        "evaluation_completed": sum(e["event"] == "attempt_completed" and e["split"] == "evaluation"
                                    for e in settled.values()),
        "charged_or_reserved_usd": str(charged), "known_usage_cost_usd": str(known),
        "unknown_cost_attempts": unknown,
        "provider_reported_actual_cost_usd": str(known_actual),
        "unknown_actual_cost_attempts": unknown_actual,
        "cost_basis": ("provider-reported charges when available; otherwise regular-rate usage "
                       "estimates or unreleased reservations; not an invoice"),
        "actual_total_cost_usd": str(known_actual) if not unknown_actual else None}


def schedule_preflight(
    requests: list[dict], models: list[dict], limits: dict | None = None,
    *, existing_events: list[dict] | None = None,
) -> dict:
    """Bound the full 4-development/24-evaluation schedule without calls or writes.

    Existing charges/reservations are retained. Only completed first responses
    release their future reservation; failed or unsettled attempts still consume
    their recorded cost. Each remaining retry is budgeted at the largest request
    bound. Metadata verification is a prerequisite, not something inferred here.
    """
    if not 1 <= len(models) <= 2:
        raise ExecutionBlocked("full schedule requires one or two frozen models")
    for model in models:
        _validate_model(model)
    if (len({model["model_id"] for model in models}) != len(models)
            or len({model["family"] for model in models}) != len(models)):
        raise ExecutionBlocked("frozen models must have distinct identifiers and families")
    supplied = limits or {}
    if set(supplied) - {"budget_usd", "development_calls", "evaluation_calls", "retry_attempts"}:
        raise ExecutionBlocked("unknown execution limit")
    cap = min(_money(supplied.get("budget_usd", "25")), Decimal(25))
    retry_limit = supplied.get("retry_attempts", 12)
    if type(retry_limit) is not int or not 0 <= retry_limit <= 12:
        raise ExecutionBlocked("retry_attempts must be an integer between zero and twelve")
    registry = {model["model_id"]: model for model in models}
    entries = []
    for request in requests:
        if set(request) != {"attempt_key", "case_id", "arm", "model_id", "split", "system", "user"}:
            raise ExecutionBlocked("request contains missing fields or non-public/unsupported fields")
        if any(not isinstance(value, str) or not value for value in request.values()):
            raise ExecutionBlocked("all request fields must be nonempty strings")
        if (request["arm"] not in {"A", "B", "C"}
                or request["split"] not in {"development", "evaluation"}
                or request["model_id"] not in registry):
            raise ExecutionBlocked("invalid arm, split, or unfrozen model")
        model = registry[request["model_id"]]
        payload = request_payload(request, model)
        tokens, reserve = request_bound(payload, model)
        entries.append({"attempt_key": request["attempt_key"], "input_token_bound": tokens,
                        "reserved_usd": str(reserve), "split": request["split"],
                        "model_id": request["model_id"], "case_id": request["case_id"],
                        "arm": request["arm"]})
    if len({r["attempt_key"] for r in entries}) != len(entries):
        raise ExecutionBlocked("duplicate request keys in full schedule")
    units = [(r["case_id"], r["model_id"], r["arm"]) for r in entries]
    if len(set(units)) != len(units):
        raise ExecutionBlocked("only one frozen request is permitted per case/model/arm")
    split_cases = {split: {r["case_id"] for r in entries if r["split"] == split}
                   for split in ("development", "evaluation")}
    if split_cases["development"] & split_cases["evaluation"]:
        raise ExecutionBlocked("development and evaluation cases must be disjoint")
    for split, cases, default_cap in (("development", 4, 24),
                                      ("evaluation", 24, 72 * len(models))):
        count = sum(r["split"] == split for r in entries)
        request_cap = min(_integer(supplied.get(split + "_calls", default_cap),
                                   split + "_calls"), default_cap)
        if len(split_cases[split]) != cases or count != cases * 3 * len(models):
            raise ExecutionBlocked("full schedule must contain all cases, models, and three arms")
        if count > request_cap:
            raise ExecutionBlocked(f"{split} request limit exceeded")
    events = existing_events or []
    if any(event["event"] == "execution_halted" for event in events):
        raise ExecutionBlocked("prior execution was halted; do not replace its ledger")
    if events and events[0].get("models_hash") != _hash(models):
        raise ExecutionBlocked("frozen models changed; preserve existing study costs")
    prior_requests = {event["attempt_key"]: event for event in events if event["event"] == "request"}
    if set(prior_requests) - {request["attempt_key"] for request in requests}:
        raise ExecutionBlocked("existing ledger contains requests outside the full schedule")
    for request in requests:
        prior = prior_requests.get(request["attempt_key"])
        if prior and prior["digest"] != _hash({
            "request": request, "payload": request_payload(request, registry[request["model_id"]])
        }):
            raise ExecutionBlocked("request payload or identity changed; refusing to resume")
    accounted = _account(events)
    remaining_retries = retry_limit - accounted["additional_retry_attempts"]
    if remaining_retries < 0:
        raise ExecutionBlocked("recorded retries already exceed the frozen retry limit")
    completed = {event["attempt_key"] for event in events if event["event"] == "attempt_completed"}
    remaining = sum((_money(entry["reserved_usd"]) for entry in entries
                     if entry["attempt_key"] not in completed), Decimal(0))
    maximum = max((_money(entry["reserved_usd"]) for entry in entries), default=Decimal(0))
    retries = maximum * remaining_retries
    prior_cost = _money(accounted["charged_or_reserved_usd"])
    total = prior_cost + remaining + retries
    if total > cap:
        raise ExecutionBlocked(f"full schedule including retry reserve requires USD {total}; cap is {cap}")
    return {"status": "ready", "requests": entries, "request_count": len(entries),
            "development_requests": 12 * len(models), "evaluation_requests": 72 * len(models),
            "prior_charged_or_reserved_usd": str(prior_cost),
            "remaining_request_reservations_usd": str(remaining),
            "maximum_attempt_reservation_usd": str(maximum),
            "remaining_retry_attempts": remaining_retries, "retry_reservation_usd": str(retries),
            "total_schedule_bound_usd": str(total), "budget_usd": str(cap)}


def run_requests(
    requests: list[dict], models: list[dict], output_dir: Path | str,
    limits: dict | None = None, *, transport: Callable | None = None,
) -> dict:
    """Run frozen public requests serially with a shared development/evaluation ledger.

    Request keys: attempt_key, case_id, arm (A/B/C), model_id, split
    (development/evaluation), system, user. Same-key or same-unit changes cannot
    resume. Empty models return an explicit blocker without creating fake results.
    All invocations for this study MUST share output_dir and identical limits/models.
    """
    access = inspect_access(models)
    if access["blockers"]:
        # Loss of credentials does not erase costs already incurred in this
        # study. A corrupt ledger blocks accounting rather than inventing zero.
        existing = _read(Path(output_dir) / "attempts.jsonl")
        return {"status": "blocked", **access, **_account(existing)}
    supplied = limits or {}
    if set(supplied) - {"budget_usd", "development_calls", "evaluation_calls", "retry_attempts"}:
        raise ExecutionBlocked("unknown execution limit")
    cap = min(_money(supplied.get("budget_usd", "25")), Decimal(25))
    caps = {
        "budget_usd": str(cap),
        "development_calls": min(_integer(supplied.get("development_calls", 24), "development_calls"), 24),
        "evaluation_calls": min(_integer(supplied.get("evaluation_calls", 72 * len(models)), "evaluation_calls"), 72 * len(models)),
        "retry_attempts": supplied.get("retry_attempts", 12),
    }
    if type(caps["retry_attempts"]) is not int or not 0 <= caps["retry_attempts"] <= 12:
        raise ExecutionBlocked("retry_attempts must be an integer between zero and twelve")
    registry = {m["model_id"]: m for m in models}
    prepared = []
    for request in requests:
        if set(request) != {"attempt_key", "case_id", "arm", "model_id", "split", "system", "user"}:
            raise ExecutionBlocked("request contains missing fields or non-public/unsupported fields")
        if any(not isinstance(request[field], str) or not request[field] for field in request):
            raise ExecutionBlocked("all request fields must be nonempty strings")
        if request["arm"] not in {"A", "B", "C"} or request["split"] not in {"development", "evaluation"}:
            raise ExecutionBlocked("invalid arm or split")
        if request["model_id"] not in registry:
            raise ExecutionBlocked("request uses an unfrozen model")
        model = registry[request["model_id"]]
        payload = request_payload(request, model)
        bound, reserve = request_bound(payload, model)
        prepared.append((request, payload, bound, reserve))
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    ledger = folder / "attempts.jsonl"
    blockers = []
    # Holding the advisory lock across network calls provides modest concurrency
    # of one and makes reservation checks atomic across invocations.
    with (folder / ".execution.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        events = _read(ledger)
        header = {"event": "study", "models_hash": _hash(models), "limits": caps}
        if events and any(events[0].get(k) != v for k, v in header.items()):
            raise ExecutionBlocked("frozen models/limits changed; refusing to resume")
        if not events:
            _append(ledger, header)
            events = _read(ledger)
        if any(e["event"] == "execution_halted" for e in events):
            return {"status": "blocked", "blockers": [
                "A prior provider bound violation halted this frozen execution."
            ], **_account(events)}
        registered = {e["attempt_key"]: e for e in events if e["event"] == "request"}
        proposed = dict(registered)
        for request, payload, bound, reserve in prepared:
            key = request["attempt_key"]
            entry = {"event": "request", "attempt_key": key, "digest": _hash({
                "request": request, "payload": payload
            }), **{field: request[field] for field in ("case_id", "model_id", "arm", "split")}}
            if key in proposed and any(proposed[key].get(k) != v for k, v in entry.items()):
                raise ExecutionBlocked("request payload or identity changed; refusing to resume")
            proposed[key] = entry
        units = [(e["case_id"], e["model_id"], e["arm"]) for e in proposed.values()]
        if len(units) != len(set(units)):
            raise ExecutionBlocked("only one frozen request is permitted per case/model/arm")
        if len({r[0]["attempt_key"] for r in prepared}) != len(prepared):
            raise ExecutionBlocked("duplicate request keys in this invocation")
        split_cases = {split: {e["case_id"] for e in proposed.values() if e["split"] == split}
                       for split in ("development", "evaluation")}
        if split_cases["development"] & split_cases["evaluation"]:
            raise ExecutionBlocked("development and evaluation cases must be disjoint")
        for split, max_cases in (("development", 4), ("evaluation", 24)):
            if len(split_cases[split]) > max_cases:
                raise ExecutionBlocked(f"{split} case limit exceeded")
            if sum(e["split"] == split for e in proposed.values()) > caps[split + "_calls"]:
                raise ExecutionBlocked(f"{split} request limit exceeded")
        for request, payload, bound, reserve in prepared:
            key = request["attempt_key"]
            safe_key = hashlib.sha256(key.encode()).hexdigest()
            _save_once(folder / "requests" / f"{safe_key}.json", {
                "public_request": request, "provider_payload": payload,
            })
            if key not in registered:
                _append(ledger, proposed[key])
        for request, payload, bound, reserve in prepared:
            key = request["attempt_key"]
            model = registry[request["model_id"]]
            while True:
                events = _read(ledger)
                previous = [e for e in events if e.get("attempt_key") == key and
                            e["event"] in {"attempt_reserved", "attempt_completed", "attempt_failed"}]
                if any(e["event"] == "attempt_completed" for e in previous):
                    break  # First completed answer is final, including invalid answers.
                if previous and previous[-1]["event"] == "attempt_reserved":
                    blockers.append(f"Unsettled prior attempt for {key}; no automatic retry.")
                    break
                if previous and not previous[-1].get("retryable", False):
                    break
                accounting = _account(events)
                number = sum(e["event"] == "attempt_reserved" for e in previous) + 1
                if number > 1 and accounting["additional_retry_attempts"] >= caps["retry_attempts"]:
                    blockers.append("Global transport retry limit exhausted.")
                    break
                if _money(accounting["charged_or_reserved_usd"]) + reserve > cap:
                    blockers.append("Remaining budget cannot cover the conservative attempt reservation.")
                    break
                api_key = os.environ.get(model["api_key_env"])
                if not api_key:
                    blockers.append("Authorized credential is no longer available.")
                    break
                attempt_id = hashlib.sha256(key.encode()).hexdigest() + f"-{number:02d}"
                common = {"attempt_id": attempt_id, "attempt_key": key,
                          "split": request["split"], "model_id": request["model_id"]}
                _append(ledger, {**common, "event": "attempt_reserved", "attempt_number": number,
                                 "input_token_bound": bound, "max_output_tokens": model["max_output_tokens"],
                                 "reserved_usd": str(reserve)})
                try:
                    response = (transport or api_transport)(model, payload, api_key)
                    if not isinstance(response, dict):
                        response = {"invalid_transport_envelope": response}
                except TransportFailure as exc:
                    _append(ledger, {**common, "event": "attempt_failed", "retryable": exc.retryable,
                                     "error": exc.code, "usage_cost_usd": None,
                                     "charged_usd": str(reserve)})
                    if not exc.retryable:
                        break
                    continue
                except Exception:
                    # Unexpected local/adapter errors may occur after the provider
                    # accepted the request. Preserve the reserve and never blindly retry.
                    _append(ledger, {**common, "event": "attempt_failed", "retryable": False,
                                     "error": "unexpected_adapter_error", "usage_cost_usd": None,
                                     "charged_usd": str(reserve)})
                    break
                usage, cost = _usage(response, model)
                actual_cost = (usage or {}).get("provider_reported_actual_cost_usd")
                charged = _money(actual_cost) if actual_cost is not None else (
                    cost if cost is not None else reserve
                )
                response_path = folder / "responses" / f"{attempt_id}.json"
                _save_once(response_path, {**common, "timestamp_utc": _now(), "raw_response": response,
                                          "completion_text": _completion(response, model["provider"])})
                _append(ledger, {**common, "event": "attempt_completed", "usage": usage,
                                 "usage_cost_usd": str(cost) if cost is not None else None,
                                 "provider_reported_actual_cost_usd": actual_cost,
                                 "charged_usd": str(charged),
                                 "response_file": str(response_path.relative_to(folder))})
                if charged > reserve or (usage and (usage["input_tokens"] > bound or
                                                   usage["output_tokens"] > model["max_output_tokens"])):
                    blockers.append("Provider usage violated the frozen token/cost-bound contract; execution stopped.")
                    _append(ledger, {"event": "execution_halted", "reason": "provider_bound_violation",
                                     "attempt_id": attempt_id})
                    return {"status": "blocked", "blockers": blockers, **_account(_read(ledger))}
                break
    final_events = _read(ledger)
    completed = {e["attempt_key"] for e in final_events if e["event"] == "attempt_completed"}
    missing = [r["attempt_key"] for r in requests if r["attempt_key"] not in completed]
    return {"status": "completed" if not missing else "incomplete", "blockers": sorted(set(blockers)),
            "missing_requests": missing, **_account(final_events)}
