"""Paired fixed-cohort metric sensitivity using untouched historical investigators.

No world generation, I/O, plotting, provider access, or alternate cohorts occur
here. Callers must verify frozen dependencies before supplying audited worlds.
"""

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, replace
from statistics import fmean

from tracebench.corruption import ReceiptObservation, corrupt
from tracebench.estimators import estimate
from tracebench.evaluate import GROUP_KEYS, paired_differences, score_edges
from tracebench.observe import Observation, Telemetry, observe
from tracebench.policies import infer
from tracebench.receipt_study import GROUP_KEYS as RECEIPT_GROUP_KEYS
from tracebench.receipt_study import PAIR_KEYS, PAIRED_METRICS

from .reference import reference_score, verify_metric_row

SCORE_METRICS = (
    "predicted_edges", "true_edges", "true_positive_edges", "false_positive_edges",
    "false_negative_edges", "eligible_targets", "precision", "recall", "f1", "theta",
    "theta_hat", "false_positive_targets", "false_negative_targets", "signed_error",
    "absolute_error", "target_disagreement", "false_attributed_target_fraction",
    "false_positive_edges_per_target",
)
RECEIPT_METRICS = tuple(dict.fromkeys((*SCORE_METRICS, *PAIRED_METRICS,
    "candidate_edges", "excluded_or_rejected_edges", "request_record_retention",
    "delivery_record_retention", "context_record_retention")))
MASK_ADAPTER_VERSION = "legacy-selection-stable-physical-record-identity-v1"


def digest(value):
    """Historical receipt-study serialization; no timestamp normalization."""
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    return hashlib.sha256(data).hexdigest()


def record_identity(channel, record):
    """One existing physical stage per request; immutable observable fields only."""
    if channel not in ("requests", "deliveries", "contexts"):
        raise ValueError(f"Unknown physical channel {channel!r}")
    return (channel, record.request_id)


def _records(observation, channel):
    result = {}
    for record in getattr(observation, channel):
        key = record_identity(channel, record)
        if key in result:
            raise ValueError(f"Physical record identity is not unique: {key}")
        result[key] = record
    return result


def couple_masks(legacy: Observation, corrected: Observation, profile, retention, mask_seed):
    """Replay unchanged legacy mask choices onto corrected observable records.

    Historical corruption._retained hashes timestamps. Its ordinary corrected
    draw is diagnostic only. Neither this adapter nor infer receives World or
    truth; completeness is exactly the original corruption declaration.
    """
    if not isinstance(legacy, Observation) or not isinstance(corrected, Observation):
        raise TypeError("Mask coupling accepts observations, never simulator truth")
    if (legacy.writes != corrected.writes or legacy.regime != corrected.regime
            or legacy.temporal_window != corrected.temporal_window):
        raise ValueError("Mask coupling requires identical write inputs and regime")
    maps = {}
    for channel in ("requests", "deliveries", "contexts"):
        left, right = _records(legacy, channel), _records(corrected, channel)
        if left.keys() != right.keys():
            raise ValueError(f"Physical identity mismatch in {channel}")
        for key in left:
            if replace(left[key], timestamp=0.0) != replace(right[key], timestamp=0.0):
                raise ValueError(f"Non-timestamp record mutation: {key}")
        maps[channel] = (left, right)
    masked_legacy = corrupt(legacy, profile, retention, mask_seed)
    ordinary_corrected = corrupt(corrected, profile, retention, mask_seed)
    replay, audit = {}, {}
    for channel, (left, right) in maps.items():
        keep = set(_records(masked_legacy.observation, channel))
        replay[channel] = tuple(record for record in getattr(corrected, channel)
                                if record_identity(channel, record) in keep)
        replay_ids = {record_identity(channel, record) for record in replay[channel]}
        if replay_ids != keep:
            raise ValueError("Coupled physical mask membership mismatch")
        ordinary_ids = set(_records(ordinary_corrected.observation, channel))
        audit[channel] = {
            "original_records": len(left), "retained_records": len(keep),
            "legacy_retained_ids": sorted(keep), "corrected_retained_ids": sorted(replay_ids),
            "retained_ids_sha256": digest(sorted(keep)),
            "membership_equal": True, "actual_retention_equal": True,
            "actual_retention": len(keep) / len(left) if left else None,
            "ordinary_corrected_mask_membership_changes": len(keep ^ ordinary_ids),
        }
    masked_corrected = ReceiptObservation(replace(corrected, **replay),
                                           masked_legacy.completeness)
    return masked_legacy, masked_corrected, {
        "adapter_version": MASK_ADAPTER_VERSION, "historical_mask_uses_timestamp": True,
        "channels": audit,
    }


