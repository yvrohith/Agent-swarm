"""Read-only scope and extrema checks over the completed chronology artifacts.

This diagnostic does not import or execute the simulator, retiming implementation,
investigators, or scorers. It checks retained primitive records and score arithmetic.
"""

import argparse
import copy
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("studies/chronology_consistency")
METRICS = (
    "predicted_edges", "true_positive_edges", "false_positive_edges",
    "false_negative_edges", "precision", "recall", "f1",
    "false_positive_targets", "false_negative_targets", "signed_error",
    "absolute_error", "target_disagreement",
)
GROUP_KEYS = (
    "cohort", "transmission_probability", "shock_strength", "method", "regime",
    "profile", "retention", "policy",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pin(root, name, pins):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), "Frozen dependency path escape")
    require(name in pins, f"Missing original dependency pin: {name}")
    require(digest(path) == pins[name], f"Frozen computational dependency changed: {name}")
    return pins[name]


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    return json.loads(data, object_pairs_hook=unique)


def index_unique(records, field):
    result = {record[field]: record for record in records}
    require(len(result) == len(records), f"Duplicate {field}")
    return result


def close(a, b):
    return a == b if a is None or b is None else math.isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)


def inspect_trace(trace, changes):
    """Check stage order, captured state, and the previously saved correction."""
    world = trace["world"]
    writes = index_unique(world["writes"], "event_id")
    snaps = index_unique(trace["snapshots"], "write_event_id")
    require(set(writes) == set(snaps), "Incomplete decision trace")
    chains = index_unique(trace["chains"], "request_id")
    records = {name: index_unique(world[name], "request_id")
               for name in ("requests", "deliveries", "contexts")}
    require(set(chains) == set(records["requests"]), "Incomplete request-chain ownership")
    require(set(records["contexts"]) <= set(records["deliveries"]) <= set(chains),
            "Receipt stages missing upstream identity")
    require(trace["instrumented_equals_uninstrumented"], "Instrumented World mismatch")
    rng = trace["rng_evidence"]
    require(rng["detailed_trace"] == rng["profile_only_reference"], "Saved RNG evidence differs")
    require(rng["final_rng_state_and_primitive_calls_match"] and rng["ordinary_world_has_no_hooks"],
            "RNG parity evidence missing")
    state = defaultdict(set)
    derived_truth = set()
    per_run = defaultdict(list)
    for snapshot in sorted(snaps.values(), key=lambda x: x["generation_index"]):
        target = writes[snapshot["write_event_id"]]
        require(target["timestamp"] == snapshot["timestamp"] and target["run_id"] == snapshot["run_id"],
                "Snapshot target differs from preserved write")
        run = snapshot["run_id"]
        owned = [q for q in snapshot["request_ids_created"]]
        for q in owned:
            chain = chains[q]
            require(chain["owner_write_id"] == target["event_id"]
                    and chain["generation_index"] == snapshot["generation_index"]
                    and chain["recipient_run_id"] == run, "Invalid chain owner")
            source = chain["source_event_id"]
            require(chain["has_context"] == (q in records["contexts"])
                    and chain["has_delivery"] == (q in records["deliveries"]), "Stage flags differ")
            if q in records["contexts"]:
                require(chain["first_installation"] == (source not in state[run]),
                        "First-context provenance differs")
                state[run].add(source)
        require(set(snapshot["context_request_ids_created"]) ==
                {q for q in owned if q in records["contexts"]}, "Created-context list differs")
        require(state[run] == set(snapshot["available_source_ids"]), "Captured availability differs from owner installs")
        selected = snapshot["selected_source_id"]
        if selected is not None and writes[selected]["run_id"] != run:
            require(selected in state[run], "Selected cross-run source unavailable in captured state")
            derived_truth.add((selected, target["event_id"]))
        per_run[run].append(snapshot)
    require(derived_truth == set(map(tuple, world["truth_edges"])), "Truth differs from captured selections")
    require(set(world["eligible_target_ids"]) == set(writes), "Eligible-target denominator differs")
    require(sum(len(x["request_ids_created"]) for x in snaps.values()) == len(chains), "Duplicate or unowned request")

    # A source/request/delivery/context chain can be correctly ordered while a
    # complete log incorrectly suggests availability at an earlier decision.
    inflight_pairs = 0
    stage_chains = 0
    bad_chains = {}
    for q, chain in chains.items():
        source = writes[chain["source_event_id"]]
        owner = writes[chain["owner_write_id"]]
        stages = [source["timestamp"], records["requests"][q]["timestamp"]]
        for name in ("deliveries", "contexts"):
            if q in records[name]:
                receipt = records[name][q]
                require(receipt["run_id"] == chain["recipient_run_id"]
                        and receipt["source_event_id"] == source["event_id"], "Receipt identity differs")
                stages.append(receipt["timestamp"])
        stages.append(owner["timestamp"])
        require(all(a < b for a, b in zip(stages, stages[1:])), "Legacy receipt-stage order violated")
        stage_chains += 1
        if q not in records["contexts"]:
            continue
        context_time = records["contexts"][q]["timestamp"]
        contradictions = []
        for snap in per_run[chain["recipient_run_id"]]:
            t = snap["timestamp"]
            if stages[1] < t <= context_time and source["event_id"] not in snap["available_source_ids"]:
                inflight_pairs += 1
            if context_time < t and source["event_id"] not in snap["available_source_ids"]:
                contradictions.append(snap["write_event_id"])
        if contradictions:
            bad_chains[q] = contradictions
    replacements = index_unique(changes, "request_id")
    require(set(replacements) == set(bad_chains), "Saved correction is not exactly the offending chains")
    corrected = copy.deepcopy(world)
    corrected_records = {name: index_unique(corrected[name], "request_id") for name in records}
    for q, change in replacements.items():
        chain = chains[q]
        owner = writes[chain["owner_write_id"]]
        previous = [s for s in per_run[chain["recipient_run_id"]] if s["timestamp"] < owner["timestamp"]]
        previous = max(previous, key=lambda s: s["timestamp"]) if previous else None
        lower = max(writes[chain["source_event_id"]]["timestamp"],
                    previous["timestamp"] if previous else -math.inf)
        expected = [lower + (owner["timestamp"] - lower) * fraction for fraction in (0.25, 0.5, 0.75)]
        require(change["new_timestamps"] == expected and change["lower_bound"] == lower,
                "Saved correction differs from frozen quarter rule")
        require(change["contradicted_write_ids"] == bad_chains[q], "Saved contradicted writes differ")
        require(lower < expected[0] < expected[1] < expected[2] < owner["timestamp"],
                "Corrected stages violate open timing bounds")
        for idx, name in enumerate(records):
            require(change["old_timestamps"][idx] == records[name][q]["timestamp"], "Saved old timestamp differs")
            corrected_records[name][q]["timestamp"] = expected[idx]
    for name in records:
        corrected[name].sort(key=lambda r: r["timestamp"])
        for q, record in corrected_records[name].items():
            require({k: v for k, v in record.items() if k != "timestamp"} ==
                    {k: v for k, v in records[name][q].items() if k != "timestamp"},
                    "Non-time record field changed")
    for name in ("config", "writes", "eligible_target_ids", "truth_edges"):
        require(corrected[name] == world[name], f"Preserved field changed: {name}")
    affected_writes = 0
    extra_pairs = 0
    missing_pairs = 0
    corrected_disagreements = 0
    for snap in snaps.values():
        captured = set(snap["available_source_ids"])
        for label, candidate in (("legacy", world), ("corrected", corrected)):
            available = {c["source_event_id"] for c in candidate["contexts"]
                         if c["run_id"] == snap["run_id"] and c["timestamp"] < snap["timestamp"]}
            if label == "legacy":
                affected_writes += available != captured
                extra_pairs += len(available - captured)
                missing_pairs += len(captured - available)
            else:
                corrected_disagreements += available != captured
    require(corrected_disagreements == 0, "Corrected availability differs at a write")
    return {
        "writes_checked": len(writes), "request_chains_checked": stage_chains,
        "receipt_stage_order_violations": 0, "corrected_availability_disagreements": 0,
        "legacy_affected_writes": affected_writes, "legacy_extra_source_decisions": extra_pairs,
        "legacy_missing_source_decisions": missing_pairs, "offending_context_chains": len(bad_chains),
        "first_contexts": sum(c["first_installation"] is True for c in chains.values()),
        "offending_first_contexts": sum(chains[q]["first_installation"] is True for q in bad_chains),
        "offending_repeat_contexts": sum(chains[q]["first_installation"] is False for q in bad_chains),
        "legitimate_inflight_request_write_pairs": inflight_pairs,
        "saved_rng_evidence_matches": True, "captured_source_selections_match_truth": True,
        "immutable_world_fields_preserved": True,
    }


