"""Direct chronology/metric checks qualified only on saved diagnostic and toys."""

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from studies.chronology_consistency.reference import (
    VerificationFailure,
    audit_availability,
    grouped_world_means,
    paired_world_differences,
    reference_score,
    verify_metric_row,
    verify_retiming,
)
from studies.chronology_consistency.retime import retime_world
from studies.chronology_consistency.trace import (
    CapturedTrace,
    ChainInstallation,
    DecisionSnapshot,
    trace_world,
)
from tracebench.evaluate import score_edges
from tracebench.model import ContextEntry, Delivery, Request, SimulationConfig, World, Write

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def diagnostic():
    saved = json.loads((ROOT / "studies/review_remediation/chronology.json").read_text())
    row = next(row for row in saved["worlds"] if row["published_cohort"] == "minimal_diagnostic")
    return trace_world(SimulationConfig(**row["config"]))


def toy_trace(*, repeated=False, narrow=False):
    """A final receipt preceding a prior write despite installation at its owner."""
    source = Write("s", 0.0, "p", "hs", ("x",), ("w",), "source")
    prior = Write("p", 1.0, "p", "hr", (), (), "recipient")
    owner_time = math.nextafter(1.0, math.inf) if narrow else 2.0
    owner = replace(prior, event_id="o", timestamp=owner_time)
    writes = (source, prior, owner)
    requests = (Request("q", 0.1, "recipient", "p"),)
    deliveries = (Delivery("q", 0.2, "recipient", "s"),)
    contexts = (ContextEntry("q", 0.5, "recipient", "s", ("x",), ("w",)),)
    chains = (ChainInstallation("q", "o", 2, "s", "recipient", True, True, True),)
    if repeated:
        writes += (replace(prior, event_id="later", timestamp=4.0),)
        requests += (Request("repeat", 2.1, "recipient", "p"),)
        deliveries += (Delivery("repeat", 2.2, "recipient", "s"),)
        contexts += (ContextEntry("repeat", 2.3, "recipient", "s", ("x",), ("w",)),)
        chains += (ChainInstallation("repeat", "later", 3, "s", "recipient", True, True, False),)
    world = World(SimulationConfig(n_runs=2, writes_per_run=2), writes, requests,
                  deliveries, contexts, frozenset(), frozenset(w.event_id for w in writes))
    snapshots = tuple(DecisionSnapshot(
        w.event_id, w.run_id, w.timestamp, i, ("s",) if i >= 2 else (),
        tuple(c.request_id for c in chains if c.owner_write_id == w.event_id),
        tuple(c.request_id for c in chains if c.owner_write_id == w.event_id),
        "fixture", None, "fixture",
    ) for i, w in enumerate(writes))
    return CapturedTrace(world, snapshots, chains, True, {})


def test_known_six_write_final_log_contradiction(diagnostic):
    audit = audit_availability(diagnostic.world, diagnostic)
    assert audit["writes_checked"] == 6
    assert audit["affected_writes"] == 1
    assert audit["distinct_first_availability_contradictions"] == 1
    assert audit["offending_chain_ids"] == ["q000001"]
    assert audit["max_time_discrepancy"] > 0
    row = audit["disagreements"][0]
    assert row["write_event_id"] == "e000003"
    assert row["extra_source_ids"] == ["e000002"]
    assert row["missing_source_ids"] == []
    # The owner is a later generation step; an append-prefix checker would miss it.
    chain = next(c for c in diagnostic.chains if c.request_id == "q000001")
    assert chain.generation_index > row["generation_index"]


def test_checker_compares_identities_not_only_available_count():
    trace = toy_trace()
    changed = replace(trace.snapshots[-1], available_source_ids=("p",))
    swapped = replace(trace, snapshots=trace.snapshots[:-1] + (changed,))
    audit = audit_availability(trace.world, swapped)
    owner = next(row for row in audit["disagreements"] if row["write_event_id"] == "o")
    assert len(owner["captured_source_ids"]) == len(owner["logged_source_ids"]) == 1
    assert owner["extra_source_ids"] == ["s"] and owner["missing_source_ids"] == ["p"]


