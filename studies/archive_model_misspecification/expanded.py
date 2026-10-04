"""Explicit loss-closure contract over already validated nominal finite archives.

Original Model and its authoritative-completeness checker remain unchanged.
Expanded hypotheses retain physical event/decision facts and weaken only the
named interpretation of completeness assertions after bounded receipt loss.
"""
from __future__ import annotations

import copy
from itertools import combinations

from tracebench.evidence_acquisition.model import Model, canonical, indices, pin

CONTRACT_ID = "bounded-context-receipt-loss-v1"
WORLD_CAP = 4096
SIGNATURE_CAP = 256
PHYSICAL_FIELDS = ("occurring_event_ids", "retained_record_ids", "recipient_writes",
                   "source_mechanism", "selected_source_ids")


def _check(condition, message):
    if not condition:
        raise ValueError(message)


def covers(scope, event):
    return (scope["source_id"] == event["source_id"]
            and scope["recipient"] == event["recipient"]
            and scope["window"][0] <= event["time"] < scope["window"][1])


def physical_world(parent, omitted=()):
    """Nominal assignment/guarantee metadata is not a current physical fact."""
    value = {field: copy.deepcopy(parent[field]) for field in PHYSICAL_FIELDS}
    value["occurring_event_ids"] = sorted(value["occurring_event_ids"])
    value["retained_record_ids"] = sorted(set(value["retained_record_ids"]) - set(omitted))
    value["selected_source_ids"] = sorted(value["selected_source_ids"])
    return value


def physical_id(physical):
    return "physical_" + pin({key: physical[key] for key in PHYSICAL_FIELDS})[:24]


def claim_value(problem, physical):
    """Derive the unchanged event/use claim from physical fields, not an input label."""
    events = {event["id"]: event for event in problem["event_catalog"]}
    claim = problem["claim"]
    target = next(write for write in physical["recipient_writes"]
                  if write["id"] == claim["target_write_id"])
    exposures = {
        source: any(events[event_id]["kind"] == "context"
                    and covers({"source_id": source, "recipient": claim["recipient"],
                                "window": claim["window"]}, events[event_id])
                    and events[event_id]["time"] < target["time"]
                    for event_id in physical["occurring_event_ids"])
        for source in claim["source_ids"]
    }
    if claim["kind"] == "any_context_exposure":
        return any(exposures.values())
    if claim["kind"] == "all_context_exposure":
        return all(exposures.values())
    _check(claim["kind"] == "source_use", "unknown claim semantics")
    return any(exposures[source] and source in physical["selected_source_ids"] for source in exposures)


def _validate_physical(problem, physical):
    """Keep positive evidence, event chains, write availability and source-use checks."""
    events = {event["id"]: event for event in problem["event_catalog"]}
    records = {record["id"]: record for record in problem["record_catalog"]}
    sources = {source["id"]: source for source in problem["sources"]}
    occurring = set(physical["occurring_event_ids"])
    retained = set(physical["retained_record_ids"])
    _check(occurring <= events.keys() and retained <= records.keys(), "unknown physical record/event")
    _check(set(problem["initial_record_ids"]) <= retained, "initial evidence was erased")
    for event_id in occurring:
        event = events[event_id]
        _check(sources[event["source_id"]]["written_at"] < event["time"] < problem["acquisition_time"],
               "invalid source/event/retrieval chronology")
        parent_id = event["parent_id"]
        if parent_id is not None:
            _check(parent_id in occurring, "event occurrence lost its parent")
            parent = events[parent_id]
            _check(parent["time"] < event["time"] and parent["source_id"] == event["source_id"]
                   and parent["recipient"] == event["recipient"], "invalid physical event chain")
    for record_id in retained:
        record = records[record_id]
        _check(record["authenticated"] is True and record["time"] <= problem["acquisition_time"],
               "unavailable or inauthentic retained record")
        if record["kind"].endswith("_receipt"):
            event = events[record["event_id"]]
            _check(record["event_id"] in occurring and record["time"] == event["time"]
                   and covers(record["scope"], event), "retained positive receipt is not truthful")
    writes = physical["recipient_writes"]
    _check(all(writes[i]["time"] < writes[i + 1]["time"] for i in range(len(writes) - 1)),
           "recipient writes are not chronological")
    for write in writes:
        available = sorted({events[event_id]["source_id"] for event_id in occurring
                            if events[event_id]["kind"] == "context"
                            and events[event_id]["recipient"] == write["recipient"]
                            and events[event_id]["time"] < write["time"]})
        _check(write["context_sources"] == available, "receipt omission altered first context availability")
    target = next(write for write in writes if write["id"] == problem["claim"]["target_write_id"])
    _check(set(physical["selected_source_ids"]) <= set(target["context_sources"]), "source use lacks exposure")
    _check(bool(physical["selected_source_ids"]) == (physical["source_mechanism"] == "direct"),
           "source selection/mechanism mismatch")


