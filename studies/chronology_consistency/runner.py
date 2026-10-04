"""Freeze, execute and verify the fixed offline chronology sensitivity."""

import argparse
import gzip
import hashlib
import json
import platform
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from tracebench.model import ContextEntry, Delivery, Request, SimulationConfig, World, Write

from .analysis import (
    evaluate_benchmark_world,
    evaluate_receipt_world,
    finalize_impact,
    unavailable_world_result,
)
from .inputs import build_input_manifest, load_json_strict, verify_input_manifest
from .reference import audit_availability, verify_retiming
from .retime import retime_world
from .trace import CapturedTrace, ChainInstallation, DecisionSnapshot, trace_world, world_sha256

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/chronology_consistency"


def normalize(value):
    if hasattr(value, "__dataclass_fields__"):
        return normalize(asdict(value))
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [normalize(v) for v in sorted(value)]
    if isinstance(value, (tuple, list)):
        return [normalize(v) for v in value]
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    payload = (json.dumps(normalize(value), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    path = Path(path)
    if path.suffix == ".gz":
        payload = gzip.compress(payload, mtime=0)
    with path.open("xb") as stream:
        stream.write(payload)


def read(path):
    path = Path(path)
    return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == ".gz" else load_json_strict(path)


def verify_preservation():
    saved = read(STUDY / "preservation.json")
    for name, expected in {**saved["tracked_sha256"], **saved["local_sha256"]}.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Historical preservation mismatch: {name}")
    return {"tracked_files": len(saved["tracked_sha256"]), "historical_local_files": len(saved["local_sha256"])}


def dependencies():
    inputs = read(STUDY / "inputs.json")
    paths = {entry["path"] for entry in inputs["artifacts"] + inputs["dependencies"]}
    paths.update(str(p.relative_to(ROOT)) for p in STUDY.glob("*.py"))
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_chronology_*.py"))
    paths.update("studies/chronology_consistency/" + name for name in (
        "inputs.json", "config.json", "preservation.json", "ISOLATION.json", "ANALYSIS.md", "METHOD.md",
        "development_checks.json", "pre_freeze_checks.json"))
    return sorted(paths)


def settings():
    config = read(STUDY / "config.json")
    expected = {"study_type": "review-informed correction sensitivity", "correction_version": "offending-chain-quarter-retiming-v1",
                "mask_coupling": "legacy-selection-stable-physical-record-identity-v1", "network_requests": 0,
                "model_calls": 0, "additional_spend_usd": "0", "new_configurations": 0,
                "availability_convention": "context.timestamp < write.timestamp", "expected_unique_configurations": 184}
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("Configuration departs from the fixed correction sensitivity")
    return config


def prepare_inputs():
    if (STUDY / "inputs.json").exists() or (STUDY / "freeze.json").exists():
        raise ValueError("Refusing to replace retained or frozen inputs")
    manifest = build_input_manifest(ROOT)
    if manifest["configuration_manifest"]["distinct_configuration_count"] != 184:
        raise ValueError("Published complete configuration count differs; inspect the mismatch")
    write_new(STUDY / "inputs.json", manifest)
    return manifest["configuration_manifest"]["cohorts"]


def qualify_development():
    settings()
    if (STUDY / "development_checks.json").exists() or (STUDY / "freeze.json").exists():
        raise ValueError("Refusing to replace development or frozen evidence")
    saved = next(w for w in read(ROOT / "studies/review_remediation/chronology.json")["worlds"]
                 if w["published_cohort"] == "minimal_diagnostic")
    sources = {name: digest(ROOT / name) for name in dependencies()
               if Path(name).name not in ("development_checks.json", "pre_freeze_checks.json")}
    captured = trace_world(SimulationConfig(**saved["config"]))
    if world_sha256(captured.world) != saved["world_sha256"]:
        raise ValueError("Known diagnostic World no longer reproduces")
    before = audit_availability(captured.world, captured)
    repaired = retime_world(captured)
    checked = verify_retiming(captured.world, repaired.world, captured)
    if before["affected_writes"] != 1 or before["offending_chain_ids"] != ["q000001"]:
        raise ValueError("Known six-write contradiction did not reproduce")
    if any(digest(ROOT / name) != expected for name, expected in sources.items()):
        raise ValueError("Source changed during development qualification")
    result = {"status": "passed", "new_published_sensitivity_outcomes_observed": 0,
              "config": saved["config"], "legacy_world_sha256": world_sha256(captured.world),
              "corrected_world_sha256": world_sha256(repaired.world), "trace": captured,
              "legacy_audit": before, "retiming": repaired.changes, "independent_check": checked,
              "source_sha256": sources, "preservation": verify_preservation()}
    write_new(STUDY / "development_checks.json", result)
    return {"status": "passed", "writes": len(captured.world.writes), "corrected_chains": len(repaired.changes)}


def freeze():
    settings()
    verify_input_manifest(ROOT, read(STUDY / "inputs.json"))
    for name in ("development_checks.json", "pre_freeze_checks.json"):
        check = read(STUDY / name)
        if check.get("status") != "passed" or check.get("new_published_sensitivity_outcomes_observed") != 0:
            raise ValueError("Pre-outcome qualification is missing or failed")
    dev = read(STUDY / "development_checks.json")
    expected = set(dependencies()) - {"studies/chronology_consistency/" + name for name in
                                      ("development_checks.json", "pre_freeze_checks.json")}
    if set(dev["source_sha256"]) != expected:
        raise ValueError("Development source scope differs from freeze")
    for name, value in dev["source_sha256"].items():
        if digest(ROOT / name) != value:
            raise ValueError("Sources changed after development qualification")
    write_new(STUDY / "freeze.json", {"schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(), "new_published_sensitivity_outcomes_observed": 0,
        "known_historical_outcomes_and_diagnostic": True, "files_sha256": {p: digest(ROOT / p) for p in dependencies()},
        "preservation": verify_preservation()})
    return {"status": "frozen", "dependencies": verify_freeze()}


def verify_freeze():
    saved = read(STUDY / "freeze.json")
    if set(saved["files_sha256"]) != set(dependencies()):
        raise ValueError("Frozen dependency set differs")
    for name, expected in saved["files_sha256"].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"Frozen dependency changed: {name}")
    settings()
    verify_input_manifest(ROOT, read(STUDY / "inputs.json"))
    return len(saved["files_sha256"])


def decode_trace(value):
    obj = value["world"]
    writes = tuple(Write(**(w | {"concepts": tuple(w["concepts"]), "witness_tokens": tuple(w["witness_tokens"])})) for w in obj["writes"])
    contexts = tuple(ContextEntry(**(c | {"concepts": tuple(c["concepts"]), "witness_tokens": tuple(c["witness_tokens"])})) for c in obj["contexts"])
    world = World(SimulationConfig(**obj["config"]), writes, tuple(Request(**r) for r in obj["requests"]),
                  tuple(Delivery(**d) for d in obj["deliveries"]), contexts,
                  frozenset(map(tuple, obj["truth_edges"])), frozenset(obj["eligible_target_ids"]))
    snapshots = tuple(DecisionSnapshot(**(s | {key: tuple(s[key]) for key in
        ("available_source_ids", "request_ids_created", "context_request_ids_created")})) for s in value["snapshots"])
    return CapturedTrace(world, snapshots, tuple(ChainInstallation(**c) for c in value["chains"]),
                         value["instrumented_equals_uninstrumented"], value["rng_evidence"])


def reconstruct_corrected(trace, changes):
    times = {c["request_id"]: c["new_timestamps"] for c in changes}
    fields = {name: tuple(sorted((replace(record, timestamp=times[record.request_id][i])
                                 if record.request_id in times else record for record in getattr(trace.world, name)),
                                key=lambda record: record.timestamp))
              for i, name in enumerate(("requests", "deliveries", "contexts"))}
    return replace(trace.world, **fields)


def evaluate_origins(item, trace, corrected, benchmark, receipts, *, failure=None):
    results = []
    for origin in item["origins"]:
        saved = benchmark if origin["cohort"] == "benchmark" else receipts
        rows = [saved["runs"][i] for i in origin["run_indices"]]
        if origin["cohort"] == "benchmark":
            value = evaluate_benchmark_world(trace.world, corrected, rows, failure_reason=failure)
        else:
            value = evaluate_receipt_world(trace.world, corrected, saved["worlds"][origin["saved_world_index"]],
                                           rows, failure_reason=failure)
        results.append({"cohort": origin["cohort"], "result": value})
    return results


def unavailable_origins(item, benchmark, receipts, failure):
    results = []
    for origin in item["origins"]:
        saved = benchmark if origin["cohort"] == "benchmark" else receipts
        saved_world = None if origin["cohort"] == "benchmark" else saved["worlds"][origin["saved_world_index"]]
        value = unavailable_world_result(origin["cohort"], [saved["runs"][i] for i in origin["run_indices"]],
                                         saved_world, item["configuration_id"], failure)
        results.append({"cohort": origin["cohort"], "result": value})
    return results


def _claim_status(old, new, unavailable, old_directions, new_directions):
    if unavailable:
        return "unavailable_due_to_failed_reproduction_or_correction"
    if old == new:
        return "unchanged_on_tested_cohort"
    def signs(values):
        return [None if x is None else (x > 0) - (x < 0) for x in values]
    if any((a is None) != (b is None) for a, b in zip(old_directions, new_directions, strict=True)):
        return "definedness_changed"
    return ("magnitude_changed_direction_retained" if signs(old_directions) == signs(new_directions)
            else "direction_changed")


def claims(impact, audits):
    """Fixed historical claim views; no outcome-selected cohorts."""
    affected = {a["configuration_id"] for a in audits if a.get("legacy_audit", {}).get("affected_writes", 0)}
    original = [g for g in impact["per_scenario_impact"] if "profile" not in g]
    output = []
    scenarios = sorted({(g["transmission_probability"], g["shock_strength"]) for g in original})
    regimes = ("writes", "identity", "requests", "delivery", "context")
    for probability, shock in scenarios:
        chosen = {g["regime"]: g for g in original if g["method"] == "witness" and
                  (g["transmission_probability"], g["shock_strength"]) == (probability, shock)}
        scenario = {"transmission_probability": probability, "shock_strength": shock, "method": "witness"}
        common = {"scenario": scenario, "n_configurations": chosen["writes"]["n_worlds"],
                  "n_affected_configurations": len(affected & set(chosen["writes"]["world_ids"]))}
        for metric in ("precision", "recall"):
            values = {v: {regime: chosen[regime]["metrics"][metric][v]["mean"] for regime in regimes}
                      for v in ("legacy", "corrected")}
            directions = {v: [None if a is None or b is None else b - a
                              for a, b in zip(list(x.values())[:-1], list(x.values())[1:], strict=True)]
                          for v, x in values.items()}
            unavailable = any(chosen[r]["n_unavailable_worlds"] or chosen[r]["status"].startswith("unavailable") for r in regimes)
            output.append(common | {"claim": "witness_" + metric + "_across_telemetry", "source": "results/benchmark.json#/summary",
                "metric": metric, "values": values, "adjacent_telemetry_differences": directions,
                "status": _claim_status(values["legacy"], values["corrected"], unavailable,
                                         directions["legacy"], directions["corrected"])})
        for metric in ("absolute_error", "signed_error", "target_disagreement"):
            values = {v: {regime: chosen[regime]["metrics"][metric][v]["mean"] for regime in ("requests", "context")}
                      for v in ("legacy", "corrected")}
            differences = {v: x["context"] - x["requests"] if None not in x.values() else None for v, x in values.items()}
            unavailable = any(chosen[r]["n_unavailable_worlds"] or chosen[r]["status"].startswith("unavailable") for r in ("requests", "context"))
            output.append(common | {"claim": "requests_to_context_" + metric,
                "source": "results/benchmark.json#/runs; studies/review_remediation/derived_target_errors.json (p=0.3,shock=0.9 only)",
                "values": values, "context_minus_requests": differences,
                "status": _claim_status(values["legacy"], values["corrected"], unavailable,
                                         [differences["legacy"]], [differences["corrected"]])})
    receipt_groups = [g for g in impact["per_scenario_impact"] if "profile" in g]
    pair_keys = ("transmission_probability", "shock_strength", "regime", "profile", "retention", "policy")
    receipts = {}
    for group in receipt_groups:
        receipts.setdefault(tuple(group[k] for k in pair_keys), {})[group["method"]] = group
    metrics = ("precision", "recall", "false_attributed_target_fraction", "false_positive_targets", "false_negative_targets",
               "signed_error", "absolute_error", "target_disagreement", "unresolved_target_fraction")
    for key, methods in sorted(receipts.items()):
        if set(methods) != {"temporal", "witness"}:
            raise ValueError("Investigator comparison lost a fixed method")
        values = {v: {method: {m: methods[method]["metrics"][m][v]["mean"] for m in metrics}
                      for method in ("temporal", "witness")} for v in ("legacy", "corrected")}
        directions = {v: {m: None if x["witness"][m] is None or x["temporal"][m] is None else x["witness"][m] - x["temporal"][m]
                          for m in metrics} for v, x in values.items()}
        unavailable = any(g["n_unavailable_worlds"] or g["status"].startswith("unavailable") for g in methods.values())
        output.append({"claim": "missing_receipt_witness_versus_temporal", "source": "studies/missing_receipts/results/study.json#/summary",
            "scenario": dict(zip(pair_keys, key)), "values": values, "witness_minus_temporal": directions,
            "n_configurations": methods["witness"]["n_worlds"],
            "n_affected_configurations": len(affected & set(methods["witness"]["world_ids"])),
            "status": _claim_status(values["legacy"], values["corrected"], unavailable,
                                     list(directions["legacy"].values()), list(directions["corrected"].values()))})
    for group in impact["policy_group_impact"]:
        values = group["metrics"]
        left = [v["legacy"]["mean"] for v in values.values()]
        right = [v["corrected"]["mean"] for v in values.values()]
        output.append({"claim": "missing_receipt_policy_contrast", "source": "studies/missing_receipts/results/study.json#/paired_summary",
            "scenario": {key: group[key] for key in ("transmission_probability", "shock_strength", "regime", "method", "profile", "retention")},
            "values": values, "n_configurations": group["n_worlds"],
            "n_affected_configurations": len(affected & set(group["world_ids"])),
            "status": _claim_status(left, right, group["n_unavailable_worlds"] or group["status"].startswith("unavailable"), left, right),
            "contrast": "evidence_aware minus conjunction within each version; corrected minus legacy of this contrast"})
    return output


def summarize_chronology(audits, manifest):
    results = []
    for cohort in ("benchmark", "missing_receipts", "all_unique"):
        members = [a for a in audits if cohort == "all_unique" or cohort in a["cohorts"]]
        valid = [a for a in members if "legacy_audit" in a]
        fields = ("writes_checked", "context_records", "request_chains", "distinct_source_run_installations",
                  "repeated_context_receipts", "affected_writes", "offending_chains", "distinct_first_availability_contradictions",
                  "extra_source_decisions", "missing_source_decisions")
        results.append({"cohort": cohort, "configurations": len(members), "audited_configurations": len(valid),
            "expected_configurations": (manifest["distinct_configuration_count"] if cohort == "all_unique" else manifest["cohorts"][cohort]["configuration_count"]),
            "affected_configurations": sum(a["legacy_audit"]["affected_writes"] > 0 for a in valid),
            "unavailable_configurations": sum(a["status"] != "verified" for a in members),
            "totals": {key: sum(a["legacy_audit"][key] for a in valid) for key in fields},
            "maximum_time_discrepancy": max((a["legacy_audit"]["max_time_discrepancy"] for a in valid), default=0),
            "all_worlds_and_rng_unchanged_by_instrumentation": all(a.get("instrumented_equals_uninstrumented", False) for a in members)})
    return results


def execute(output):
    verify_freeze()
    verify_preservation()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    inputs = read(STUDY / "inputs.json")["configuration_manifest"]
    benchmark = read(ROOT / "results/benchmark.json")
    receipts = read(ROOT / "studies/missing_receipts/results/study.json")
    old_audit = read(ROOT / "studies/review_remediation/chronology.json")
    old_pins = {json.dumps(w["config"], sort_keys=True): w["world_sha256"] for w in old_audit["worlds"]}
    records, audits, benchmark_results, receipt_results, failures = [], [], [], [], []
    start = perf_counter()
    for item in inputs["configurations"]:
        identity = item["configuration_id"]
        audit = {"configuration_id": identity, "config": item["config"], "cohorts": sorted({o["cohort"] for o in item["origins"]})}
        trace = None
        try:
            trace = trace_world(SimulationConfig(**item["config"]))
            historical_pin = old_pins.get(json.dumps(item["config"], sort_keys=True))
            if historical_pin is not None and world_sha256(trace.world) != historical_pin:
                raise ValueError("Saved remediation World hash does not reproduce")
            audit.update(legacy_audit=audit_availability(trace.world, trace), instrumented_equals_uninstrumented=True,
                         legacy_world_sha256=world_sha256(trace.world), historical_world_pin_available=historical_pin is not None,
                         historical_world_pin_matches=True if historical_pin else None)
            corrected = None
            correction_error = None
            changes = ()
            try:
                repaired = retime_world(trace)
                audit["independent_retiming_check"] = verify_retiming(trace.world, repaired.world, trace)
                corrected, changes = repaired.world, repaired.changes
                audit.update(status="verified", corrected_world_sha256=world_sha256(corrected),
                             world_byte_values_unchanged=trace.world == corrected)
            except Exception as error:
                correction_error = {"type": type(error).__name__, "message": str(error)}
                audit.update(status="unavailable_due_to_correction_failure", failure=correction_error)
            origin_results = evaluate_origins(item, trace, corrected, benchmark, receipts, failure=correction_error)
            for result in origin_results:
                (benchmark_results if result["cohort"] == "benchmark" else receipt_results).append(result["result"])
            records.append({"configuration_id": identity, "trace": trace, "retiming_changes": changes,
                            "correction_available": corrected is not None, "origin_results": origin_results})
        except Exception as error:
            audit.update(status="unavailable_due_to_failed_reproduction", failure={"type": type(error).__name__, "message": str(error)})
            failures.append({"configuration_id": identity, "failure": audit["failure"]})
            origin_results = unavailable_origins(item, benchmark, receipts, audit["failure"])
            for result in origin_results:
                (benchmark_results if result["cohort"] == "benchmark" else receipt_results).append(result["result"])
            records.append({"configuration_id": identity, "trace": trace, "failure": audit["failure"],
                            "origin_results": origin_results})
        audits.append(audit)
        print(json.dumps({"audited": len(audits), "total": len(inputs["configurations"]), "status": audit["status"]}), flush=True)
    try:
        impact = finalize_impact(benchmark, receipts, benchmark_results, receipt_results)
        claim_rows = claims(impact, audits)
    except Exception as error:
        failures.append({"stage": "aggregation", "failure": {"type": type(error).__name__, "message": str(error)}})
        impact = {"status": "unavailable", "failures": failures, "benchmark_partial": benchmark_results, "receipts_partial": receipt_results}
        claim_rows = []
    chronology = summarize_chronology(audits, inputs)
    for name, value in (("worlds.json.gz", records), ("chronology.json", {"summary": chronology, "worlds": audits}),
                        ("impact.json.gz", impact), ("claims.json", claim_rows)):
        write_new(output / name, value)
    status = ("passed" if not failures and all(a["status"] == "verified" for a in audits)
              and impact.get("counts", {}).get("reproduction_all_matched") else "unavailable_or_failed_results_retained")
    validation = {"status": status, "configurations": len(audits), "chronology": chronology,
                  "impact_counts": impact.get("counts"), "failures": failures, "wall_seconds": perf_counter() - start,
                  "preservation": verify_preservation(), "frozen_dependencies": verify_freeze(),
                  "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
    write_new(output / "validation.json", validation)
    write_new(output / "manifest.json", {"freeze_sha256": digest(STUDY / "freeze.json"),
              "files_sha256": {p.name: digest(p) for p in sorted(output.iterdir())}})
    return validation


def verify_outputs(output):
    """Verify retained worlds/paths without generating another simulator world."""
    verify_freeze()
    output = Path(output)
    manifest = read(output / "manifest.json")
    if manifest["freeze_sha256"] != digest(STUDY / "freeze.json"):
        raise ValueError("Result freeze pin differs")
    for name, expected in manifest["files_sha256"].items():
        if Path(name).name != name or digest(output / name) != expected:
            raise ValueError("Saved result hash differs")
    inputs = read(STUDY / "inputs.json")["configuration_manifest"]
    items = {i["configuration_id"]: i for i in inputs["configurations"]}
    records = read(output / "worlds.json.gz")
    audits = read(output / "chronology.json")["worlds"]
    if len(records) != len(items) or {r["configuration_id"] for r in records} != set(items):
        raise ValueError("Retained world census differs")
    by_id = {a["configuration_id"]: a for a in audits}
    if len(by_id) != len(audits) or set(by_id) != set(items):
        raise ValueError("Retained chronology census differs")
    benchmark, receipts = read(ROOT / "results/benchmark.json"), read(ROOT / "studies/missing_receipts/results/study.json")
    benchmark_results, receipt_results = [], []
    writes_checked = unavailable = 0
    for record in records:
        identity = record["configuration_id"]
        if record.get("failure"):
            unavailable += 1
            reproduced = unavailable_origins(items[identity], benchmark, receipts, record["failure"])
            if normalize(reproduced) != record["origin_results"]:
                raise ValueError("Unavailable saved evaluation grid differs")
            for result in reproduced:
                (benchmark_results if result["cohort"] == "benchmark" else receipt_results).append(result["result"])
            continue
        trace = decode_trace(record["trace"])
        if (not trace.instrumented_equals_uninstrumented
                or not trace.rng_evidence["final_rng_state_and_primitive_calls_match"]
                or trace.rng_evidence["profile_only_reference"] != trace.rng_evidence["detailed_trace"]):
            raise ValueError("Retained instrumentation noninterference evidence differs")
        if asdict(trace.world.config) != items[identity]["config"]:
            raise ValueError("Retained world has the wrong configuration")
        if audit_availability(trace.world, trace) != by_id[identity]["legacy_audit"]:
            raise ValueError("Saved chronology audit differs from full-log reconstruction")
        if world_sha256(trace.world) != by_id[identity]["legacy_world_sha256"]:
            raise ValueError("Retained legacy World hash differs")
        corrected = reconstruct_corrected(trace, record["retiming_changes"]) if record["correction_available"] else None
        if corrected is not None:
            checked = verify_retiming(trace.world, corrected, trace)
            if checked != by_id[identity]["independent_retiming_check"] or world_sha256(corrected) != by_id[identity]["corrected_world_sha256"]:
                raise ValueError("Retained correction evidence differs")
        else:
            unavailable += 1
        reproduced = evaluate_origins(items[identity], trace, corrected, benchmark, receipts, failure=by_id[identity].get("failure"))
        if normalize(reproduced) != record["origin_results"]:
            raise ValueError("Saved prediction/scoring/mask evidence differs")
        for result in reproduced:
            (benchmark_results if result["cohort"] == "benchmark" else receipt_results).append(result["result"])
        writes_checked += len(trace.world.writes)
    impact = finalize_impact(benchmark, receipts, benchmark_results, receipt_results)
    if normalize(impact) != read(output / "impact.json.gz") or normalize(claims(impact, audits)) != read(output / "claims.json"):
        raise ValueError("Saved aggregation/claim sensitivity differs")
    if summarize_chronology(audits, inputs) != read(output / "chronology.json")["summary"]:
        raise ValueError("Chronology denominators differ")
    return {"status": "passed" if not unavailable else "unavailable_rows_retained", "configurations_checked": len(records),
            "writes_checked": writes_checked, "unavailable_configurations": unavailable, "preservation": verify_preservation(),
            "scope": "Retained World values, direct full-log availability, independent quarter-order/field checks, unchanged investigator/scorer reproduction, stable mask IDs and exact grouped arithmetic; no generator or independent finite study rerun."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "develop", "freeze", "run", "verify", "preservation"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_inputs()
    elif args.command == "develop":
        result = qualify_development()
    elif args.command == "freeze":
        result = freeze()
    elif args.command == "preservation":
        result = verify_preservation()
    elif args.command == "verify":
        result = verify_outputs(args.output or STUDY / "results")
    else:
        result = execute(args.output or STUDY / "results")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