def test_repeated_receipts_are_one_source_and_only_offending_chain_moves():
    trace = toy_trace(repeated=True)
    audit = audit_availability(trace.world, trace)
    assert audit["context_records"] == 2
    assert audit["distinct_source_run_installations"] == 1
    assert audit["repeated_context_receipts"] == 1
    assert audit["extra_source_decisions"] == 1
    assert audit["offending_chain_ids"] == ["q"]
    corrected = retime_world(trace).world
    result = verify_retiming(trace.world, corrected, trace)
    assert result["corrected_affected_writes"] == 0
    assert corrected.contexts[-1] == trace.world.contexts[-1]
    assert audit_availability(corrected, trace)["affected_writes"] == 0


def test_repeated_receipt_itself_can_be_offending_without_new_source_installation():
    trace = toy_trace(repeated=True)
    first, repeated = trace.world.contexts
    contexts = (replace(repeated, timestamp=0.4), replace(first, timestamp=1.5))
    trace = replace(trace, world=replace(trace.world, contexts=contexts))
    audit = audit_availability(trace.world, trace)
    assert audit["offending_chain_ids"] == ["repeat"]
    assert audit["distinct_first_availability_contradictions"] == 1
    assert not trace.chains[-1].first_installation
    verified = verify_retiming(trace.world, retime_world(trace).world, trace)
    assert verified["corrected_request_ids"] == ["repeat"]


def test_independent_retiming_verifier_checks_every_write_and_preservation(diagnostic):
    corrected = retime_world(diagnostic).world
    checked = verify_retiming(diagnostic.world, corrected, diagnostic)
    assert checked["writes_checked"] == 6
    assert checked["corrected_chains"] == 1
    assert checked["all_other_fields_preserved"]
    with pytest.raises(VerificationFailure, match="immutable World field: truth_edges"):
        verify_retiming(diagnostic.world, replace(corrected, truth_edges=frozenset({("x", "y")})),
                        diagnostic)
    with pytest.raises(VerificationFailure, match="Unexpected timestamp/non-timestamp/order"):
        changed = replace(corrected.contexts[0], witness_tokens=("changed",))
        verify_retiming(diagnostic.world, replace(corrected, contexts=(changed,)), diagnostic)


def test_unaffected_world_and_chains_must_remain_exactly_unchanged():
    trace = toy_trace(repeated=True)
    safe_contexts = (replace(trace.world.contexts[0], timestamp=1.5), trace.world.contexts[1])
    trace = replace(trace, world=replace(trace.world, contexts=safe_contexts))
    assert verify_retiming(trace.world, trace.world, trace)["corrected_chains"] == 0
    altered = replace(trace.world.requests[0], timestamp=0.11)
    corrected = replace(trace.world, requests=(altered,) + trace.world.requests[1:])
    with pytest.raises(VerificationFailure, match="Unexpected timestamp"):
        verify_retiming(trace.world, corrected, trace)


def test_retiming_verifier_rejects_missing_stage_and_unrepresentable_interval():
    trace = toy_trace()
    missing = replace(trace.world, deliveries=())
    with pytest.raises(VerificationFailure, match="upstream records"):
        audit_availability(missing, trace)
    narrow = toy_trace(narrow=True)
    with pytest.raises(VerificationFailure, match="Unrepresentable strict quarter-interval"):
        verify_retiming(narrow.world, narrow.world, narrow)


def test_retiming_verifier_requires_exact_quarters_and_complete_trace():
    trace = toy_trace()
    corrected = retime_world(trace).world
    bad = replace(corrected, requests=(replace(corrected.requests[0], timestamp=1.3),))
    with pytest.raises(VerificationFailure, match="Unexpected timestamp"):
        verify_retiming(trace.world, bad, trace)
    with pytest.raises(VerificationFailure, match="every write exactly once"):
        audit_availability(trace.world, replace(trace, snapshots=trace.snapshots[:-1]))


