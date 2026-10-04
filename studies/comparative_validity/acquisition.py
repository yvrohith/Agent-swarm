"""Retrospective competent-baseline comparison on the frozen acquisition inputs.

No generator, provider, network client, or private preservation file is used.
Historical paths are read and checked, not optimized again. New comparators
receive only the same finite nominal model and paid history.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path

from studies.acquisition_prior_robustness.aggregation import average, weights_for
from studies.acquisition_prior_robustness.sensitivity import (
    DISTRIBUTIONS,
    MODES,
    _trajectory_check,
    deployment_priors,
    number,
    saved_trajectories,
    summarize_trajectories,
    with_prior,
)
from tracebench.evidence_acquisition.model import Model, indices, pin
from tracebench.evidence_acquisition.policies import (
    POLICIES,
    ChargedLookup,
    Planner,
    run_policy,
    schema_order,
)

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/comparative_validity"
ORIGINAL = ROOT / "studies/evidence_acquisition"
PRIOR = ROOT / "studies/acquisition_prior_robustness"
NEW_POLICIES = ("schema_skip", "terminal_class_entropy")
ALL_POLICIES = (*POLICIES, *NEW_POLICIES)
GAIN_TOLERANCE = 1e-12
COMPARISONS = tuple(("pair_cut", p) for p in ALL_POLICIES if p != "pair_cut") + (
    ("schema_skip", "exact_optimal"), ("terminal_class_entropy", "exact_optimal"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    data = Path(path).read_bytes()
    if str(path).endswith(".gz"):
        data = gzip.decompress(data)
    return json.loads(data, object_pairs_hook=unique)


def write_new(path, value):
    path = Path(path)
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if path.suffix == ".gz":
        data = gzip.compress(data, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def terminal_entropy(model, state):
    """Entropy of complete-archive class tau, not Boolean claim/world entropy."""
    mass = model.mass(state)
    require(mass > 0, "entropy requires a nonempty state")
    classes = defaultdict(Fraction)
    for i in indices(state):
        classes[model.tau[i]] += model.priors[i]
    return -math.fsum(float(p / mass) * math.log2(float(p / mass))
                      for _, p in sorted(classes.items()))


def terminal_gain(model, state, query_id):
    mass = model.mass(state)
    after = math.fsum(float(model.mass(child) / mass) * terminal_entropy(model, child)
                      for _, child in sorted(model.partition(state, query_id).items()) if child)
    result = terminal_entropy(model, state) - after
    require(result >= -GAIN_TOLERANCE, "materially negative class information gain")
    return max(0.0, result)


class ComparativePlanner(Planner):
    """Two fixed baseline rules; the historical policy module stays unchanged."""

    def __init__(self, model, policy):
        require(policy in NEW_POLICIES, "unknown comparison policy")
        super().__init__(model, "schema_aware")
        self.policy = policy
        self.order = schema_order(model)

    def choose(self, history):
        remaining = self._remaining(history)
        state = self.model.compatible(history)
        if not state or self.model.terminal(state) is not None:
            return None
        remaining = tuple(q for q in remaining
                          if sum(bool(s) for s in self.model.partition(state, q).values()) > 1)
        require(remaining, "nonterminal archive has no nonconstant query")
        if self.policy == "schema_skip":
            return remaining[0]
        scores = {q: terminal_gain(self.model, state, q) / self.model.queries[q]["cost"]
                  for q in remaining}
        best = max(scores.values())
        # Complementary zero-gain queries must not be mistaken for irreducibility.
        candidates = (remaining if best <= GAIN_TOLERANCE else
                      tuple(q for q in remaining if best - scores[q] <= GAIN_TOLERANCE))
        return min(candidates, key=lambda q: (self.model.queries[q]["cost"], q))


def run_comparator(model, policy):
    planner = ComparativePlanner(model, policy)
    paths, certificates = [], {}
    for index, signature in enumerate(sorted(model.signature_cells)):
        result = run_policy(model, policy, ChargedLookup(model, signature), planner=planner)
        certificate = result["certificate"]
        certificate_id = pin(certificate)
        certificates[certificate_id] = certificate
        path = {k: copy.deepcopy(result[k]) for k in
                ("cost", "query_count", "returned_bytes", "status", "history", "certificate_valid")}
        path.update(signature_index=index, certificate=certificate_id)
        _trajectory_check(model, signature, path, certificate)
        paths.append(path)
    return paths, certificates


def check_ec2(model, states):
    """Independent explicit hypothesis-pair arithmetic, sharing declared tau."""
    planner = Planner(model, "pair_cut")
    checked = 0

    def edges(state):
        return sum((model.priors[i] * model.priors[j]
                    for i, j in combinations(indices(state), 2) if model.tau[i] != model.tau[j]),
                   Fraction())

    for state in sorted(set(states)):
        require(state > 0, "empty EC2 comparison state")
        require(planner.edge_mass(state) == edges(state), "EC2 edge weight mismatch")
        for q in model.queries:
            expected = edges(state) - sum(
                (model.mass(child) / model.mass(state) * edges(child)
                 for child in model.partition(state, q).values() if child), Fraction())
            require(planner.pair_gain(state, q) == expected, "EC2 expected cut mismatch")
            checked += 1
    return checked


def new_problem_results(problem):
    """Complete finite expectations, reweighting q0 paths versus matched planning."""
    base = Model(problem)
    priors = deployment_priors(base)
    rows, all_paths, certificates, ec2_checks = [], [], {}, 0
    original = {}
    for policy in NEW_POLICIES:
        original[policy], produced = run_comparator(base, policy)
        certificates.update(produced)
    common = {key: problem[key] for key in ("problem_id", "seed", "stratum", "subtype")}
    common["structure_group"] = problem["unweighted_structure_fingerprint"]
    for deployment, weights in priors.items():
        changed = with_prior(base, weights)
        visited = {base.full_state}
        for policy in NEW_POLICIES:
            for mode in MODES:
                if mode == "frozen_p0" or policy == "schema_skip" or deployment == "q0":
                    paths = original[policy]
                    certificate_model = base
                else:
                    paths, produced = run_comparator(changed, policy)
                    certificates.update(produced)
                    certificate_model = changed
                for path in paths:
                    signature = sorted(changed.signature_cells)[path["signature_index"]]
                    _trajectory_check(certificate_model, signature, path, certificates[path["certificate"]])
                    for length in range(len(path["history"]) + 1):
                        history = path["history"][:length]
                        state = base.compatible(history)
                        require(state == changed.compatible(history)
                                and base.terminal(state) == changed.terminal(state),
                                "positive-prior change altered support")
                        visited.add(state)
                    all_paths.append({**common, "deployment": deployment,
                                      "planning_mode": mode, "policy": policy, **path})
                rows.append({**common, "deployment": deployment, "planning_mode": mode,
                             "policy": policy, "availability": "complete",
                             "coincides_with": [name for name, prior in priors.items()
                                                if name != deployment and prior == weights],
                             "trajectory_source": "new_q0_paths_reweighted" if mode == "frozen_p0"
                             else "new_matched_prior_rule",
                             **summarize_trajectories(base, weights, paths)})
        ec2_checks += check_ec2(changed, visited)
    return {"rows": rows, "trajectories": all_paths, "certificates": certificates,
            "ec2_pair_arithmetic_checks": ec2_checks}


def historical_rows(problems):
    """Check every retained prior row against paid signature paths and certificates.

    This is same-model accounting validation, not a new exact solve or an
    independent physical-semantics implementation.
    """
    runs = read(ORIGINAL / "results/signature_runs.json.gz")
    certificates = read(ORIGINAL / "results/certificates.json.gz")
    rows = read(PRIOR / "results/per_problem.json")
    details = read(PRIOR / "results/details.json.gz")
    detail_map = {row["problem_id"]: row for row in details}
    require(len(detail_map) == len(details) == len(problems), "historical problem identities differ")
    indexed = {}
    for row in rows:
        key = tuple(row[k] for k in ("problem_id", "deployment", "planning_mode", "policy"))
        require(key not in indexed, "duplicate historical condition")
        indexed[key] = row
    expected = set(product([p["problem_id"] for p in problems], DISTRIBUTIONS, MODES, POLICIES))
    require(set(indexed) == expected, "historical condition grid differs")
    checked = 0
    for problem in problems:
        base = Model(problem)
        saved = saved_trajectories(base, runs, certificates)
        detail = detail_map[problem["problem_id"]]
        require(not detail["failures"], "historical unavailable result needs explicit handling")
        for deployment, weights in deployment_priors(base).items():
            changed = with_prior(base, weights)
            for mode, policy in product(MODES, POLICIES):
                row = indexed[problem["problem_id"], deployment, mode, policy]
                if mode == "frozen_p0" or policy in {"read_all", "schema_aware"}:
                    paths = saved[policy]
                    certs = certificates
                    certificate_model = base
                else:
                    paths = sorted((p for p in detail["trajectories"] if p["deployment"] == deployment
                                    and p["policy"] == policy and p["planning_mode"] == mode),
                                   key=lambda p: p["signature_index"])
                    certs = detail["certificates"]
                    certificate_model = changed
                for path in paths:
                    signature = sorted(changed.signature_cells)[path["signature_index"]]
                    _trajectory_check(certificate_model, signature, path, certs[path["certificate"]])
                metrics = summarize_trajectories(base, weights, paths)
                require(metrics["expected"] == row["expected"], "historical exact accounting differs")
                require(row["availability"] == "complete", "historical unavailable row")
                if deployment == "q0":
                    original = summarize_trajectories(base, weights, saved[policy])
                    require(original["expected"] == row["expected"], "q0 original score mismatch")
                checked += 1
    return copy.deepcopy(rows), checked


def summarize(rows, problems):
    groups = {p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems}
    strata = {p["problem_id"]: p["stratum"] for p in problems}
    indexed = {}
    for row in rows:
        key = tuple(row[k] for k in ("problem_id", "deployment", "planning_mode", "policy"))
        require(key not in indexed, "duplicate condition")
        require(row["availability"] == "complete", "unavailable comparison must remain explicit")
        indexed[key] = row
    require(set(indexed) == set(product(groups, DISTRIBUTIONS, MODES, ALL_POLICIES)),
            "incomplete comparison grid")
    for pid, deployment, mode, policy in indexed:
        row = indexed[pid, deployment, mode, policy]
        optimum = Fraction(indexed[pid, deployment, "matched_q", "exact_optimal"]
                           ["expected"]["cost"]["exact"])
        cost = Fraction(row["expected"]["cost"]["exact"])
        require(cost >= optimum, "comparison beats saved matched exact optimum")
        row["matched_optimum"] = number(optimum)
        row["optimum_excess"] = number(cost - optimum)
        row["optimum_ratio"] = number(cost / optimum) if optimum else None
        row["zero_optimum"] = optimum == 0
    policy_summaries, paired, per_problem = [], [], []
    populations = {"all": sorted(groups), **{s: sorted(pid for pid in groups if strata[pid] == s)
                                           for s in sorted(set(strata.values()))}}
    for deployment, mode in product(DISTRIBUTIONS, MODES):
        for left, right in COMPARISONS:
            for pid in sorted(groups):
                lcost = Fraction(indexed[pid, deployment, mode, left]["expected"]["cost"]["exact"])
                rcost = Fraction(indexed[pid, deployment, mode, right]["expected"]["cost"]["exact"])
                per_problem.append({"problem_id": pid, "stratum": strata[pid], "structure_group": groups[pid],
                                    "deployment": deployment, "planning_mode": mode,
                                    "left": left, "right": right, "left_cost": number(lcost),
                                    "right_cost": number(rcost), "left_minus_right": number(lcost - rcost),
                                    "relation": "win" if lcost < rcost else "loss" if lcost > rcost else "tie"})
        for weighting, (stratum, ids) in product(("equal_problem", "structure_balanced"), populations.items()):
            common = {"deployment": deployment, "planning_mode": mode, "weighting": weighting,
                      "stratum": stratum, "problem_count": len(ids),
                      "structure_group_count": len({groups[pid] for pid in ids})}
            for policy in ALL_POLICIES:
                selected = {pid: indexed[pid, deployment, mode, policy] for pid in ids}
                costs = {pid: Fraction(r["expected"]["cost"]["exact"]) for pid, r in selected.items()}
                gaps = {pid: Fraction(r["optimum_excess"]["exact"]) for pid, r in selected.items()}
                positive = [pid for pid, r in selected.items() if not r["zero_optimum"]]
                ratios = {pid: Fraction(selected[pid]["optimum_ratio"]["exact"]) for pid in positive}
                policy_summaries.append({**common, "policy": policy,
                    "expected_cost": average(costs, ids, groups, weighting),
                    "matched_optimum_excess": average(gaps, ids, groups, weighting),
                    "zero_optimum_problems": [pid for pid, r in selected.items() if r["zero_optimum"]],
                    "zero_cost_problems": [pid for pid, cost in costs.items() if cost == 0],
                    "positive_optimum_ratio": average(ratios, positive, groups, weighting) if positive else None})
            for left, right in COMPARISONS:
                values = {pid: Fraction(indexed[pid, deployment, mode, left]["expected"]["cost"]["exact"])
                          - Fraction(indexed[pid, deployment, mode, right]["expected"]["cost"]["exact"])
                          for pid in ids}
                weighted = weights_for(ids, groups, weighting)
                paired.append({**common, "left": left, "right": right,
                    "left_minus_right": average(values, ids, groups, weighting),
                    "wins": sum(v < 0 for v in values.values()), "ties": sum(v == 0 for v in values.values()),
                    "losses": sum(v > 0 for v in values.values()),
                    "weighted_win_mass": number(sum((weighted[p] for p in ids if values[p] < 0), Fraction())),
                    "weighted_tie_mass": number(sum((weighted[p] for p in ids if values[p] == 0), Fraction())),
                    "weighted_loss_mass": number(sum((weighted[p] for p in ids if values[p] > 0), Fraction()))})
    return {"policy_summaries": policy_summaries, "paired_summaries": paired,
            "per_problem_contrasts": per_problem,
            "weighting": "Equal problem, or mean within the existing structure groups then equal groups; within-stratum weights are recomputed within that fixed stratum.",
            "interpretation": "Finite-model expectations and algorithmic comparisons, not incident samples; no sampling intervals."}


def source_dependencies():
    return ["studies/comparative_validity/acquisition.py",
            "studies/comparative_validity/acquisition_protocol.json",
            "tests/test_comparative_acquisition.py", "src/tracebench/__init__.py",
            "tests/test_acquisition_policies.py",
            *[f"src/tracebench/evidence_acquisition/{name}.py" for name in
              ("__init__", "model", "certificates", "policies")],
            "studies/acquisition_prior_robustness/sensitivity.py",
            "studies/acquisition_prior_robustness/aggregation.py",
            "studies/acquisition_prior_robustness/structure_groups.json",
            "studies/evidence_acquisition/evaluation_problems.json",
            "studies/evidence_acquisition/development_problems.json",
            "studies/evidence_acquisition/results/signature_runs.json.gz",
            "studies/evidence_acquisition/results/certificates.json.gz",
            "studies/acquisition_prior_robustness/results/per_problem.json",
            "studies/acquisition_prior_robustness/results/details.json.gz"]


def create_freeze(prechecks):
    require(prechecks.get("status") == "passed" and prechecks.get("evaluation_outcomes_observed") == 0,
            "freeze requires passed prechecks before evaluation")
    require(prechecks.get("focused_tests_passed", 0) > 0 and prechecks.get("code_review"),
            "freeze requires focused tests and a code review")
    payload = {"schema_version": 1, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
               "prechecks": copy.deepcopy(prechecks),
               "dependencies_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
                                        for f in source_dependencies()}}
    write_new(STUDY / "acquisition_freeze.json", payload)
    return payload


def verify_freeze():
    frozen = read(STUDY / "acquisition_freeze.json")
    require(frozen["prechecks"]["status"] == "passed"
            and frozen["prechecks"]["evaluation_outcomes_observed"] == 0,
            "invalid pre-evaluation freeze")
    pins = frozen["dependencies_sha256"]
    require(set(pins) == set(source_dependencies()), "freeze dependency closure differs")
    for name, expected in pins.items():
        require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected,
                f"freeze mismatch: {name}")
    return len(pins)


def execute(output):
    frozen_dependencies = verify_freeze()
    output = Path(output)
    require(not output.exists(), "comparison output directory already exists; use a fresh path")
    problems = read(ORIGINAL / "evaluation_problems.json")
    require(len(problems) == 40 and len({p["problem_id"] for p in problems}) == 40
            and all(p["split"] == "evaluation" for p in problems), "evaluation problem scope differs")
    group_document = read(PRIOR / "structure_groups.json")
    saved_groups = {pid: group["group_id"] for group in group_document["groups"] for pid in group["members"]}
    require(saved_groups == {p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems},
            "structure group assignment changed")
    references, checked = historical_rows(problems)
    details = [new_problem_results(problem) for problem in problems]
    rows = references + [row for detail in details for row in detail["rows"]]
    summary = summarize(rows, problems)
    targets = {"pair_cut": Fraction("3.793750"), "schema_skip": Fraction("3.721875"),
               "terminal_class_entropy": Fraction("3.50703125")}
    target_checks = {}
    for policy, target in targets.items():
        selected = [r for r in summary["policy_summaries"] if r["policy"] == policy
                    and r["deployment"] == "q0" and r["planning_mode"] == "frozen_p0"
                    and r["weighting"] == "equal_problem" and r["stratum"] == "all"]
        actual = Fraction(selected[0]["expected_cost"]["mean"]["exact"])
        target_checks[policy] = {"supplied_target": number(target), "actual": number(actual),
                                 "matches": actual == target, "difference": number(actual - target)}
    pair = next(r for r in summary["paired_summaries"] if r["left"] == "pair_cut"
                and r["right"] == "schema_skip" and r["deployment"] == "q0"
                and r["planning_mode"] == "frozen_p0" and r["weighting"] == "equal_problem"
                and r["stratum"] == "all")
    target_checks["pair_cut_vs_schema_skip_counts"] = {
        "supplied": [13, 14, 13], "actual": [pair["wins"], pair["ties"], pair["losses"]],
        "matches": [pair["wins"], pair["ties"], pair["losses"]] == [13, 14, 13]}
    require(verify_freeze() == frozen_dependencies, "freeze closure changed during execution")
    write_new(output / "acquisition_rows.json", rows)
    write_new(output / "acquisition_summary.json", summary)
    write_new(output / "acquisition_details.json.gz", details)
    validation = {"status": "passed", "problems": 40, "structure_groups": len(set(saved_groups.values())),
                  "frozen_dependencies_verified": frozen_dependencies,
                  "historical_exact_rows_reproduced_from_saved_paths": checked,
                  "comparison_rows": len(rows), "new_comparator_rows": len(rows) - checked,
                  "ec2_explicit_pair_arithmetic_checks": sum(d["ec2_pair_arithmetic_checks"] for d in details),
                  "supplied_q0_targets": target_checks, "historical_policies_reoptimized": False,
                  "semantic_check_scope": "Existing Model/certificate checker plus explicit pair arithmetic and paid-path accounting; not independent physical semantics.",
                  "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0"}
    write_new(output / "acquisition_validation.json", validation)
    files = ["acquisition_rows.json", "acquisition_summary.json", "acquisition_details.json.gz",
             "acquisition_validation.json"]
    write_new(output / "acquisition_manifest.json", {
        "results_sha256": {f: hashlib.sha256((output / f).read_bytes()).hexdigest() for f in files},
        "dependencies_sha256": {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
                                 for f in source_dependencies()}})
    require(verify_freeze() == frozen_dependencies, "freeze closure changed at execution end")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(execute(arguments.output), sort_keys=True))