def _assert_world_invariants(legacy, corrected):
    if corrected is None:
        return
    for field in ("config", "writes", "truth_edges", "eligible_target_ids"):
        if getattr(legacy, field) != getattr(corrected, field):
            raise ValueError(f"Retiming changed invariant {field}")


def _scores(predictions, world):
    values = score_edges(predictions, world.truth_edges, world.eligible_target_ids)
    if values != reference_score(predictions, world.truth_edges, world.eligible_target_ids):
        raise ValueError("Independent score reconstruction differs from historical scorer")
    verify_metric_row(values)
    # Independently computed count identities do not replace historical scoring.
    n = values["eligible_targets"]
    fp, fn = values["false_positive_targets"], values["false_negative_targets"]
    if not math.isclose(values["signed_error"], (fp - fn) / n, abs_tol=1e-15):
        raise ValueError("Signed target-fraction error identity failed")
    if values["target_disagreement"] != (fp + fn) / n:
        raise ValueError("Target-disagreement identity failed")
    return values


def _mismatches(saved, actual):
    return [{"field": key, "saved": value, "reproduced": actual.get(key),
             "reason": "missing_field" if key not in actual else "value_mismatch"}
            for key, value in saved.items() if key not in actual or actual[key] != value]


def _impact_row(cohort, legacy, corrected, saved, failures):
    metrics = SCORE_METRICS if cohort == "benchmark" else RECEIPT_METRICS
    keys = GROUP_KEYS if cohort == "benchmark" else RECEIPT_GROUP_KEYS
    unavailable = bool(failures) or corrected is None
    left = {key: legacy[key] for key in metrics}
    right = {key: corrected[key] for key in metrics} if not unavailable else None
    delta = {key: (right[key] - left[key]
                   if right is not None and left[key] is not None and right[key] is not None
                   else None) for key in metrics}
    changed = [key for key in metrics if right is not None and left[key] != right[key]]
    return {
        "cohort": cohort, "world_id": legacy["world_id"], "seed": legacy["seed"],
        "legacy_available": True,
        **{key: legacy[key] for key in keys},
        "mask_seed": legacy.get("mask_seed"), "legacy": left, "corrected": right,
        "corrected_minus_legacy": delta, "changed_metrics": changed,
        "status": ("unavailable_due_to_failed_reproduction" if failures else
                   "unavailable_due_to_correction_failure" if corrected is None else
                   "changed_on_tested_cohort" if changed else "unchanged_on_tested_cohort"),
        "unavailable_reasons": list(failures),
        "legacy_predictions_sha256": legacy["predictions_sha256"],
        "corrected_predictions_sha256": corrected["predictions_sha256"] if not unavailable else None,
        "predictions_equal": (legacy["predictions_sha256"] == corrected["predictions_sha256"]
                              if not unavailable else None),
        "saved_metric_fields": sorted(set(saved) & set(metrics)),
        "derived_legacy_metric_fields": sorted(set(metrics) - set(saved)),
    }