@pytest.mark.parametrize("predictions,truth", [
    (frozenset(), frozenset()),
    (frozenset({("s", "a")}), frozenset()),
    (frozenset(), frozenset({("s", "a")})),
    (frozenset({("wrong", "a")}), frozenset({("s", "a")})),
    (frozenset({("s", "a"), ("other", "a")}), frozenset({("s", "b")})),
])
def test_independent_scores_and_undefined_denominators(predictions, truth):
    eligible = frozenset({"a", "b", "c"})
    actual = score_edges(predictions, truth, eligible)
    assert actual == reference_score(predictions, truth, eligible)
    verify_metric_row(actual)
    with pytest.raises(VerificationFailure, match="Metric identity failed: target_disagreement"):
        verify_metric_row(actual | {"target_disagreement": actual["target_disagreement"] + 0.1})


def test_target_swap_has_zero_signed_error_but_positive_disagreement():
    row = reference_score({("s", "a")}, {("s", "b")}, {"a", "b", "c", "d"})
    assert row["signed_error"] == row["absolute_error"] == 0
    assert row["target_disagreement"] == 0.5
    assert row["false_positive_targets"] == row["false_negative_targets"] == 1
    with pytest.raises(VerificationFailure, match="Target count identities"):
        verify_metric_row(row | {"false_positive_targets": 0})


def test_world_means_keep_absolute_error_and_undefined_denominators():
    rows = [dict(seed=0, signed_error=-0.5, absolute_error=0.5, precision=None),
            dict(seed=1, signed_error=0.5, absolute_error=0.5, precision=1.0)]
    mean = grouped_world_means(rows, group_keys=(),
                               metric_names=("signed_error", "absolute_error", "precision"))[0]
    assert mean["n_worlds"] == 2
    assert mean["metrics"]["absolute_error"]["mean"] == 0.5
    assert mean["metrics"]["signed_error"]["mean"] == 0
    assert mean["metrics"]["precision"] == {"mean": 1.0, "n_defined": 1, "n_worlds": 2}
    with pytest.raises(VerificationFailure, match="one row per world"):
        grouped_world_means(rows + rows[:1], group_keys=(), metric_names=("absolute_error",))
    with pytest.raises(VerificationFailure, match="omits study dimensions"):
        grouped_world_means([row | {"policy": "conjunction"} for row in rows],
                            group_keys=(), metric_names=("absolute_error",))


def test_paired_axes_and_difference_of_policy_contrasts_have_correct_sign():
    rows = [dict(seed=0, version=version, policy=policy, eligible_targets=10, true_edges=2,
                 theta=0.2, precision=None, error=value)
            for version, policy, value in (("legacy", "conjunction", 0.3),
                                            ("legacy", "evidence_aware", 0.2),
                                            ("corrected", "conjunction", 0.1),
                                            ("corrected", "evidence_aware", 0.4))]
    paired = paired_world_differences(rows, group_keys=("version",),
                                     metric_names=("error", "precision"), pair_key="policy",
                                     reference="conjunction", comparison="evidence_aware")
    indexed = {row["version"]: row for row in paired}
    assert indexed["legacy"]["error"] == pytest.approx(-0.1)
    assert indexed["corrected"]["error"] == pytest.approx(0.3)
    change = paired_world_differences(paired, group_keys=(), metric_names=("error", "precision"))
    assert change[0]["error"] == pytest.approx(0.4)
    assert change[0]["precision"] is None
    with pytest.raises(VerificationFailure, match="both paired"):
        paired_world_differences(rows[:-1], group_keys=("policy",), metric_names=("error",))
    with pytest.raises(VerificationFailure, match="eligible_targets"):
        altered = [row | {"eligible_targets": 11} if row["version"] == "corrected" else row
                   for row in rows]
        paired_world_differences(altered, group_keys=("policy",), metric_names=("error",))
