"""Frozen loss-closure census and nominal exact-policy observation experiment."""
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

from studies.acquisition_prior_robustness.aggregation import weights_for
from studies.acquisition_prior_robustness.sensitivity import CappedPlanner, ExactStateCap
from tracebench.evidence_acquisition.model import Model, canonical, indices, pin

from .expanded import ExpandedModel

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/archive_model_misspecification"
ORIGINAL = ROOT / "studies/evidence_acquisition"
DEFINITE = {"established", "ruled_out"}
KS = (0, 1, 2)
POLICY_METRICS = ("conflict_detected", "full_conflict_missed", "unsupported_definite",
                  "overstrong_archive_irreducibility", "query_count", "retrieval_cost")
METRIC_NAMES = (
    "lost_fraction_original_signatures", "lost_fraction_original_definite",
    "lost_fraction_original_established", "lost_fraction_original_ruled_out",
    "new_fraction_expanded_signatures",
    *(f"{population}_{name}_per_signature" for population in ("original", "new", "all")
      for name in POLICY_METRICS),
)


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
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
            stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False) + "\n")


def number(value):
    return None if value is None else {"exact": str(Fraction(value)), "value": float(value)}


def nominal_claim_status(model, history):
    state = model.compatible(history)
    if not state:
        return "model_conflict"
    values = {model.claim_values[i] for i in indices(state)}
    return "unresolved" if len(values) > 1 else "established" if True in values else "ruled_out"


def nominal_terminal_status(model, history):
    status = model.terminal(model.compatible(history))
    return "model_conflict" if status == "inconsistent" else status or "unresolved_pending"


class PassiveArchive:
    """Private evaluator archive; unlike the old lookup, signatures may be novel.

    The planner never receives this object or its unqueried answers. Each call
    charges the catalogue price, returns outcome identifiers, and accounts for
    the unchanged observable payload's canonical byte length.
    """

    def __init__(self, nominal, signature):
        if len(signature) != len(nominal.query_ids):
            raise ValueError("Archive signature length differs from the catalogue")
        self._model = nominal
        self._answers = dict(zip(nominal.query_ids, signature, strict=True))
        if any(outcome not in nominal.queries[qid]["outcomes"]
               for qid, outcome in self._answers.items()):
            raise ValueError("Archive contains an unknown outcome")
        self.history = []
        self.cost = self.returned_bytes = 0

    def __call__(self, query_id):
        if query_id not in self._answers or any(h["query_id"] == query_id for h in self.history):
            raise ValueError("Unknown or repeated paid lookup")
        query = self._model.queries[query_id]
        outcome = self._answers[query_id]
        payload = canonical(query["outcomes"][outcome])
        self.cost += query["cost"]
        self.returned_bytes += len(payload)
        observation = {"query_id": query_id, "outcome_id": outcome}
        self.history.append(observation)
        return dict(observation)


def nominal_acquire(nominal, signature, *, planner=None):
    """Run only the nominal exact policy; stop on its first inconsistent prefix."""
    if planner is None:
        planner = CappedPlanner(nominal, "exact_optimal", state_cap=100_000)
    if planner.model is not nominal or planner.policy != "exact_optimal":
        raise ValueError("Nominal acquisition requires the original exact planner/model")
    archive = PassiveArchive(nominal, tuple(signature))
    history = []
    failure = None
    while True:
        state = nominal.compatible(history)
        if not state:
            status = "model_conflict_detected"
            break
        try:
            query_id = planner.choose(history)
        except ExactStateCap as error:
            status, failure = "unavailable", {"type": type(error).__name__, "message": str(error)}
            break
        if query_id is None:
            status = nominal.terminal(state)
            if status not in {*DEFINITE, "archive_irreducible"}:
                raise ValueError("Nominal policy stopped without its original terminal certificate")
            break
        history.append(archive(query_id))
        # No subsequent planner call or lookup is allowed after this conflict.
        if not nominal.compatible(history):
            status = "model_conflict_detected"
            break
    certificate = nominal.certificate(history)
    valid = nominal.verify_certificate(certificate)
    if not valid:
        raise ValueError("Original nominal checker rejected its acquisition certificate")
    return {
        "history": history, "cost": archive.cost, "query_count": len(history),
        "returned_bytes": archive.returned_bytes, "status": status, "failure": failure,
        "claim_status": nominal_claim_status(nominal, history),
        "terminal_status": nominal_terminal_status(nominal, history),
        "certificate": certificate, "certificate_valid": valid,
        "solver_states_total": planner.solver_states,
    }