def _failure_text(failure):
    """Preserve structured failure text across sorted-JSON output round trips."""
    return (json.dumps(failure, sort_keys=True, allow_nan=False)
            if isinstance(failure, (dict, list, tuple)) else str(failure))


def unavailable_world_result(cohort, saved_rows, saved_world, configuration_id, failure):
    """Retain the complete saved grid when no reproducible World is available.

    ``saved_legacy`` is explicitly authoritative historical input, never a
    computed baseline. All unavailable computed metrics and effects remain null.
    """
    if cohort not in ("benchmark", "missing_receipts"):
        raise ValueError("Unknown historical cohort")
    metrics = SCORE_METRICS if cohort == "benchmark" else RECEIPT_METRICS
    keys = GROUP_KEYS if cohort == "benchmark" else RECEIPT_GROUP_KEYS
    problem = {"reason": "generation_or_audit_failure", "detail": _failure_text(failure)}
    result = {"world_id": configuration_id, "runs": [], "legacy_rows": [],
              "corrected_rows": [], "reproduction": [], "mask_audit": [],
              "legacy_available": False, "failure": problem,
              "saved_world": saved_world,
              "saved_eligible_targets": saved_rows[0].get("eligible_targets") if saved_rows else None,
              "world_reproduction": {"matched": False, "mismatches": [problem]}}
    for saved in saved_rows:
        identity = {key: saved[key] for key in (*keys, "seed")}
        metadata = {**identity, "world_id": configuration_id}
        if cohort == "missing_receipts":
            metadata.update(mask_seed=saved["mask_seed"], observation_sha256=None)
        missing = dict.fromkeys(metrics)
        result["legacy_rows"].append({**metadata, **missing, "_unavailable": True})
        result["reproduction"].append({**identity, "matched": False,
                                         "mismatches": [problem], "not_computed": True})
        result["runs"].append({
            **metadata, "cohort": cohort, "mask_seed": saved.get("mask_seed"),
            "legacy": missing.copy(), "corrected": None,
            "corrected_minus_legacy": missing.copy(), "changed_metrics": [],
            "legacy_available": False, "saved_legacy": dict(saved),
            "saved_eligible_targets": saved.get("eligible_targets"),
            "status": "unavailable_due_to_failed_reproduction",
            "unavailable_reasons": [problem], "legacy_predictions_sha256": None,
            "corrected_predictions_sha256": None, "predictions_equal": None,
            "saved_metric_fields": sorted(set(saved) & set(metrics)),
            "derived_legacy_metric_fields": sorted(set(metrics) - set(saved)),
        })
    if cohort == "missing_receipts":
        masks = {}
        for saved in saved_rows:
            key = (saved["profile"], saved["retention"], saved["mask_seed"])
            masks.setdefault(key, saved)
        for (profile, retention, mask_seed), saved in masks.items():
            result["mask_audit"].append({
                "world_id": configuration_id, "profile": profile, "retention": retention,
                "mask_seed": mask_seed, "adapter_version": MASK_ADAPTER_VERSION,
                "historical_mask_uses_timestamp": True,
                "status": "unavailable_due_to_failed_reproduction", "failure": problem,
                "saved_legacy": {key: value for key, value in saved.items()
                                  if "_record" in key},
                "channels": {channel: {
                    "original_records": None, "retained_records": None,
                    "legacy_retained_ids": None, "corrected_retained_ids": None,
                    "retained_ids_sha256": None, "membership_equal": None,
                    "actual_retention_equal": None, "actual_retention": None,
                    "ordinary_corrected_mask_membership_changes": None,
                } for channel in ("requests", "deliveries", "contexts")},
            })
    return result


