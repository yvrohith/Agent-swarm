"""Independent finite observation contract; no legacy simulator imports."""
from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction

TERMINAL = {"established", "ruled_out", "archive_irreducible", "inconsistent"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def pin(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def indices(state):
    while state:
        bit = state & -state
        yield bit.bit_length() - 1
        state ^= bit


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _covers(scope, event):
    return (scope["source_id"] == event["source_id"]
            and scope["recipient"] == event["recipient"]
            and scope["window"][0] <= event["time"] < scope["window"][1])


def _scope(scope):
    _require(set(scope) == {"source_id", "recipient", "window"}, "invalid scope fields")
    _require(isinstance(scope["source_id"], str) and isinstance(scope["recipient"], str),
             "invalid scope identities")
    window = scope["window"]
    _require(isinstance(window, list) and len(window) == 2
             and all(isinstance(x, int) and not isinstance(x, bool) for x in window)
             and window[0] < window[1], "invalid scope window")


class Model:
    """A public hypothesis space, never an accessor to a realized world.

    Worlds represent generative assignments, so duplicate physical realizations
    may retain distinct positive prior mass. Compatibility ignores prior masses.
    """

    def __init__(self, problem):
        self.problem = copy.deepcopy(problem)
        p = self.problem
        _require(p.get("schema_version") == 1, "unsupported finite model")
        self.claim = p["claim"]
        _require(self.claim["kind"] in {
            "any_context_exposure", "all_context_exposure", "source_use"}, "invalid claim kind")
        _require(self.claim["source_ids"] and len(set(self.claim["source_ids"]))
                 == len(self.claim["source_ids"]), "invalid claim sources")
        for source in self.claim["source_ids"]:
            _scope({"source_id": source, "recipient": self.claim["recipient"],
                    "window": self.claim["window"]})
        self.worlds = tuple(p["worlds"])
        _require(0 < len(self.worlds) <= 64, "world count outside bounded contract")
        _require(len({w["id"] for w in self.worlds}) == len(self.worlds), "duplicate world ID")
        self.priors = tuple(Fraction(x) for x in p["prior"])
        _require(len(self.priors) == len(self.worlds) and all(x > 0 for x in self.priors)
                 and sum(self.priors) == 1, "prior must be positive and normalized")
        self.queries = {q["id"]: q for q in p["queries"]}
        _require(0 < len(self.queries) == len(p["queries"]) <= 8, "invalid query catalogue")
        self.query_ids = tuple(self.queries)
        records = {r["id"]: r for r in p["record_catalog"]}
        _require(len(records) == len(p["record_catalog"]), "duplicate record ID")
        events = {e["id"]: e for e in p["event_catalog"]}
        _require(len(events) == len(p["event_catalog"]), "duplicate event ID")
        sources = {s["id"]: s for s in p["sources"]}
        _require(len(sources) == len(p["sources"]), "duplicate source ID")
        _require(set(self.claim["source_ids"]) <= set(sources), "unknown claim source")
        for event in events.values():
            _require(event["kind"] in {"request", "delivery", "context"}, "invalid event kind")
            _require(event["source_id"] in sources, "unknown event source")
            _require(sources[event["source_id"]]["written_at"] < event["time"],
                     "event precedes source availability")
            _require(event["time"] < p["acquisition_time"], "event after retrieval time")
            if event["kind"] == "request":
                _require(event["parent_id"] is None, "request has unexpected parent")
            else:
                parent = events.get(event["parent_id"])
                expected = "request" if event["kind"] == "delivery" else "delivery"
                _require(parent is not None and parent["kind"] == expected
                         and parent["source_id"] == event["source_id"]
                         and parent["recipient"] == event["recipient"]
                         and parent["time"] < event["time"], "invalid temporal event chain")
        for record in records.values():
            _scope(record["scope"])
            _require(record.get("authenticated") is True, "unauthenticated archive record")
            _require(record["time"] <= p["acquisition_time"], "record not yet available")
            if record["kind"].endswith("_receipt"):
                event = events.get(record.get("event_id"))
                _require(event is not None and record["kind"] == event["kind"] + "_receipt"
                         and record["time"] == event["time"] and _covers(record["scope"], event),
                         "receipt/event mismatch")
            else:
                _require(record["kind"] in {"completeness", "archive_record"}, "invalid record kind")
            if record["kind"] == "completeness":
                _require(record.get("event_kind") == "context"
                         and record.get("logging_complete") is True
                         and record["time"] >= record["scope"]["window"][1],
                         "invalid or premature retrospective completeness declaration")
        for query in self.queries.values():
            _scope(query["scope"])
            _require(isinstance(query["cost"], int) and not isinstance(query["cost"], bool)
                     and query["cost"] in {1, 2, 4}, "invalid query cost")
            record = records.get(query["record_id"])
            _require(record is not None and query["scope"] == record["scope"]
                     and query["kind"] == record["kind"], "query/record scope mismatch")
            expected = {"missing": {"kind": "lookup_empty", "scope": query["scope"]},
                        "present": record}
            _require(query["outcomes"] == expected, "query observable payload mismatch")
        claim_values, answers = [], []
        for world in self.worlds:
            occurrence = set(world["occurring_event_ids"])
            retained = set(world["retained_record_ids"])
            _require(len(occurrence) == len(world["occurring_event_ids"])
                     and occurrence <= set(events), "invalid event occurrence set")
            _require(len(retained) == len(world["retained_record_ids"])
                     and retained <= set(records), "invalid retained record set")
            for event_id in occurrence:
                parent = events[event_id]["parent_id"]
                _require(parent is None or parent in occurrence, "occurring event lacks parent")
            for record_id in retained:
                record = records[record_id]
                if record["kind"].endswith("_receipt"):
                    _require(record["event_id"] in occurrence, "retained receipt for nonexistent event")
                if record["kind"] == "completeness":
                    _require(record["scope"] in world["complete_context_scopes"],
                             "unjustified completeness declaration")
            for scope in world["complete_context_scopes"]:
                _scope(scope)
                for event_id in occurrence:
                    event = events[event_id]
                    if event["kind"] == "context" and _covers(scope, event):
                        _require(any(records[r].get("event_id") == event_id for r in retained),
                                 "complete logging dropped a relevant receipt")
            for record_id in p["initial_record_ids"]:
                _require(record_id in retained, "world contradicts initial evidence")
            _require(p["initial_evidence"] == [records[r] for r in p["initial_record_ids"]],
                     "initial evidence does not match records")
            writes = world["recipient_writes"]
            _require(len({w["id"] for w in writes}) == len(writes), "duplicate write ID")
            _require(all(writes[i]["time"] < writes[i + 1]["time"]
                         for i in range(len(writes) - 1)), "nonchronological writes")
            for write in writes:
                available = sorted({events[e]["source_id"] for e in occurrence
                                    if events[e]["kind"] == "context"
                                    and events[e]["recipient"] == write["recipient"]
                                    and events[e]["time"] < write["time"]})
                _require(write["context_sources"] == available,
                         "context first availability contradicts write decision state")
            target = next((w for w in writes if w["id"] == self.claim["target_write_id"]), None)
            _require(target is not None and target["recipient"] == self.claim["recipient"],
                     "missing or mis-scoped target write")
            _require(target["time"] < p["acquisition_time"], "target unavailable during retrieval")
            selection = world["selected_source_ids"]
            _require(set(selection) <= set(target["context_sources"]), "use without prior exposure")
            _require(world["source_mechanism"] in {"direct", "shared_input"}, "invalid use mechanism")
            _require(bool(selection) == (world["source_mechanism"] == "direct"),
                     "source mechanism/selection mismatch")
            exposure = {source: any(events[e]["kind"] == "context"
                                    and _covers({"source_id": source,
                                                 "recipient": self.claim["recipient"],
                                                 "window": self.claim["window"]}, events[e])
                                    and events[e]["time"] < target["time"] for e in occurrence)
                        for source in self.claim["source_ids"]}
            if self.claim["kind"] == "all_context_exposure":
                value = all(exposure.values())
            elif self.claim["kind"] == "any_context_exposure":
                value = any(exposure.values())
            else:
                value = any(source in selection and exposure[source] for source in exposure)
            claim_values.append(value)
            answers.append(tuple("present" if q["record_id"] in retained else "missing"
                                 for q in self.queries.values()))
        self.claim_values = tuple(claim_values)
        self.answers = tuple(answers)
        self.full_state = (1 << len(self.worlds)) - 1
        self.signature_cells = {}
        for i, signature in enumerate(self.answers):
            self.signature_cells[signature] = self.signature_cells.get(signature, 0) | (1 << i)
        tau = [None] * len(self.worlds)
        for cell in self.signature_cells.values():
            values = {self.claim_values[i] for i in indices(cell)}
            status = ("archive_irreducible" if len(values) > 1 else
                      "established" if True in values else "ruled_out")
            for i in indices(cell):
                tau[i] = status
        self.tau = tuple(tau)
        self.model_pin = pin(p)

    def partition(self, state, query_id):
        self._state(state)
        position = self.query_ids.index(query_id)
        output = {}
        for i in indices(state):
            answer = self.answers[i][position]
            output[answer] = output.get(answer, 0) | (1 << i)
        return dict(sorted(output.items()))

    def _state(self, state):
        _require(isinstance(state, int) and state >= 0 and state & ~self.full_state == 0,
                 "invalid candidate state")

    def mass(self, state):
        self._state(state)
        return sum((self.priors[i] for i in indices(state)), Fraction())

    def compatible(self, history):
        state = self.full_state
        for item in history:
            _require(set(item) == {"query_id", "outcome_id"}, "invalid history item")
            qid, outcome = item["query_id"], item["outcome_id"]
            _require(qid in self.queries and outcome in self.queries[qid]["outcomes"],
                     "unknown query or outcome")
            state = self.partition(state, qid).get(outcome, 0)
        return state

    def terminal(self, state):
        self._state(state)
        if not state:
            return "inconsistent"
        classes = {self.tau[i] for i in indices(state)}
        if len(classes) == 1:
            return next(iter(classes))
        return None

    def certificate(self, history, status=None):
        from .certificates import certificate
        return certificate(self, history, status)

    def verify_certificate(self, cert):
        from .certificates import verify_certificate
        return verify_certificate(self, cert)