def _certificate_ref(certificates, model, history):
    certificate = model.certificate(history)
    if not model.verify_certificate(certificate):
        raise ValueError("A census certificate failed its own contract's verifier")
    key = pin(certificate)
    if key in certificates and canonical(certificates[key]) != canonical(certificate):
        raise ValueError("Certificate digest collision")
    certificates[key] = certificate
    return key


def _counterexample(nominal, expanded, signature, nominal_status):
    nominal_cell = nominal.signature_cells[signature]
    expanded_cell = expanded.signature_cells[signature]
    wanted = nominal_status == "established"
    nominal_index = next(i for i in indices(nominal_cell) if nominal.claim_values[i] == wanted)
    opposite = next(i for i in indices(expanded_cell) if expanded.claim_values[i] != wanted)
    if nominal.answers[nominal_index] != expanded.answers[opposite]:
        raise ValueError("Counterexample must agree on every catalogue answer")
    return {
        "nominal_world_index": nominal_index, "nominal_world_id": nominal.worlds[nominal_index]["id"],
        "expanded_world_index": opposite, "expanded_world_id": expanded.worlds[opposite]["id"],
        "nominal_claim_value": wanted, "expanded_claim_value": not wanted,
        "full_signature": list(signature),
    }


def _policy_classification(policy, full_conflict):
    unsupported = policy["claim_status"] in DEFINITE and policy["expanded_claim_status"] == "unresolved"
    overstrong = (policy["terminal_status"] == "archive_irreducible"
                  and policy["expanded_terminal_status"] != "archive_irreducible")
    if policy["status"] == "unavailable":
        classification = "policy_unavailable"
    elif policy["status"] == "model_conflict_detected":
        classification = "conflict_detected"
    elif full_conflict:
        classification = "full_conflict_missed"
    elif unsupported:
        classification = "nominal_compatible_unsupported_definite"
    elif overstrong:
        classification = "nominal_archive_irreducibility_overstrong"
    else:
        classification = "nominal_conclusion_remains_justified"
    return classification, unsupported, overstrong