def evaluate_benchmark_world(legacy, corrected, saved_rows, *, failure_reason=None):
    """Reproduce every authoritative saved row, then form a paired sensitivity."""
    _assert_world_invariants(legacy, corrected)
    world_id = digest(asdict(legacy.config))
    result = {"world_id": world_id, "runs": [], "legacy_rows": [], "corrected_rows": [],
              "reproduction": []}
    seen = set()
    for saved in saved_rows:
        key = tuple(saved[name] for name in (*GROUP_KEYS, "seed"))
        if key in seen:
            raise ValueError("Duplicate benchmark saved evaluation")
        seen.add(key)
        row = {name: saved[name] for name in (*GROUP_KEYS, "seed")}
        expected = legacy.config
        if (row["seed"], row["transmission_probability"], row["shock_strength"]) != (
                expected.seed, expected.transmission_probability, expected.shock_strength):
            raise ValueError("Saved evaluation belongs to another configuration")
        left_obs = observe(legacy, Telemetry(row["regime"]))
        left_predictions = estimate(left_obs, row["method"])
        left = row | _scores(left_predictions, legacy) | {"world_id": world_id,
            "predictions_sha256": digest(sorted(left_predictions))}
        mismatches = _mismatches(saved, left)
        right = None
        if corrected is not None and not mismatches:
            right_obs = observe(corrected, Telemetry(row["regime"]))
            right_predictions = estimate(right_obs, row["method"])
            if left_obs == right_obs and left_predictions != right_predictions:
                raise ValueError("Identical observations produced unequal predictions")
            right = row | _scores(right_predictions, corrected) | {"world_id": world_id,
                "predictions_sha256": digest(sorted(right_predictions))}
        result["legacy_rows"].append(left)
        if right is not None:
            result["corrected_rows"].append(right)
        result["reproduction"].append(row | {"matched": not mismatches,
                                             "mismatches": mismatches})
        result["runs"].append(_impact_row("benchmark", left, right, saved, mismatches))
        if failure_reason:
            result["runs"][-1]["unavailable_reasons"].append({"correction": failure_reason})
    return result


def _receipt_row(world, masked, template, full):
    row = {name: template[name] for name in (*RECEIPT_GROUP_KEYS, "seed", "mask_seed")}
    row["world_id"] = digest(asdict(world.config))
    row["observation_sha256"] = digest(asdict(masked))
    for singular, plural in (("request", "requests"), ("delivery", "deliveries"),
                             ("context", "contexts")):
        original, retained = len(getattr(full, plural)), len(getattr(masked.observation, plural))
        row[f"{singular}_records_original"] = original
        row[f"{singular}_records_retained"] = retained
        row[f"{singular}_record_retention"] = retained / original if original else None
    inference = infer(masked, row["method"], row["policy"])
    row.update(_scores(inference.predictions, world))
    row["predictions_sha256"] = digest(sorted(inference.predictions))
    unresolved_targets = {target for _, target in inference.unresolved}
    n = len(world.eligible_target_ids)
    row.update({
        "candidate_edges": len(inference.candidates),
        "excluded_or_rejected_edges": len(inference.excluded),
        "unresolved_edges": len(inference.unresolved),
        "unresolved_targets": len(unresolved_targets),
        "unresolved_target_fraction": len(unresolved_targets) / n,
        "unresolved_edges_per_target": len(inference.unresolved) / n,
        "unresolved_candidate_fraction": (len(inference.unresolved) / len(inference.candidates)
                                           if inference.candidates else None),
    })
    return row