def identity(row, world=True):
    return {k: row[k] for k in (*GROUP_KEYS, *(("world_id", "seed", "mask_seed") if world else ())) if k in row}


def extrema(rows, grouped=False):
    """Retain exact extrema and one deterministic witness; null is not zero."""
    result = {}
    for metric in METRICS:
        values = [(r["metrics"][metric]["corrected_minus_legacy"]["mean"] if grouped
                   else r["corrected_minus_legacy"][metric], r) for r in rows]
        defined = [(v, r) for v, r in values if v is not None]
        detail = {"total_rows": len(rows), "defined_rows": len(defined),
                  "undefined_rows": len(values) - len(defined)}
        if defined:
            low = min(defined, key=lambda x: x[0])
            high = max(defined, key=lambda x: x[0])
            largest = max(defined, key=lambda x: abs(x[0]))
            detail.update(minimum_delta=low[0], maximum_delta=high[0], maximum_absolute_delta=abs(largest[0]),
                          minimum_witness=identity(low[1], not grouped),
                          maximum_witness=identity(high[1], not grouped),
                          maximum_absolute_witness=identity(largest[1], not grouped),
                          decreases=sum(v < 0 for v, _ in defined), increases=sum(v > 0 for v, _ in defined),
                          unchanged=sum(v == 0 for v, _ in defined))
        else:
            detail.update(minimum_delta=None, maximum_delta=None, maximum_absolute_delta=None)
        result[metric] = detail
    return result


