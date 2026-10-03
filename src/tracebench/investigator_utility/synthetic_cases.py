"""Finite receipt reasoning fixtures, separate from the structural simulator.

The public view contains a deliberately small, explicit generative contract.
Gold exhausts that contract, including an independently rendered shared-input
mechanism. It never reads an existing simulator world or source-selection label.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from copy import deepcopy

CHANNELS = ("request", "delivery", "context")
STAGES = (*CHANNELS, "use")
CONTRACT = "receipt-chain-shared-scaffold-v1"
RULE = "finite-exhaustion-with-rendered-mechanisms-v1"
CHAIN_STATES = ((False, False, False), (True, False, False),
                (True, True, False), (True, True, True))
FINITE_CONTRACT_TEXT = (
    "This is a finite reasoning fixture, not an observation of a real agent. Each declared "
    "(source, run, window) permits at most one request at window start + 2, one successful "
    "delivery at + 3, and one context entry at + 4. Delivery requires that request; context "
    "requires that delivery. Each event may fail to occur. Source and shared-input records "
    "are available at target-window start + 1; the target is written at + 9. The target "
    "uses exactly one of two declared mechanisms: copy the named source record's body "
    "(requiring its context entry), or independently fill the shared input's literal "
    "'Plan: {topic}' scaffold with its topic, which does not use the source record. Both "
    "mechanisms wrap their intermediate text as 'Result: ' + text + '.'. The generated "
    "output must equal the supplied target text. The selected mechanism is not logged. "
    "No other output mechanism or event slot exists within this finite contract.")
AUTHENTICITY_TEXT = (
    "All supplied receipt records are assumed authentic and semantically valid for "
    "their named source, run, and timestamp. This is an explicit evidence assumption, "
    "not a claim that a cryptographic signature was verified. A supplied request "
    "records occurrence only, a delivery records successful receipt, and a context "
    "record records entry of that source content into context.")
LOGGING_TEXT = (
    "Receipt channels may have missing records. Absence implies nonoccurrence only "
    "when a completeness declaration names that channel, source, and run and covers "
    "the event's timestamp in its inclusive interval. Other source/run/window "
    "declarations confer no coverage. Completeness means every occurring event in "
    "that scope has its corresponding record in this bundle.")


def _completeness_text(channel: str, scope: dict) -> str:
    return (f"The {channel} channel is complete for source {scope['source_id']}, "
            f"run {scope['run_id']}, within inclusive interval {scope['window']}.")


class InconsistentEvidenceError(ValueError):
    """No world satisfies all supplied records and material assumptions."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _scope_key(scope: dict) -> tuple:
    return scope["source_id"], scope["run_id"], tuple(scope["window"])


def _claim_text(scope: dict, stage: str) -> str:
    source, run, window = _scope_key(scope)
    suffix = f"source {source}, run {run}, during [{window[0]}, {window[1]}]"
    return {
        "request": f"A request occurred for {suffix}.",
        "delivery": f"Successful delivery occurred for {suffix}.",
        "context": f"The source content entered the target context for {suffix}.",
        "use": f"The target selected that source content to generate its output for {suffix}.",
    }[stage]


def _event_time(scope: dict, channel: str) -> int:
    return scope["window"][0] + CHANNELS.index(channel) + 2


def _coverage(assumption: dict, scope: dict, channel: str) -> bool:
    settings = assumption.get("parameters", {})
    return (settings.get("type") == "complete_logging"
            and settings["channel"] == channel
            and settings["source_id"] == scope["source_id"]
            and settings["run_id"] == scope["run_id"]
            and settings["window"][0] <= _event_time(scope, channel)
            <= settings["window"][1])