def evaluate_receipt_world(legacy, corrected, saved_world, saved_rows, *, failure_reason=None):
    _assert_world_invariants(legacy, corrected)
    world_id = digest(asdict(legacy.config))
    reproduced_world = {
        "world_id": world_id, "config": asdict(legacy.config),
        "mask_seed": saved_world["mask_seed"],
        "truth_sha256": digest(sorted(legacy.truth_edges)),
        "eligible_targets_sha256": digest(sorted(legacy.eligible_target_ids)),
        "writes_sha256": digest([asdict(write) for write in legacy.writes]),
        "true_edges": len(legacy.truth_edges), "eligible_targets": len(legacy.writes),
    }
    world_failures = _mismatches(saved_world, reproduced_world)
    result = {"world_id": world_id, "runs": [], "legacy_rows": [], "corrected_rows": [],
              "reproduction": [], "mask_audit": [], "world_reproduction": {
                  "matched": not world_failures, "mismatches": world_failures}}
    full_legacy = observe(legacy, Telemetry.CONTEXT)
    full_corrected = observe(corrected, Telemetry.CONTEXT) if corrected is not None else None
    masks, seen = {}, set()
    for saved in saved_rows:
        row_key = tuple(saved[name] for name in (*RECEIPT_GROUP_KEYS, "seed"))
        if row_key in seen:
            raise ValueError("Duplicate missing-receipt saved evaluation")
        seen.add(row_key)
        expected = legacy.config
        if (saved["seed"], saved["transmission_probability"], saved["shock_strength"]) != (
                expected.seed, expected.transmission_probability, expected.shock_strength):
            raise ValueError("Saved evaluation belongs to another configuration")
        key = (saved["profile"], saved["retention"], saved["mask_seed"])
        if key not in masks:
            if full_corrected is not None:
                left_mask, right_mask, audit = couple_masks(full_legacy, full_corrected, *key)
                result["mask_audit"].append({"world_id": world_id, "profile": key[0],
                    "retention": key[1], "mask_seed": key[2], **audit})
            else:
                left_mask, right_mask = corrupt(full_legacy, *key), None
                channels = {}
                for channel in ("requests", "deliveries", "contexts"):
                    original = _records(full_legacy, channel)
                    kept = set(_records(left_mask.observation, channel))
                    channels[channel] = {
                        "original_records": len(original), "retained_records": len(kept),
                        "legacy_retained_ids": sorted(kept), "corrected_retained_ids": None,
                        "retained_ids_sha256": digest(sorted(kept)),
                        "actual_retention": len(kept) / len(original) if original else None,
                        "membership_equal": None, "actual_retention_equal": None,
                        "ordinary_corrected_mask_membership_changes": None,
                    }
                result["mask_audit"].append({
                    "world_id": world_id, "profile": key[0], "retention": key[1],
                    "mask_seed": key[2], "adapter_version": MASK_ADAPTER_VERSION,
                    "historical_mask_uses_timestamp": True,
                    "status": "unavailable_due_to_correction_failure",
                    "failure": _failure_text(failure_reason or "corrected World unavailable"),
                    "channels": channels,
                })
            masks[key] = (left_mask, right_mask)
        left_mask, right_mask = masks[key]
        left = _receipt_row(legacy, left_mask, saved, full_legacy)
        mismatches = world_failures + _mismatches(saved, left)
        right = (_receipt_row(corrected, right_mask, saved, full_corrected)
                 if right_mask is not None and not mismatches else None)
        result["legacy_rows"].append(left)
        if right is not None:
            result["corrected_rows"].append(right)
        result["reproduction"].append({**{name: saved[name] for name in
                                         (*RECEIPT_GROUP_KEYS, "seed")},
                                       "matched": not mismatches, "mismatches": mismatches})
        result["runs"].append(_impact_row("missing_receipts", left, right, saved, mismatches))
        if failure_reason:
            result["runs"][-1]["unavailable_reasons"].append({"correction": failure_reason})
    return result


