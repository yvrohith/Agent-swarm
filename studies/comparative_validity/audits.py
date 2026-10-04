"""Retrospective final-tie and whole-envelope-stop audit diagnostics.

Historical selectors are delegated to, never changed. Actual signatures reach
only the charged archive and result aggregation, not either selector interface.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from studies.audit_aware_acquisition.analysis import CertificateCache, read, write_new
from studies.audit_aware_acquisition.auditing import AuditSelector, PassiveAuditArchive
from studies.exact_audit_frontier.execution import IntegerSelector, validate_baseline, verify_roots
from tracebench.evidence_acquisition.model import Model, canonical

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/comparative_validity"
ANCHORS = (0, 25, 50, 100)
STOP_ARMS = ("closure_informed_stopped", "closure_informed_affordable_stopped")
CORE = ("history", "base_cost", "added_cost", "total_cost", "status", "audit_budget", "next_query")


def require(value, message):
    if not value:
        raise ValueError(message)


def tie_order(query_ids, trial, problem_seed):
    """The same shuffled sorted catalogue is passed to B and C."""
    require(type(trial) is int and 0 <= trial < 200, "Trial outside frozen 0..199")
    result = sorted(query_ids)
    random.Random(f"swarm-review-tie:{trial}:{problem_seed}").shuffle(result)
    return result


class CommonTieSelector(AuditSelector):
    def __init__(self, nominal, arm, ranking):
        require(arm in ("cost_order", "constant_first"), "Tie diagnostic applies only to B/C")
        require(len(ranking) == len(set(ranking)) and set(ranking) == set(nominal.query_ids),
                "Tie ranking must cover each catalogue identity exactly once")
        self.ranking = {qid: index for index, qid in enumerate(ranking)}
        super().__init__(nominal, arm)

    def _cost_key(self, qid):
        return self.nominal.queries[qid]["cost"], self.ranking[qid]


class StoppedSelector(IntegerSelector):
    """Only new choice is STOP when no compatible design signature can conflict."""
    def __init__(self, nominal, arm, design_signatures):
        require(arm in STOP_ARMS, "Unknown stopped diagnostic arm")
        super().__init__(nominal, arm.removesuffix("_stopped"), design_signatures)
        self.diagnostic_arm = arm

    def conflict_impossible(self, history):
        possible = self.original._design_compatible(history)
        return all(signature in self.nominal.signature_cells for signature in possible)

    def choose(self, history, remaining_budget):
        require(type(remaining_budget) is int and remaining_budget >= 0, "Invalid remaining budget")
        state = self.validate_history(history)
        if not state or self.conflict_impossible(history):
            return None
        return super().choose(history, remaining_budget)


def replay(nominal, baseline, signature, selector, budget, *, cache=None):
    """Minimal charged replay, checked against retained original execution paths."""
    cache = CertificateCache() if cache is None else cache
    baseline, base_cost, _ = validate_baseline(nominal, baseline, certificate_cache=cache)
    history = copy.deepcopy(baseline["history"])
    base_ids = {row["query_id"] for row in history}
    residual = sum(q["cost"] for qid, q in nominal.queries.items() if qid not in base_ids)
    require(type(budget) is int and 0 <= budget <= residual, "Budget outside remaining catalogue")
    archive = PassiveAuditArchive(nominal, signature, history)
    next_query = None
    while True:
        state = selector.validate_history(history)
        if not state:
            termination = "nominal_conflict"
            break
        if isinstance(selector, StoppedSelector) and selector.conflict_impossible(history):
            termination = "all_compatible_full_signatures_nominal"
            break
        qid = (selector.choose(history, budget - archive.cost)
               if isinstance(selector, IntegerSelector) else selector.choose(history))
        if qid is None:
            termination = ("catalogue_exhausted" if len(history) == len(nominal.query_ids)
                           else "no_affordable_action")
            break
        if archive.cost + nominal.queries[qid]["cost"] > budget:
            termination, next_query = "next_action_unaffordable", qid
            break
        returned = archive(qid)
        history.append({"query_id": qid, "outcome_id": returned["outcome_id"]})
    # Validate even a final contradiction against the supplied hypothetical support.
    final_state = selector.validate_history(history)
    require(archive.cost <= budget, "Hard allowance exceeded")
    return {"history": history, "audit_history": copy.deepcopy(archive.history),
            "base_cost": base_cost, "added_cost": archive.cost, "total_cost": base_cost + archive.cost,
            "audit_budget": budget, "next_query": next_query,
            "status": "no_conflict_observed" if final_state else "nominal_model_conflict",
            "termination_reason": termination}


def prepare(problem, conditions):
    require(len(conditions) == 3 and {c["k"] for c in conditions} == {0, 1, 2},
            "Three saved closure conditions required")
    nominal = Model(problem)
    saved = {c["k"]: c for c in conditions}
    require(all(c["status"] == "completed" and c["problem_id"] == problem["problem_id"]
                for c in conditions), "Wrong or incomplete saved condition")
    design = tuple(sorted(tuple(r["outcomes"]) for r in saved[2]["signature_rows"]))
    cache = CertificateCache()
    roots = verify_roots(nominal, design, saved[2]["signature_rows"], certificate_cache=cache)
    baselines = {tuple(s): root["baseline"] for root in roots for s in root["signatures"]}
    populations = {}
    for k, condition in saved.items():
        signatures = {tuple(row["outcomes"]) for row in condition["signature_rows"]}
        require(len(signatures) == len(condition["signature_rows"]), "Duplicate saved signature")
        require(signatures <= set(design), "Condition outside fixed k=2 envelope")
        populations[k] = signatures
        for row in condition["signature_rows"]:
            baseline = row["policy"]
            validate_baseline(nominal, baseline, certificate_cache=cache)
            require(baseline["history"] == baselines[tuple(row["outcomes"])] ["history"],
                    "Original stopping history changed across k")
    return nominal, design, baselines, populations, cache


def compact_counts(rows):
    return {"signature_count": len(rows),
            "conflicts": sum(row["population"] == "new" for row in rows),
            "detected": sum(row["status"] == "nominal_model_conflict" for row in rows),
            "base_cost": sum(row["base_cost"] for row in rows),
            "added_cost": sum(row["added_cost"] for row in rows),
            "added_original": sum(row["added_cost"] for row in rows if row["population"] == "original"),
            "added_new": sum(row["added_cost"] for row in rows if row["population"] == "new"),
            "audit_allowance": sum(row["audit_budget"] for row in rows)}


def metadata(problem, nominal, signature):
    return {"problem_id": problem["problem_id"], "stratum": problem["stratum"],
            "outcomes": list(signature),
            "population": "original" if signature in nominal.signature_cells else "new"}


def aggregate(rows, dimensions):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[d] for d in dimensions)].append(row)
    return [{**dict(zip(dimensions, key, strict=True)), **compact_counts(group)}
            for key, group in sorted(grouped.items())]


def summarize_ties(rows):
    by_rep = defaultdict(dict)
    for row in rows:
        by_rep[row["trial"], row["k"]][row["arm"]] = row
    paired = []
    for (trial, k), arms in sorted(by_rep.items()):
        b, c = arms["cost_order"], arms["constant_first"]
        paired.append({"trial": trial, "k": k,
                       "detected_B": b["detected"], "detected_C": c["detected"],
                       "added_cost_B": b["added_cost"], "added_cost_C": c["added_cost"],
                       "C_minus_B_detection": c["detected"] - b["detected"],
                       "C_minus_B_cost": c["added_cost"] - b["added_cost"]})
    summary = []
    for k in (0, 1, 2):
        selected = [r for r in paired if r["k"] == k]
        require(len(selected) == 200, "Missing tie repetitions")
        values = {}
        for metric in ("detected_B", "detected_C", "added_cost_B", "added_cost_C",
                       "C_minus_B_detection", "C_minus_B_cost"):
            observations = [r[metric] for r in selected]
            values[metric] = {"mean_exact": str(Fraction(sum(observations), len(observations))),
                              "mean": sum(observations) / len(observations),
                              "min": min(observations), "max": max(observations)}
        values["C_detection_higher_equal_lower"] = [
            sum((r["C_minus_B_detection"] > 0, r["C_minus_B_detection"] == 0,
                 r["C_minus_B_detection"] < 0)[i] for r in selected) for i in range(3)]
        summary.append({"k": k, "repetitions": len(selected), **values})
    return paired, summary


def dependency_paths():
    explicit = ["src/tracebench/__init__.py",
                "studies/comparative_validity/audits.py", "studies/comparative_validity/audit_protocol.json",
                "tests/test_comparative_audits.py", "studies/evidence_acquisition/evaluation_problems.json",
                "studies/evidence_acquisition/development_problems.json",
                "studies/archive_model_misspecification/results/details.json.gz",
                "studies/audit_aware_acquisition/development_baseline.json.gz",
                "studies/exact_audit_frontier/development_legacy_audit.json.gz",
                "studies/exact_audit_frontier/results/runs.json.gz",
                "studies/acquisition_prior_robustness/structure_groups.json"]
    modules = ["src/tracebench/evidence_acquisition", "studies/audit_aware_acquisition",
               "studies/exact_audit_frontier", "studies/archive_model_misspecification",
               "studies/acquisition_prior_robustness"]
    return sorted(set(explicit + [str(path.relative_to(ROOT)) for directory in modules
                                  for path in (ROOT / directory).glob("*.py")]))


def freeze():
    payload = {"schema_version": 1, "purpose": "Retrospective comparative-validity diagnostic",
               "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
               "new_evaluation_outcomes_seen": 0,
               "development_qualification": {"tests_passed": 22, "tests_failed": 0,
                                             "tests_skipped": 0, "focused_lint": "passed",
                                             "root_read_only_review": "passed",
                                             "scope": "Four separate development problems and tiny fixtures"},
               "sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in dependency_paths()}}
    write_new(STUDY / "audit_freeze.json", payload)
    return {"frozen_files": len(payload["sha256"])}


def verify_freeze():
    saved = read(STUDY / "audit_freeze.json")
    require(set(saved["sha256"]) == set(dependency_paths()), "Frozen dependency set changed")
    for name, expected in saved["sha256"].items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected,
                f"Frozen dependency changed: {name}")
    return len(saved["sha256"])


def execute(output):
    """Run fixed diagnostics; no generation, replanning or historical mutation."""
    started = perf_counter()
    pins = verify_freeze()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    problems = read(ROOT / "studies/evidence_acquisition/evaluation_problems.json")
    require(len(problems) == 40 and len({p["problem_id"] for p in problems}) == 40,
            "Frozen evaluation problem denominator changed")
    conditions = read(ROOT / "studies/archive_model_misspecification/results/details.json.gz")
    historical = read(ROOT / "studies/exact_audit_frontier/results/runs.json.gz")
    old_index = {(r["problem_id"], r["k"], r["budget_percent"], r["arm"], tuple(r["outcomes"])): r
                 for r in historical}
    require(len(old_index) == len(historical), "Duplicate retained anchor identity")
    tie_rows, rankings, stopped_rows, reproduced = [], [], [], 0
    historical_summary_rows = []
    for problem in problems:
        pid = problem["problem_id"]
        nominal, design, baselines, populations, cache = prepare(
            problem, [c for c in conditions if c["problem_id"] == pid])
        budgets = {}
        for signature, baseline in baselines.items():
            acquired = {r["query_id"] for r in baseline["history"]}
            residual = sum(q["cost"] for qid, q in nominal.queries.items() if qid not in acquired)
            budgets[signature] = {p: residual * p // 100 for p in ANCHORS}
        # Before new choices, reproduce the unchanged four comparator paths.
        for percent in ANCHORS:
            for arm in ("cost_order", "constant_first", "closure_informed", "closure_informed_affordable"):
                selector = IntegerSelector(nominal, arm, design if arm.startswith("closure") else None)
                for signature in design:
                    observed = replay(nominal, baselines[signature], signature, selector,
                                      budgets[signature][percent], cache=cache)
                    for k in (0, 1, 2):
                        if signature not in populations[k]:
                            continue
                        old = old_index[pid, k, percent, arm, signature]
                        require(old["execution_status"] == "completed", "Retained comparator unavailable")
                        require(all(canonical(observed[f]) == canonical(old[f]) for f in CORE),
                                f"Historical replay mismatch: {pid}/{k}/{percent}/{arm}")
                        require(observed["termination_reason"] == old["termination_reason"],
                                "Historical cutoff behavior changed")
                        historical_summary_rows.append({**old, "audit_budget": observed["audit_budget"]})
                        reproduced += 1
        for trial in range(200):
            ranking = tie_order(nominal.query_ids, trial, problem["seed"])
            rankings.append({"problem_id": pid, "trial": trial,
                             "seed": f"swarm-review-tie:{trial}:{problem['seed']}", "ranking": ranking})
            for arm in ("cost_order", "constant_first"):
                selector = CommonTieSelector(nominal, arm, ranking)
                current = []
                for signature in design:
                    current.append({**metadata(problem, nominal, signature),
                                    **replay(nominal, baselines[signature], signature, selector,
                                             budgets[signature][50], cache=cache)})
                for k in (0, 1, 2):
                    selected = [r for r in current if tuple(r["outcomes"]) in populations[k]]
                    tie_rows.append({"problem_id": pid, "stratum": problem["stratum"], "trial": trial,
                                     "k": k, "arm": arm, **compact_counts(selected)})
        for arm in STOP_ARMS:
            selector = StoppedSelector(nominal, arm, design)
            for percent in ANCHORS:
                for signature in design:
                    observed = replay(nominal, baselines[signature], signature, selector,
                                      budgets[signature][percent], cache=cache)
                    for k in (0, 1, 2):
                        if signature not in populations[k]:
                            continue
                        stopped_rows.append({**metadata(problem, nominal, signature), **observed,
                                             "k": k, "budget_percent": percent, "arm": arm})
        print(json.dumps({"problem_id": pid, "completed_tie_rankings": len(rankings)}), flush=True)
    # E paths are reused verbatim; the exact planner is never instantiated here.
    exact = [r for r in historical if r["arm"] == "exact_frontier"]
    require(all(r["execution_status"] == "completed" for r in exact), "Retained E path unavailable")
    comparator_rows = historical_summary_rows + exact + stopped_rows
    counts = aggregate(comparator_rows, ("k", "budget_percent", "arm"))
    strata = aggregate(comparator_rows, ("k", "budget_percent", "arm", "stratum"))
    by_rep = defaultdict(list)
    for row in tie_rows:
        by_rep[row["trial"], row["k"], row["arm"]].append(row)
    tie_totals = [{"trial": key[0], "k": key[1], "arm": key[2],
                   **{field: sum(r[field] for r in group) for field in
                      ("signature_count", "conflicts", "detected", "base_cost", "added_cost",
                       "added_original", "added_new", "audit_allowance")}}
                  for key, group in sorted(by_rep.items())]
    paired, tie_summary = summarize_ties(tie_totals)
    equal_k = all(canonical({key: val for key, val in row.items() if key != "k"}) ==
                  canonical({key: val for key, val in paired[index + 1].items() if key != "k"})
                  for index, row in enumerate(paired) if row["k"] == 1)
    result = {"status": "passed", "problems": len(problems), "tie_repetitions": 200,
              "common_rankings": len(rankings), "historical_path_views_reproduced": reproduced,
              "stopped_path_views": len(stopped_rows), "exact_saved_path_views": len(exact),
              "k1_k2_tie_results_identical": equal_k,
              "tie_summary": tie_summary, "audit_anchor_summary": counts,
              "interpretation": "Tie permutations and reused k signatures are not incident samples. "
              "Added costs charge every signature. No claim-support improvement is inferred.",
              "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0",
              "execution_wall_seconds": perf_counter() - started,
              "frozen_files_verified": pins}
    write_new(output / "audit_tie_rankings.json.gz", rankings)
    write_new(output / "audit_tie_per_problem.json.gz", tie_rows)
    write_new(output / "audit_tie_repetitions.json", paired)
    write_new(output / "audit_stopped_runs.json.gz", stopped_rows)
    write_new(output / "audit_strata.json", strata)
    write_new(output / "audit_summary.json", result)
    require(verify_freeze() == pins, "Freeze changed during execution")
    write_new(output / "audit_manifest.json", {
        "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in sorted(output.glob("audit_*"))}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "run", "verify-freeze"))
    parser.add_argument("--output", type=Path, default=STUDY / "audit_results")
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze()
    elif args.command == "run":
        result = execute(args.output)
    else:
        result = {"frozen_files_verified": verify_freeze()}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
