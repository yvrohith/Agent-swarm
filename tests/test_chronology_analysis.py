"""Focused small-world checks of stable masking and paired metric accounting."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studies.chronology_consistency.analysis import (  # noqa: E402
    SCORE_METRICS,
    aggregate_impacts,
    couple_masks,
    evaluate_benchmark_world,
    record_identity,
)
from studies.chronology_consistency.retime import retime_world  # noqa: E402
from studies.chronology_consistency.trace import trace_world  # noqa: E402
from tracebench.estimators import estimate  # noqa: E402
from tracebench.evaluate import score_edges  # noqa: E402
from tracebench.model import ContextEntry, Delivery, Request, SimulationConfig, Write  # noqa: E402
from tracebench.observe import Observation, Telemetry, observe  # noqa: E402


@pytest.fixture(scope="module")
def diagnostic():
    captured = trace_world(SimulationConfig(seed=0, n_runs=2, writes_per_run=3,
                                           n_task_families=1, shock_strength=0.0))
    return captured.world, retime_world(captured).world


def receipt_observations():
    source = Write("source", 0.0, "page", "h1", ("c",), ("w",), "run1")
    target = Write("target", 10.0, "page", "h2", ("c",), ("w",), "run2")
    requests = tuple(Request(f"q{i}", 1.0 + i, "run2", "page") for i in range(3))
    deliveries = tuple(Delivery(f"q{i}", 2.0 + i, "run2", "source") for i in range(3))
    contexts = tuple(ContextEntry(f"q{i}", 3.0 + i, "run2", "source", ("c",), ("w",))
                     for i in range(3))
    original = Observation(Telemetry.CONTEXT, (source, target), requests, deliveries, contexts)
    changed = replace(original,
        requests=tuple(replace(r, timestamp=r.timestamp + 0.25) for r in reversed(requests)),
        deliveries=tuple(replace(r, timestamp=r.timestamp + 0.25) for r in reversed(deliveries)),
        contexts=tuple(replace(r, timestamp=r.timestamp + 0.25) for r in reversed(contexts)))
    return original, changed


@pytest.mark.parametrize("profile", ["drop_delivery", "drop_context"])
@pytest.mark.parametrize("retention", [0, 0.5, 1])
def test_masks_preserve_physical_identity_and_actual_retention(profile, retention):
    original, corrected = receipt_observations()
    left, right, audit = couple_masks(original, corrected, profile, retention, 11)
    assert left.completeness == right.completeness
    for channel in ("requests", "deliveries", "contexts"):
        assert {record_identity(channel, r) for r in getattr(left.observation, channel)} == {
            record_identity(channel, r) for r in getattr(right.observation, channel)}
        assert audit["channels"][channel]["membership_equal"]
        assert audit["channels"][channel]["actual_retention_equal"]
        # Corrected timestamps survive the adapter; it must not substitute legacy records.
        for record in getattr(right.observation, channel):
            assert record in getattr(corrected, channel)
    assert audit["historical_mask_uses_timestamp"]


def test_mask_rejects_identity_ambiguity_and_non_timestamp_change():
    original, corrected = receipt_observations()
    with pytest.raises(ValueError, match="not unique"):
        couple_masks(original, replace(corrected, contexts=corrected.contexts * 2),
                     "drop_context", 0.5, 11)
    invalid = replace(corrected.contexts[0], witness_tokens=("mutated",))
    with pytest.raises(ValueError, match="Non-timestamp"):
        couple_masks(original, replace(corrected, contexts=(invalid, *corrected.contexts[1:])),
                     "drop_context", 0.5, 11)
    with pytest.raises(ValueError, match="identity mismatch"):
        couple_masks(original, replace(corrected, deliveries=()), "drop_delivery", 0.5, 11)


def test_mask_does_not_accept_truth(diagnostic):
    legacy, corrected = diagnostic
    with pytest.raises(TypeError, match="observations"):
        couple_masks(legacy, corrected, "drop_context", 0.5, 11)


def benchmark_rows(world):
    rows = []
    for regime in Telemetry:
        for method in ("temporal", "witness"):
            score = score_edges(estimate(observe(world, regime), method), world.truth_edges,
                                world.eligible_target_ids)
            # Historical benchmark did not save these later-derived target fields.
            for metric in ("false_positive_targets", "false_negative_targets", "signed_error",
                           "target_disagreement"):
                del score[metric]
            rows.append({"seed": world.config.seed, "transmission_probability": 0.3,
                         "shock_strength": 0.0, "regime": regime.value, "method": method,
                         **score})
    return rows


def test_benchmark_reproduction_preserves_old_fields_and_augments_target_errors(diagnostic):
    legacy, corrected = diagnostic
    result = evaluate_benchmark_world(legacy, corrected, benchmark_rows(legacy))
    assert all(row["matched"] for row in result["reproduction"])
    assert len(result["runs"]) == 10
    for row in result["runs"]:
        assert set(row["legacy"]) == set(SCORE_METRICS)
        assert "signed_error" in row["derived_legacy_metric_fields"]
        assert "absolute_error" in row["saved_metric_fields"]
        if row["regime"] in ("writes", "identity"):
            assert not row["changed_metrics"]


def test_failed_reproduction_is_unavailable_not_an_effect(diagnostic):
    legacy, corrected = diagnostic
    saved = benchmark_rows(legacy)
    saved[0]["predicted_edges"] += 1
    result = evaluate_benchmark_world(legacy, corrected, saved)
    row = result["runs"][0]
    assert row["status"] == "unavailable_due_to_failed_reproduction"
    assert row["corrected"] is None
    assert all(value is None for value in row["corrected_minus_legacy"].values())
    assert row["unavailable_reasons"][0]["field"] == "predicted_edges"


def test_correction_failure_preserves_legacy_and_denominators(diagnostic):
    legacy, _ = diagnostic
    result = evaluate_benchmark_world(legacy, None, benchmark_rows(legacy),
                                      failure_reason="unrepresentable interval")
    assert len(result["runs"]) == 10
    assert all(row["matched"] for row in result["reproduction"])
    assert all(row["status"] == "unavailable_due_to_correction_failure"
               for row in result["runs"])
    assert result["runs"][0]["unavailable_reasons"] == [
        {"correction": "unrepresentable interval"}]


def impact(seed, signed, absolute, *, corrected=True):
    left = {"signed_error": signed, "absolute_error": absolute, "precision": None}
    return {"seed": seed, "world_id": str(seed), "scenario": "one", "legacy": left,
            "corrected": left if corrected else None,
            "corrected_minus_legacy": {"signed_error": 0.0, "absolute_error": 0.0,
                                        "precision": None}, "changed_metrics": []}


def test_grouping_means_absolute_errors_without_cancellation_and_keeps_nulls():
    rows = [impact(0, 0.25, 0.25), impact(1, -0.25, 0.25)]
    group = aggregate_impacts(rows, group_keys=("scenario",))[0]
    assert group["n_worlds"] == 2
    assert group["metrics"]["signed_error"]["legacy"]["mean"] == 0
    assert group["metrics"]["absolute_error"]["legacy"]["mean"] == 0.25
    assert group["metrics"]["precision"]["corrected_minus_legacy"] == {
        "mean": None, "n_defined_worlds": 0}
    with pytest.raises(ValueError, match="Repeated world"):
        aggregate_impacts(rows + rows[:1], group_keys=("scenario",))


def test_grouping_does_not_substitute_partial_cohort_for_unavailable_world():
    rows = [impact(0, 0.25, 0.25), impact(1, -0.25, 0.25, corrected=False)]
    group = aggregate_impacts(rows, group_keys=("scenario",))[0]
    assert group["n_worlds"] == 2
    assert group["n_unavailable_worlds"] == 1
    assert group["metrics"]["absolute_error"]["legacy"]["mean"] == 0.25
    assert group["metrics"]["absolute_error"]["corrected"]["mean"] is None
    assert group["metrics"]["absolute_error"]["corrected_minus_legacy"]["mean"] is None


def test_grouping_requires_original_dimensions_and_fixed_denominators():
    row = impact(0, 0.25, 0.25)
    row["profile"] = "drop_context"
    with pytest.raises(ValueError, match="scenario dimension"):
        aggregate_impacts([row], group_keys=("scenario",))
    row["legacy"] = row["legacy"] | {"eligible_targets": 6}
    row["corrected"] = row["corrected"] | {"eligible_targets": 7}
    with pytest.raises(ValueError, match="denominator"):
        aggregate_impacts([row], group_keys=("scenario", "profile"))


def test_policy_difference_of_differences_is_not_one_policy_treatment_effect():
    from studies.chronology_consistency.analysis import RECEIPT_METRICS, _policy_impacts
    from tracebench.evaluate import paired_differences
    from tracebench.receipt_study import PAIR_KEYS, PAIRED_METRICS

    truth, eligible = frozenset({("a", "t1")}), frozenset({"t1", "t2", "t3", "t4"})
    common = {"seed": 0, "transmission_probability": 0.3, "shock_strength": 0.0,
              "regime": "context", "method": "temporal", "profile": "drop_delivery",
              "retention": 0.5, "mask_seed": 11, "world_id": "example"}

    def row(policy, predictions, observation):
        return {**dict.fromkeys(RECEIPT_METRICS, 0), **common, "policy": policy,
                "observation_sha256": observation,
                **score_edges(frozenset(predictions), truth, eligible)}

    legacy = [row("conjunction", [], "legacy"),
              row("evidence_aware", [("a", "t1"), ("b", "t2")], "legacy")]
    corrected = [row("conjunction", [("a", "t1")], "corrected"),
                 row("evidence_aware", [("a", "t1"), ("b", "t2")], "corrected")]
    saved = paired_differences(legacy, group_keys=PAIR_KEYS, metric_names=PAIRED_METRICS)
    inputs = [{"world_id": "example", "legacy_rows": legacy, "corrected_rows": corrected}]
    contrasts, reproduction = _policy_impacts(inputs, saved)
    assert reproduction[0]["matched"]
    assert contrasts[0]["legacy"]["signed_error"] == 0.5
    assert contrasts[0]["corrected"]["signed_error"] == 0.25
    assert contrasts[0]["corrected_minus_legacy"]["signed_error"] == -0.25
    assert contrasts[0]["eligible_targets"] == 4
    assert corrected[1]["signed_error"] - legacy[1]["signed_error"] == 0.0
    corrected[1]["eligible_targets"] = 5
    with pytest.raises(ValueError, match="eligible denominator"):
        _policy_impacts(inputs, saved)


@pytest.fixture
def saved_small_cohorts(diagnostic):
    """Create development inputs via the unchanged historical scientific calls."""
    from dataclasses import asdict

    from tracebench.corruption import corrupt
    from tracebench.evaluate import paired_differences, summarize
    from tracebench.policies import infer
    from tracebench.receipt_study import (
        GROUP_KEYS,
        PAIR_KEYS,
        PAIRED_METRICS,
        STUDY_METRICS,
        _digest,
    )

    legacy, _ = diagnostic
    benchmark = benchmark_rows(legacy)
    benchmark_saved = {"runs": benchmark, "summary": summarize(
        benchmark, 100, metric_names=tuple(k for k in SCORE_METRICS if k in benchmark[0]))}
    full = observe(legacy, Telemetry.CONTEXT)
    world_id = _digest(asdict(legacy.config))
    saved_world = {"world_id": world_id, "config": asdict(legacy.config), "mask_seed": 11,
                   "truth_sha256": _digest(sorted(legacy.truth_edges)),
                   "eligible_targets_sha256": _digest(sorted(legacy.eligible_target_ids)),
                   "writes_sha256": _digest([asdict(w) for w in legacy.writes]),
                   "true_edges": len(legacy.truth_edges), "eligible_targets": len(legacy.writes)}
    runs, retention_audit = [], []
    for profile in ("drop_delivery", "drop_context"):
        for retention in (1, 0.5):
            masked = corrupt(full, profile, retention, 11)
            audit = {"world_id": world_id, "mask_seed": 11, "seed": 0,
                     "transmission_probability": 0.3, "shock_strength": 0.0,
                     "regime": "context", "profile": profile, "retention": retention,
                     "observation_sha256": _digest(asdict(masked))}
            for singular, plural in (("request", "requests"), ("delivery", "deliveries"),
                                     ("context", "contexts")):
                original = len(getattr(full, plural))
                retained = len(getattr(masked.observation, plural))
                audit[f"{singular}_records_original"] = original
                audit[f"{singular}_records_retained"] = retained
                audit[f"{singular}_record_retention"] = retained / original if original else None
            retention_audit.append(audit)
            for method in ("temporal", "witness"):
                for policy in ("conjunction", "evidence_aware"):
                    inferred = infer(masked, method, policy)
                    unresolved = len({target for _, target in inferred.unresolved})
                    runs.append({**audit, "method": method, "policy": policy,
                        **score_edges(inferred.predictions, legacy.truth_edges,
                                      legacy.eligible_target_ids),
                        "candidate_edges": len(inferred.candidates),
                        "excluded_or_rejected_edges": len(inferred.excluded),
                        "unresolved_edges": len(inferred.unresolved), "unresolved_targets": unresolved,
                        "unresolved_target_fraction": unresolved / len(legacy.writes),
                        "unresolved_edges_per_target": len(inferred.unresolved) / len(legacy.writes),
                        "unresolved_candidate_fraction": (len(inferred.unresolved)
                            / len(inferred.candidates) if inferred.candidates else None)})
    paired = paired_differences(runs, group_keys=PAIR_KEYS, metric_names=PAIRED_METRICS)
    receipts_saved = {"runs": runs, "retention_audit": retention_audit,
        "worlds": [saved_world], "paired_runs": paired,
        "summary": summarize(runs, 100, group_keys=GROUP_KEYS, metric_names=STUDY_METRICS),
        "paired_summary": summarize(paired, 100, group_keys=PAIR_KEYS, metric_names=PAIRED_METRICS)}
    return benchmark_saved, receipts_saved


def test_complete_small_receipt_reproduction_and_finalizer(diagnostic, saved_small_cohorts):
    from studies.chronology_consistency.analysis import evaluate_receipt_world, finalize_impact

    legacy, corrected = diagnostic
    benchmark_saved, receipts_saved = saved_small_cohorts
    benchmark = evaluate_benchmark_world(legacy, corrected, benchmark_saved["runs"])
    receipt = evaluate_receipt_world(legacy, corrected, receipts_saved["worlds"][0],
                                    receipts_saved["runs"])
    result = finalize_impact(benchmark_saved, receipts_saved, [benchmark], [receipt])
    assert result["counts"]["reproduction_all_matched"]
    assert result["counts"]["benchmark_evaluations"] == 10
    assert result["counts"]["receipt_evaluations"] == 16
    assert result["counts"]["policy_contrasts"] == 8
    assert len(result["mask_audit"]) == 4
    assert all(row["corrected"] is not None for row in result["per_world_impact"])
    assert all(row["n_worlds"] == 1 for row in result["per_scenario_impact"])


def test_missing_generated_world_preserves_entire_saved_grid(saved_small_cohorts):
    from studies.chronology_consistency.analysis import finalize_impact, unavailable_world_result

    benchmark_saved, receipts_saved = saved_small_cohorts
    world_id = receipts_saved["worlds"][0]["world_id"]
    benchmark = unavailable_world_result("benchmark", benchmark_saved["runs"], None,
                                         world_id, "fixture generation failed")
    receipt = unavailable_world_result("missing_receipts", receipts_saved["runs"],
                                       receipts_saved["worlds"][0], world_id,
                                       "fixture saved hash mismatch")
    result = finalize_impact(benchmark_saved, receipts_saved, [benchmark], [receipt])
    assert result["counts"]["unavailable_evaluations"] == 26
    assert not result["counts"]["reproduction_all_matched"]
    assert len(result["policy_paired_impact"]) == 8
    assert len(result["mask_audit"]) == 4
    assert all(row["status"] == "unavailable_due_to_failed_reproduction"
               for row in result["mask_audit"])
    for row in result["per_world_impact"]:
        assert row["saved_legacy"]["eligible_targets"] == 6
        assert not row["legacy_available"]
        assert all(value is None for value in row["legacy"].values())
        assert all(value is None for value in row["corrected_minus_legacy"].values())
    for row in result["per_scenario_impact"] + result["policy_group_impact"]:
        assert row["n_worlds"] == 1
        assert row["n_unavailable_worlds"] == 1
        assert all(metric["legacy"]["mean"] is None for metric in row["metrics"].values())
    for row in result["policy_paired_impact"]:
        assert row["eligible_targets"] == 6
        assert row["saved_legacy"]
        assert not row["legacy_available"]


def test_correction_failure_keeps_computed_legacy_mask_grid(diagnostic, saved_small_cohorts):
    from studies.chronology_consistency.analysis import evaluate_receipt_world

    legacy, _ = diagnostic
    _, saved = saved_small_cohorts
    result = evaluate_receipt_world(legacy, None, saved["worlds"][0], saved["runs"],
                                    failure_reason="fixture unrepresentable interval")
    assert len(result["mask_audit"]) == 4
    assert len(result["runs"]) == 16
    assert all(row["matched"] for row in result["reproduction"])
    for audit in result["mask_audit"]:
        assert audit["status"] == "unavailable_due_to_correction_failure"
        assert audit["failure"] == "fixture unrepresentable interval"
        for channel in audit["channels"].values():
            assert channel["retained_records"] == len(channel["legacy_retained_ids"])
            assert channel["original_records"] >= channel["retained_records"]
            assert channel["corrected_retained_ids"] is None
            assert channel["membership_equal"] is None
            assert channel["actual_retention_equal"] is None


def test_structured_failure_round_trip_is_canonical(saved_small_cohorts):
    from studies.chronology_consistency.analysis import unavailable_world_result

    saved, _ = saved_small_cohorts
    one = unavailable_world_result("benchmark", saved["runs"], None, "id",
                                    {"type": "ValueError", "message": "bad hash"})
    two = unavailable_world_result("benchmark", saved["runs"], None, "id",
                                    {"message": "bad hash", "type": "ValueError"})
    assert one == two
