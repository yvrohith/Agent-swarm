"""Direct reference checks, independent of the retiming implementation.

Shared interfaces are the historical immutable record types and the captured
trace's attribute schema. This module neither calls the correction routine nor
imports its trigger helpers. Availability is reconstructed from the *final*
complete context stream at every write using strict ``context time < write
time``. Repeated receipts contribute one source identity to a set.
"""

import math
from collections import defaultdict
from dataclasses import replace
from statistics import fmean

from tracebench.model import World


class VerificationFailure(ValueError):
    """Unsupported or inconsistent inputs; never a valid corrected estimate."""


def _unique(records, field, label):
    result = {}
    for record in records:
        identity = getattr(record, field)
        if identity in result:
            raise VerificationFailure(f"Duplicate {label} identity: {identity}")
        result[identity] = record
    return result


def _trace_index(world, trace):
    """Check complete provenance, using no mutable simulator state or helpers."""
    writes = _unique(world.writes, "event_id", "write")
    snapshots = _unique(trace.snapshots, "write_event_id", "snapshot")
    chains = _unique(trace.chains, "request_id", "chain")
    requests = _unique(world.requests, "request_id", "request")
    deliveries = _unique(world.deliveries, "request_id", "delivery")
    contexts = _unique(world.contexts, "request_id", "context")
    if snapshots.keys() != writes.keys():
        raise VerificationFailure("Trace must cover every write exactly once")
    if chains.keys() != requests.keys():
        raise VerificationFailure("Trace must own every request exactly once")
    if not deliveries.keys() <= requests.keys() or not contexts.keys() <= deliveries.keys():
        raise VerificationFailure("Context-bearing chains require existing upstream records")
    for index, snapshot in enumerate(trace.snapshots):
        write = writes[snapshot.write_event_id]
        if (snapshot.generation_index != index or world.writes[index] != write
                or snapshot.timestamp != write.timestamp or snapshot.run_id != write.run_id):
            raise VerificationFailure("Snapshot position/time/run disagrees with write")
        if (len(set(snapshot.available_source_ids)) != len(snapshot.available_source_ids)
                or not set(snapshot.available_source_ids) <= writes.keys()):
            raise VerificationFailure("Captured availability must contain distinct known sources")
        expected_requests = {c.request_id for c in trace.chains
                             if c.owner_write_id == write.event_id}
        if set(snapshot.request_ids_created) != expected_requests:
            raise VerificationFailure("Snapshot created-request provenance disagrees")
        if set(snapshot.context_request_ids_created) != expected_requests & contexts.keys():
            raise VerificationFailure("Snapshot created-context provenance disagrees")
    installed = set()
    for chain in sorted(trace.chains, key=lambda c: c.generation_index):
        if chain.owner_write_id not in writes or chain.source_event_id not in writes:
            raise VerificationFailure("Chain has an unknown owner or source")
        owner = writes[chain.owner_write_id]
        source = writes[chain.source_event_id]
        request = requests[chain.request_id]
        snapshot = snapshots[chain.owner_write_id]
        if (chain.generation_index != snapshot.generation_index
                or chain.recipient_run_id != owner.run_id
                or request.run_id != owner.run_id or request.page != owner.page
                or source.page != request.page or source.run_id == owner.run_id
                or not source.timestamp < owner.timestamp):
            raise VerificationFailure("Chain provenance/source/owner bounds disagree")
        if (chain.has_delivery != (chain.request_id in deliveries)
                or chain.has_context != (chain.request_id in contexts)):
            raise VerificationFailure("Trace stage occurrence disagrees")
        for record in (deliveries.get(chain.request_id), contexts.get(chain.request_id)):
            if record is not None and (record.run_id != owner.run_id
                                      or record.source_event_id != source.event_id):
                raise VerificationFailure("Receipt source or recipient disagrees with provenance")
        pair = (chain.recipient_run_id, chain.source_event_id)
        expected_first = pair not in installed if chain.has_context else None
        if chain.first_installation != expected_first:
            raise VerificationFailure("First-installation/repeated-receipt trace disagrees")
        if chain.has_context:
            installed.add(pair)
    return writes, snapshots, chains, requests, deliveries, contexts