def _contract(case: dict) -> dict:
    if case.get("schema_version") != 1 or case.get("subset") != "synthetic":
        raise ValueError("Not a supported synthetic case")
    assumptions = [a for a in case["assumptions"]
                   if a.get("parameters", {}).get("contract") == CONTRACT]
    if len(assumptions) != 1:
        raise ValueError("Expected one declared finite contract")
    if assumptions[0]["text"] != FINITE_CONTRACT_TEXT:
        raise ValueError("Finite contract explanation differs from the supported semantics")
    settings = assumptions[0]["parameters"]
    scopes = settings["scopes"]
    keys = [_scope_key(scope) for scope in scopes]
    if not scopes or len(set(keys)) != len(keys) or len(scopes) > 4:
        raise ValueError("The finite contract requires one to four distinct scopes")
    if _scope_key(settings["target_scope"]) not in keys:
        raise ValueError("Target scope must be declared")
    for scope in scopes:
        if (len(scope["window"]) != 2
                or not all(type(t) is int for t in scope["window"])
                or scope["window"][1] - scope["window"][0] < 9):
            raise ValueError("Declared windows must contain all fixed event times")
    if not any(a["text"] == AUTHENTICITY_TEXT for a in case["assumptions"]):
        raise ValueError("The authentic-receipt assumption must be explicitly supplied")
    if not any(a["text"] == LOGGING_TEXT for a in case["assumptions"]):
        raise ValueError("The incomplete-by-default logging assumption must be explicit")
    if case["claims"] != [{"id": f"c{i:02}", "text": _claim_text(
            settings["target_scope"], stage)} for i, stage in enumerate(STAGES, 1)]:
        raise ValueError("Claims differ from the declared four-claim template")
    ids = [row["id"] for row in case["records"] + case["assumptions"]]
    if len(set(ids)) != len(ids):
        raise ValueError("Record and assumption identifiers must be unique")
    for assumption in case["assumptions"]:
        parameters = assumption.get("parameters", {})
        if parameters.get("type") == "complete_logging":
            if (parameters["channel"] not in CHANNELS
                    or len(parameters["window"]) != 2
                    or not all(type(t) is int for t in parameters["window"])
                    or parameters["window"][0] > parameters["window"][1]
                    or assumption["text"] != _completeness_text(
                        parameters["channel"], parameters)):
                raise ValueError("Invalid scoped completeness declaration")
        elif parameters.get("contract") != CONTRACT and assumption["text"] not in (
                AUTHENTICITY_TEXT, LOGGING_TEXT):
            raise ValueError("Unsupported assumption outside the declared evidence contract")
    return settings