def analyze_cell(problem, k, *, planner=None):
    """One fixed support condition, retaining original/new signature populations."""
    expanded = ExpandedModel(problem, k)
    nominal = expanded.nominal
    if planner is None:
        planner = CappedPlanner(nominal, "exact_optimal", state_cap=100_000)
    elif canonical(planner.model.problem) != canonical(nominal.problem):
        raise ValueError("Reused planner belongs to a different nominal problem")
    # Reuse the identical nominal object held by the planner, not expanded state.
    nominal = planner.model
    certificates, rows = {}, []
    for signature in sorted(expanded.signature_cells):
        history = [{"query_id": query_id, "outcome_id": outcome}
                   for query_id, outcome in zip(nominal.query_ids, signature, strict=True)]
        old_claim = nominal_claim_status(nominal, history)
        new_claim = expanded.claim_status(history)
        old_terminal = nominal_terminal_status(nominal, history)
        new_terminal = expanded.terminal_status(history)
        if old_claim in DEFINITE and new_claim not in {old_claim, "unresolved"}:
            raise ValueError("Expansion reversed or removed an embedded nominal definite witness")
        if old_claim == "unresolved" and new_claim != "unresolved":
            raise ValueError("Expansion removed a nominal ambiguity witness")
        original = signature in nominal.signature_cells
        transition = ("nominal_conflict" if not original else
                      "definite_to_unresolved" if old_claim in DEFINITE and new_claim == "unresolved"
                      else "originally_ambiguous" if old_claim == "unresolved"
                      else "unchanged_definite")
        policy = nominal_acquire(nominal, signature, planner=planner)
        policy_certificate = policy.pop("certificate")
        policy["certificate"] = pin(policy_certificate)
        certificates[policy["certificate"]] = policy_certificate
        policy["expanded_claim_status"] = expanded.claim_status(policy["history"])
        policy["expanded_terminal_status"] = expanded.terminal_status(policy["history"])
        if (policy["claim_status"] in DEFINITE
                and policy["expanded_claim_status"] not in {policy["claim_status"], "unresolved"}):
            raise ValueError("Expanded partial history violated definite-status monotonicity")
        policy["expanded_certificate"] = _certificate_ref(certificates, expanded, policy["history"])
        classification, unsupported, overstrong = _policy_classification(policy, not original)
        policy.update(classification=classification, unsupported_definite=unsupported,
                      overstrong_archive_irreducibility=overstrong)
        rows.append({
            "signature_id": pin({"query_ids": nominal.query_ids, "outcomes": signature}),
            "outcomes": list(signature), "population": "original" if original else "new",
            "nominal_claim_status": old_claim, "expanded_claim_status": new_claim,
            "nominal_terminal_status": old_terminal, "expanded_terminal_status": new_terminal,
            "transition": transition,
            "nominal_certificate": _certificate_ref(certificates, nominal, history),
            "expanded_certificate": _certificate_ref(certificates, expanded, history),
            "counterexample": _counterexample(nominal, expanded, signature, old_claim)
            if transition == "definite_to_unresolved" else None,
            "policy": policy,
        })
    old = [row for row in rows if row["population"] == "original"]
    new = [row for row in rows if row["population"] == "new"]
    if len(old) != len(nominal.signature_cells):
        raise ValueError("Original full-signature population was not preserved")
    counts = {
        "original_signatures": len(old), "new_signatures": len(new), "expanded_signatures": len(rows),
        "original_established": sum(row["nominal_claim_status"] == "established" for row in old),
        "original_ruled_out": sum(row["nominal_claim_status"] == "ruled_out" for row in old),
        "original_unresolved": sum(row["nominal_claim_status"] == "unresolved" for row in old),
        "lost_established": sum(row["nominal_claim_status"] == "established"
                                and row["transition"] == "definite_to_unresolved" for row in old),
        "lost_ruled_out": sum(row["nominal_claim_status"] == "ruled_out"
                              and row["transition"] == "definite_to_unresolved" for row in old),
        "new_established": sum(row["expanded_claim_status"] == "established" for row in new),
        "new_ruled_out": sum(row["expanded_claim_status"] == "ruled_out" for row in new),
        "new_unresolved": sum(row["expanded_claim_status"] == "unresolved" for row in new),
    }
    counts["original_definite"] = counts["original_established"] + counts["original_ruled_out"]
    counts["lost_definite"] = counts["lost_established"] + counts["lost_ruled_out"]
    for label in ("established", "ruled_out"):
        counts[f"unchanged_{label}"] = counts[f"original_{label}"] - counts[f"lost_{label}"]
    for population, selected in (("original", old), ("new", new), ("all", rows)):
        counts[f"{population}_policy_unavailable"] = sum(r["policy"]["status"] == "unavailable"
                                                         for r in selected)
        for flag in ("unsupported_definite", "overstrong_archive_irreducibility"):
            counts[f"{population}_{flag}"] = sum(r["policy"][flag] for r in selected)
        for label in ("conflict_detected", "full_conflict_missed",
                      "nominal_compatible_unsupported_definite",
                      "nominal_archive_irreducibility_overstrong", "nominal_conclusion_remains_justified"):
            counts[f"{population}_{label}"] = sum(r["policy"]["classification"] == label for r in selected)
        counts[f"{population}_query_count"] = sum(r["policy"]["query_count"] for r in selected)
        counts[f"{population}_retrieval_cost"] = sum(r["policy"]["cost"] for r in selected)
    eligible = {query["record_id"] for query in nominal.queries.values()
                if query["kind"] == "context_receipt" and query["record_id"] not in problem["initial_record_ids"]}
    possible_omissions = any(eligible & set(world["retained_record_ids"]) for world in nominal.worlds)
    controls = {
        "no_eligible_omissions": not possible_omissions,
        "no_support_change": len(expanded.worlds)
        == len({entry["expanded_world_id"] for entry in expanded.embedding}),
        "no_new_signatures": not new,
        "no_changed_conclusions": counts["lost_definite"] == 0,
        "nominal_initially_irreducible": nominal_terminal_status(nominal, []) == "archive_irreducible",
    }
    available = not counts["all_policy_unavailable"]
    return {
        "problem_id": problem["problem_id"], "stratum": problem["stratum"],
        "subtype": problem.get("subtype", problem["stratum"]), "k": k,
        "status": "completed" if available else "policy_unavailable",
        "census_status": "completed", "policy_status": "completed" if available else "unavailable",
        "counts": counts, "controls": controls, "expansion": expanded.to_dict(),
        "expansion_stats": expanded.stats,
        "certificates": certificates, "signature_rows": rows,
    }