def omission_provenance(problem, parent, parent_index, omitted, physical):
    events = {event["id"]: event for event in problem["event_catalog"]}
    records = {record["id"]: record for record in problem["record_catalog"]}
    retained = set(physical["retained_record_ids"])
    initial = set(problem["initial_record_ids"])
    applicable, support_only, violated_assertions = [], [], set()
    violated_scopes = {}
    for record_id in omitted:
        event = events[records[record_id]["event_id"]]
        assertions = sorted(rid for rid in retained if records[rid]["kind"] == "completeness"
                            and records[rid]["event_kind"] == "context"
                            and covers(records[rid]["scope"], event))
        applicable.append({"omitted_record_id": record_id, "event_id": event["id"],
                           "assertion_ids": assertions,
                           "initial_assertion_ids": [rid for rid in assertions if rid in initial]})
        if not assertions:
            support_only.append(record_id)
        # Match the nominal validator: any still-retained receipt of this event
        # satisfies that occurrence's logging implication, including another copy.
        event_receipt_remains = any(records[rid].get("event_id") == event["id"] for rid in retained)
        if event_receipt_remains:
            continue
        violated_assertions.update(assertions)
        for scope in parent["complete_context_scopes"]:
            if covers(scope, event):
                key = pin({"scope": scope, "event_id": event["id"]})
                violated_scopes[key] = {
                    "event_id": event["id"], "scope": copy.deepcopy(scope),
                    "omitted_record_ids": sorted(rid for rid in omitted
                                                  if records[rid]["event_id"] == event["id"]),
                }
    return {
        "parent_world_id": parent["id"], "parent_world_index": parent_index,
        "nominal_retained_record_ids": sorted(parent["retained_record_ids"]),
        "nominal_complete_context_scopes": copy.deepcopy(parent["complete_context_scopes"]),
        "omitted_record_ids": list(omitted),
        "affected_query_ids": sorted(query["id"] for query in problem["queries"]
                                     if query["record_id"] in omitted),
        "violated_nominal_completeness": [violated_scopes[key] for key in sorted(violated_scopes)],
        "applicable_retained_assertions": applicable,
        "violated_retained_assertion_ids": sorted(violated_assertions),
        "support_only_omitted_record_ids": support_only,
    }


