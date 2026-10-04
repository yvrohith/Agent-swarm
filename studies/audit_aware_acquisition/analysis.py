"""Fixed audit-order comparison on retained nominal prefixes and loss closures."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from studies.acquisition_prior_robustness.aggregation import weights_for
from studies.archive_model_misspecification.expanded import ExpandedModel
from tracebench.evidence_acquisition.model import Model, canonical, pin

from .auditing import AuditSelector, PassiveAuditArchive, audit

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/audit_aware_acquisition"
ARMS = ("no_audit", "cost_order", "constant_first", "closure_informed")
BUDGETS = (0, 25, 50, 100)
KS = (0, 1, 2)
POPULATIONS = ("original", "new", "all")
DEFINITE = {"established", "ruled_out"}
SUPPORT_FLAGS = (
    "initially_supported_definite", "initially_unsupported_definite", "supported_definite_remaining",
    "finally_supported_definite", "finally_unsupported_definite",
    "warrant_restored", "unwithdrawn_warrant_restored", "still_unsupported_without_conflict",
    "withdrawn_definite", "preaudit_irreducible", "irreducibility_warranted_at_start",
    "irreducibility_warranted_at_end", "irreducibility_overstrong", "residual_full_archive_ambiguity",
)
COST_FIELDS = ("base_cost", "added_cost", "total_cost", "base_query_count", "added_query_count",
               "total_query_count", "base_returned_bytes", "added_returned_bytes", "total_returned_bytes")
COUNT_FIELDS = ("detected", "full_conflict_missed", "false_alarm", "catalogue_exhausted", *SUPPORT_FLAGS)
METRICS = (*COST_FIELDS, *COUNT_FIELDS, "detection_fraction_conflicts", "restoration_fraction_initially_unsupported",
           "added_cost_on_nominal_compatible", "alias_added_queries", "alias_added_cost", "alias_added_bytes",
           "catalogue_coverage_fraction", "added_cost_at_detection")


def read(path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("Duplicate JSON key")
            output[key] = value
        return output
    path = Path(path)
    data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(data, object_pairs_hook=unique)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with path.open("xb") as stream:
            stream.write(gzip.compress(canonical(value), mtime=0))
    else:
        with path.open("x") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def number(value):
    return None if value is None else {"exact": str(Fraction(value)), "value": float(value)}


def classify_support(proposal, baseline_claim, baseline_terminal, final_claim,
                     final_terminal, alarm, full_archive_terminal):
    """Warrant and withdrawal are orthogonal; only evidence can restore warrant."""
    definite = proposal in DEFINITE
    initially = definite and baseline_claim == proposal
    finally_supported = definite and final_claim == proposal
    if initially and not finally_supported:
        raise ValueError("Further compatible evidence removed an already warranted definite proposition")
    restored = definite and not initially and finally_supported
    if definite:
        disposition = ("definite_proposal_withdrawn" if alarm else
                       "definite_supported_remaining" if initially else
                       "definite_warrant_restored" if restored else "definite_still_unsupported")
    else:
        if proposal != "archive_irreducible":
            raise ValueError("Saved nominal proposal is not a terminal conclusion")
        disposition = ("withdrawn_irreducibility" if alarm else "irreducibility_warranted"
                       if final_terminal == "archive_irreducible" else "irreducibility_overstrong")
    return {
        "initially_supported_definite": initially,
        "initially_unsupported_definite": definite and not initially,
        "supported_definite_remaining": initially and finally_supported,
        "finally_supported_definite": finally_supported,
        "finally_unsupported_definite": definite and not finally_supported,
        "warrant_restored": restored,
        "unwithdrawn_warrant_restored": restored and not alarm,
        "still_unsupported_without_conflict": definite and not finally_supported and not alarm,
        "withdrawn_definite": definite and alarm,
        "preaudit_irreducible": proposal == "archive_irreducible",
        "irreducibility_warranted_at_start": proposal == "archive_irreducible"
        and baseline_terminal == "archive_irreducible",
        "irreducibility_warranted_at_end": proposal == "archive_irreducible"
        and final_terminal == "archive_irreducible",
        "irreducibility_overstrong": proposal == "archive_irreducible"
        and final_terminal != "archive_irreducible",
        "residual_full_archive_ambiguity": full_archive_terminal == "archive_irreducible",
        "disposition": disposition,
    }


class CertificateCache:
    """Cache ordered histories under their correct model/contract, not actual answers."""

    def __init__(self):
        self.certificates = {}
        self._keys = {}
        self.references = 0
        self.verified = 0
        self.generation_seconds = self.verification_seconds = 0.0

    def get(self, model, history, expected=None):
        contract = getattr(model, "contract_pin", "original_nominal_contract")
        key = (model.model_pin, contract, pin(history))
        if key not in self._keys:
            started = perf_counter()
            certificate = model.certificate(history)
            self.generation_seconds += perf_counter() - started
            certificate_id = pin(certificate)
            if certificate_id not in self.certificates:
                started = perf_counter()
                valid = model.verify_certificate(certificate)
                self.verification_seconds += perf_counter() - started
                if not valid:
                    raise ValueError("Existing contract checker rejected a certificate")
                self.certificates[certificate_id] = certificate
                self.verified += 1
            elif canonical(self.certificates[certificate_id]) != canonical(certificate):
                raise ValueError("Certificate hash collision")
            self._keys[key] = certificate_id
        certificate_id = self._keys[key]
        if expected is not None and canonical(self.certificates[certificate_id]) != canonical(expected):
            raise ValueError("Saved baseline certificate differs from unchanged contract machinery")
        self.references += 1
        return certificate_id

    def stats(self):
        return {"distinct_certificates_verified": self.verified,
                "model_contract_history_keys": len(self._keys), "cache_references": self.references,
                "certificate_generation_seconds": self.generation_seconds,
                "certificate_verification_seconds": self.verification_seconds}


def _alias_measurements(nominal, base_history, audit_history):
    queried = {nominal.queries[h["query_id"]]["record_id"] for h in base_history}
    initial = set(nominal.problem["initial_record_ids"])
    count = cost = byte_count = initial_count = 0
    for observation in audit_history:
        query = nominal.queries[observation["query_id"]]
        record_id = query["record_id"]
        if record_id in queried:
            count += 1
            cost += query["cost"]
            byte_count += len(canonical(query["outcomes"][observation["outcome_id"]]))
        initial_count += record_id in initial
        queried.add(record_id)
    return {"alias_added_queries": count, "alias_added_cost": cost, "alias_added_bytes": byte_count,
            "added_lookups_of_initial_records": initial_count,
            "unique_queried_record_count": len(queried)}


def qualify_run(problem, nominal, expanded, source_row, result, cache, saved_certificates):
    """Evaluator-only expanded support; nothing here influences the audit selector."""
    baseline = source_row["policy"]
    base_history, history = baseline["history"], result["history"]
    if result["base_history"] != base_history:
        raise ValueError("Audit changed the original nominal stopping prefix")
    base_claim, base_terminal = expanded.claim_status(base_history), expanded.terminal_status(base_history)
    if (base_claim, base_terminal) != (baseline["expanded_claim_status"], baseline["expanded_terminal_status"]):
        raise ValueError("Saved expanded support at nominal stopping did not reproduce")
    final_claim, final_terminal = expanded.claim_status(history), expanded.terminal_status(history)
    if final_claim == "model_conflict":
        raise ValueError("Paid answers contradict the saved actual expanded support")
    alarm = result["status"] == "nominal_model_conflict"
    support = classify_support(baseline["status"], base_claim, base_terminal,
                               final_claim, final_terminal, alarm, source_row["expanded_terminal_status"])
    certificate_refs = {
        "base_nominal": cache.get(nominal, base_history, saved_certificates[baseline["certificate"]]),
        "base_expanded": cache.get(expanded, base_history, saved_certificates[baseline["expanded_certificate"]]),
        "final_nominal": cache.get(nominal, history), "final_expanded": cache.get(expanded, history),
    }
    full_conflict = source_row["population"] == "new"
    if alarm and not full_conflict:
        raise ValueError("Truthful nominal archive was falsely reported as a model conflict")
    return {
        **result, "problem_id": problem["problem_id"], "stratum": problem["stratum"],
        "subtype": problem.get("subtype", problem["stratum"]), "k": expanded.k,
        "signature_id": source_row["signature_id"], "outcomes": source_row["outcomes"],
        "population": source_row["population"], "base_nominal_proposal": baseline["status"],
        "baseline_expanded_claim_status": base_claim, "baseline_expanded_terminal_status": base_terminal,
        "final_expanded_claim_status": final_claim, "final_expanded_terminal_status": final_terminal,
        "complete_nominal_conflict": full_conflict, "detected": alarm,
        "full_conflict_missed": full_conflict and not alarm, "false_alarm": alarm and not full_conflict,
        "catalogue_exhausted": len(history) == len(nominal.query_ids),
        "catalogue_query_count": len(nominal.query_ids), "certificates": certificate_refs,
        "support": support,
        "joint_category": {"alarm": alarm, "proposal": baseline["status"],
                           "final_claim_status": final_claim, "final_terminal_status": final_terminal,
                           "warrant_restored": support["warrant_restored"],
                           "withdrawn_definite": support["withdrawn_definite"],
                           "disposition": support["disposition"]},
        **_alias_measurements(nominal, base_history, result["audit_history"]),
    }


def _population_summary(runs):
    size = len(runs)
    counts = {name: sum(row.get(name, row["support"].get(name, False)) for row in runs)
              for name in COUNT_FIELDS}
    counts.update({"signatures": size, "full_conflicts": sum(row["complete_nominal_conflict"] for row in runs),
                   "nominal_compatible": sum(not row["complete_nominal_conflict"] for row in runs)})
    totals = {name: sum(row[name] for row in runs) for name in COST_FIELDS}
    totals.update({name: sum(row[name] for row in runs) for name in
                   ("alias_added_queries", "alias_added_cost", "alias_added_bytes",
                    "added_lookups_of_initial_records")})
    metrics = {name: number(Fraction((totals if name in totals else counts)[name], size)) if size else None
               for name in (*COST_FIELDS, *COUNT_FIELDS, "alias_added_queries", "alias_added_cost", "alias_added_bytes")}
    metrics["detection_fraction_conflicts"] = number(Fraction(counts["detected"], counts["full_conflicts"])) \
        if counts["full_conflicts"] else None
    metrics["restoration_fraction_initially_unsupported"] = number(
        Fraction(counts["warrant_restored"], counts["initially_unsupported_definite"])) \
        if counts["initially_unsupported_definite"] else None
    compatible_cost = sum(row["added_cost"] for row in runs if not row["complete_nominal_conflict"])
    metrics["added_cost_on_nominal_compatible"] = number(Fraction(compatible_cost, counts["nominal_compatible"])) \
        if counts["nominal_compatible"] else None
    detected_cost = sum(row["added_cost"] for row in runs if row["detected"])
    totals["added_cost_on_detected_conflicts"] = detected_cost
    totals["added_cost_on_nominal_compatible"] = compatible_cost
    metrics["added_cost_at_detection"] = number(Fraction(detected_cost, counts["detected"])) if counts["detected"] else None
    metrics["catalogue_coverage_fraction"] = number(sum(
        (Fraction(row["total_query_count"], row["catalogue_query_count"]) for row in runs), Fraction()) / size) if size else None
    joint = Counter(canonical(row["joint_category"]).decode() for row in runs)
    return {"signature_count": size, "counts": counts, "totals": totals, "metrics": metrics,
            "worst": {name: max((row[name] for row in runs), default=None) for name in COST_FIELDS},
            "joint_counts": [{**json.loads(key), "count": count} for key, count in sorted(joint.items())]}


def aggregate_cell(problem, k, arm, budget, runs, expected_count, failure=None):
    if len({row["signature_id"] for row in runs}) != len(runs):
        raise ValueError("Duplicate per-signature run in aggregate cell")
    complete = failure is None and len(runs) == expected_count
    return {"problem_id": problem["problem_id"], "stratum": problem["stratum"],
            "subtype": problem.get("subtype", problem["stratum"]), "k": k, "arm": arm,
            "budget_percent": budget, "status": "completed" if complete else "unavailable",
            "failure": failure, "expected_signatures": expected_count, "completed_signatures": len(runs),
            "populations": {population: _population_summary(
                [row for row in runs if population == "all" or row["population"] == population])
                for population in POPULATIONS}}


def analyze_problem(problem, saved_conditions, *, cache=None):
    """All 48 fixed cells for one problem; selector inputs never include actual k."""
    cache = cache if cache is not None else CertificateCache()
    saved = {cell["k"]: cell for cell in saved_conditions}
    if set(saved) != set(KS) or len(saved) != len(saved_conditions):
        raise ValueError("Exactly three saved support conditions are required")
    if any(cell["status"] != "completed" or cell["problem_id"] != problem["problem_id"] for cell in saved.values()):
        raise ValueError("Incomplete or mismatched saved baseline condition")
    nominal = Model(problem)
    design = tuple(tuple(row["outcomes"]) for row in saved[2]["signature_rows"])
    selectors = {arm: AuditSelector(nominal, arm, design_signatures=design if arm == "closure_informed" else None)
                 for arm in ARMS}
    runs, cells = [], []
    for k in KS:
        source_rows = saved[k]["signature_rows"]
        try:
            expanded = ExpandedModel(problem, k)
            if canonical(expanded.to_dict()) != canonical(saved[k]["expansion"]):
                raise ValueError("Reconstructed immutable support differs from the saved closure")
            # Validate the saved prefix's actual certificate bytes before any
            # audit uses its compact public certificate identifier.
            for source_row in source_rows:
                baseline = source_row["policy"]
                nominal_ref = cache.get(nominal, baseline["history"], saved[k]["certificates"][baseline["certificate"]])
                expanded_ref = cache.get(expanded, baseline["history"], saved[k]["certificates"][baseline["expanded_certificate"]])
                if nominal_ref != baseline["certificate"] or expanded_ref != baseline["expanded_certificate"]:
                    raise ValueError("Saved baseline certificate reference differs from its actual byte-value pin")
        except Exception as error:
            failure = {"type": type(error).__name__, "message": str(error)}
            for arm in ARMS:
                for budget in BUDGETS:
                    cells.append(aggregate_cell(problem, k, arm, budget, [], len(source_rows), failure))
            continue
        for arm in ARMS:
            for budget in BUDGETS:
                current = []
                failure = None
                try:
                    for source_row in source_rows:
                        baseline = {key: source_row["policy"][key] for key in (
                            "history", "cost", "query_count", "returned_bytes", "status",
                            "certificate", "certificate_valid")}
                        lookup = PassiveAuditArchive(nominal, tuple(source_row["outcomes"]),
                                                     initial_history=baseline["history"])
                        result = audit(nominal, baseline, lookup, selectors[arm], budget)
                        row = qualify_run(problem, nominal, expanded, source_row, result,
                                          cache, saved[k]["certificates"])
                        current.append(row)
                except Exception as error:
                    failure = {"type": type(error).__name__, "message": str(error)}
                runs.extend(current)
                cells.append(aggregate_cell(problem, k, arm, budget, current, len(source_rows), failure))
    return {"runs": runs, "cells": cells}


def _weighted_metric(selected, population, name, groups, weighting):
    failed = [cell["problem_id"] for cell in selected if cell["status"] != "completed"]
    values = {cell["problem_id"]: cell["populations"][population]["metrics"][name] for cell in selected}
    defined = [problem_id for problem_id, value in values.items() if value is not None and problem_id not in failed]
    undefined = [problem_id for problem_id in values if problem_id not in failed and problem_id not in defined]
    value = None
    if defined and not failed:
        weights = weights_for(defined, groups, weighting)
        value = sum((weights[pid] * Fraction(values[pid]["exact"]) for pid in defined), Fraction())
    return {"mean": number(value), "expected_problems": len(selected), "defined_problems": len(defined),
            "undefined_problems": undefined, "failed_problems": failed,
            "defined_structures": len({groups[pid] for pid in defined})}


def summarize(cells, groups):
    index = {(c["problem_id"], c["k"], c["arm"], c["budget_percent"]): c for c in cells}
    expected = {(pid, k, arm, budget) for pid in groups for k in KS for arm in ARMS for budget in BUDGETS}
    if len(index) != len(cells) or set(index) != expected:
        raise ValueError("All fixed problem/condition/arm/budget cells must remain present")
    buckets = defaultdict(list)
    for cell in cells:
        for stratum, subtype in {("all", "all"), (cell["stratum"], "all"),
                                 (cell["stratum"], cell["subtype"])}:
            buckets[cell["k"], cell["arm"], cell["budget_percent"], stratum, subtype].append(cell)
    result = []
    for (k, arm, budget, stratum, subtype), selected in sorted(buckets.items()):
        for population in POPULATIONS:
            pooled_counts, pooled_totals, joint = Counter(), Counter(), Counter()
            for cell in selected:
                part = cell["populations"][population]
                pooled_counts.update(part["counts"])
                pooled_totals.update(part["totals"])
                for item in part["joint_counts"]:
                    joint[canonical({key: value for key, value in item.items() if key != "count"}).decode()] += item["count"]
            for weighting in ("equal_problem", "structure_balanced"):
                result.append({
                    "k": k, "arm": arm, "budget_percent": budget, "stratum": stratum, "subtype": subtype,
                    "population": population, "weighting": weighting,
                    "comparison_scope": "extra_model_knowledge" if arm == "closure_informed" else "nominal_only",
                    "problem_count": len(selected), "structure_count": len({groups[c["problem_id"]] for c in selected}),
                    "unavailable_problems": [c["problem_id"] for c in selected if c["status"] != "completed"],
                    "pooled_counts": dict(pooled_counts), "pooled_totals": dict(pooled_totals),
                    "pooled_counts_complete": all(c["status"] == "completed" for c in selected),
                    "joint_counts": [{**json.loads(key), "count": value} for key, value in sorted(joint.items())],
                    "metrics": {name: _weighted_metric(selected, population, name, groups, weighting) for name in METRICS},
                })
    return {"interpretation": "Descriptive signature census, not a deployment prior; actual k populations remain separate",
            "problem_to_group": groups, "conditions": result}


def paired_differences(cells, groups):
    index = {(c["problem_id"], c["k"], c["arm"], c["budget_percent"]): c for c in cells}
    per_problem = []
    comparisons = (("constant_first", "cost_order", "primary_nominal_only"),
                   ("closure_informed", "cost_order", "secondary_extra_model_knowledge"),
                   ("closure_informed", "constant_first", "secondary_extra_model_knowledge"))
    for pid in sorted(groups):
        for k in KS:
            for budget in BUDGETS:
                for left, right, scope in comparisons:
                    a, b = index[pid, k, left, budget], index[pid, k, right, budget]
                    for population in POPULATIONS:
                        values = {}
                        for name in METRICS:
                            av = a["populations"][population]["metrics"][name]
                            bv = b["populations"][population]["metrics"][name]
                            values[name] = number(Fraction(av["exact"]) - Fraction(bv["exact"])) \
                                if av is not None and bv is not None and a["status"] == b["status"] == "completed" else None
                        per_problem.append({"problem_id": pid, "structure_group": groups[pid],
                                            "stratum": a["stratum"], "subtype": a["subtype"], "k": k,
                                            "budget_percent": budget, "left": left, "right": right,
                                            "comparison_scope": scope, "population": population,
                                            "available": a["status"] == b["status"] == "completed", "differences": values})
    buckets = defaultdict(list)
    for row in per_problem:
        for stratum in {"all", row["stratum"]}:
            buckets[row["k"], row["budget_percent"], row["left"], row["right"], row["population"], stratum].append(row)
    summaries = []
    for (k, budget, left, right, population, stratum), rows in sorted(buckets.items()):
        for weighting in ("equal_problem", "structure_balanced"):
            metrics = {}
            for name in METRICS:
                failed = [r["problem_id"] for r in rows if not r["available"]]
                defined = {r["problem_id"]: Fraction(r["differences"][name]["exact"])
                           for r in rows if r["differences"][name] is not None and r["available"]}
                mean = None
                if defined and not failed:
                    weights = weights_for(defined, groups, weighting)
                    mean = sum((weights[pid] * value for pid, value in defined.items()), Fraction())
                metrics[name] = {"mean": number(mean), "expected_problems": len(rows),
                                 "defined_problems": len(defined), "failed_problems": failed,
                                 "undefined_problems": [r["problem_id"] for r in rows
                                                        if r["problem_id"] not in defined and r["problem_id"] not in failed],
                                 "lower": sum(v < 0 for v in defined.values()),
                                 "tied": sum(v == 0 for v in defined.values()),
                                 "higher": sum(v > 0 for v in defined.values())}
            summaries.append({"k": k, "budget_percent": budget, "left": left, "right": right,
                              "comparison_scope": rows[0]["comparison_scope"], "population": population,
                              "stratum": stratum, "weighting": weighting, "metrics": metrics})
    return {"direction": "left minus right; lower retrieval cost is not sufficient without coverage/support",
            "per_problem": per_problem, "summary": summaries}


def settings():
    config = read(STUDY / "config.json")
    expected = {
        "evaluation_problems": 40, "development_problems": 4, "evaluation_aggregate_cells": 1920,
        "omission_budgets": list(KS), "arms": list(ARMS), "extra_budget_percentages": list(BUDGETS),
        "design_envelope_k": 2, "expanded_world_cap": 4096, "signature_cap": 256, "query_cap": 8,
        "outcomes_per_query_cap": 2, "exact_state_cap": 100000,
        "evaluation_source": "studies/evidence_acquisition/evaluation_problems.json",
        "development_source": "studies/evidence_acquisition/development_problems.json",
        "evaluation_baseline_source": "studies/archive_model_misspecification/results/details.json.gz",
        "development_baseline_source": "studies/audit_aware_acquisition/development_baseline.json.gz",
        "group_source": "studies/acquisition_prior_robustness/structure_groups.json",
        "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0",
    }
    if any(config.get(key) != value for key, value in expected.items()):
        raise ValueError("Configuration differs from the fixed authorized audit design")
    return config


def verify_preservation():
    saved = read(STUDY / "preservation.json")
    if digest(ROOT / saved["local_preservation_manifest"]) != saved["local_preservation_manifest_sha256"]:
        raise ValueError("Historical local preservation manifest changed")
    local = read(ROOT / saved["local_preservation_manifest"])
    for path, expected in {**saved["tracked_sha256"], **local["sha256"]}.items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Historical byte preservation mismatch: {path}")
    return {"tracked_files": len(saved["tracked_sha256"]), "local_files": len(local["sha256"])}


def dependencies():
    paths = ["src/tracebench/__init__.py",
             *[f"src/tracebench/evidence_acquisition/{name}.py" for name in ("__init__", "model", "policies", "certificates")],
             "studies/acquisition_prior_robustness/aggregation.py", "studies/acquisition_prior_robustness/structure_groups.json",
             "studies/acquisition_prior_robustness/sensitivity.py",
             "studies/archive_model_misspecification/expanded.py", "studies/archive_model_misspecification/reference.py",
             "studies/archive_model_misspecification/analysis.py",
             "studies/archive_model_misspecification/results/details.json.gz",
             "studies/evidence_acquisition/development_problems.json", "studies/evidence_acquisition/evaluation_problems.json",
             *[f"studies/audit_aware_acquisition/{name}" for name in
               ("analysis.py", "auditing.py", "reference.py", "config.json", "ANALYSIS.md", "METHOD.md",
                "development_baseline.json.gz", "input_provenance.json", "baseline_verification.json",
                "development_checks.json", "pre_freeze_checks.json")],
             "tests/test_audit_aware_acquisition.py", "tests/test_audit_acquisition_reference.py"]
    return [ROOT / path for path in paths]


def verify_freeze():
    frozen = read(STUDY / "freeze.json")
    if set(frozen["files_sha256"]) != {str(path.relative_to(ROOT)) for path in dependencies()}:
        raise ValueError("Frozen computational dependency closure differs")
    for path, expected in frozen["files_sha256"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Frozen computational input changed: {path}")
    settings()
    return len(frozen["files_sha256"])


def freeze():
    settings()
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        if read(STUDY / name).get("status") != "passed":
            raise ValueError(f"Pre-freeze check has not passed: {name}")
    if read(STUDY / "pre_freeze_checks.json").get("evaluation_audit_outcomes_observed") != 0:
        raise ValueError("Evaluation audit chronology is not pre-outcome")
    write_new(STUDY / "freeze.json", {
        "schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_audit_outcomes_observed": 0, "known_nominal_baseline_outcomes": True,
        "python_version": sys.version,
        "files_sha256": {str(path.relative_to(ROOT)): digest(path) for path in dependencies()},
        "preservation": verify_preservation(),
    })
    return {"status": "frozen", "dependencies": verify_freeze()}


def _inputs(development):
    config = settings()
    problems = read(ROOT / config["development_source" if development else "evaluation_source"])
    saved = read(ROOT / config["development_baseline_source" if development else "evaluation_baseline_source"])
    expected = config["development_problems" if development else "evaluation_problems"]
    if len(problems) != expected or len(saved) != expected * 3:
        raise ValueError("Fixed problem/support counts differ")
    groups = ({p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems} if development else
              read(ROOT / config["group_source"])["problem_to_group"])
    if set(groups) != {p["problem_id"] for p in problems}:
        raise ValueError("Structural-group mapping differs from fixed problem population")
    return problems, saved, groups


def execute(output, *, development=False):
    from .reference import verify_runs

    if not development:
        verify_freeze()
    verify_preservation()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    problems, saved, groups = _inputs(development)
    cache = CertificateCache()
    runs, cells, failures = [], [], []
    started = perf_counter()
    for problem in problems:
        selected = [cell for cell in saved if cell["problem_id"] == problem["problem_id"]]
        try:
            result = analyze_problem(problem, selected, cache=cache)
            runs.extend(result["runs"])
            cells.extend(result["cells"])
        except Exception as error:
            failure = {"problem_id": problem["problem_id"], "type": type(error).__name__, "message": str(error)}
            failures.append(failure)
            for source in selected:
                for arm in ARMS:
                    for budget in BUDGETS:
                        cells.append(aggregate_cell(problem, source["k"], arm, budget, [], len(source["signature_rows"]), failure))
        print(json.dumps({"problem_id": problem["problem_id"], "aggregate_cells_retained": len(cells),
                          "signature_runs_retained": len(runs)}), flush=True)
        if not development:
            verify_freeze()
    reference_started = perf_counter()
    try:
        independent = verify_runs(problems, saved, runs, cache.certificates)
    except Exception as error:
        independent = {"status": "failed", "failure": {"type": type(error).__name__, "message": str(error)}}
    reference_seconds = perf_counter() - reference_started
    summary, paired = summarize(cells, groups), paired_differences(cells, groups)
    write_new(output / "runs.json.gz", runs)
    write_new(output / "certificates.json.gz", cache.certificates)
    write_new(output / "per_condition.json.gz", cells)
    write_new(output / "summary.json.gz", summary)
    write_new(output / "paired.json.gz", paired)
    write_new(output / "independent_verification.json", independent)
    completed = sum(cell["status"] == "completed" for cell in cells)
    validation = {
        "status": "passed" if completed == len(cells) and independent.get("status") == "passed" else "unavailable_or_failed_checks_retained",
        "split": "development" if development else "evaluation", "problems": len(problems),
        "aggregate_cells": len(cells), "completed_cells": completed, "signature_runs": len(runs),
        "expected_signature_runs": sum(len(cell["signature_rows"]) for cell in saved) * len(ARMS) * len(BUDGETS),
        "failures": failures, "certificate_checks": cache.stats(),
        "implementation_overhead": {"total_seconds": perf_counter() - started,
                                    "selection_seconds": sum(r["selection_seconds"] for r in runs),
                                    "nominal_compatibility_seconds": sum(r["checking_seconds"] for r in runs),
                                    "independent_reference_seconds": reference_seconds},
        "preservation": verify_preservation(), "frozen_dependencies": None if development else verify_freeze(),
        "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0",
    }
    write_new(output / "validation.json", validation)
    write_new(output / "manifest.json", {
        "freeze_sha256": None if development else digest(STUDY / "freeze.json"),
        "files_sha256": {path.name: digest(path) for path in sorted(output.iterdir())},
    })
    if development:
        write_new(STUDY / "development_checks.json", {**validation,
                  "output": str(output.resolve().relative_to(ROOT)), "manifest_sha256": digest(output / "manifest.json"),
                  "evaluation_audit_outcomes_observed": 0})
    return validation


def verify_outputs(output):
    from .reference import verify_runs

    verify_freeze()
    output = Path(output)
    manifest = read(output / "manifest.json")
    if manifest["freeze_sha256"] != digest(STUDY / "freeze.json"):
        raise ValueError("Result freeze pin differs")
    for name, expected in manifest["files_sha256"].items():
        if Path(name).name != name or digest(output / name) != expected:
            raise ValueError("Result manifest bytes differ")
    problems, saved, groups = _inputs(False)
    runs, certificates = read(output / "runs.json.gz"), read(output / "certificates.json.gz")
    checked = verify_runs(problems, saved, runs, certificates)
    if checked.get("status") != "passed":
        raise ValueError("Independent verification did not pass")
    by_key = defaultdict(list)
    for row in runs:
        by_key[row["problem_id"], row["k"], row["arm"], row["budget_percent"]].append(row)
    problem_map = {p["problem_id"]: p for p in problems}
    source_map = {(c["problem_id"], c["k"]): c for c in saved}
    cells = read(output / "per_condition.json.gz")
    for cell in cells:
        key = cell["problem_id"], cell["k"], cell["arm"], cell["budget_percent"]
        expected = aggregate_cell(problem_map[key[0]], *key[1:], by_key[key],
                                  len(source_map[key[:2]]["signature_rows"]), cell["failure"])
        if canonical(cell) != canonical(expected):
            raise ValueError("Saved aggregate cell differs from run reaggregation")
    if canonical(summarize(cells, groups)) != canonical(read(output / "summary.json.gz")):
        raise ValueError("Saved summaries differ from exact reaggregation")
    if canonical(paired_differences(cells, groups)) != canonical(read(output / "paired.json.gz")):
        raise ValueError("Saved paired differences differ from exact reaggregation")
    return {"status": "passed", "aggregate_cells": len(cells), "signature_runs": len(runs),
            "independent_verification": checked,
            "scope": "Scientific dependencies and saved outputs only; historical checkout preservation is separate"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("develop", "freeze", "run", "verify"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze()
    elif args.command == "develop":
        if args.output is None:
            parser.error("development requires a fresh ignored --output directory")
        result = execute(args.output, development=True)
    elif args.command == "verify":
        result = verify_outputs(args.output or STUDY / "results")
    else:
        result = execute(args.output or STUDY / "results")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