def earliest_losses(cells):
    grouped = defaultdict(dict)
    for cell in cells:
        grouped[cell["problem_id"]][cell["k"]] = cell
    result = []
    for problem_id, conditions in sorted(grouped.items()):
        baseline = conditions[0]
        if baseline.get("census_status") != "completed":
            result.append({"problem_id": problem_id, "status": "unavailable", "signature_id": None})
            continue
        for row in baseline["signature_rows"]:
            if row["nominal_claim_status"] not in DEFINITE:
                continue
            observed = []
            missing = []
            for k in KS:
                cell = conditions[k]
                if cell.get("census_status") != "completed":
                    missing.append(k)
                    continue
                match = next(r for r in cell["signature_rows"] if r["signature_id"] == row["signature_id"])
                if match["transition"] == "definite_to_unresolved":
                    observed.append(k)
            first = min(observed) if observed else None
            value = ("unavailable" if any(first is None or k < first for k in missing)
                     else first if first is not None else "not_observed_within_budget")
            result.append({"problem_id": problem_id, "signature_id": row["signature_id"],
                           "outcomes": row["outcomes"], "nominal_claim_status": row["nominal_claim_status"],
                           "earliest_loss_k": value, "unavailable_conditions": missing})
    return result


def _cell_metrics(cell):
    if cell.get("census_status") != "completed":
        return None
    counts = cell["counts"]
    def ratio(numerator, denominator):
        return Fraction(counts[numerator], counts[denominator]) if counts[denominator] else None
    result = {
        "lost_fraction_original_signatures": ratio("lost_definite", "original_signatures"),
        "lost_fraction_original_definite": ratio("lost_definite", "original_definite"),
        "lost_fraction_original_established": ratio("lost_established", "original_established"),
        "lost_fraction_original_ruled_out": ratio("lost_ruled_out", "original_ruled_out"),
        "new_fraction_expanded_signatures": ratio("new_signatures", "expanded_signatures"),
    }
    for population, denominator in (("original", "original_signatures"), ("new", "new_signatures"),
                                    ("all", "expanded_signatures")):
        for name in POLICY_METRICS:
            result[f"{population}_{name}_per_signature"] = (
                ratio(f"{population}_{name}", denominator) if cell["policy_status"] == "completed" else None)
    return result


