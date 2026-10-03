"""Evidence rules preserve exposure/source-use ambiguity under receipt loss."""

from dataclasses import replace

import pytest

from tracebench.corruption import PROFILES, LoggingCompleteness, ReceiptObservation, corrupt
from tracebench.estimators import METHODS, estimate
from tracebench.model import SimulationConfig
from tracebench.observe import Telemetry, observe
from tracebench.policies import POLICIES, infer
from tracebench.simulate import observational_equivalence_pair, simulate


@pytest.fixture
def pair_observation():
    _, source_use = observational_equivalence_pair()
    return observe(source_use, Telemetry.CONTEXT)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("profile", PROFILES)
def test_clean_mode_parity_and_common_candidate_partition(method, profile):
    world = simulate(SimulationConfig(seed=41, n_runs=30, writes_per_run=3,
                                     shock_strength=0.9))
    observation = observe(world, Telemetry.CONTEXT)
    clean_predictions = estimate(observation, method)
    assert clean_predictions, "Exercise at least one recovered candidate"
    for retention in (1, 0.9, 0.5, 0):
        masked = corrupt(observation, profile, retention, 731)
        outcomes = [infer(masked, method, policy) for policy in POLICIES]
        assert outcomes[0].candidates == outcomes[1].candidates
        assert outcomes[0].predictions == estimate(masked.observation, method)
        for result in outcomes:
            assert not (result.predictions & result.unresolved
                        or result.predictions & result.excluded
                        or result.unresolved & result.excluded)
            assert result.candidates == result.predictions | result.unresolved | result.excluded
        if retention == 1:
            assert all(result.predictions == clean_predictions for result in outcomes)
            assert all(not result.unresolved for result in outcomes)


@pytest.mark.parametrize("method", METHODS)
def test_authentic_context_positive_survives_missing_delivery_and_request(pair_observation, method):
    masked = corrupt(pair_observation, "drop_delivery", 0, 32)
    expected = frozenset({("e000000", "e000001")})
    assert not infer(masked, method, "conjunction").predictions
    assert infer(masked, method, "evidence_aware").predictions == expected
    without_request = ReceiptObservation(
        replace(masked.observation, requests=()), LoggingCompleteness(False, False, True),
    )
    assert infer(without_request, method, "evidence_aware").predictions == expected
    assert not infer(without_request, method, "evidence_aware").unresolved


def test_genuine_nondelivery_differs_from_unlogged_success(pair_observation):
    # Identical writes and page requests; the successful event has a downstream
    # receipt whereas true non-delivery has none. Source-use truth is not an input.
    failed_delivery = replace(pair_observation, deliveries=(), contexts=())
    genuine = ReceiptObservation(failed_delivery, LoggingCompleteness(True, True, True))
    successful = corrupt(pair_observation, "drop_delivery", 0, 11)
    assert genuine.observation.deliveries == successful.observation.deliveries == ()
    failure = infer(genuine, "temporal", "evidence_aware")
    success = infer(successful, "temporal", "evidence_aware")
    assert failure.excluded == success.predictions == success.candidates
    assert not failure.predictions and not failure.unresolved


@pytest.mark.parametrize("method", METHODS)
def test_missing_context_is_unknown_without_completeness_assurance(pair_observation, method):
    lost_context = corrupt(pair_observation, "drop_context", 0, 51)
    incomplete = infer(lost_context, method, "evidence_aware")
    complete = infer(replace(lost_context, completeness=LoggingCompleteness(True, True, True)),
                     method, "evidence_aware")
    assert incomplete.unresolved == complete.excluded == incomplete.candidates
    assert not incomplete.predictions and not complete.predictions
    assert not incomplete.excluded and not complete.unresolved
    # The baseline's rejected set is deliberately not evidentiary exclusion.
    conjunction = infer(lost_context, method, "conjunction")
    assert conjunction.excluded == incomplete.unresolved
    assert not conjunction.unresolved


