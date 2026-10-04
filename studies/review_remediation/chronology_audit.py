"""Read-only line tracing of legacy generation; preserve its RNG and outputs."""

import hashlib
import inspect
import json
import sys
from dataclasses import asdict
from pathlib import Path

from tracebench.model import SimulationConfig
from tracebench.simulate import simulate

ROOT = Path(__file__).resolve().parents[2]


def canonical_world(world):
    value = asdict(world)
    value["truth_edges"] = sorted(value["truth_edges"])
    value["eligible_target_ids"] = sorted(value["eligible_target_ids"])
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def audit_world(config):
    """Trace state at the actual selection point without adding RNG draws."""
    lines, first_line = inspect.getsourcelines(simulate)
    selection_lines = [first_line + offset for offset, text in enumerate(lines)
                       if text.strip() == "selected = None"]
    if len(selection_lines) != 1:
        raise ValueError("Expected unique legacy selection entry; inspect changed source")
    selection_line = selection_lines[0]
    snapshots, installations = [], []
    first_installations = {}
    context_count = 0

    def trace(frame, event, arg):
        nonlocal context_count
        if frame.f_code is not simulate.__code__:
            return None
        if event == "line" and frame.f_lineno == selection_line:
            local = frame.f_locals
            run = local["run_id"]
            snapshot = {"write_event_id": local["event_id"], "timestamp": local["timestamp"],
                        "run_id": run,
                        "available_source_ids": sorted(local["available_context"].get(run, {}))}
            snapshots.append(snapshot)
            for receipt in local["contexts"][context_count:]:
                pair = (receipt.run_id, receipt.source_event_id)
                if pair not in first_installations:
                    record = {"context": asdict(receipt),
                              "installed_during_write": dict(snapshot),
                              "installation_generation_index": local["index"]}
                    first_installations[pair] = record
                    installations.append(record)
            context_count = len(local["contexts"])
        return trace

    if sys.gettrace() is not None:
        raise RuntimeError("Do not replace an existing trace hook")
    try:
        sys.settrace(trace)
        traced = simulate(config)
    finally:
        sys.settrace(None)
    untraced = simulate(config)
    if traced != untraced:
        raise AssertionError("Instrumentation changed simulator outputs")
    writes = {w.event_id: w for w in traced.writes}
    requests = {r.request_id: r for r in traced.requests}
    deliveries = {d.request_id: d for d in traced.deliveries}
    snapshot_by_id = {s["write_event_id"]: s for s in snapshots}
    violations = []
    ordinary_order_violations = []
    for installed in installations:
        context = installed["context"]
        source = writes[context["source_event_id"]]
        request = requests[context["request_id"]]
        delivery = deliveries[context["request_id"]]
        current = installed["installed_during_write"]
        if not (source.timestamp < request.timestamp < delivery.timestamp
                < context["timestamp"] < current["timestamp"]):
            ordinary_order_violations.append(context["request_id"])
        # First source/run installation only. A later duplicate is not evidence
        # of absent prior availability; the snapshot independently checks absence.
        prior = [w for w in traced.writes if w.run_id == context["run_id"]
                 and context["timestamp"] < w.timestamp < current["timestamp"]]
        for earlier in prior:
            state = snapshot_by_id[earlier.event_id]
            if source.event_id in state["available_source_ids"]:
                raise AssertionError("First-installation witness unexpectedly already available")
            violations.append({
                "source_event_id": source.event_id, "source_run_id": source.run_id,
                "source_timestamp": source.timestamp, "recipient_run_id": context["run_id"],
                "request_id": context["request_id"], "request_timestamp": request.timestamp,
                "delivery_timestamp": delivery.timestamp, "context_timestamp": context["timestamp"],
                "earlier_recipient_write": asdict(earlier),
                "earlier_selection_available_sources": state["available_source_ids"],
                "installed_during_write_id": current["write_event_id"],
                "installed_during_write_timestamp": current["timestamp"],
                "installation_generation_index": installed["installation_generation_index"],
                "first_source_run_installation": True,
                "all_contexts_for_source_run": [asdict(c) for c in traced.contexts
                                               if c.run_id == context["run_id"]
                                               and c.source_event_id == source.event_id],
                "first_available_context_timestamp": context["timestamp"],
                "ordinary_chain_order_passes": source.timestamp < request.timestamp
                     < delivery.timestamp < context["timestamp"] < current["timestamp"],
                "contradiction": "The retained first context receipt precedes a recipient write "
                    "whose actual selection-state snapshot lacked this source. State was first "
                    "installed while generating the later write, after that earlier decision.",
            })
    return {"config": asdict(config), "instrumented_equals_uninstrumented": True,
            "world_sha256": hashlib.sha256(canonical_world(traced).encode()).hexdigest(),
            "writes_checked": len(snapshots), "context_records": len(traced.contexts),
            "distinct_first_source_run_installations": len(installations),
            "ordinary_chain_order_violations": ordinary_order_violations,
            "violating_prior_decisions": len(violations),
            "violating_first_installations": len({(v["source_event_id"], v["recipient_run_id"])
                                                  for v in violations}),
            "violations": violations}