def audit_availability(world: World, trace) -> dict:
    """Compare final-log source sets with captured state at every decision.

    ``max_time_discrepancy`` is the maximum affected-write timestamp minus the
    timestamp of a context receipt falsely advertising availability there.
    ``distinct_first_availability_contradictions`` counts recipient/source pairs;
    offending chains and affected writes have separate, explicit denominators.
    """
    writes, snapshots, chains, _, _, contexts = _trace_index(world, trace)
    disagreements = []
    offending = set()
    contradicted_pairs = set()
    max_discrepancy = 0.0
    missing_count = extra_count = 0
    for write in world.writes:
        final_receipts = [c for c in world.contexts
                          if c.run_id == write.run_id and c.timestamp < write.timestamp]
        logged = {c.source_event_id for c in final_receipts}
        captured = set(snapshots[write.event_id].available_source_ids)
        extra, missing = logged - captured, captured - logged
        if extra or missing:
            responsible = sorted(c.request_id for c in final_receipts
                                 if c.source_event_id in extra)
            offending.update(responsible)
            contradicted_pairs.update((write.run_id, source) for source in extra)
            extra_count += len(extra)
            missing_count += len(missing)
            for identity in responsible:
                max_discrepancy = max(max_discrepancy,
                                      write.timestamp - contexts[identity].timestamp)
            disagreements.append({
                "write_event_id": write.event_id, "run_id": write.run_id,
                "timestamp": write.timestamp,
                "generation_index": snapshots[write.event_id].generation_index,
                "captured_source_ids": sorted(captured), "logged_source_ids": sorted(logged),
                "extra_source_ids": sorted(extra), "missing_source_ids": sorted(missing),
                "offending_chain_ids": responsible,
            })
    return {
        "writes_checked": len(writes), "context_records": len(contexts),
        "request_chains": len(chains),
        "distinct_source_run_installations": sum(c.first_installation is True
                                                  for c in trace.chains),
        "repeated_context_receipts": sum(c.first_installation is False for c in trace.chains),
        "affected_writes": len(disagreements),
        "offending_chain_ids": sorted(offending), "offending_chains": len(offending),
        "distinct_first_availability_contradictions": len(contradicted_pairs),
        "extra_source_decisions": extra_count, "missing_source_decisions": missing_count,
        "max_time_discrepancy": max_discrepancy, "disagreements": disagreements,
    }


def verify_retiming(legacy: World, corrected: World, trace) -> dict:
    """Independently enforce the fixed targeted quarter-interval correction."""
    if legacy != trace.world:
        raise VerificationFailure("Legacy input differs from captured World")
    before = audit_availability(legacy, trace)
    writes, _, chains, requests, deliveries, contexts = _trace_index(legacy, trace)
    if before["missing_source_decisions"]:
        raise VerificationFailure("Unsupported missing logged availability in legacy world")
    for field in ("config", "writes", "truth_edges", "eligible_target_ids"):
        if getattr(corrected, field) != getattr(legacy, field):
            raise VerificationFailure(f"Correction changed immutable World field: {field}")
    new_requests = _unique(corrected.requests, "request_id", "corrected request")
    new_deliveries = _unique(corrected.deliveries, "request_id", "corrected delivery")
    new_contexts = _unique(corrected.contexts, "request_id", "corrected context")
    replacements = {"requests": {}, "deliveries": {}, "contexts": {}}
    bounds = []
    for identity in before["offending_chain_ids"]:
        chain = chains[identity]
        if identity not in requests or identity not in deliveries or identity not in contexts:
            raise VerificationFailure("Correction requires every existing upstream stage")
        owner, source = writes[chain.owner_write_id], writes[chain.source_event_id]
        predecessors = [w for w in legacy.writes[:chain.generation_index]
                        if w.run_id == owner.run_id]
        previous = predecessors[-1] if predecessors else None
        lo = max(source.timestamp, previous.timestamp) if previous else source.timestamp
        gap = owner.timestamp - lo
        quarter_times = (lo + gap / 4, lo + gap / 2, lo + 3 * gap / 4)
        q, d, c = quarter_times
        if (not all(math.isfinite(t) for t in (lo, owner.timestamp, q, d, c))
                or not lo < q < d < c < owner.timestamp
                or not source.timestamp < q):
            raise VerificationFailure("Unrepresentable strict quarter-interval timing bounds")
        for field, time in zip(replacements, quarter_times, strict=True):
            replacements[field][identity] = time
        bounds.append({"request_id": identity, "source_event_id": source.event_id,
                       "owner_write_id": owner.event_id,
                       "previous_recipient_write_id": previous.event_id if previous else None,
                       "lo": lo, "owner_timestamp": owner.timestamp,
                       "request_timestamp": q, "delivery_timestamp": d, "context_timestamp": c})
    for field, old_index, new_index in (
        ("requests", requests, new_requests), ("deliveries", deliveries, new_deliveries),
        ("contexts", contexts, new_contexts),
    ):
        if old_index.keys() != new_index.keys():
            raise VerificationFailure(f"Correction changed {field} identities or occurrence")
        expected = tuple(sorted((replace(record, timestamp=replacements[field][record.request_id])
                                 if record.request_id in replacements[field] else record
                                 for record in getattr(legacy, field)), key=lambda r: r.timestamp))
        if getattr(corrected, field) != expected:
            raise VerificationFailure(f"Unexpected timestamp/non-timestamp/order change in {field}")
    after = audit_availability(corrected, trace)
    if after["affected_writes"]:
        raise VerificationFailure("Corrected final log disagrees with captured state at a write")
    return {"status": "verified", "writes_checked": len(writes),
            "corrected_request_ids": before["offending_chain_ids"],
            "corrected_chains": len(bounds), "bounds": bounds,
            "legacy_affected_writes": before["affected_writes"],
            "corrected_affected_writes": after["affected_writes"],
            "all_other_fields_preserved": True}