class ExpandedModel:
    """Unweighted, deduplicated support. No realized world or new prior is supplied."""

    def __init__(self, problem, k, *, world_cap=WORLD_CAP, signature_cap=SIGNATURE_CAP):
        _check(type(k) is int and k in (0, 1, 2), "omission budget must be 0, 1, or 2")
        _check(type(world_cap) is int and 0 < world_cap <= WORLD_CAP, "invalid expanded-world cap")
        _check(type(signature_cap) is int and 0 < signature_cap <= SIGNATURE_CAP, "invalid signature cap")
        self.problem = copy.deepcopy(problem)
        self.k, self.world_cap, self.signature_cap = k, world_cap, signature_cap
        # The original reliable-completeness contract is validated as written.
        self.nominal = Model(self.problem)
        self.claim = self.problem["claim"]
        self.queries = copy.deepcopy(self.nominal.queries)
        self.query_ids = tuple(self.queries)
        self.nominal_problem_pin = pin(self.problem)
        self.contract = {
            "schema_version": 1, "contract_id": CONTRACT_ID, "omission_budget": k,
            "nominal_problem_pin": self.nominal_problem_pin,
            "mechanism": "all subsets of at most k unique retained queried noninitial context receipt IDs",
            "authenticity": "surviving positive receipts truthfully identify unchanged occurring events",
            "completeness_assumption_change":
                "retained completeness bytes authenticate a nominal assertion; affected assertions do not "
                "guarantee completeness of the post-omission retrievable archive",
            "initial_evidence": "unaltered and not eligible for omission",
            "physical_truth": "event occurrence, timestamps, write context, source selection and output mechanism unchanged",
            "nominal_snapshot_metadata": "parent assignments and complete_context_scopes are provenance, not current facts",
            "support_semantics": "finite loss closure only, with no new probability distribution or invented event mechanism",
            "world_cap": world_cap, "signature_cap": signature_cap,
        }
        self.contract_pin = pin(self.contract)
        records = {record["id"]: record for record in self.problem["record_catalog"]}
        queried = {query["record_id"] for query in self.queries.values()}
        initial = set(self.problem["initial_record_ids"])
        unique, raw_candidates, embedding = {}, 0, []
        for parent_index, parent in enumerate(self.nominal.worlds):
            eligible = sorted(rid for rid in set(parent["retained_record_ids"]) & queried - initial
                              if records[rid]["kind"] == "context_receipt")
            for count in range(min(k, len(eligible)) + 1):
                for omitted in combinations(eligible, count):
                    raw_candidates += 1
                    physical = physical_world(parent, omitted)
                    _validate_physical(self.problem, physical)
                    _check(claim_value(self.problem, physical) == self.nominal.claim_values[parent_index],
                           "omission changed the physical claim truth")
                    for field in PHYSICAL_FIELDS:
                        if field == "retained_record_ids":
                            _check(set(physical[field]) == set(parent[field]) - set(omitted),
                                   "omission changed unexpected retained records")
                        elif field in {"occurring_event_ids", "selected_source_ids"}:
                            _check(set(physical[field]) == set(parent[field]), "physical event/use field changed")
                        else:
                            _check(physical[field] == parent[field], "physical write/mechanism field changed")
                    _check(not initial.intersection(omitted), "initial record omission")
                    pid = physical_id(physical)
                    key = canonical(physical)
                    if key not in unique:
                        _check(len(unique) < world_cap, "expanded-world safety cap exceeded; support not truncated")
                        unique[key] = {"id": pid, **physical, "provenance": []}
                    else:
                        _check(unique[key]["id"] == pid, "physical identity mismatch")
                    provenance = omission_provenance(self.problem, parent, parent_index, omitted, physical)
                    unique[key]["provenance"].append(provenance)
                    if not omitted:
                        embedding.append({"nominal_world_id": parent["id"], "nominal_world_index": parent_index,
                                          "expanded_world_id": pid})
        self.worlds = tuple(sorted(unique.values(), key=lambda world: world["id"]))
        _check(len({world["id"] for world in self.worlds}) == len(self.worlds), "physical hash collision")
        self.full_state = (1 << len(self.worlds)) - 1
        self.claim_values = tuple(claim_value(self.problem, world) for world in self.worlds)
        self.answers = tuple(tuple("present" if query["record_id"] in world["retained_record_ids"] else "missing"
                                   for query in self.queries.values()) for world in self.worlds)
        self.signature_cells = {}
        for index, signature in enumerate(self.answers):
            self.signature_cells[signature] = self.signature_cells.get(signature, 0) | (1 << index)
        _check(len(self.signature_cells) <= signature_cap,
               "expanded signature cap exceeded; support not truncated")
        self.embedding = embedding
        by_id = {world["id"]: index for index, world in enumerate(self.worlds)}
        for entry in embedding:
            nominal_index, expanded_index = entry["nominal_world_index"], by_id[entry["expanded_world_id"]]
            _check(self.answers[expanded_index] == self.nominal.answers[nominal_index]
                   and self.claim_values[expanded_index] == self.nominal.claim_values[nominal_index],
                   "nominal no-loss embedding changed observations or claim")
        _check(len(embedding) == len(self.nominal.worlds), "nominal support embedding incomplete")
        self.support_pin = pin([{field: world[field] for field in PHYSICAL_FIELDS} for world in self.worlds])
        self.model_pin = pin({"nominal_problem_pin": self.nominal_problem_pin,
                              "contract_pin": self.contract_pin, "physical_support_pin": self.support_pin})
        tau = [None] * len(self.worlds)
        for cell in self.signature_cells.values():
            values = {self.claim_values[index] for index in indices(cell)}
            status = "archive_irreducible" if len(values) == 2 else "established" if True in values else "ruled_out"
            for index in indices(cell):
                tau[index] = status
        self.tau = tuple(tau)
        provenance_rows = [row for world in self.worlds for row in world["provenance"]]
        self.stats = {
            "nominal_world_count": len(self.nominal.worlds), "generated_world_count": raw_candidates,
            "deduplicated_world_count": len(self.worlds), "signature_count": len(self.signature_cells),
            "nominal_signature_count": len(self.nominal.signature_cells),
            "overlapping_signature_count": len(self.signature_cells.keys() & self.nominal.signature_cells.keys()),
            "new_signature_count": len(self.signature_cells.keys() - self.nominal.signature_cells.keys()),
            "nonempty_omission_constructions": sum(bool(row["omitted_record_ids"]) for row in provenance_rows),
            "constructions_violating_nominal_completeness": sum(bool(row["violated_nominal_completeness"])
                                                                for row in provenance_rows),
            "constructions_violating_retained_assertions": sum(bool(row["violated_retained_assertion_ids"])
                                                               for row in provenance_rows),
            "constructions_with_support_only_omissions": sum(bool(row["support_only_omitted_record_ids"])
                                                             for row in provenance_rows),
            "nominal_embedding_count": len(embedding), "no_truncation": True,
        }

    def _state(self, state):
        _check(type(state) is int and state >= 0 and not state & ~self.full_state, "invalid expanded state")

    def compatible(self, history):
        state = self.full_state
        for item in history:
            _check(set(item) == {"query_id", "outcome_id"}, "invalid acquired history item")
            qid, outcome = item["query_id"], item["outcome_id"]
            _check(qid in self.queries and outcome in self.queries[qid]["outcomes"], "unknown query/outcome")
            position = self.query_ids.index(qid)
            state = sum(1 << index for index in indices(state) if self.answers[index][position] == outcome)
        return state

    def claim_status_state(self, state):
        self._state(state)
        if not state:
            return "model_conflict"
        values = {self.claim_values[index] for index in indices(state)}
        return "unresolved" if len(values) == 2 else "established" if True in values else "ruled_out"

    def claim_status(self, history):
        return self.claim_status_state(self.compatible(history))

    def terminal_state(self, state):
        status = self.claim_status_state(state)
        if status != "unresolved":
            return status
        possible_cells = [state & cell for cell in self.signature_cells.values() if state & cell]
        mixed = all({self.claim_values[index] for index in indices(cell)} == {False, True}
                    for cell in possible_cells)
        return "archive_irreducible" if mixed else "unresolved_pending"

    def terminal_status(self, history):
        return self.terminal_state(self.compatible(history))

    def certificate(self, history):
        history = copy.deepcopy(list(history))
        state = self.compatible(history)
        status, terminal = self.claim_status_state(state), self.terminal_state(state)
        result = {
            "schema_version": 1, "certificate_kind": "expanded_archive_support",
            "contract_id": CONTRACT_ID, "contract_pin": self.contract_pin, "contract": copy.deepcopy(self.contract),
            "nominal_problem_pin": self.nominal_problem_pin, "model_pin": self.model_pin,
            "support_pin": self.support_pin, "k": self.k, "claim": copy.deepcopy(self.claim),
            "initial_evidence": copy.deepcopy(self.problem["initial_evidence"]),
            "initial_evidence_pin": pin(self.problem["initial_evidence"]), "query_order": list(self.query_ids),
            "history": history,
            "acquired_evidence": [copy.deepcopy(self.queries[item["query_id"]]["outcomes"][item["outcome_id"]])
                                  for item in history],
            "claim_status": status, "terminal_status": terminal, "compatible_world_count": state.bit_count(),
            "scope_limit": "only this named loss-closure contract and the unchanged permitted query catalogue",
        }
        candidates = list(indices(state))
        if status != "unresolved":
            result["exhaustive_compatible_hypotheses"] = [self.worlds[index]["id"] for index in candidates]
        else:
            result["opposite_claim_witnesses"] = [self.worlds[next(index for index in candidates
                                                                 if self.claim_values[index] == value)]["id"]
                                                  for value in (False, True)]
            if terminal == "archive_irreducible":
                coverage = []
                for signature, full_cell in sorted(self.signature_cells.items()):
                    cell = state & full_cell
                    if not cell:
                        continue
                    members = list(indices(cell))
                    witnesses = [self.worlds[next(index for index in members
                                                 if self.claim_values[index] == value)]["id"]
                                 for value in (False, True)]
                    coverage.append({"complete_query_signature": list(signature),
                                     "compatible_world_count": cell.bit_count(),
                                     "opposite_claim_witnesses": witnesses})
                result["all_remaining_signature_cells"] = coverage
        return result

    def verify_certificate(self, candidate):
        try:
            rebuilt = ExpandedModel(self.problem, self.k, world_cap=self.world_cap,
                                    signature_cap=self.signature_cap)
            return canonical(candidate) == canonical(rebuilt.certificate(candidate["history"]))
        except (ValueError, KeyError, TypeError, IndexError, StopIteration):
            return False

    def comparison_witness(self, signature):
        signature = tuple(signature)
        _check(signature in self.signature_cells, "comparison requires an expanded reachable signature")
        history = [{"query_id": qid, "outcome_id": outcome}
                   for qid, outcome in zip(self.query_ids, signature, strict=True)]
        nominal_state = self.nominal.compatible(history)
        expanded_status = self.claim_status(history)
        base = {"schema_version": 1, "nominal_problem_pin": self.nominal_problem_pin,
                "expanded_model_pin": self.model_pin, "expanded_contract_pin": self.contract_pin,
                "full_signature": list(signature), "query_order": list(self.query_ids), "history": history,
                "nominal_certificate": self.nominal.certificate(history),
                "expanded_certificate": self.certificate(history)}
        if not nominal_state:
            return {**base, "witness_kind": "nominal_incompatible_full_history"}
        values = {self.nominal.claim_values[index] for index in indices(nominal_state)}
        if len(values) != 1 or expanded_status != "unresolved":
            return None
        nominal_index = next(indices(nominal_state))
        value = self.nominal.claim_values[nominal_index]
        cell = self.signature_cells[signature]
        opposite = next(index for index in indices(cell) if self.claim_values[index] != value)
        _check(self.nominal.answers[nominal_index] == self.answers[opposite] == signature,
               "counterexample does not match all catalogue observations")
        return {**base, "witness_kind": "same_signature_opposite_claim",
                "nominal_world_id": self.nominal.worlds[nominal_index]["id"],
                "expanded_world_id": self.worlds[opposite]["id"]}

    def verify_comparison_witness(self, candidate):
        try:
            rebuilt = ExpandedModel(self.problem, self.k, world_cap=self.world_cap,
                                    signature_cap=self.signature_cap)
            expected = rebuilt.comparison_witness(candidate["full_signature"])
            return (expected is not None and canonical(candidate) == canonical(expected)
                    and rebuilt.nominal.verify_certificate(candidate["nominal_certificate"])
                    and rebuilt.verify_certificate(candidate["expanded_certificate"]))
        except (ValueError, KeyError, TypeError, IndexError, StopIteration):
            return False

    def to_dict(self):
        return {"schema_version": 1, "problem_id": self.problem["problem_id"], "k": self.k,
                "contract": copy.deepcopy(self.contract), "contract_pin": self.contract_pin,
                "nominal_problem_pin": self.nominal_problem_pin, "model_pin": self.model_pin,
                "support_pin": self.support_pin, "stats": copy.deepcopy(self.stats),
                "embedding": copy.deepcopy(self.embedding), "worlds": copy.deepcopy(list(self.worlds)),
                "query_order": list(self.query_ids), "answers": [list(row) for row in self.answers]}