def aggregate_impacts(rows, *, group_keys):
    """Equal-weight means of paired worlds; preserve unavailable and null rows."""
    if len(set(group_keys)) != len(group_keys) or {"seed", "world_id"} & set(group_keys):
        raise ValueError("Scenario grouping dimensions must be distinct and exclude world IDs")
    for dimension in ("profile", "retention", "policy"):
        if any(dimension in row for row in rows) and dimension not in group_keys:
            raise ValueError(f"Missing historical scenario dimension: {dimension}")
    groups = defaultdict(list)
    for row in rows:
        if row["corrected"] is not None:
            for field in ("eligible_targets", "true_edges", "theta"):
                if field in row["legacy"] and row["legacy"][field] != row["corrected"][field]:
                    raise ValueError(f"Paired versions changed invariant denominator {field}")
        groups[tuple(row[key] for key in group_keys)].append(row)
    results = []
    for key, members in sorted(groups.items()):
        ids = [row["world_id"] for row in members]
        if len(ids) != len(set(ids)):
            raise ValueError("Repeated world in scenario aggregation")
        if len({row["seed"] for row in members}) != len(members):
            raise ValueError("Repeated seed in historical scenario aggregation")
        unavailable = [row for row in members if row["corrected"] is None]
        missing_legacy = [row for row in members if not row.get("legacy_available", True)]
        metrics = {}
        for metric in members[0]["legacy"]:
            entry = {}
            for version in ("legacy", "corrected", "corrected_minus_legacy"):
                values = [row[version][metric] for row in members
                          if row[version] is not None and row[version][metric] is not None]
                entry[version] = {"mean": (fmean(values) if values else None),
                                  "n_defined_worlds": len(values)}
                # Do not silently report a partial-cohort impact estimate.
                if (unavailable and version != "legacy") or (missing_legacy and version == "legacy"):
                    entry[version]["mean"] = None
            metrics[metric] = entry
        results.append(dict(zip(group_keys, key)) | {
            "cohort": members[0].get("cohort"),
            "n_worlds": len(members), "n_unavailable_worlds": len(unavailable),
            "n_unreproduced_worlds": len(missing_legacy),
            "n_changed_worlds": sum(bool(row["changed_metrics"]) for row in members),
            "world_ids": sorted(ids), "metrics": metrics,
            "status": ("unavailable_due_to_failed_reproduction_or_correction" if unavailable else
                       "changed_on_tested_cohort" if any(row["changed_metrics"] for row in members)
                       else "unchanged_on_tested_cohort"),
        })
    return results


