"""Cold-cache construction of complete reachable policies, at the original prior.

This measures a fixed local workload, not acquisition/deployment latency. A
validated Model is shared read-only; each policy/repetition gets a fresh planner.
Only hypothetical outcome branches are enumerated, never a realized archive.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from contextlib import contextmanager
from statistics import mean
from time import perf_counter_ns, process_time_ns

from studies.acquisition_prior_robustness.sensitivity import CappedPlanner, ExactStateCap
from tracebench.evidence_acquisition.model import Model, canonical, pin
from tracebench.evidence_acquisition.policies import POLICIES

REPETITIONS = 3
PHASES = (
    "planner_setup", "planner_decisions", "certificate_construction",
    "certificate_verification", "evaluation_bookkeeping", "serialization",
)


@contextmanager
def _measure(timings, phase):
    wall, cpu = perf_counter_ns(), process_time_ns()
    try:
        yield
    finally:
        timings[phase]["cpu_seconds"] += (process_time_ns() - cpu) / 1_000_000_000
        timings[phase]["wall_seconds"] += (perf_counter_ns() - wall) / 1_000_000_000


def _blank_timings(phases):
    return {phase: {"cpu_seconds": 0.0, "wall_seconds": 0.0} for phase in phases}


def model_state_pin(model):
    """Check input and derived public-model state, not just its stored input pin."""
    return pin({
        "problem": model.problem, "model_pin": model.model_pin,
        "query_ids": model.query_ids, "queries": model.queries,
        "worlds": model.worlds, "priors": [str(p) for p in model.priors],
        "answers": model.answers, "claim_values": model.claim_values,
        "tau": model.tau, "full_state": model.full_state,
        "signature_cells": [[list(s), cell] for s, cell in model.signature_cells.items()],
    })


def measure_construction(model, policy, *, planner_factory=CappedPlanner):
    """Build every reachable history once using a new, initially empty planner.

    The driver passes one immutable validated model to every policy. Each tree
    visits all possible outcomes of the chosen query in lexical outcome order.
    Leaf certificate work is measured separately; its count may differ between
    policies. No budget sweep, selected signature, or environment lookup is used.
    """
    if policy not in POLICIES:
        raise ValueError("unknown timing policy")
    phases = _blank_timings(PHASES)
    started_wall, started_cpu = perf_counter_ns(), process_time_ns()
    planner = None
    nodes, leaves = [], []
    choose_calls = action_count = certificate_count = certificate_failures = 0
    before_pin = None
    status, failure = "completed", None
    try:
        with _measure(phases, "evaluation_bookkeeping"):
            before_pin = model_state_pin(model)
            stack = [[]]
        with _measure(phases, "planner_setup"):
            planner = planner_factory(model, policy)
            if planner._values or planner._actions or planner._edges or planner.solver_states:
                raise ValueError("timing requires a fresh planner with empty caches")
        while stack:
            with _measure(phases, "evaluation_bookkeeping"):
                history = stack.pop()
                state = model.compatible(history)
                if not state:
                    raise ValueError("DFS visited an impossible history")
            with _measure(phases, "planner_decisions"):
                choose_calls += 1
                query_id = planner.choose(history)
            with _measure(phases, "evaluation_bookkeeping"):
                nodes.append({"history": history, "query_id": query_id})
                if query_id is None:
                    terminal = model.terminal(state)
                    if terminal not in {"established", "ruled_out", "archive_irreducible"}:
                        raise ValueError("policy construction stopped without a terminal class")
                    if policy == "read_all" and len(history) != len(model.queries):
                        raise ValueError("read-all stopped before retrieving the entire catalogue")
                    leaves.append((history, terminal))
                else:
                    if query_id not in model.queries or any(
                        row["query_id"] == query_id for row in history
                    ):
                        raise ValueError("policy selected an unknown or repeated query")
                    action_count += 1
                    outcomes = model.partition(state, query_id)
                    # Reverse insertion gives lexical visitation with a LIFO stack.
                    for outcome_id, child in sorted(outcomes.items(), reverse=True):
                        if child:
                            stack.append(history + [{
                                "query_id": query_id, "outcome_id": outcome_id,
                            }])
        certificates = []
        for history, terminal in leaves:
            with _measure(phases, "certificate_construction"):
                certificate = model.certificate(history, status=terminal)
            with _measure(phases, "certificate_verification"):
                valid = model.verify_certificate(certificate)
            with _measure(phases, "evaluation_bookkeeping"):
                certificate_count += 1
                certificate_failures += int(not valid)
                certificates.append({"certificate": certificate, "valid": valid})
        if certificate_failures:
            status, failure = "failed", "one or more leaf certificates failed verification"
    except ExactStateCap as exc:
        status, failure = "capped", str(exc)
        certificates = []
    except (ValueError, RuntimeError) as exc:
        status, failure = "failed", f"{type(exc).__name__}: {exc}"
        certificates = []
    with _measure(phases, "evaluation_bookkeeping"):
        after_pin = model_state_pin(model)
        immutable = before_pin is not None and before_pin == after_pin
        if not immutable:
            status, failure = "failed", "shared validated model was mutated"
        counters = {
            "choose_calls": choose_calls,
            "decision_count": action_count,
            "visited_histories": len(nodes),
            "terminal_histories": len(leaves),
            "certificate_count": certificate_count,
            "certificate_failures": certificate_failures,
            "solver_states": planner.solver_states if planner is not None else 0,
            "memoized_states": len(planner._values) if planner is not None else 0,
            "admitted_exact_states": len(planner.capped_states) if planner is not None else 0,
            "exact_state_cap": planner.state_cap if planner is not None else None,
            "pair_cut_edge_cache_entries": len(planner._edges) if planner is not None else 0,
        }
    with _measure(phases, "serialization"):
        serialized = canonical({"nodes": nodes, "certificates": certificates})
        workload_sha256 = hashlib.sha256(serialized).hexdigest()
    return {
        "policy": policy, "status": status, "failure": failure,
        "shared_model_unchanged": immutable,
        "model_state_sha256": before_pin,
        "workload_sha256": workload_sha256,
        "serialized_workload_bytes": len(serialized),
        "timing": phases,
        "planning_cpu_seconds": sum(phases[p]["cpu_seconds"]
                                    for p in ("planner_setup", "planner_decisions")),
        "planning_wall_seconds": sum(phases[p]["wall_seconds"]
                                     for p in ("planner_setup", "planner_decisions")),
        "total_cpu_seconds": (process_time_ns() - started_cpu) / 1_000_000_000,
        "total_wall_seconds": (perf_counter_ns() - started_wall) / 1_000_000_000,
        **counters,
    }


def run_timing(problems, *, planner_factory=CappedPlanner):
    """Exactly three fresh-planner repetitions, with no favorable-run selection.

    Input order, repetition order 1..3, and frozen POLICIES order are fixed.
    Model/signature preprocessing is timed once per problem and shared by all
    fifteen constructions. The caller supplies the 40 frozen p0 evaluation
    problems after freezing; development tests supply only existing dev inputs.
    """
    rows, preprocessing = [], []
    problem_ids = set()
    for problem in problems:
        problem_id = problem["problem_id"]
        if problem_id in problem_ids:
            raise ValueError("duplicate timing problem")
        problem_ids.add(problem_id)
        shared = _blank_timings(("model_validation_and_signature_preprocessing",))
        with _measure(shared, "model_validation_and_signature_preprocessing"):
            model = Model(problem)
        preprocessing.append({"problem_id": problem_id, "timing": shared,
                              "world_count": len(model.worlds),
                              "signature_count": len(model.signature_cells)})
        original_pin = model_state_pin(model)
        for repetition in range(1, REPETITIONS + 1):
            for policy in POLICIES:
                if model_state_pin(model) != original_pin:
                    raise ValueError("shared model changed before next timing construction")
                row = measure_construction(model, policy, planner_factory=planner_factory)
                row.update(problem_id=problem_id, stratum=problem["stratum"], repetition=repetition)
                rows.append(row)
    grouped = defaultdict(list)
    if not problem_ids:
        raise ValueError("timing requires at least one frozen problem")
    for row in rows:
        grouped[row["stratum"], row["policy"]].append(row)
        grouped["all", row["policy"]].append(row)
    summary = []
    for (stratum, policy), group in sorted(grouped.items()):
        completed = [row for row in group if row["status"] == "completed"]
        summary.append({
            "stratum": stratum, "policy": policy,
            "recorded_repetitions": len(group), "completed_repetitions": len(completed),
            "capped_repetitions": sum(r["status"] == "capped" for r in group),
            "failed_repetitions": sum(r["status"] == "failed" for r in group),
            "problem_count": len({row["problem_id"] for row in group}),
            "mean_planning_cpu_seconds": mean(r["planning_cpu_seconds"] for r in completed)
            if len(completed) == len(group) else None,
            "mean_planning_wall_seconds": mean(r["planning_wall_seconds"] for r in completed)
            if len(completed) == len(group) else None,
            "mean_solver_states": mean(r["solver_states"] for r in completed)
            if len(completed) == len(group) else None,
            "mean_decision_count": mean(r["decision_count"] for r in completed)
            if len(completed) == len(group) else None,
        })
    repeated = defaultdict(list)
    for row in rows:
        repeated[row["problem_id"], row["policy"]].append(row)
    return {
        "schema_version": 1,
        "scope": "complete reachable policy construction from initial history; original prior only",
        "repetitions": REPETITIONS, "policy_order": list(POLICIES),
        "problem_count": len(problem_ids), "recorded_constructions": len(rows),
        "cache_rule": "fresh planner per policy/problem/repetition; shared only within its DFS",
        "clock_sources": {"cpu": "process_time_ns", "wall": "perf_counter_ns"},
        "model_preprocessing": preprocessing,
        "rows": rows, "summary": summary,
        "all_repetitions_completed": all(row["status"] == "completed" for row in rows),
        "all_three_repetitions_recorded": all(len(group) == REPETITIONS for group in repeated.values()),
        "completed_repetition_workloads_agree": all(
            len({row["workload_sha256"] for row in group if row["status"] == "completed"}) <= 1
            for group in repeated.values()
        ),
        "limitations": [
            "Cold-cache local runtime, not deployment latency or a scalability result.",
            "Leaf counts and certificate checking work differ with the constructed policy tree.",
            "Certificate verification includes any model reconstruction performed by the existing checker.",
            "All three repetitions are retained; no minimum or favorable run replaces them.",
            "No conversion between seconds and abstract retrieval costs is supplied.",
            "Shared-model hash checks outside constructions are driver overhead, not planner time.",
        ],
    }