def check_impact(impact, world_ids):
    rows = impact["per_world_impact"]
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        key = tuple(identity(row).items())
        require(key not in seen, "Duplicate evaluation identity")
        seen.add(key)
        require(row["world_id"] in world_ids, "Evaluation refers to unknown World")
        require(row["legacy_available"] and not row["unavailable_reasons"], "Unavailable retained evaluation")
        for metric, delta in row["corrected_minus_legacy"].items():
            before, after = row["legacy"][metric], row["corrected"][metric]
            expected = None if before is None or after is None else after - before
            require(close(delta, expected), f"Saved paired delta differs: {metric}")
        for side in ("legacy", "corrected"):
            score = row[side]
            n, fp, fn = score["eligible_targets"], score["false_positive_targets"], score["false_negative_targets"]
            require(close(score["signed_error"], (fp - fn) / n), "Target signed-error identity differs")
            require(close(score["absolute_error"], abs(score["signed_error"])), "Absolute error differs")
            require(close(score["target_disagreement"], (fp + fn) / n), "Target disagreement differs")
        groups[tuple(row.get(k) for k in GROUP_KEYS)].append(row)
    saved_groups = impact["per_scenario_impact"]
    require(len(saved_groups) == len(groups), "Scenario-group count differs")
    for group in saved_groups:
        group_rows = groups.pop(tuple(group.get(k) for k in GROUP_KEYS))
        require(group["n_unavailable_worlds"] == group["n_unreproduced_worlds"] == 0,
                "Unavailable or unreproduced scenario group")
        require(group["n_worlds"] == len(group_rows), "Group denominator differs")
        require(set(group["world_ids"]) == {r["world_id"] for r in group_rows}, "Group World identities differ")
        for metric, tables in group["metrics"].items():
            for side, table in tables.items():
                values = [r[side][metric] for r in group_rows if r[side][metric] is not None]
                require(table["n_defined_worlds"] == len(values) and
                        close(table["mean"], mean(values) if values else None), "Group aggregation differs")
    require(not groups, "Unreported scenario group")
    for mask in impact["mask_audit"]:
        for channel in mask["channels"].values():
            require(channel["legacy_retained_ids"] == channel["corrected_retained_ids"], "Mask survivor identities differ")
            require(channel["membership_equal"] and channel["actual_retention_equal"], "Mask equality flag failed")