def test_upstream_absence_excludes_only_with_relevant_completeness(pair_observation):
    empty_receipts = replace(pair_observation, deliveries=(), contexts=())
    delivery_complete = ReceiptObservation(empty_receipts, LoggingCompleteness(True, True, False))
    delivery_unknown = replace(delivery_complete,
                               completeness=LoggingCompleteness(True, False, False))
    excluded = infer(delivery_complete, "temporal", "evidence_aware")
    unknown = infer(delivery_unknown, "temporal", "evidence_aware")
    assert excluded.excluded == unknown.unresolved == unknown.candidates
    no_upstream = replace(empty_receipts, requests=())
    request_complete = ReceiptObservation(no_upstream, LoggingCompleteness(True, False, False))
    request_unknown = replace(request_complete,
                              completeness=LoggingCompleteness(False, False, False))
    assert infer(request_complete, "temporal", "evidence_aware").excluded == unknown.candidates
    assert infer(request_unknown, "temporal", "evidence_aware").unresolved == unknown.candidates


@pytest.mark.parametrize("changes", [
    {"run_id": "unrelated-run"}, {"source_event_id": "unrelated-source"},
    {"timestamp": 0}, {"timestamp": 1}, {"concepts": ("forged-content",)},
    {"witness_tokens": ("forged-token",)},
])
def test_malformed_context_cannot_assert_exposure(pair_observation, changes):
    malformed = replace(pair_observation,
                        contexts=(replace(pair_observation.contexts[0], **changes),))
    result = infer(ReceiptObservation(malformed, LoggingCompleteness(True, True, True)),
                   "temporal", "evidence_aware")
    assert result.candidates
    assert not result.predictions


@pytest.mark.parametrize("channel,changes", [
    ("requests", {"run_id": "unrelated-run"}),
    ("requests", {"page": "wrong-page"}),
    ("requests", {"timestamp": 0.8}),
    ("deliveries", {"run_id": "unrelated-run"}),
    ("deliveries", {"source_event_id": "wrong-source"}),
    ("deliveries", {"timestamp": 0.8}),
    ("deliveries", {"timestamp": 0.1}),
])
def test_present_inconsistent_upstream_references_do_not_authenticate_context(
    pair_observation, channel, changes,
):
    malformed = replace(pair_observation,
                        **{channel: (replace(getattr(pair_observation, channel)[0], **changes),)})
    result = infer(ReceiptObservation(malformed, LoggingCompleteness(True, True, True)),
                   "temporal", "evidence_aware")
    assert not result.predictions


def test_unauthenticated_receipts_cannot_assert_exposure(pair_observation):
    untrusted = ReceiptObservation(pair_observation, LoggingCompleteness(True, True, True, False))
    result = infer(untrusted, "temporal", "evidence_aware")
    assert result.unresolved == result.candidates
    assert not result.predictions and not result.excluded


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("profile,retention", [("drop_delivery", 1), ("drop_delivery", 0),
                                             ("drop_context", 0)])
def test_exposure_and_missing_receipts_leave_source_use_ambiguous(method, profile, retention):
    independent, source_use = observational_equivalence_pair()
    assert independent.truth_edges != source_use.truth_edges
    left = corrupt(observe(independent, Telemetry.CONTEXT), profile, retention, 27)
    right = corrupt(observe(source_use, Telemetry.CONTEXT), profile, retention, 27)
    assert left == right
    for policy in POLICIES:
        assert infer(left, method, policy) == infer(right, method, policy)
    aware = infer(left, method, "evidence_aware")
    if profile == "drop_delivery":
        # Same heuristic attribution in a zero-use and a positive-control world.
        assert aware.predictions == source_use.truth_edges
    else:
        assert aware.unresolved == source_use.truth_edges
        assert not aware.predictions


def test_policies_reject_truth_and_unknown_policy(pair_observation):
    world, _ = observational_equivalence_pair()
    with pytest.raises(TypeError, match="ReceiptObservation"):
        infer(world, "temporal", "evidence_aware")
    with pytest.raises(ValueError, match="policy"):
        infer(corrupt(pair_observation, "drop_context", 1, 7), "temporal", "replay")
