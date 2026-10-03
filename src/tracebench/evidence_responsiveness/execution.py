"""Small execution adapter with an immutable historical spending carryforward.

The completed utility implementation and ledger are read-only dependencies.
One fixed follow-up ledger, protected together with the historical lock, prevents
development, evaluation, or another process from resetting the cumulative cap.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
from decimal import Decimal
from pathlib import Path

from tracebench.investigator_utility.execution import (
    ExecutionBlocked,
    TransportFailure,
    _account,
    _append,
    _completion,
    _money,
    _now,
    _read,
    _save_once,
    _usage,
    _validate_model,
    api_transport,
    request_bound,
    request_payload,
)

from .common import digest, file_hash, read

HISTORICAL_LEDGER = "artifacts/investigator-utility/calls/attempts.jsonl"
CALL_DIRECTORY = "artifacts/evidence-responsiveness/calls"
PRESERVATION = "studies/evidence_responsiveness/preservation.json"
CONFIG = "studies/evidence_responsiveness/config.json"
REQUEST_FIELDS = {"attempt_key", "case_id", "model_id", "split", "system", "user"}


def _paths(root, ledger_dir):
    root = Path(root).resolve()
    folder = root / CALL_DIRECTORY
    if ledger_dir is not None and Path(ledger_dir).resolve() != folder.resolve():
        raise ExecutionBlocked("alternate ledger directories cannot reset cumulative spending")
    expected = {(root / HISTORICAL_LEDGER).resolve(), (folder / "attempts.jsonl").resolve()}
    if any(path.resolve() not in expected for path in (root / "artifacts").rglob("attempts.jsonl")):
        raise ExecutionBlocked("an unregistered study ledger exists; cumulative accounting is incomplete")
    return root, folder


def _history(root):
    preservation = read(root / PRESERVATION)
    pin = preservation.get("historical_ledger")
    if pin is None:
        pin = {"path": HISTORICAL_LEDGER,
               "sha256": preservation.get("historical_raw_sha256", {}).get(HISTORICAL_LEDGER)}
    if pin.get("path") != HISTORICAL_LEDGER or not pin.get("sha256"):
        raise ExecutionBlocked("mandatory historical ledger pin is missing")
    path = root / HISTORICAL_LEDGER
    if not path.exists() or file_hash(path) != pin["sha256"]:
        raise ExecutionBlocked("historical ledger changed; preserve it and reconcile cumulative costs")
    events = _read(path)
    if not events or events[0].get("event") != "study":
        raise ExecutionBlocked("historical study ledger is missing its accounting header")
    if any(e["event"] == "execution_halted" for e in events):
        raise ExecutionBlocked("historical execution halted; its bound violation is unresolved")
    return events, pin


def _models(root, models):
    if not 1 <= len(models) <= 2:
        raise ExecutionBlocked("one or two previously authorized model families are required")
    previous = read(root / "studies/investigator_utility/openrouter_v1/config.json")["models"]
    allowed = {m["model_id"] for m in previous}
    if len({m["model_id"] for m in models}) != len(models) or len({m["family"] for m in models}) != len(models):
        raise ExecutionBlocked("model identifiers and families must be distinct")
    for model in models:
        _validate_model(model)
        if (model["provider"] != "openrouter" or model["api_key_env"] != "OPENROUTER_KEY"
                or model["model_id"] not in allowed):
            raise ExecutionBlocked("reuse the authorized model aliases with OPENROUTER_KEY only")


def _prepare(requests, models, historical):
    registry = {m["model_id"]: m for m in models}
    old_keys = {e["attempt_key"] for e in historical if e["event"] == "request"}
    keys, units, entries = set(), set(), []
    for request in requests:
        if set(request) != REQUEST_FIELDS or any(not isinstance(v, str) or not v for v in request.values()):
            raise ExecutionBlocked("request must contain only the six public execution fields")
        if request["split"] not in {"development", "evaluation"} or request["model_id"] not in registry:
            raise ExecutionBlocked("invalid request split or unfrozen model")
        key = request["attempt_key"]
        unit = (request["case_id"], request["model_id"])
        if key in keys or key in old_keys or unit in units:
            raise ExecutionBlocked("request identity collides with this or the completed study")
        keys.add(key)
        units.add(unit)
        model = registry[request["model_id"]]
        payload = request_payload(request, model)
        bound, reserve = request_bound(payload, model)
        entries.append({"request": request, "payload": payload, "input_token_bound": bound,
                        "reserved_usd": str(reserve), "request_sha256": digest(request)})
    split_cases = {split: {e["request"]["case_id"] for e in entries
                           if e["request"]["split"] == split}
                   for split in ("development", "evaluation")}
    if split_cases["development"] & split_cases["evaluation"]:
        raise ExecutionBlocked("development and evaluation variants must be disjoint")
    if len(split_cases["evaluation"]) != 36 or len(split_cases["development"]) > 6:
        raise ExecutionBlocked("full schedule requires 36 evaluation variants and at most six development variants")
    for model in models:
        for split, cases in split_cases.items():
            actual = {e["request"]["case_id"] for e in entries
                      if e["request"]["model_id"] == model["model_id"]
                      and e["request"]["split"] == split}
            if actual != cases:
                raise ExecutionBlocked("all frozen variants must be scheduled for each model")
    return entries


def _cap(root):
    path = root / CONFIG
    config = read(path) if path.exists() else {}
    return min(Decimal(25), _money(config.get("cumulative_budget_usd", "25")),
               _money(config.get("budget_usd", "25")))


def _retry_cap(root, historical):
    path = root / CONFIG
    configured = read(path).get("transport_retry_limit", 4) if path.exists() else 4
    inherited = historical[0].get("limits", {}).get("retry_attempts", 12)
    if (type(configured) is not int or configured < 0
            or type(inherited) is not int or inherited < 0):
        raise ExecutionBlocked("transport retry limits must be nonnegative integers")
    return min(4, configured, inherited - _account(historical)["additional_retry_attempts"])


def _held_unknown(events):
    reserved = {e["attempt_id"]: e for e in events if e["event"] == "attempt_reserved"}
    settled = {e["attempt_id"]: e for e in events if e["event"] in {
        "attempt_completed", "attempt_failed"}}
    return sum((_money(settled.get(key, {}).get("charged_usd", entry["reserved_usd"]))
                for key, entry in reserved.items()
                if settled.get(key, {}).get("provider_reported_actual_cost_usd") is None), Decimal(0))


def _summary(historical, events):
    prior, current = _account(historical), _account(events)
    known_actual = (_money(prior["provider_reported_actual_cost_usd"])
                    + _money(current["provider_reported_actual_cost_usd"]))
    unknown = prior["unknown_actual_cost_attempts"] + current["unknown_actual_cost_attempts"]
    return {**current, "historical_charged_or_reserved_usd": prior["charged_or_reserved_usd"],
            "cumulative_charged_or_reserved_usd": str(
                _money(prior["charged_or_reserved_usd"]) + _money(current["charged_or_reserved_usd"])),
            "cumulative_known_actual_usd": str(known_actual),
            "cumulative_actual_total_cost_usd": None if unknown else str(known_actual),
            "cumulative_unresolved_reservation_usd": str(_held_unknown(historical) + _held_unknown(events)),
            "cumulative_unknown_actual_attempts": unknown}


def cumulative_preflight(requests, models, root, ledger_dir=None):
    """Read-only bound for the entire frozen schedule plus allowed retries."""
    root, folder = _paths(root, ledger_dir)
    historical, pin = _history(root)
    _models(root, models)
    entries = _prepare(requests, models, historical)
    events = _read(folder / "attempts.jsonl")
    current = _account(events)
    retry_cap = _retry_cap(root, historical)
    if retry_cap < 0:
        raise ExecutionBlocked("historical retries already exceed the cumulative allowance")
    cap = _cap(root)
    header = {"event": "study", "models_hash": digest(models), "schedule_hash": digest(requests),
              "historical_ledger": pin, "cumulative_budget_usd": str(cap),
              "development_calls": 6 * len(models), "evaluation_calls": 36 * len(models),
              "retry_attempts": retry_cap}
    if events and any(events[0].get(k) != v for k, v in header.items()):
        raise ExecutionBlocked("frozen schedule, model metadata, or spending contract changed")
    if any(e["event"] == "execution_halted" for e in events):
        raise ExecutionBlocked("a prior token/cost bound violation halted this follow-up")
    saved_schedule = folder / "schedule.json"
    if saved_schedule.exists() and read(saved_schedule) != {"requests": requests, "models_hash": digest(models)}:
        raise ExecutionBlocked("registered public requests changed")
    registered = {e["attempt_key"]: e for e in events if e["event"] == "request"}
    if set(registered) - {e["request"]["attempt_key"] for e in entries}:
        raise ExecutionBlocked("ledger contains a request outside the frozen schedule")
    for entry in entries:
        old = registered.get(entry["request"]["attempt_key"])
        if old and old["request_sha256"] != entry["request_sha256"]:
            raise ExecutionBlocked("registered request content changed")
    completed = {e["attempt_key"] for e in events if e["event"] == "attempt_completed"}
    attempted = {e["attempt_key"] for e in events if e["event"] == "attempt_reserved"}
    remaining = sum((_money(e["reserved_usd"]) for e in entries
                     if e["request"]["attempt_key"] not in attempted), Decimal(0))
    maximum = max((_money(e["reserved_usd"]) for e in entries
                   if e["request"]["attempt_key"] not in completed), default=Decimal(0))
    remaining_retries = retry_cap - current["additional_retry_attempts"]
    if remaining_retries < 0:
        raise ExecutionBlocked("follow-up transport retry allowance exhausted")
    retries = maximum * remaining_retries
    accounted = _summary(historical, events)
    total = _money(accounted["cumulative_charged_or_reserved_usd"]) + remaining + retries
    if total > cap:
        raise ExecutionBlocked(f"complete cumulative schedule requires USD {total}; cap is {cap}")
    return {"status": "ready", "study_header": header, "request_count": len(entries),
            "development_requests": sum(e["request"]["split"] == "development" for e in entries),
            "evaluation_requests": sum(e["request"]["split"] == "evaluation" for e in entries),
            "remaining_primary_reservations_usd": str(remaining),
            "maximum_attempt_reservation_usd": str(maximum),
            "remaining_retry_attempts": remaining_retries, "retry_reservation_usd": str(retries),
            "total_cumulative_bound_usd": str(total), "budget_usd": str(cap), **accounted}


def run_requests(requests, models, root, ledger_dir=None, *, all_requests=None, transport=None):
    """Register the full schedule once, then execute only the supplied subset.

    The initial development call requires all_requests. Later invocations load
    that exact schedule; they cannot add or replace requests. Transport injection
    exists only for unit tests and must never fabricate experimental responses.
    """
    root, folder = _paths(root, ledger_dir)
    _history(root)
    historical_lock = (root / HISTORICAL_LEDGER).parent / ".execution.lock"
    if not historical_lock.exists():
        raise ExecutionBlocked("historical execution lock is unavailable")
    folder.mkdir(parents=True, exist_ok=True)
    with historical_lock.open("r") as old_lock, (folder / ".execution.lock").open("a") as new_lock:
        fcntl.flock(old_lock, fcntl.LOCK_EX)
        fcntl.flock(new_lock, fcntl.LOCK_EX)
        schedule_path = folder / "schedule.json"
        if all_requests is None:
            if not schedule_path.exists():
                raise ExecutionBlocked("the entire development/evaluation schedule is required before calls")
            all_requests = read(schedule_path)["requests"]
        preflight = cumulative_preflight(all_requests, models, root, ledger_dir)
        historical, _ = _history(root)
        entries = _prepare(all_requests, models, historical)
        by_key = {entry["request"]["attempt_key"]: entry for entry in entries}
        if len({r.get("attempt_key") for r in requests}) != len(requests):
            raise ExecutionBlocked("duplicate subset request keys")
        for request in requests:
            if request.get("attempt_key") not in by_key or request != by_key[request["attempt_key"]]["request"]:
                raise ExecutionBlocked("execution subset is not an exact part of the frozen schedule")
        ledger = folder / "attempts.jsonl"
        if not _read(ledger):
            _append(ledger, preflight["study_header"])
        _save_once(schedule_path, {"requests": all_requests, "models_hash": digest(models)})
        registered = {e["attempt_key"] for e in _read(ledger) if e["event"] == "request"}
        for entry in entries:
            request = entry["request"]
            key = request["attempt_key"]
            safe = hashlib.sha256(key.encode()).hexdigest()
            _save_once(folder / "requests" / f"{safe}.json", {
                "public_request": request, "provider_payload": entry["payload"]})
            if key not in registered:
                _append(ledger, {"event": "request", **{k: request[k] for k in (
                    "attempt_key", "case_id", "model_id", "split")},
                    "request_sha256": entry["request_sha256"]})
        registry = {m["model_id"]: m for m in models}
        blockers = []
        for request in requests:
            key, model = request["attempt_key"], registry[request["model_id"]]
            entry = by_key[key]
            reserve = _money(entry["reserved_usd"])
            while True:
                historical, _ = _history(root)
                events = _read(ledger)
                previous = [e for e in events if e.get("attempt_key") == key and e["event"] in {
                    "attempt_reserved", "attempt_completed", "attempt_failed"}]
                if any(e["event"] == "attempt_completed" for e in previous):
                    break
                if previous and previous[-1]["event"] == "attempt_reserved":
                    blockers.append(f"Unsettled prior attempt {key}; no automatic retry.")
                    break
                if previous and not previous[-1].get("retryable", False):
                    break
                number = sum(e["event"] == "attempt_reserved" for e in previous) + 1
                current = _summary(historical, events)
                if number > 1 and current["additional_retry_attempts"] >= preflight["study_header"]["retry_attempts"]:
                    blockers.append("Four-attempt/global remaining transport retry allowance exhausted.")
                    break
                if _money(current["cumulative_charged_or_reserved_usd"]) + reserve > _cap(root):
                    blockers.append("Cumulative budget cannot cover another conservative reservation.")
                    break
                key_value = os.environ.get("OPENROUTER_KEY")
                if not key_value:
                    blockers.append("OPENROUTER_KEY is unavailable; no request issued.")
                    break
                attempt_id = "responsiveness-" + hashlib.sha256(key.encode()).hexdigest() + f"-{number:02d}"
                common = {"attempt_id": attempt_id, "attempt_key": key,
                          "model_id": request["model_id"], "split": request["split"]}
                _append(ledger, {**common, "event": "attempt_reserved", "attempt_number": number,
                                 "input_token_bound": entry["input_token_bound"],
                                 "max_output_tokens": model["max_output_tokens"], "reserved_usd": str(reserve)})
                try:
                    response = (transport or api_transport)(model, entry["payload"], key_value)
                    if not isinstance(response, dict):
                        response = {"invalid_transport_envelope": response}
                except TransportFailure as exc:
                    _append(ledger, {**common, "event": "attempt_failed", "retryable": exc.retryable,
                                     "error": exc.code, "usage_cost_usd": None, "charged_usd": str(reserve)})
                    if exc.retryable:
                        continue
                    break
                except Exception:
                    _append(ledger, {**common, "event": "attempt_failed", "retryable": False,
                                     "error": "unexpected_adapter_error", "usage_cost_usd": None,
                                     "charged_usd": str(reserve)})
                    break
                usage, cost = _usage(response, model)
                actual = (usage or {}).get("provider_reported_actual_cost_usd")
                # Token counts are useful estimates, not authoritative charges.
                # Missing actual-cost metadata leaves the entire reservation held.
                charged = _money(actual) if actual is not None else reserve
                response_path = folder / "responses" / f"{attempt_id}.json"
                _save_once(response_path, {**common, "timestamp_utc": _now(), "raw_response": response,
                                          "completion_text": _completion(response, model["provider"])})
                _append(ledger, {**common, "event": "attempt_completed", "usage": usage,
                                 "usage_cost_usd": str(cost) if cost is not None else None,
                                 "provider_reported_actual_cost_usd": actual, "charged_usd": str(charged),
                                 "response_file": str(response_path.relative_to(folder))})
                if charged > reserve or (usage and (usage["input_tokens"] > entry["input_token_bound"]
                                                   or usage["output_tokens"] > model["max_output_tokens"])):
                    _append(ledger, {"event": "execution_halted", "reason": "provider_bound_violation",
                                     "attempt_id": attempt_id})
                    return {"status": "blocked", "blockers": ["Provider token/cost bound violated."],
                            **_summary(historical, _read(ledger))}
                break
    events = _read(folder / "attempts.jsonl")
    completed = {e["attempt_key"] for e in events if e["event"] == "attempt_completed"}
    missing = [r["attempt_key"] for r in requests if r["attempt_key"] not in completed]
    return {"status": "completed" if not missing else "incomplete", "missing_requests": missing,
            "blockers": sorted(set(blockers)), **_summary(_history(root)[0], events)}