def run(root=ROOT):
    study = root / SOURCE
    result_dir = study / "results"
    manifest = load(result_dir / "manifest.json")
    dependencies = {}
    for name, expected in manifest["files_sha256"].items():
        path = (result_dir / name).resolve()
        require(path.is_relative_to(result_dir.resolve()), "Result manifest path escape")
        require(digest(path) == expected, f"Saved result bytes differ: {name}")
        dependencies[str(path.relative_to(root))] = expected
    require(digest(study / "freeze.json") == manifest["freeze_sha256"], "Completed chronology freeze changed")
    frozen = load(study / "freeze.json")["files_sha256"]
    # This additive diagnostic binds numerical inputs and the original source
    # authority, without requiring unrelated presentation bytes or ignored local
    # preservation files. It does not execute those scientific implementations.
    material = {name for name in frozen if name.endswith(".py")}
    material.update(str(SOURCE / name) for name in ("inputs.json", "development_checks.json", "config.json"))
    material.update(("results/benchmark.json", "studies/missing_receipts/config.json",
                     "studies/missing_receipts/results/config.json", "studies/missing_receipts/results/study.json",
                     "studies/review_remediation/chronology.json"))
    for name in sorted(material):
        dependencies[name] = check_pin(root, name, frozen)
    for name in ("freeze.json", "inputs.json", "development_checks.json", "results/manifest.json"):
        dependencies[str(SOURCE / name)] = digest(study / name)
    saved_worlds = load(result_dir / "worlds.json.gz")
    inputs = load(study / "inputs.json")["configuration_manifest"]["configurations"]
    declared = index_unique(inputs, "configuration_id")
    worlds = index_unique(saved_worlds, "configuration_id")
    require(set(declared) == set(worlds), "Saved World/configuration scope mismatch")
    rows = []
    for world_id, saved in worlds.items():
        require(saved["correction_available"], "Completed correction unavailable")
        require(saved["trace"]["world"]["config"] == declared[world_id]["config"], "Saved configuration differs")
        cohorts = [o["cohort"] for o in declared[world_id]["origins"]]
        require(len(cohorts) == 1, "Unexpected duplicated cohort World")
        rows.append({"configuration_id": world_id, "cohort": cohorts[0],
                     "config": declared[world_id]["config"],
                     **inspect_trace(saved["trace"], saved["retiming_changes"])})
    dev = load(study / "development_checks.json")
    development = inspect_trace(dev["trace"], dev["retiming"])
    require(development["writes_checked"] == 6 and development["legacy_affected_writes"] == 1,
            "Saved six-write counterexample differs")
    impact = load(result_dir / "impact.json.gz")
    check_impact(impact, set(worlds))
    summaries = []
    for cohort in ("benchmark", "missing_receipts"):
        for shock in sorted({r["config"]["shock_strength"] for r in rows if r["cohort"] == cohort}):
            subset = [r for r in rows if r["cohort"] == cohort and r["config"]["shock_strength"] == shock]
            summaries.append({"cohort": cohort, "shock_strength": shock, "configurations": len(subset),
                              "affected_configurations": sum(r["legacy_affected_writes"] > 0 for r in subset),
                              **{k: sum(r[k] for r in subset) for k in development if isinstance(development[k], int)
                                 and not isinstance(development[k], bool)}})
    metrics = {}
    for cohort in ("benchmark", "missing_receipts"):
        world_rows = [r for r in impact["per_world_impact"] if r["cohort"] == cohort]
        grouped_rows = [r for r in impact["per_scenario_impact"] if r["cohort"] == cohort]
        metrics[cohort] = {"per_evaluation": extrema(world_rows), "per_condition_mean": extrema(grouped_rows, True),
                           "evaluation_count": len(world_rows), "condition_count": len(grouped_rows),
                           "changed_evaluations": sum(bool(r["changed_metrics"]) for r in world_rows),
                           "worlds_with_changed_evaluations": len({r["world_id"] for r in world_rows if r["changed_metrics"]})}
    per_world_maxima = []
    for row in rows:
        items = [r for r in impact["per_world_impact"] if r["world_id"] == row["configuration_id"]]
        per_world_maxima.append({"configuration_id": row["configuration_id"], "cohort": row["cohort"],
                                "metrics": {k: v["maximum_absolute_delta"] for k, v in extrema(items).items()}})
    return {"schema_version": 1, "status": "verified", "source": "completed retained chronology artifacts",
            "scope": "Supplementary read-only diagnostic; no generator, correction, investigator, or score execution",
            "source_sha256": dependencies, "development_counterexample": development,
            "dependency_scope": "Retained result manifest plus original freeze pins for source .py files, full configurations, original numerical cohorts, retained trace inputs and six-write diagnostic; no private preservation or presentation-byte gate",
            "scope_by_shock": summaries, "worlds": rows, "impact_extrema": metrics,
            "per_world_maximum_absolute_changes": per_world_maxima,
            "unavailable_configurations": 0, "unavailable_evaluations": 0,
            "mask_records_checked": len(impact["mask_audit"]),
            "limits": ["Recorded trace/RNG parity evidence is checked, not regenerated in this correction pass.",
                       "Stage ordering alone does not establish decision-time availability.",
                       "A request before a write can be legitimately in flight; no run-start event is inferred.",
                       "State-preserving timing consistency does not establish physical realism.",
                       "No additional configurations or independent finite/model studies were evaluated."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Create a new result; refuses overwrite")
    parser.add_argument("--verify", type=Path, help="Compare retained diagnostic with a fresh saved-data check")
    args = parser.parse_args()
    require(not (args.output and args.verify), "Choose output or verify")
    result = run()
    if args.output:
        with args.output.open("x") as stream:
            json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    if args.verify:
        require(load(args.verify) == result, "Retained chronology-scope diagnostic differs")
    print(json.dumps({"status": result["status"], "configurations": len(result["worlds"]),
                      "scope_by_shock": result["scope_by_shock"]}, sort_keys=True))


if __name__ == "__main__":
    main()