def enumerate_compatible_worlds(case: dict) -> list[dict]:
    """Exhaust the declared finite mechanisms or reject inconsistent evidence.

    Four receipt-chain states per scope and two output mechanisms are the entire
    declared possibility set. Authentic surviving records constrain occurrence;
    absence constrains it only when an explicit relevant completeness interval
    covers that channel's fixed event time. The source-copy mechanism additionally
    requires context entry. Both output mechanisms must reproduce the raw output.
    """
    settings = _contract(case)
    scopes = settings["scopes"]
    keys = [_scope_key(scope) for scope in scopes]
    target_index = keys.index(_scope_key(settings["target_scope"]))
    records = {row["id"]: row for row in case["records"]}
    source = records[settings["source_record_id"]]
    shared = records[settings["shared_record_id"]]
    target = records[settings["target_record_id"]]
    if (source["kind"], shared["kind"], target["kind"]) != (
            "source_write", "shared_input", "target_write"):
        raise ValueError("The finite contract requires source, scaffold, and target records")
    if shared["scaffold"] != "Plan: {topic}":
        raise ValueError("Only the declared literal shared scaffold is supported")
    if (source["source_id"] != settings["target_scope"]["source_id"]
            or target["run_id"] != settings["target_scope"]["run_id"]
            or shared["run_id"] != target["run_id"]):
        raise ValueError("Content records must match the named target scope")
    start = settings["target_scope"]["window"][0]
    if (source["timestamp"], shared["timestamp"], target["timestamp"]) != (
            start + 1, start + 1, start + 9):
        raise ValueError("Content records must satisfy the declared chronology")
    positive = set()
    for row in records.values():
        if row["kind"] in CHANNELS:
            key = _scope_key(row)
            if key not in keys or row["timestamp"] != _event_time(row, row["kind"]):
                raise ValueError("Receipt falls outside the declared finite event slots")
            positive.add((keys.index(key), CHANNELS.index(row["kind"])))
        elif row["kind"] not in ("source_write", "shared_input", "target_write"):
            raise ValueError("Unrecognized evidence record kind")

    worlds = []
    for chains in itertools.product(CHAIN_STATES, repeat=len(scopes)):
        if any(not chains[i][j] for i, j in positive):
            continue
        if any(chains[i][j] and (i, j) not in positive
               and any(_coverage(a, scope, channel) for a in case["assumptions"])
               for i, scope in enumerate(scopes) for j, channel in enumerate(CHANNELS)):
            continue
        for use_source in (False, True):
            if use_source and not chains[target_index][2]:
                continue
            if use_source:
                intermediate = source["body"]
                mechanism = "copy_source_payload"
                input_id = source["id"]
            else:
                intermediate = shared["scaffold"].replace("{topic}", shared["topic"])
                mechanism = "fill_shared_scaffold"
                input_id = shared["id"]
            rendered = f"Result: {intermediate}."
            if rendered != target["body"]:
                continue
            worlds.append({
                "world_id": f"w{len(worlds) + 1:03}",
                "scopes": [{**scope, "events": [
                    {"kind": channel, "timestamp": _event_time(scope, channel)}
                    for channel, occurred in zip(CHANNELS, chain, strict=True) if occurred
                ]} for scope, chain in zip(scopes, chains, strict=True)],
                "source_selected": use_source,
                "construction": {"mechanism": mechanism, "input_record_id": input_id,
                                 "intermediate_text": intermediate, "output_text": rendered,
                                 "output_record_id": target["id"]},
            })
    if not worlds:
        raise InconsistentEvidenceError("No compatible world: inconsistent evidence/contract")
    return worlds


def _gold(case: dict) -> dict:
    worlds = enumerate_compatible_worlds(case)
    target_key = _scope_key(_contract(case)["target_scope"])
    claims = []
    for claim, stage in zip(case["claims"], STAGES, strict=True):
        yes, no = [], []
        for world in worlds:
            scope = next(s for s in world["scopes"] if _scope_key(s) == target_key)
            value = (world["source_selected"] if stage == "use" else
                     any(event["kind"] == stage for event in scope["events"]))
            (yes if value else no).append(world)
        status = "unresolved" if yes and no else "established" if yes else "ruled_out"
        claims.append({"id": claim["id"], "status": status, "certificate": {
            "method": RULE, "true_world_ids": [w["world_id"] for w in yes],
            "false_world_ids": [w["world_id"] for w in no],
            "disagreeing_constructions": [deepcopy(yes[0]), deepcopy(no[0])] if yes and no else [],
        }})
    return {"case_id": case["case_id"], "claims": claims, "validation": {
        "method": RULE, "public_case_sha256": hashlib.sha256(_canonical(case).encode()).hexdigest(),
        "compatible_world_count": len(worlds), "compatible_worlds": worlds,
        "review_type": "mechanical finite enumeration; no human validation claimed",
    }}


def validate_synthetic_gold(case: dict, gold: dict) -> None:
    """Re-enumerate and re-render rather than trusting stored verdicts or labels."""
    if gold != _gold(case):
        raise ValueError("Synthetic gold or certificate differs from finite re-enumeration")