def summarize(cells, groups):
    indexed = {(c["problem_id"], c["k"]): c for c in cells}
    if len(indexed) != len(cells) or set(indexed) != {(p, k) for p in groups for k in KS}:
        raise ValueError("Summary requires every fixed problem/omission condition exactly once")
    buckets = defaultdict(list)
    for cell in cells:
        keys = [("all", "all", "all"), (cell["stratum"], "all", "all"),
                (cell["stratum"], cell["subtype"], "all")]
        for control, active in cell.get("controls", {}).items():
            keys.append(("all", "all", f"{control}={str(active).lower()}"))
        for stratum, subtype, control in set(keys):
            buckets[cell["k"], stratum, subtype, control].append(cell)
    summaries = []
    for (k, stratum, subtype, control), selected in sorted(buckets.items()):
        metrics = {cell["problem_id"]: _cell_metrics(cell) for cell in selected}
        for weighting in ("equal_problem", "structure_balanced"):
            estimates = {}
            for name in METRIC_NAMES:
                failures = [c["problem_id"] for c in selected
                            if c.get("census_status") != "completed"
                            or ("_per_signature" in name and c.get("policy_status") != "completed")]
                defined = [p for p, values in metrics.items() if values and values.get(name) is not None]
                undefined = [p for p in metrics if p not in failures and p not in defined]
                value = None
                if defined and not failures:
                    weights = weights_for(defined, groups, weighting)
                    value = sum((weights[p] * metrics[p][name] for p in defined), Fraction())
                estimates[name] = {"mean": number(value), "expected_problems": len(selected),
                                   "defined_problems": len(defined), "undefined_problems": undefined,
                                   "failed_problems": failures,
                                   "defined_structures": len({groups[p] for p in defined})}
            totals = Counter()
            for cell in selected:
                if cell.get("census_status") == "completed":
                    totals.update(cell["counts"])
            summaries.append({"k": k, "stratum": stratum, "subtype": subtype, "control": control,
                              "weighting": weighting, "problem_count": len(selected),
                              "structure_count": len({groups[c["problem_id"]] for c in selected}),
                              "unavailable_census_problems": [c["problem_id"] for c in selected
                                                              if c.get("census_status") != "completed"],
                              "unavailable_policy_problems": [c["problem_id"] for c in selected
                                                              if c.get("policy_status") != "completed"],
                              "pooled_counts_for_audit_only": dict(totals), "metrics": estimates})
    coincidences = []
    for problem_id in groups:
        for left, right in ((0, 1), (0, 2), (1, 2)):
            a, b = indexed[problem_id, left], indexed[problem_id, right]
            available = a.get("census_status") == b.get("census_status") == "completed"
            coincidences.append({
                "problem_id": problem_id, "k_left": left, "k_right": right,
                "available": available,
                "identical_physical_support": a["expansion"]["support_pin"] == b["expansion"]["support_pin"]
                if available else None,
                "identical_full_signatures": {tuple(r["outcomes"]) for r in a["signature_rows"]}
                == {tuple(r["outcomes"]) for r in b["signature_rows"]} if available else None,
            })
    return {"interpretation": "Within-problem signature fractions and descriptive lookup costs; no deployment prior",
            "conditions": summaries, "earliest_loss": earliest_losses(cells),
            "condition_coincidences": coincidences, "problem_to_group": groups}


def settings():
    value = read(STUDY / "config.json")
    expected = {"evaluation_problems": 40, "development_problems": 4, "omission_budgets": list(KS),
                "evaluation_source": "studies/evidence_acquisition/evaluation_problems.json",
                "development_source": "studies/evidence_acquisition/development_problems.json",
                "group_source": "studies/acquisition_prior_robustness/structure_groups.json",
                "expanded_world_cap": 4096, "signature_cap": 256, "query_cap": 8,
                "outcomes_per_query_cap": 2, "exact_state_cap": 100000,
                "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
    if any(value.get(key) != setting for key, setting in expected.items()):
        raise ValueError("Configuration differs from the bounded authorized design")
    return value


def verify_preservation():
    saved = read(STUDY / "preservation.json")
    if digest(ROOT / saved["local_preservation_manifest"]) != saved["local_preservation_manifest_sha256"]:
        raise ValueError("Historical local-byte manifest changed")
    local = read(ROOT / saved["local_preservation_manifest"])
    for relative, expected in {**saved["tracked_sha256"], **local["sha256"]}.items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"Historical byte preservation mismatch: {relative}")
    return {"tracked_files": len(saved["tracked_sha256"]), "local_files": len(local["sha256"])}