def reference_score(predictions, truth, eligible) -> dict:
    """Independent edge/target set arithmetic; no historical scorer imported."""
    predictions, truth, eligible = set(predictions), set(truth), set(eligible)
    if not eligible or any(t not in eligible for _, t in predictions | truth):
        raise VerificationFailure("Invalid eligible target universe")
    hits = sum(edge in truth for edge in predictions)
    extras, missed = len(predictions) - hits, len(truth) - hits
    predicted_targets = {edge[1] for edge in predictions}
    true_targets = {edge[1] for edge in truth}
    target_fp = sum(target not in true_targets for target in predicted_targets)
    target_fn = sum(target not in predicted_targets for target in true_targets)
    n = len(eligible)
    theta, theta_hat = len(true_targets) / n, len(predicted_targets) / n
    return {
        "true_positive_edges": hits, "false_positive_edges": extras,
        "false_negative_edges": missed, "predicted_edges": len(predictions),
        "true_edges": len(truth), "eligible_targets": n,
        "precision": hits / len(predictions) if predictions else None,
        "recall": hits / len(truth) if truth else None,
        "f1": 2 * hits / (len(predictions) + len(truth)) if predictions or truth else None,
        "theta": theta, "theta_hat": theta_hat, "signed_error": theta_hat - theta,
        "absolute_error": abs(theta_hat - theta), "false_positive_targets": target_fp,
        "false_negative_targets": target_fn, "target_disagreement": (target_fp + target_fn) / n,
        "false_attributed_target_fraction": target_fp / n,
        "false_positive_edges_per_target": extras / n,
    }


def _same_number(actual, expected):
    return (actual is None and expected is None) or (
        actual is not None and expected is not None
        and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12))