def _case(number: int, split: str, receipts: tuple[str, ...], complete: tuple[str, ...],
          irrelevant: tuple[str, ...] = ()) -> dict:
    case_id = f"s{number:03}"
    source_id, run_id = f"document_{number:03}", f"run_{number:03}"
    scope = {"source_id": source_id, "run_id": run_id, "window": [0, 10]}
    topic = ("amber bridge", "silver orchard", "quiet harbor", "violet garden",
             "copper tower", "winter meadow", "paper lantern", "indigo valley",
             "cedar path", "crystal lake")[number - 1]
    records = [
        {"id": "r01", "kind": "source_write", "source_id": source_id,
         "timestamp": 1, "body": f"Plan: {topic}"},
        {"id": "r02", "kind": "shared_input", "run_id": run_id, "timestamp": 1,
         "scaffold": "Plan: {topic}", "topic": topic},
        {"id": "r03", "kind": "target_write", "run_id": run_id,
         "timestamp": 9, "body": f"Result: Plan: {topic}."},
    ]
    records.extend({"id": f"r{i:02}", "kind": channel, **deepcopy(scope),
                    "timestamp": _event_time(scope, channel)}
                   for i, channel in enumerate(receipts, 4))
    assumptions = [{"id": "a01", "text": FINITE_CONTRACT_TEXT,
        "parameters": {"contract": CONTRACT, "target_scope": deepcopy(scope),
                       "scopes": [deepcopy(scope)], "source_record_id": "r01",
                       "shared_record_id": "r02", "target_record_id": "r03"}},
        {"id": "a02", "text": AUTHENTICITY_TEXT},
        {"id": "a03", "text": LOGGING_TEXT},
    ]
    declarations = [(channel, deepcopy(scope)) for channel in complete]
    for dimension in irrelevant:
        other = deepcopy(scope)
        if dimension == "source":
            other["source_id"] = f"document_other_{number:03}"
        elif dimension == "run":
            other["run_id"] = f"run_other_{number:03}"
        elif dimension == "window":
            other["window"] = [20, 30]
        else:
            raise ValueError("Unknown scope dimension")
        assumptions[0]["parameters"]["scopes"].append(other)
        declarations.append(("context", other))
    for channel, declared in declarations:
        assumptions.append({"id": f"a{len(assumptions) + 1:02}",
            "text": _completeness_text(channel, declared),
            "parameters": {"type": "complete_logging", "channel": channel,
                           **deepcopy(declared)}})
    return {"schema_version": 1, "case_id": case_id, "subset": "synthetic", "split": split,
            "cluster_id": case_id, "records": records, "assumptions": assumptions,
            "claims": [{"id": f"c{i:02}", "text": _claim_text(scope, stage)}
                       for i, stage in enumerate(STAGES, 1)]}


def build_synthetic_cases() -> tuple[list[dict], list[dict], dict]:
    """Build two development and eight evaluation cases with fixed selection."""
    cases = [
        _case(1, "development", ("context",), ("context",)),
        _case(2, "development", ("request", "delivery"), ("context",)),
        _case(3, "evaluation", ("context",), ("context",)),
        _case(4, "evaluation", ("request", "delivery"), ("request", "delivery")),
        _case(5, "evaluation", ("request", "delivery"), CHANNELS),
        _case(6, "evaluation", ("request",), ("request", "delivery")),
        _case(7, "evaluation", CHANNELS, CHANNELS),
        _case(8, "evaluation", (), ("request",)),
        _case(9, "evaluation", (), (), ("source",)),
        _case(10, "evaluation", ("request", "delivery"), (), ("run", "window")),
    ]
    gold = [_gold(case) for case in cases]
    manifest = {"schema_version": 1, "subset": "synthetic", "contract": CONTRACT,
                "development_cases": 2, "evaluation_cases": 8,
                "selection": "fixed enumerated receipt/scope scenarios; no model-outcome selection",
                "unit": "one public observation bundle; compatible mechanisms are not extra cases",
                "inconsistency_rule": "reject bundles with no compatible finite world before inference",
                "case_ids": [case["case_id"] for case in cases],
                "public_cases_sha256": hashlib.sha256(_canonical(cases).encode()).hexdigest(),
                "gold_sha256": hashlib.sha256(_canonical(gold).encode()).hexdigest()}
    return cases, gold, manifest