def dependencies():
    names = ["src/tracebench/__init__.py",
             *[f"src/tracebench/evidence_acquisition/{n}.py" for n in
               ("__init__", "model", "certificates", "policies")],
             "studies/acquisition_prior_robustness/sensitivity.py",
             "studies/acquisition_prior_robustness/aggregation.py",
             "studies/acquisition_prior_robustness/structure_groups.json",
             *[f"studies/evidence_acquisition/{n}" for n in
               ("development_problems.json", "evaluation_problems.json")],
             *[f"studies/evidence_acquisition/results/{n}" for n in
               ("signature_runs.json.gz", "certificates.json.gz")],
             *[f"studies/archive_model_misspecification/{n}" for n in
               ("analysis.py", "expanded.py", "reference.py", "config.json", "ANALYSIS.md", "METHOD.md",
                "baseline_verification.json", "development_checks.json", "pre_freeze_checks.json")],
             "tests/test_archive_model_misspecification.py",
             "tests/test_archive_misspecification_reference.py"]
    return [ROOT / name for name in names]


def verify_freeze():
    frozen = read(STUDY / "freeze.json")
    expected = {str(path.relative_to(ROOT)) for path in dependencies()}
    if set(frozen["files_sha256"]) != expected:
        raise ValueError("Incomplete frozen computational dependency closure")
    for relative, expected_hash in frozen["files_sha256"].items():
        if digest(ROOT / relative) != expected_hash:
            raise ValueError(f"Frozen computational input changed: {relative}")
    settings()
    return len(expected)


def freeze():
    settings()
    for name in ("baseline_verification.json", "development_checks.json", "pre_freeze_checks.json"):
        if read(STUDY / name).get("status") != "passed":
            raise ValueError(f"Required pre-freeze check has not passed: {name}")
    if read(STUDY / "pre_freeze_checks.json").get("evaluation_policy_outcomes_observed") != 0:
        raise ValueError("Evaluation already observed or pre-freeze chronology missing")
    value = {"schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
             "label": "Review-informed support expansion on previously examined nominal problems",
             "evaluation_policy_outcomes_observed": 0, "python_version": sys.version,
             "files_sha256": {str(p.relative_to(ROOT)): digest(p) for p in dependencies()},
             "preservation": verify_preservation()}
    write_new(STUDY / "freeze.json", value)
    return {"status": "frozen", "dependencies": verify_freeze()}


def _baseline_exact():
    certificates = read(ORIGINAL / "results/certificates.json.gz")
    runs = read(ORIGINAL / "results/signature_runs.json.gz")
    return {(row["problem_id"], row["signature_index"]): {
        **{key: row[key] for key in ("cost", "query_count", "returned_bytes", "status")},
        "history": certificates[row["certificate"]]["history"],
    } for row in runs if row["policy"] == "exact_optimal" and row["budget_percent"] == 100}