def _summary_reproduction(saved_summary, rows, group_keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
    result = []
    for saved in saved_summary:
        key = tuple(saved[name] for name in group_keys)
        members = [row for row in groups.get(key, []) if not row.get("_unavailable", False)]
        mismatches = []
        if len(members) != saved["n_seeds"]:
            mismatches.append({"field": "n_seeds", "saved": saved["n_seeds"],
                               "reproduced": len(members)})
        for metric, stats in saved["metrics"].items():
            values = [row[metric] for row in members if row[metric] is not None]
            actual = {"mean": fmean(values) if values else None, "n": len(values)}
            mismatches.extend({"metric": metric, **item} for item in
                              _mismatches({k: stats[k] for k in ("mean", "n")}, actual))
        result.append(dict(zip(group_keys, key)) | {"matched": not mismatches,
            "mismatches": mismatches,
            "scope": "saved mean and defined-world n; historical intervals preserved, not recomputed"})
    return result


def _policy_impacts(receipt_results, saved_paired):
    output, reproduction = [], []
    all_metrics = tuple(metric for metric in RECEIPT_METRICS
                        if not metric.endswith("record_retention"))
    saved_index = {tuple(row[key] for key in (*PAIR_KEYS, "seed")): row for row in saved_paired}
    for result in receipt_results:
        invariant_index = {}
        for row in result["legacy_rows"] + result["corrected_rows"]:
            key = tuple(row[name] for name in (*PAIR_KEYS, "seed"))
            invariant = tuple(row[name] for name in ("eligible_targets", "true_edges", "theta"))
            if key in invariant_index and invariant_index[key] != invariant:
                raise ValueError("Paired policies changed truth or eligible denominator")
            invariant_index[key] = invariant
        legacy = paired_differences(result["legacy_rows"], group_keys=PAIR_KEYS,
                                    metric_names=all_metrics)
        complete = len(result["corrected_rows"]) == len(result["legacy_rows"])
        corrected = (paired_differences(result["corrected_rows"], group_keys=PAIR_KEYS,
                                       metric_names=all_metrics) if complete else [])
        corrected_index = {tuple(row[key] for key in (*PAIR_KEYS, "seed")): row
                           for row in corrected}
        for left in legacy:
            key = tuple(left[name] for name in (*PAIR_KEYS, "seed"))
            saved = saved_index.get(key)
            if saved is None:
                raise ValueError("Missing authoritative saved policy contrast")
            mismatches = _mismatches(saved, left)
            reproduction.append({**dict(zip((*PAIR_KEYS, "seed"), key)),
                                 "matched": not mismatches, "mismatches": mismatches})
            right = corrected_index.get(key) if not mismatches else None
            left_metrics = {metric: left[metric] for metric in all_metrics}
            right_metrics = {metric: right[metric] for metric in all_metrics} if right else None
            delta = {metric: (right[metric] - left[metric]
                              if right is not None and right[metric] is not None
                              and left[metric] is not None else None) for metric in all_metrics}
            output.append({**dict(zip((*PAIR_KEYS, "seed"), key)),
                "cohort": "missing_receipts", "world_id": result["world_id"],
                "eligible_targets": result.get("saved_eligible_targets", invariant_index[key][0]),
                "legacy_available": result.get("legacy_available", True),
                "saved_legacy": saved if not result.get("legacy_available", True) else None,
                "legacy": left_metrics,
                "corrected": right_metrics, "corrected_minus_legacy": delta,
                "contrast": "evidence_aware minus conjunction",
                "sensitivity": "change in paired policy contrast, corrected minus legacy",
                "changed_metrics": [metric for metric in all_metrics if right is not None
                                    and left[metric] != right[metric]],
                "unavailable_reasons": (mismatches if mismatches or right else
                                        [{"reason": "constituent corrected score unavailable"}]),
                "status": "available" if right else "unavailable_due_to_failed_reproduction_or_correction",
            })
    if len(reproduction) != len(saved_paired):
        raise ValueError("Saved paired policy denominator differs from recomputation")
    return output, reproduction


def finalize_impact(benchmark_saved, receipts_saved, benchmark_results, receipt_results):
    """Complete scenario means and original paired-policy difference of differences."""
    benchmark_rows = [row for result in benchmark_results for row in result["runs"]]
    receipt_rows = [row for result in receipt_results for row in result["runs"]]
    if len(benchmark_rows) != len(benchmark_saved["runs"]):
        raise ValueError("Benchmark saved evaluation denominator not preserved")
    if len(receipt_rows) != len(receipts_saved["runs"]):
        raise ValueError("Missing-receipt saved evaluation denominator not preserved")
    legacy_benchmark = [row for result in benchmark_results for row in result["legacy_rows"]]
    legacy_receipt = [row for result in receipt_results for row in result["legacy_rows"]]
    policy_rows, policy_reproduction = _policy_impacts(receipt_results, receipts_saved["paired_runs"])
    legacy_policy = [{**{key: row[key] for key in (*PAIR_KEYS, "seed")}, **row["legacy"],
                      "_unavailable": not row.get("legacy_available", True)}
                     for row in policy_rows]
    retention_index = {}
    for row in legacy_receipt:
        key = tuple(row[name] for name in ("world_id", "profile", "retention", "mask_seed"))
        retention_index[key] = row
    retention_reproduction = []
    for saved in receipts_saved["retention_audit"]:
        key = tuple(saved[name] for name in ("world_id", "profile", "retention", "mask_seed"))
        actual = retention_index.get(key, {})
        mismatches = _mismatches(saved, actual)
        retention_reproduction.append({"world_id": saved["world_id"],
            "profile": saved["profile"], "retention": saved["retention"],
            "matched": not mismatches, "mismatches": mismatches})
    if len(retention_index) != len(receipts_saved["retention_audit"]):
        raise ValueError("Saved masked-observation denominator differs from recomputation")
    reproduction = {
        "benchmark_rows": [row for result in benchmark_results for row in result["reproduction"]],
        "receipt_rows": [row for result in receipt_results for row in result["reproduction"]],
        "receipt_worlds": [result["world_reproduction"] for result in receipt_results],
        "benchmark_summary": _summary_reproduction(benchmark_saved["summary"],
                                                      legacy_benchmark, GROUP_KEYS),
        "receipt_summary": _summary_reproduction(receipts_saved["summary"],
                                                    legacy_receipt, RECEIPT_GROUP_KEYS),
        "receipt_paired_rows": policy_reproduction,
        "receipt_paired_summary": _summary_reproduction(receipts_saved["paired_summary"],
                                                          legacy_policy, PAIR_KEYS),
        "receipt_retention": retention_reproduction,
    }
    all_rows = benchmark_rows + receipt_rows
    matched = all(row["matched"] for rows in reproduction.values() for row in rows)
    scenario_impacts = (aggregate_impacts(benchmark_rows, group_keys=GROUP_KEYS)
                        + aggregate_impacts(receipt_rows, group_keys=RECEIPT_GROUP_KEYS))
    policy_impacts = aggregate_impacts(policy_rows, group_keys=PAIR_KEYS)
    for checks, impacts, keys in (
        (reproduction["benchmark_summary"], scenario_impacts, GROUP_KEYS),
        (reproduction["receipt_summary"], scenario_impacts, RECEIPT_GROUP_KEYS),
        (reproduction["receipt_paired_summary"], policy_impacts, PAIR_KEYS),
    ):
        for check in checks:
            if check["matched"]:
                continue
            for group in impacts:
                if all(group.get(key) == check[key] for key in keys):
                    group["status"] = "unavailable_due_to_failed_reproduction"
                    group["reproduction_mismatches"] = check["mismatches"]
                    for metric in group["metrics"].values():
                        for version in ("corrected", "corrected_minus_legacy"):
                            metric[version]["mean"] = None
    return {
        "schema_version": 1,
        "metadata": {
            "label": "review-informed correction sensitivity",
            "metric_direction": "corrected minus legacy",
            "source_using_fraction_error": "signed_error = theta_hat - theta = (FP_targets-FN_targets)/N",
            "absolute_fraction_error": "absolute_error = abs(theta_hat-theta); grouped mean of per-world absolute errors",
            "target_disagreement": "(FP_targets+FN_targets)/N; distinct from absolute fraction error",
            "aggregation": "equal-weight historical world-level means, paired before aggregation; undefined excluded with n shown",
            "policy_contrast": "evidence_aware minus conjunction within each version; then corrected minus legacy of contrast",
            "mask_adapter_version": MASK_ADAPTER_VERSION,
            "baseline_comparison": "exact JSON scalar equality; only saved fields compared; augmented target metrics separately labeled",
            "historical_intervals": "preserved in saved inputs; not recomputed or reinterpreted as sensitivity uncertainty",
        },
        "counts": {
            "benchmark_configurations": len(benchmark_results),
            "receipt_configurations": len(receipt_results),
            "benchmark_evaluations": len(benchmark_rows), "receipt_evaluations": len(receipt_rows),
            "policy_contrasts": len(policy_rows),
            "changed_evaluations": sum(bool(row["changed_metrics"]) for row in all_rows),
            "unavailable_evaluations": sum(row["corrected"] is None for row in all_rows),
            "reproduction_all_matched": matched,
        },
        "per_world_impact": all_rows,
        "per_scenario_impact": scenario_impacts,
        "policy_paired_impact": policy_rows,
        "policy_group_impact": policy_impacts,
        "mask_audit": [row for result in receipt_results for row in result["mask_audit"]],
        "reproduction": reproduction,
    }
