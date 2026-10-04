"""Public saved-result checks with independently written filtering and arithmetic.

No selector, planner, generator, summary helper, network, or private artifact is
used. The existing Model supplies shared physical semantics and nominal answer
signatures: these checks are not an independent physical model or human review.
Only saved B/C rankings are replayed, and no new optimization is performed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import product
from pathlib import Path

from tracebench.evidence_acquisition.model import Model

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/comparative_validity"
PRIORS = ("q0", "qS", "qT", "qMinus", "qPlus")
MODES = ("frozen_p0", "matched_q")
ARMS = ("read_all", "schema_aware", "world_entropy", "pair_cut", "exact_optimal",
        "schema_skip", "terminal_class_entropy")
COUNTS = ("signature_count", "conflicts", "detected", "base_cost", "added_cost",
          "added_original", "added_new", "audit_allowance")


def check(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            check(key not in result, "Duplicate JSON object key")
            result[key] = value
        return result
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith(".gz") else data,
                      object_pairs_hook=unique)


def index(rows, fields):
    result = {}
    for row in rows:
        key = tuple(tuple(row[f]) if isinstance(row[f], list) else row[f] for f in fields)
        check(key not in result, f"Duplicate result identity: {key}")
        result[key] = row
    return result


def verify_pins(base, pins):
    for name, expected in pins.items():
        path = (base / name).resolve()
        check(not Path(name).is_absolute() and path.is_relative_to(base.resolve()), "Path escape")
        check(path.is_file(), f"Missing pinned public file: {name}")
        check(hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"Changed public bytes: {name}")
    return len(pins)


def fraction(value):
    check(isinstance(value, dict) and set(value) == {"exact", "value"}, "Invalid exact number")
    number = Fraction(value["exact"])
    check(float(number) == value["value"], "Inconsistent rational display value")
    return number


def compatible(signatures, positions, history):
    return {s for s in signatures if all(s[positions[r["query_id"]]] == r["outcome_id"]
                                        for r in history)}


def conflict_impossible(nominal, design, positions, history):
    possible = compatible(design, positions, history)
    check(possible, "Paid history outside hypothetical envelope")
    return possible <= nominal


def counts(rows):
    return {"signature_count": len(rows),
            "conflicts": sum(r["population"] == "new" for r in rows),
            "detected": sum(r["status"] == "nominal_model_conflict" for r in rows),
            "base_cost": sum(r["base_cost"] for r in rows),
            "added_cost": sum(r["added_cost"] for r in rows),
            "added_original": sum(r["added_cost"] for r in rows if r["population"] == "original"),
            "added_new": sum(r["added_cost"] for r in rows if r["population"] == "new"),
            "audit_allowance": sum(r["audit_budget"] for r in rows)}


def check_grouped(rows, saved, dimensions):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[d] for d in dimensions)].append(row)
    indexed = index(saved, dimensions)
    check(set(groups) == set(indexed), "Aggregate condition grid differs")
    for key, group in groups.items():
        check(all(indexed[key][f] == value for f, value in counts(group).items()), "Aggregate differs")


def verify_audits(problems, models):
    out = STUDY / "audit_results"
    pins = verify_pins(out, read(out / "audit_manifest.json")["sha256"])
    conditions = read(ROOT / "studies/archive_model_misspecification/results/details.json.gz")
    condition_index = index(conditions, ("problem_id", "k"))
    check(set(condition_index) == set(product(models, range(3))), "Closure grid differs")
    retained = read(ROOT / "studies/exact_audit_frontier/results/runs.json.gz")
    old = index(retained, ("problem_id", "k", "budget_percent", "arm", "outcomes"))
    stopped = read(out / "audit_stopped_runs.json.gz")
    stopped_index = index(stopped, ("problem_id", "k", "budget_percent", "arm", "outcomes"))
    rank_rows = read(out / "audit_tie_rankings.json.gz")
    ranks = index(rank_rows, ("problem_id", "trial"))
    tie_rows = read(out / "audit_tie_per_problem.json.gz")
    ties = index(tie_rows, ("problem_id", "trial", "k", "arm"))
    check(set(ranks) == set(product(models, range(200))), "Common ranking grid differs")
    check(set(ties) == set(product(models, range(200), range(3), ("cost_order", "constant_first"))),
          "Tie condition grid differs")
    expected_stops = set()
    checked_paths = 0
    for problem in problems:
        pid, model = problem["problem_id"], models[problem["problem_id"]]
        positions = {q: i for i, q in enumerate(model.query_ids)}
        costs = {q: row["cost"] for q, row in model.queries.items()}
        nominal = set(model.answers)
        population_rows = {k: condition_index[pid, k]["signature_rows"] for k in range(3)}
        populations = {k: {tuple(r["outcomes"]) for r in rows} for k, rows in population_rows.items()}
        check(all(len(populations[k]) == len(population_rows[k]) for k in range(3)), "Duplicate signature")
        check(populations[0] == nominal and populations[0] <= populations[1] <= populations[2],
              "Nested signature support differs")
        design = populations[2]
        baselines = {tuple(r["outcomes"]): r["policy"]["history"] for r in population_rows[2]}
        for k, rows in population_rows.items():
            for row in rows:
                signature = tuple(row["outcomes"])
                check(row["policy"]["history"] == baselines[signature], "Baseline changed across k")
                for percent, arm in product((0, 25, 50, 100),
                                            ("closure_informed_stopped", "closure_informed_affordable_stopped")):
                    key = pid, k, percent, arm, signature
                    expected_stops.add(key)
                    saved = stopped_index[key]
                    historical = old[pid, k, percent, arm.removesuffix("_stopped"), signature]
                    history, base = saved["history"], baselines[signature]
                    check(history == historical["history"][:len(history)] and history[:len(base)] == base,
                          "Stopped history is not the unchanged paid-prefix")
                    check(len({r["query_id"] for r in history}) == len(history), "Duplicate paid query")
                    check(signature in compatible(design, positions, history), "Paid outcome mismatch")
                    base_cost = sum(costs[r["query_id"]] for r in base)
                    added = sum(costs[r["query_id"]] for r in history[len(base):])
                    budget = (sum(costs.values()) - base_cost) * percent // 100
                    check((saved["base_cost"], saved["added_cost"], saved["total_cost"], saved["audit_budget"])
                          == (base_cost, added, base_cost + added, budget) and added <= budget,
                          "Stopped charges or allowance differ")
                    for length in range(len(base), len(history)):
                        prefix = history[:length]
                        check(compatible(nominal, positions, prefix), "Continued after first conflict")
                        check(not conflict_impossible(nominal, design, positions, prefix), "Missed permitted stop")
                    alarm = not compatible(nominal, positions, history)
                    impossible = conflict_impossible(nominal, design, positions, history)
                    check(saved["status"] == ("nominal_model_conflict" if alarm else "no_conflict_observed"),
                          "Stopped conflict status differs")
                    check(saved["population"] == ("original" if signature in nominal else "new"),
                          "Signature population differs")
                    if alarm:
                        check(saved["termination_reason"] == "nominal_conflict", "Missing first-conflict stop")
                    elif impossible:
                        check(saved["termination_reason"] == "all_compatible_full_signatures_nominal"
                              and saved["next_query"] is None, "Missing whole-envelope stop")
                    else:
                        check(history == historical["history"]
                              and saved["termination_reason"] == historical["termination_reason"]
                              and saved["next_query"] == historical["next_query"], "Other cutoff changed")
                    checked_paths += 1
        for trial in range(200):
            ranking = ranks[pid, trial]
            seed = f"swarm-review-tie:{trial}:{problem['seed']}"
            expected = sorted(model.query_ids)
            random.Random(seed).shuffle(expected)
            check(ranking["seed"] == seed and ranking["ranking"] == expected, "Tie convention differs")
            priority = {qid: i for i, qid in enumerate(expected)}
            for arm in ("cost_order", "constant_first"):
                replayed = []
                for signature in sorted(design):
                    base = baselines[signature]
                    history = list(base)
                    acquired = {r["query_id"] for r in base}
                    base_cost = sum(costs[q] for q in acquired)
                    budget = (sum(costs.values()) - base_cost) // 2
                    added = 0
                    possible = compatible(nominal, positions, history)
                    while possible and len(acquired) < len(costs):
                        remaining = set(costs) - acquired
                        if arm == "constant_first":
                            constant = {q for q in remaining if len({s[positions[q]] for s in possible}) == 1}
                            remaining = constant or remaining
                        qid = min(remaining, key=lambda q: (costs[q], priority[q]))
                        if added + costs[qid] > budget:
                            break
                        acquired.add(qid)
                        added += costs[qid]
                        history.append({"query_id": qid, "outcome_id": signature[positions[qid]]})
                        possible = compatible(possible, positions, history[-1:])
                    replayed.append({"outcomes": signature, "population": "original" if signature in nominal else "new",
                                     "status": "no_conflict_observed" if possible else "nominal_model_conflict",
                                     "base_cost": base_cost, "added_cost": added, "audit_budget": budget})
                for k in range(3):
                    expected = counts([r for r in replayed if r["outcomes"] in populations[k]])
                    check(all(ties[pid, trial, k, arm][key] == value for key, value in expected.items()),
                          "Independent tie replay differs")
    check(set(stopped_index) == expected_stops, "Stopped condition grid differs")
    summary = read(out / "audit_summary.json")
    comparators = [r for r in retained if r["arm"] in
                  {"cost_order", "constant_first", "closure_informed", "closure_informed_affordable", "exact_frontier"}]
    check_grouped(comparators + stopped, summary["audit_anchor_summary"], ("k", "budget_percent", "arm"))
    check_grouped(comparators + stopped, read(out / "audit_strata.json"),
                  ("k", "budget_percent", "arm", "stratum"))
    repetitions = index(read(out / "audit_tie_repetitions.json"), ("trial", "k"))
    check(set(repetitions) == set(product(range(200), range(3))), "Tie repetition grid differs")
    for trial, k in repetitions:
        saved = repetitions[trial, k]
        totals = {arm: {field: sum(ties[pid, trial, k, arm][field] for pid in models) for field in COUNTS}
                  for arm in ("cost_order", "constant_first")}
        check(saved["detected_B"] == totals["cost_order"]["detected"]
              and saved["detected_C"] == totals["constant_first"]["detected"]
              and saved["added_cost_B"] == totals["cost_order"]["added_cost"]
              and saved["added_cost_C"] == totals["constant_first"]["added_cost"]
              and saved["C_minus_B_detection"] == saved["detected_C"] - saved["detected_B"]
              and saved["C_minus_B_cost"] == saved["added_cost_C"] - saved["added_cost_B"], "Paired tie totals differ")
    for saved in summary["tie_summary"]:
        selected = [r for (trial, k), r in repetitions.items() if k == saved["k"]]
        for field in ("detected_B", "detected_C", "added_cost_B", "added_cost_C", "C_minus_B_detection", "C_minus_B_cost"):
            values = [r[field] for r in selected]
            expected = {"mean_exact": str(Fraction(sum(values), 200)), "mean": sum(values) / 200,
                        "min": min(values), "max": max(values)}
            check(saved[field] == expected, "Tie mean/range differs")
        check(saved["C_detection_higher_equal_lower"] == [sum(r["C_minus_B_detection"] > 0 for r in selected),
              sum(r["C_minus_B_detection"] == 0 for r in selected), sum(r["C_minus_B_detection"] < 0 for r in selected)],
              "Tie win counts differ")
    check(all({f: v for f, v in repetitions[trial, 1].items() if f != "k"}
              == {f: v for f, v in repetitions[trial, 2].items() if f != "k"} for trial in range(200)),
          "Saved k=1/k=2 identity claim differs")
    return {"result_pins": pins, "stopped_paid_paths": checked_paths, "common_rankings": len(ranks),
            "independently_replayed_tie_problem_conditions": len(ties), "paired_tie_totals": len(repetitions),
            "all_anchor_and_stratum_aggregates": "passed"}


def prior_weights(model):
    signature_sizes, class_sizes = Counter(model.answers), Counter(model.tau)
    presence = [sum(model.queries[q]["outcomes"][outcome]["kind"] != "lookup_empty"
                    for q, outcome in zip(model.query_ids, signature, strict=True)) for signature in model.answers]
    raw = {"q0": model.priors,
           "qS": [Fraction(1, len(signature_sizes) * signature_sizes[s]) for s in model.answers],
           "qT": [Fraction(1, len(class_sizes) * class_sizes[t]) for t in model.tau],
           "qMinus": [p / 2 ** b for p, b in zip(model.priors, presence, strict=True)],
           "qPlus": [p * 2 ** b for p, b in zip(model.priors, presence, strict=True)]}
    return {name: tuple(p / sum(weights) for p in weights) for name, weights in raw.items()}


def average(values, ids, groups, weighting):
    members = Counter(groups[pid] for pid in ids)
    weights = {pid: Fraction(1, len(ids)) if weighting == "equal_problem"
               else Fraction(1, len(members) * members[groups[pid]]) for pid in ids}
    return sum((weights[pid] * values[pid] for pid in ids), Fraction()), weights


def check_average(saved, values, ids, groups, weighting):
    mean, weights = average(values, ids, groups, weighting)
    check(fraction(saved["mean"]) == mean and fraction(saved["observed_weighted_sum"]) == mean
          and fraction(saved["available_weight"]) == 1 and saved["missing_problems"] == []
          and saved["expected_problems"] == saved["available_problems"] == len(ids), "Weighted summary differs")
    return weights


def verify_acquisition(problems, models):
    out = STUDY / "results/acquisition_results"
    manifest = read(out / "acquisition_manifest.json")
    pin_count = verify_pins(out, manifest["results_sha256"])
    pin_count += verify_pins(ROOT, manifest["dependencies_sha256"])
    rows = read(out / "acquisition_rows.json")
    indexed = index(rows, ("problem_id", "deployment", "planning_mode", "policy"))
    check(set(indexed) == set(product(models, PRIORS, MODES, ARMS)), "Acquisition condition grid differs")
    detail_rows = read(out / "acquisition_details.json.gz")
    details = {d["rows"][0]["problem_id"]: d for d in detail_rows}
    check(len(details) == len(detail_rows), "Duplicate new acquisition problem")
    check(set(details) == set(models), "New path problem grid differs")
    previous = {d["problem_id"]: d for d in read(ROOT / "studies/acquisition_prior_robustness/results/details.json.gz")}
    original = read(ROOT / "studies/evidence_acquisition/results/signature_runs.json.gz")
    original_certificates = read(ROOT / "studies/evidence_acquisition/results/certificates.json.gz")
    base_paths = defaultdict(list)
    for row in original:
        if row["budget_percent"] == 100:
            path = dict(row, history=original_certificates[row["certificate"]]["history"])
            base_paths[row["problem_id"], row["policy"]].append(path)
    checked_paths = 0
    groups = {p["problem_id"]: p["unweighted_structure_fingerprint"] for p in problems}
    group_document = read(ROOT / "studies/acquisition_prior_robustness/structure_groups.json")
    check(groups == {pid: g["group_id"] for g in group_document["groups"] for pid in g["members"]}, "Structure groups differ")
    strata = {p["problem_id"]: p["stratum"] for p in problems}
    costs = {}
    for pid, model in models.items():
        weights = prior_weights(model)
        signatures = sorted(set(model.answers))
        positions = {q: i for i, q in enumerate(model.query_ids)}
        for deployment, mode, arm in product(PRIORS, MODES, ARMS):
            key = pid, deployment, mode, arm
            saved = indexed[key]
            check(saved["availability"] == "complete" and saved["stratum"] == strata[pid]
                  and saved["structure_group"] == groups[pid], "Acquisition identity unavailable or differs")
            if arm in ARMS[-2:]:
                paths = [p for p in details[pid]["trajectories"] if (p["deployment"], p["planning_mode"], p["policy"])
                         == (deployment, mode, arm)]
            elif mode == "frozen_p0" or arm in ("read_all", "schema_aware"):
                paths = base_paths[pid, arm]
            else:
                paths = [p for p in previous[pid]["trajectories"] if (p["deployment"], p["planning_mode"], p["policy"])
                         == (deployment, mode, arm)]
            path_index = index(paths, ("signature_index",))
            check(set(path_index) == {(i,) for i in range(len(signatures))}, "Paid trajectory grid differs")
            metrics = dict.fromkeys(("cost", "query_count", "returned_bytes", "established", "ruled_out", "archive_irreducible"), Fraction())
            for (i,), path in path_index.items():
                signature = signatures[i]
                history = path["history"]
                check(len({h["query_id"] for h in history}) == len(history), "Duplicate acquisition query")
                check(signature in compatible(set(signatures), positions, history), "Paid acquisition outcomes differ")
                direct_cost = sum(model.queries[h["query_id"]]["cost"] for h in history)
                direct_bytes = sum(len(json.dumps(model.queries[h["query_id"]]["outcomes"][h["outcome_id"]],
                                                 sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()) for h in history)
                check((path["cost"], path["query_count"], path["returned_bytes"])
                      == (direct_cost, len(history), direct_bytes), "Paid acquisition accounting differs")
                member_ids = [j for j, s in enumerate(model.answers) if s in compatible(set(signatures), positions, history)]
                classes = {model.tau[j] for j in member_ids}
                check(len(classes) == 1 and path["status"] == next(iter(classes)), "Terminal class differs")
                mass = sum((weights[deployment][j] for j, s in enumerate(model.answers) if s == signature), Fraction())
                for name in ("cost", "query_count", "returned_bytes"):
                    metrics[name] += mass * path[name]
                metrics[path["status"]] += mass
                checked_paths += 1
            check(saved["signature_count"] == len(signatures), "Signature count differs")
            check({name: fraction(value) for name, value in saved["expected"].items()} == metrics,
                  "Exact prior reweighting differs")
            costs[key] = metrics["cost"]
    for key, row in indexed.items():
        pid, deployment, mode, arm = key
        optimum = costs[pid, deployment, "matched_q", "exact_optimal"]
        check(costs[key] >= optimum and fraction(row["matched_optimum"]) == optimum
              and fraction(row["optimum_excess"]) == costs[key] - optimum
              and row["zero_optimum"] == (optimum == 0), "Optimality gap differs")
        check(row["optimum_ratio"] is None if optimum == 0
              else fraction(row["optimum_ratio"]) == costs[key] / optimum, "Zero optimum or ratio differs")
    summary = read(out / "acquisition_summary.json")
    populations = {"all": sorted(models), **{s: sorted(pid for pid in models if strata[pid] == s) for s in set(strata.values())}}
    policy_index = index(summary["policy_summaries"], ("deployment", "planning_mode", "weighting", "stratum", "policy"))
    check(set(policy_index) == set(product(PRIORS, MODES, ("equal_problem", "structure_balanced"), populations, ARMS)), "Policy summary grid differs")
    for (deployment, mode, weighting, stratum, arm), row in policy_index.items():
        ids = populations[stratum]
        selected = {pid: costs[pid, deployment, mode, arm] for pid in ids}
        optima = {pid: costs[pid, deployment, "matched_q", "exact_optimal"] for pid in ids}
        gaps = {pid: selected[pid] - optima[pid] for pid in ids}
        check_average(row["expected_cost"], selected, ids, groups, weighting)
        check_average(row["matched_optimum_excess"], gaps, ids, groups, weighting)
        positive = [pid for pid in ids if optima[pid]]
        if positive:
            check_average(row["positive_optimum_ratio"], {p: selected[p] / optima[p] for p in positive}, positive, groups, weighting)
        else:
            check(row["positive_optimum_ratio"] is None, "Undefined ratio replaced")
        check(row["zero_cost_problems"] == [pid for pid in ids if selected[pid] == 0]
              and row["zero_optimum_problems"] == [pid for pid in ids if optima[pid] == 0], "Zero-cost population differs")
    comparisons = tuple(("pair_cut", p) for p in ARMS if p != "pair_cut") + (("schema_skip", "exact_optimal"), ("terminal_class_entropy", "exact_optimal"))
    paired = index(summary["paired_summaries"], ("deployment", "planning_mode", "weighting", "stratum", "left", "right"))
    check(set(paired) == {(d, m, w, s, left, right) for d, m, w, s, (left, right) in product(PRIORS, MODES, ("equal_problem", "structure_balanced"), populations, comparisons)}, "Paired summary grid differs")
    for (deployment, mode, weighting, stratum, left, right), row in paired.items():
        ids = populations[stratum]
        differences = {pid: costs[pid, deployment, mode, left] - costs[pid, deployment, mode, right] for pid in ids}
        weights = check_average(row["left_minus_right"], differences, ids, groups, weighting)
        for label, predicate in (("win", lambda v: v < 0), ("tie", lambda v: v == 0), ("loss", lambda v: v > 0)):
            check(row[label + ("es" if label == "loss" else "s")] == sum(predicate(v) for v in differences.values())
                  and fraction(row["weighted_" + label + "_mass"]) == sum((weights[p] for p in ids if predicate(differences[p])), Fraction()), "Paired relation counts differ")
    contrasts = index(summary["per_problem_contrasts"], ("problem_id", "deployment", "planning_mode", "left", "right"))
    check(set(contrasts) == {(p, d, m, left, right) for p, d, m, (left, right) in product(models, PRIORS, MODES, comparisons)}, "Contrast grid differs")
    for (pid, deployment, mode, left, right), row in contrasts.items():
        lcost, rcost = costs[pid, deployment, mode, left], costs[pid, deployment, mode, right]
        check(fraction(row["left_cost"]) == lcost and fraction(row["right_cost"]) == rcost
              and fraction(row["left_minus_right"]) == lcost - rcost
              and row["relation"] == ("win" if lcost < rcost else "loss" if lcost > rcost else "tie"), "Per-problem contrast differs")
    return {"result_and_dependency_pins": pin_count, "complete_condition_rows": len(rows),
            "paid_trajectory_views": checked_paths, "policy_summaries": len(policy_index),
            "paired_summaries": len(paired), "per_problem_contrasts": len(contrasts),
            "independent_prior_reweighting_and_exact_aggregation": "passed"}


def verify():
    audit_freeze = read(STUDY / "audit_freeze.json")
    acquisition_freeze = read(STUDY / "acquisition_freeze.json")
    freeze_count = verify_pins(ROOT, audit_freeze["sha256"])
    freeze_count += verify_pins(ROOT, acquisition_freeze["dependencies_sha256"])
    problems = read(ROOT / "studies/evidence_acquisition/evaluation_problems.json")
    check(len(problems) == 40 and len({p["problem_id"] for p in problems}) == 40, "Problem denominator differs")
    models = {p["problem_id"]: Model(p) for p in problems}
    audit = verify_audits(problems, models)
    acquisition = verify_acquisition(problems, models)
    verify_pins(ROOT, audit_freeze["sha256"])
    verify_pins(ROOT, acquisition_freeze["dependencies_sha256"])
    return {"status": "passed", "frozen_dependency_pin_checks": freeze_count,
            "audits": audit, "acquisition": acquisition,
            "scope": "Separately implemented complete-signature filtering, paid-prefix and first-conflict checks, replay of saved B/C rankings, prior arithmetic and aggregates. Existing Model supplies shared physical semantics. Historical exact policies are retained, never optimized. No independent human or physical-semantics validation is claimed.",
            "network_requests": 0, "model_calls": 0, "additional_spend_usd": "0"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x") as stream:
            stream.write(encoded)
    print(encoded, end="")