def execute(output, *, development=False):
    from .reference import verify_cell

    config = settings()
    if not development:
        verify_freeze()
    preservation = verify_preservation()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    problems = read(ROOT / config["development_source" if development else "evaluation_source"])
    expected = config["development_problems" if development else "evaluation_problems"]
    if len(problems) != expected:
        raise ValueError("Frozen problem count differs")
    groups = ({p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems} if development
              else read(ROOT / config["group_source"])["problem_to_group"])
    baseline = {} if development else _baseline_exact()
    cells, checks = [], []
    for problem in problems:
        planner = None
        for k in KS:
            cell = None
            try:
                if planner is None:
                    planner = CappedPlanner(Model(problem), "exact_optimal", state_cap=config["exact_state_cap"])
                cell = analyze_cell(problem, k, planner=planner)
                if k == 0 and baseline:
                    for index, row in enumerate(cell["signature_rows"]):
                        saved = baseline[problem["problem_id"], index]
                        if any(row["policy"][key] != value for key, value in saved.items()):
                            raise ValueError("k=0 nominal path differs from saved exact-policy results")
                check = verify_cell(problem, k, cell)
                if check.get("verified") is not True:
                    raise ValueError("Independent checker did not verify a computed cell")
                checks.append({"problem_id": problem["problem_id"], "k": k, "result": check})
            except Exception as error:
                attempted_cell = cell
                cell = {"problem_id": problem["problem_id"], "stratum": problem["stratum"],
                        "subtype": problem.get("subtype", problem["stratum"]), "k": k,
                        "status": "unavailable", "census_status": "unavailable", "policy_status": "unavailable",
                        "failure": {"type": type(error).__name__, "message": str(error)}}
                if attempted_cell is not None:
                    cell["attempted_cell"] = attempted_cell
                checks.append({"problem_id": problem["problem_id"], "k": k, "status": "failed",
                               "failure": cell["failure"]})
            cells.append(cell)
        print(json.dumps({"problem_id": problem["problem_id"], "cells_retained": len(cells)}), flush=True)
    summary = summarize(cells, groups)
    write_new(output / "details.json.gz", cells)
    write_new(output / "per_condition.json", [{key: value for key, value in cell.items()
                                              if key not in {"expansion", "certificates", "signature_rows"}}
                                             for cell in cells])
    write_new(output / "summary.json", summary)
    write_new(output / "independent_verification.json", checks)
    completed = sum(cell["status"] == "completed" for cell in cells)
    validation = {"status": "passed" if completed == len(cells) else "unavailable_cells_retained",
                  "split": "development" if development else "evaluation", "problems": len(problems),
                  "cells": len(cells), "completed_cells": completed,
                  "unavailable_cells": len(cells) - completed, "preservation": verify_preservation(),
                  "initial_preservation": preservation,
                  "frozen_dependencies": None if development else verify_freeze(),
                  "model_calls": 0, "network_requests": 0, "additional_spend_usd": "0"}
    write_new(output / "validation.json", validation)
    write_new(output / "manifest.json", {
        "freeze_sha256": None if development else digest(STUDY / "freeze.json"),
        "files_sha256": {p.name: digest(p) for p in sorted(output.iterdir())},
    })
    if development:
        write_new(STUDY / "development_checks.json", {**validation,
                  "output": str(output.resolve().relative_to(ROOT)),
                  "manifest_sha256": digest(output / "manifest.json"),
                  "evaluation_policy_outcomes_observed": 0})
    return validation


def verify_outputs(output):
    from .reference import verify_cell

    verify_freeze()
    output = Path(output)
    manifest = read(output / "manifest.json")
    if manifest["freeze_sha256"] != digest(STUDY / "freeze.json"):
        raise ValueError("Result freeze pin differs")
    for name, expected in manifest["files_sha256"].items():
        if Path(name).name != name or digest(output / name) != expected:
            raise ValueError("Result manifest file mismatch")
    cells = read(output / "details.json.gz")
    problems = {p["problem_id"]: p for p in read(ROOT / settings()["evaluation_source"])}
    checks = [verify_cell(problems[cell["problem_id"]], cell["k"], cell) for cell in cells]
    groups = read(ROOT / settings()["group_source"])["problem_to_group"]
    if canonical(summarize(cells, groups)) != canonical(read(output / "summary.json")):
        raise ValueError("Saved aggregate differs from exact reaggregation")
    complete = sum(cell["status"] == "completed" for cell in cells)
    return {"status": "passed" if complete == len(cells) else "saved_unavailability_verified",
            "cells_checked": len(checks), "completed_cells": complete,
            "unavailable_cells": len(cells) - complete,
            "scope": "Frozen computational inputs and saved outputs; separate preservation checks cover historical checkout"}


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
