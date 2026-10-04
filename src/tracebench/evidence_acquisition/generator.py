"""Seed-fixed finite assignments; eligibility never consults acquisition performance."""
from __future__ import annotations

import copy
import itertools
import random

from .model import Model, pin

VERSION = "finite-retention-v1"
STRATA = ("positive_receipt", "negative_completeness", "complementary_candidates", "archive_ambiguity")
DEVELOPMENT_SEEDS = tuple(range(94100, 94104))
EVALUATION_SEEDS = tuple(range(94200, 94240))


def seed_design(seed, stratum=None):
    if seed in DEVELOPMENT_SEEDS:
        index, split = seed - 94100, "development"
        inferred, local = STRATA[index], index
    elif seed in EVALUATION_SEEDS:
        inferred, local, split = STRATA[(seed - 94200) // 10], (seed - 94200) % 10, "evaluation"
    else:
        raise ValueError("seed outside declared development/evaluation sets")
    if stratum is not None and stratum != inferred:
        raise ValueError("stratum contradicts seed allocation")
    return inferred, local, split


def generate_problem(seed, stratum=None):
    stratum, local, split = seed_design(seed, stratum)
    rng = random.Random(seed)
    ambiguity = stratum == "archive_ambiguity"
    subtype = ("globally_indistinguishable_source_use" if local % 2 == 0 else
               "mixed_resolvability_source_use") if ambiguity else stratum
    routes = (2 if stratum == "complementary_candidates" else
              1 if ambiguity else 1 + local % 2)
    retention = ("independent", "shared", "opposite")[local % 3]
    fixed_complete = local in {2, 7} and stratum != "positive_receipt"
    context_gate = local % 2 == 0
    source_ids = [f"source_{i}" for i in range(routes)]
    def scope(source):
        return {"source_id": source, "recipient": "run_target", "window": [15, 35]}
    target_scopes = [scope(s) for s in source_ids]
    wrong_scope = copy.deepcopy(target_scopes[0])
    if local % 3 == 0:
        wrong_scope["source_id"] = "unrelated_source"
    elif local % 3 == 1:
        wrong_scope["recipient"] = "unrelated_run"
    else:
        wrong_scope["window"] = [70, 80]
    sources = [{"id": source, "written_at": 1 + i} for i, source in enumerate(source_ids)]
    events, records = [], []
    for i, source in enumerate(source_ids):
        parent = None
        for step, kind in enumerate(("request", "delivery", "context")):
            event_id = f"{kind}_{i}"
            event = {"id": event_id, "kind": kind, "source_id": source,
                     "recipient": "run_target", "time": 20 + 5 * i + step, "parent_id": parent}
            events.append(event)
            records.append({"id": f"record_{kind}_{i}", "kind": kind + "_receipt",
                            "scope": target_scopes[i], "event_id": event_id,
                            "time": event["time"], "authenticated": True})
            parent = event_id
        records.append({"id": f"complete_{i}", "kind": "completeness", "scope": target_scopes[i],
                        "event_kind": "context", "logging_complete": True,
                        "time": 45, "authenticated": True})
    records.extend([
        {"id": "wrong_complete", "kind": "completeness", "scope": wrong_scope,
         "event_kind": "context", "logging_complete": True, "time": 85, "authenticated": True},
        {"id": "nuisance", "kind": "archive_record", "scope": wrong_scope,
         "time": 41, "authenticated": True, "value": "retained checkpoint marker"},
        {"id": "initial_marker", "kind": "archive_record", "scope": wrong_scope,
         "time": 9 if local % 2 == 0 else 39, "authenticated": True,
         "value": "same visible output is compatible with direct and shared input"},
    ])
    catalog = {r["id"]: r for r in records}
    variables = []
    global_ambiguity = subtype == "globally_indistinguishable_source_use"
    if not global_ambiguity:
        variables.extend(f"event_{i}" for i in range(routes))
    variables.extend(f"retention_{i}" for i in range(routes if retention == "independent" else 1))
    if stratum != "positive_receipt" and not fixed_complete:
        variables.append("complete")
    if ambiguity:
        variables.append("use")
    variables.append("nuisance")
    if len(variables) > 6:
        raise ValueError("generative assignment bound exceeded")
    worlds = []
    for values in itertools.product((False, True), repeat=len(variables)):
        assignment = dict(zip(variables, values, strict=True))
        complete = fixed_complete or assignment.get("complete", False)
        occurred = [global_ambiguity or assignment[f"event_{i}"] for i in range(routes)]
        retained, occurring, complete_scopes = {"initial_marker"}, set(), [wrong_scope]
        if assignment["nuisance"]:
            retained.update({"nuisance", "wrong_complete"})
        for i in range(routes):
            occurring.add(f"request_{i}")
            if context_gate or occurred[i]:
                occurring.add(f"delivery_{i}")
            if occurred[i]:
                occurring.add(f"context_{i}")
            if assignment["nuisance"]:
                retained.add(f"record_request_{i}")
                if f"delivery_{i}" in occurring:
                    retained.add(f"record_delivery_{i}")
            bit = assignment[f"retention_{i if retention == 'independent' else 0}"]
            if retention == "opposite" and i % 2:
                bit = not bit
            if occurred[i] and (bit or complete):
                retained.add(f"record_context_{i}")
            if complete:
                retained.add(f"complete_{i}")
                complete_scopes.append(target_scopes[i])
        exposed = [s for i, s in enumerate(source_ids) if occurred[i]]
        direct = bool(exposed) and (assignment.get("use", False) if ambiguity else False)
        selected = [exposed[0]] if direct else []
        worlds.append({
            "id": f"hypothesis_{len(worlds):02d}", "assignment": assignment,
            "occurring_event_ids": sorted(occurring), "retained_record_ids": sorted(retained),
            "complete_context_scopes": complete_scopes,
            "source_mechanism": "direct" if direct else "shared_input",
            "selected_source_ids": selected,
            "recipient_writes": [
                {"id": "earlier_write", "recipient": "run_target", "time": 10, "context_sources": []},
                {"id": "intermediate_write", "recipient": "run_target", "time": 40,
                 "context_sources": exposed},
                {"id": "target", "recipient": "run_target", "time": 50, "context_sources": exposed},
            ],
        })
    record_order = [f"record_context_{i}" for i in range(routes)]
    if stratum != "positive_receipt" and not fixed_complete:
        record_order.extend(f"complete_{i}" for i in range(routes))
    record_order.extend(["wrong_complete", f"record_{'delivery' if local % 2 else 'request'}_0"])
    if local % 3 != 1:
        record_order.append("nuisance")
    # A second lookup of the same physical archive record is explicitly dependent.
    if local % 2 == 0:
        record_order.append("record_context_0")
    if len(record_order) > 8:
        raise ValueError("query catalogue bound exceeded")
    queries = []
    for i, record_id in enumerate(record_order):
        record = catalog[record_id]
        queries.append({"id": "q_" + pin([VERSION, seed, i])[:12], "record_id": record_id,
                        "kind": record["kind"], "scope": copy.deepcopy(record["scope"]),
                        "cost": rng.choice((1, 2, 4)),
                        "outcomes": {"missing": {"kind": "lookup_empty", "scope": record["scope"]},
                                     "present": copy.deepcopy(record)}})
    # Catalogue order is visible but does not reveal the realized return.
    rng.shuffle(queries)
    initial_ids = ["initial_marker"] + ([f"complete_{i}" for i in range(routes)] if fixed_complete else [])
    problem = {
        "schema_version": 1, "generator_version": VERSION, "problem_id": f"acq_{seed}",
        "seed": seed, "split": split, "stratum": stratum, "subtype": subtype,
        "claim": {"kind": "source_use" if ambiguity else
                  "all_context_exposure" if stratum == "complementary_candidates" else "any_context_exposure",
                  "source_ids": source_ids, "recipient": "run_target", "window": [15, 35],
                  "target_write_id": "target"},
        "assumptions": {
            "closed_catalogue": True, "authenticity": "retained receipts truthfully identify occurring events",
            "completeness": "only declared exact source/recipient/window context scopes force receipt retention",
            "query_semantics": "passive retained-record lookup; empty means no retained record, not no event",
            "temporal_semantics": "source precedes request, delivery and context; writes see all strictly prior contexts",
            "use_alternative": "same target output can arise from direct exposed source use or independent shared input",
            "initial_information": "only initial_evidence and this hypothetical model; no realized world identifier",
            "assignment_prior": "uniform independent Boolean generative assignments; not an empirical incident distribution",
            "dependencies": {"context_retention": retention, "completeness_shared_across_routes": True,
                             "upstream_wrong_completeness_and_nuisance_retention_shared": True,
                             "duplicate_queries_retrieve_same_record": True},
        },
        "structure": {"routes": routes, "retention": retention, "initial_complete": fixed_complete,
                      "failure_gate": "context" if context_gate else "delivery", "variables": variables},
        "acquisition_time": 100, "sources": sources, "event_catalog": events, "record_catalog": records,
        "initial_record_ids": initial_ids, "initial_evidence": [copy.deepcopy(catalog[r]) for r in initial_ids],
        "queries": queries, "worlds": worlds, "prior": [f"1/{len(worlds)}"] * len(worlds),
        "selection": {"rule": "seed maps to fixed structural choices before policy execution",
                      "rejections": [], "policy_outcomes_consulted": False},
    }
    model = Model(problem)
    # IDs/seed/order are removed; costs and actual semantic scope/dependency tables remain.
    normalized_queries = sorted(queries, key=lambda q: (q["record_id"], q["cost"]))
    positions = [model.query_ids.index(q["id"]) for q in normalized_queries]
    structural = {"claim": problem["claim"], "structure": problem["structure"],
                  "initial_evidence": problem["initial_evidence"],
                  "queries": [{k: v for k, v in q.items() if k != "id"} for q in normalized_queries],
                  "assignments": [{"assignment": w["assignment"], "claim": model.claim_values[i],
                                   "answers": [model.answers[i][j] for j in positions]}
                                  for i, w in enumerate(worlds)]}
    problem["structural_fingerprint"] = pin(structural)
    # Cost-free fingerprint also exposes cases differing only in retrieval prices.
    for query in structural["queries"]:
        query.pop("cost")
    problem["unweighted_structure_fingerprint"] = pin(structural)
    return problem


def generate_split(split):
    if split not in {"development", "evaluation"}:
        raise ValueError("unknown split")
    seeds = DEVELOPMENT_SEEDS if split == "development" else EVALUATION_SEEDS
    return [generate_problem(seed) for seed in seeds]