def main():
    benchmark = json.loads((ROOT / "results/benchmark.json").read_text())["metadata"]
    baseline = benchmark["default_generator_config"]
    missing = json.loads((ROOT / "studies/missing_receipts/config.json").read_text())
    configurations = [("original", SimulationConfig(**{**baseline, "seed": seed,
                       "transmission_probability": 0.3, "shock_strength": 0.9}))
                      for seed in benchmark["seeds"]]
    configurations += [("missing_receipts", SimulationConfig(**{
        **baseline, "seed": seed, "transmission_probability": probability,
        "shock_strength": 0.9, "n_runs": missing["n_runs"],
        "writes_per_run": missing["writes_per_run"]}))
        for probability in missing["transmission_probabilities"] for seed in missing["world_seeds"]]
    # A six-write supported configuration is a deterministic regression example,
    # not a new scientific grid or a replacement for a published scenario.
    configurations.append(("minimal_diagnostic", SimulationConfig(
        seed=0, n_runs=2, n_task_families=1, writes_per_run=3, shock_strength=0.0)))
    worlds = [{"published_cohort": cohort, **audit_world(config)}
              for cohort, config in configurations]
    inputs = ["src/tracebench/model.py", "src/tracebench/simulate.py", "src/tracebench/observe.py",
              "src/tracebench/estimators.py", "src/tracebench/evaluate.py",
              "results/benchmark.json", "studies/missing_receipts/config.json"]
    output = {
        "status": "verified" if any(w["violations"] for w in worlds) else "not_supported",
        "method": "Read-only sys.settrace snapshots at the original generator's selection entry; "
                  "no source edits, no injected RNG calls. Each traced World equals an "
                  "independent uninstrumented call using the identical configuration.",
        "run_start_semantics": "The schedule samples a local start variable to place writes; "
            "World has no run-start event, available-from timestamp, or constraint forbidding "
            "receipts before the first write. No run start was invented from the first write.",
        "tested_worlds": len(worlds), "worlds_with_first_availability_contradiction":
            sum(bool(w["violations"]) for w in worlds),
        "ordinary_chain_order_violations": sum(len(w["ordinary_chain_order_violations"]) for w in worlds),
        "first_availability_contradictions": sum(w["violating_first_installations"] for w in worlds),
        "prior_selection_decisions_affected": sum(w["violating_prior_decisions"] for w in worlds),
        "worlds": worlds,
        "inputs_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs},
        "scope": "The supported six-write configuration demonstrates a legacy simulator "
            "timestamp/state inconsistency. The original benchmark and missing-receipt "
            "follow-up use this generator, so blanket chronological replay fidelity is "
            "unsupported. No first-context-availability contradiction was found in the "
            "tested 12 original high-shock worlds or 40 missing-receipt worlds; other "
            "published scenarios were not tested. Ordinary chain order can remain valid "
            "while state availability contradicts declared timestamps.",
        "estimate_impact": "Not measured. This audit neither patches generation nor computes "
            "counterfactual corrected historical scores. Preserved numerical results remain "
            "results of the legacy generator, conditional on its stated source-selection mechanism.",
        "unaffected_scope": "The real wiki export/reference analysis, utility and responsiveness "
            "finite constructed receipt cases, saved model outputs/scoring, and offline failure "
            "audit are not invalidated merely by repository proximity; their results do not "
            "depend on replaying simulate() histories.",
        "phase_b_isolation": "Independent finite event/archive model must not import or reuse "
            "simulate() histories; it must enforce its own event-time/state invariants. This "
            "bounded legacy audit does not block that independent implementation.",
        "correction_policy": "Legacy source/results unchanged. A material simulator correction "
            "requires separately versioned generation and evaluation before replacing numbers.",
    }
    path = Path(__file__).with_name("chronology.json")
    with path.open("x") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({k: v for k, v in output.items() if k in (
        "status", "tested_worlds", "worlds_with_first_availability_contradiction",
        "ordinary_chain_order_violations", "first_availability_contradictions",
        "prior_selection_decisions_affected")}, indent=2))
    example = next((w["violations"][0] for w in worlds if w["violations"]), None)
    print(json.dumps({"first_example": example}, indent=2))


if __name__ == "__main__":
    main()