def verify_metric_row(metrics) -> None:
    """Verify count, undefined-denominator, and signed/absolute target identities."""
    names = ("eligible_targets", "true_positive_edges", "false_positive_edges",
             "false_negative_edges", "predicted_edges", "true_edges",
             "false_positive_targets", "false_negative_targets")
    if any(not isinstance(metrics[name], int) or isinstance(metrics[name], bool)
           or metrics[name] < 0 for name in names):
        raise VerificationFailure("Metrics require nonnegative integer counts")
    n = metrics["eligible_targets"]
    if not n:
        raise VerificationFailure("Metrics require a positive eligible denominator")
    tp, fp, fn = (metrics[name] for name in names[1:4])
    predicted, true = metrics["predicted_edges"], metrics["true_edges"]
    target_fp, target_fn = metrics["false_positive_targets"], metrics["false_negative_targets"]
    if predicted != tp + fp or true != tp + fn:
        raise VerificationFailure("Edge count identities failed")
    target_counts = []
    for name in ("theta", "theta_hat"):
        value = metrics[name]
        if (not math.isfinite(value) or not 0 <= value <= 1
                or not math.isclose(value * n, round(value * n), rel_tol=0, abs_tol=1e-10)):
            raise VerificationFailure("Fraction incompatible with integer target counts")
        target_counts.append(round(value * n))
    true_targets, predicted_targets = target_counts
    if (predicted_targets - target_fp != true_targets - target_fn
            or not 0 <= predicted_targets - target_fp <= min(true_targets, predicted_targets)
            or target_fp > fp or target_fn > fn
            or true_targets > true or predicted_targets > predicted
            or true_targets + target_fp > n):
        raise VerificationFailure("Target count identities failed")
    expected = {
        "precision": tp / predicted if predicted else None,
        "recall": tp / true if true else None,
        "f1": 2 * tp / (predicted + true) if predicted or true else None,
        "signed_error": (target_fp - target_fn) / n,
        "absolute_error": abs(target_fp - target_fn) / n,
        "target_disagreement": (target_fp + target_fn) / n,
        "false_attributed_target_fraction": target_fp / n,
        "false_positive_edges_per_target": fp / n,
    }
    for name, value in expected.items():
        if not _same_number(metrics[name], value):
            raise VerificationFailure(f"Metric identity failed: {name}")


def _check_dimensions(rows, group_keys, paired_axis=None):
    if len(set(group_keys)) != len(group_keys) or {"seed", "mask_seed"} & set(group_keys):
        raise VerificationFailure("Grouping dimensions must be distinct and exclude seeds")
    required = ("transmission_probability", "shock_strength", "regime", "method",
                "profile", "retention", "policy", "version")
    omitted = [key for key in required if key != paired_axis and key not in group_keys
               and any(key in row for row in rows)]
    if omitted:
        raise VerificationFailure(f"Grouping omits study dimensions: {omitted}")


def grouped_world_means(rows, *, group_keys, metric_names) -> list[dict]:
    """Unweighted per-world means with explicit total and defined denominators."""
    _check_dimensions(rows, group_keys)
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
    result = []
    for key, members in sorted(groups.items()):
        if len({row["seed"] for row in members}) != len(members):
            raise VerificationFailure("A group requires one row per world, not repeated masks")
        result.append(dict(zip(group_keys, key, strict=True)) | {
            "n_worlds": len(members),
            "metrics": {name: {"mean": fmean(defined) if defined else None,
                               "n_defined": len(defined), "n_worlds": len(members)}
                        for name in metric_names
                        for defined in [[row[name] for row in members if row[name] is not None]]},
        })
    return result


def paired_world_differences(rows, *, group_keys, metric_names, pair_key="version",
                             reference="legacy", comparison="corrected") -> list[dict]:
    """Per-world comparison minus reference, preserving undefined quantities."""
    if reference == comparison:
        raise VerificationFailure("The paired comparison requires distinct axis values")
    keys = tuple(key for key in group_keys if key != pair_key)
    _check_dimensions(rows, keys, paired_axis=pair_key)
    groups = defaultdict(dict)
    for row in rows:
        identity = tuple(row[key] for key in keys) + (row["seed"],)
        axis = row[pair_key]
        if axis not in (reference, comparison) or axis in groups[identity]:
            raise VerificationFailure("Unexpected or duplicate paired world")
        groups[identity][axis] = row
    result = []
    for identity, members in sorted(groups.items()):
        if set(members) != {reference, comparison}:
            raise VerificationFailure("Each world requires both paired versions/policies")
        a, b = members[reference], members[comparison]
        for field in ("eligible_targets", "true_edges", "theta", "mask_seed"):
            if (field in a or field in b) and (field not in a or field not in b or a[field] != b[field]):
                raise VerificationFailure(f"Paired worlds disagree on {field}")
        if pair_key == "policy" and ("observation_sha256" in a or "observation_sha256" in b):
            if a.get("observation_sha256") != b.get("observation_sha256"):
                raise VerificationFailure("Paired policies require the identical observation")
        result.append(dict(zip(keys, identity[:-1], strict=True)) | {
            "seed": identity[-1], "reference": reference, "comparison": comparison,
            **{name: b[name] - a[name] if a[name] is not None and b[name] is not None else None
               for name in metric_names},
        })
    return result
