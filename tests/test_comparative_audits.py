"""Development-only tests for final-ID ties and envelope-impossibility STOP."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from studies.audit_aware_acquisition.analysis import read
from studies.audit_aware_acquisition.auditing import AuditSelector
from studies.comparative_validity.audits import (
    CommonTieSelector,
    StoppedSelector,
    prepare,
    replay,
    tie_order,
)
from studies.exact_audit_frontier.execution import IntegerSelector, execute_audit

ROOT = Path(__file__).resolve().parents[1]


class TinyNominal:
    """Two correlated bits with a third, nominally constant query."""
    def __init__(self):
        self.query_ids = ("a", "b", "c")
        self.queries = {qid: {"cost": 1, "outcomes": {"0": {}, "1": {}}, "record_id": qid}
                        for qid in self.query_ids}
        self.signature_cells = {("0", "0", "0"): 1, ("1", "1", "0"): 2}

    def compatible(self, history):
        return sum(cell for sig, cell in self.signature_cells.items()
                   if all(sig[self.query_ids.index(h["query_id"])] == h["outcome_id"] for h in history))

    def partition(self, state, qid):
        result = {}
        for signature, cell in self.signature_cells.items():
            if cell & state:
                outcome = signature[self.query_ids.index(qid)]
                result[outcome] = result.get(outcome, 0) | cell
        return result


@pytest.fixture(scope="module")
def development():
    problems = read(ROOT / "studies/evidence_acquisition/development_problems.json")
    saved = read(ROOT / "studies/audit_aware_acquisition/development_baseline.json.gz")
    assert len(problems) == 4 and all(p["split"] == "development" for p in problems)
    return [(p, prepare(p, [c for c in saved if c["problem_id"] == p["problem_id"]])) for p in problems]


def test_ties_reproducible_complete_common_and_only_final_priority():
    nominal = TinyNominal()
    first = tie_order(nominal.query_ids, 0, 94100)
    assert first == tie_order(reversed(nominal.query_ids), 0, 94100)
    assert set(first) == set(nominal.query_ids)
    b = CommonTieSelector(nominal, "cost_order", ["b", "a", "c"])
    c = CommonTieSelector(nominal, "constant_first", ["b", "a", "c"])
    assert b.ranking == c.ranking
    assert b.choose([]) == "b"
    assert c.choose([]) == "c"  # Constant priority survives adverse final ranking.
    nominal.queries["b"]["cost"] = 2
    assert b.choose([]) == "a"  # Cost still outranks arbitrary ID ordering.


@pytest.mark.parametrize("ranking", [["a", "a", "c"], ["a", "b"], ["a", "b", "other"]])
def test_tie_rankings_cannot_drop_duplicate_or_invent_queries(ranking):
    with pytest.raises(ValueError, match="each catalogue identity"):
        CommonTieSelector(TinyNominal(), "cost_order", ranking)


@pytest.mark.parametrize("trial", [-1, 200, True])
def test_trial_bounds(trial):
    with pytest.raises(ValueError, match="Trial"):
        tie_order(["a", "b"], trial, 94100)


@pytest.mark.parametrize("arm", ["closure_informed_stopped", "closure_informed_affordable_stopped"])
def test_zero_immediate_scores_do_not_stop_complementary_detection(arm):
    nominal = TinyNominal()
    design = (*nominal.signature_cells, ("0", "1", "0"))
    selector = StoppedSelector(nominal, arm, design)
    assert set(selector.original.detection_scores([]).values()) == {0}
    assert not selector.conflict_impossible([])
    assert selector.choose([], 5) == "c"  # Historical constant fallback is retained.
    paid = [{"query_id": "c", "outcome_id": "0"}]
    assert selector.choose(paid, 4) == "a"
    paid.append({"query_id": "a", "outcome_id": "0"})
    assert not selector.conflict_impossible(paid)
    assert selector.choose(paid, 3) == "b"  # Its complementary answer can contradict.
    assert not nominal.compatible(paid + [{"query_id": "b", "outcome_id": "1"}])


@pytest.mark.parametrize("arm", ["closure_informed_stopped", "closure_informed_affordable_stopped"])
def test_stop_requires_full_compatible_envelope_nominal_not_realized_nominal(arm):
    nominal = TinyNominal()
    design = (*nominal.signature_cells, ("0", "1", "0"))
    selector = StoppedSelector(nominal, arm, design)
    assert not selector.conflict_impossible([])
    # A paid a=1 excludes the only nonnominal signature; remaining queries cost nothing.
    history = [{"query_id": "a", "outcome_id": "1"}]
    assert selector.conflict_impossible(history)
    assert selector.choose(history, 100) is None
    with pytest.raises(ValueError, match="budget"):
        selector.choose(history, -1)


def test_nominal_envelope_stops_at_zero_without_requesting_constant_queries():
    nominal = TinyNominal()
    selector = StoppedSelector(nominal, "closure_informed_stopped", nominal.signature_cells)
    assert selector.choose([], 0) is None


def test_opaque_order_recovers_original_priority_and_stop_knowledge_boundaries():
    nominal = TinyNominal()
    for arm in ("cost_order", "constant_first"):
        selector = CommonTieSelector(nominal, arm, sorted(nominal.query_ids))
        assert selector.choose([]) == AuditSelector(nominal, arm).choose([])
    assert set(inspect.signature(StoppedSelector).parameters) == {"nominal", "arm", "design_signatures"}
    assert set(inspect.signature(StoppedSelector.choose).parameters) == {"self", "history", "remaining_budget"}
    assert set(inspect.signature(CommonTieSelector).parameters) == {"nominal", "arm", "ranking"}


@pytest.mark.parametrize("index", range(4))
def test_charged_replay_matches_original_development_paths_and_cutoffs(development, index):
    _, (nominal, design, baselines, _, cache) = development[index]
    for signature in design:
        baseline = baselines[signature]
        acquired = {h["query_id"] for h in baseline["history"]}
        residual = sum(q["cost"] for qid, q in nominal.queries.items() if qid not in acquired)
        for arm in ("cost_order", "constant_first", "closure_informed", "closure_informed_affordable"):
            envelope = design if arm.startswith("closure") else None
            selector = IntegerSelector(nominal, arm, envelope)
            for percent in (0, 25, 50, 100):
                budget = residual * percent // 100
                observed = replay(nominal, baseline, signature, selector, budget, cache=cache)
                old = execute_audit(nominal, baseline, signature, arm, budget,
                                    design_signatures=envelope, certificate_cache=cache)
                assert all(observed[key] == old[key] for key in observed)
                if arm in ("cost_order", "constant_first"):
                    opaque = CommonTieSelector(nominal, arm, sorted(nominal.query_ids))
                    assert replay(nominal, baseline, signature, opaque, budget, cache=cache) == observed


@pytest.mark.parametrize("index", range(4))
def test_stopped_development_retains_detection_cost_bounds_and_charges_prefix(development, index):
    _, (nominal, design, baselines, _, cache) = development[index]
    for signature in design:
        baseline = baselines[signature]
        acquired = {h["query_id"] for h in baseline["history"]}
        residual = sum(q["cost"] for qid, q in nominal.queries.items() if qid not in acquired)
        for arm in ("closure_informed_stopped", "closure_informed_affordable_stopped"):
            selector = StoppedSelector(nominal, arm, design)
            original = IntegerSelector(nominal, arm.removesuffix("_stopped"), design)
            for percent in (0, 25, 50, 100):
                budget = residual * percent // 100
                new = replay(nominal, baseline, signature, selector, budget, cache=cache)
                old = replay(nominal, baseline, signature, original, budget, cache=cache)
                assert new["status"] == old["status"]
                assert new["added_cost"] <= old["added_cost"] <= budget
                assert old["history"][:len(new["history"])] == new["history"]
                assert new["added_cost"] == sum(nominal.queries[h["query_id"]]["cost"]
                                                 for h in new["audit_history"])
                if new["termination_reason"] == "all_compatible_full_signatures_nominal":
                    assert selector.conflict_impossible(new["history"])
                    assert new["status"] == "no_conflict_observed"
                if new["status"] == "nominal_model_conflict":
                    assert nominal.compatible(new["history"][:-1])


def test_nominal_compatible_paths_can_cost_before_knowledge_proves_stop(development):
    costs = []
    for _, (nominal, design, baselines, _, cache) in development:
        selector = StoppedSelector(nominal, "closure_informed_stopped", design)
        for signature in nominal.signature_cells:
            baseline = baselines[signature]
            paid = {h["query_id"] for h in baseline["history"]}
            budget = sum(q["cost"] for qid, q in nominal.queries.items() if qid not in paid)
            result = replay(nominal, baseline, signature, selector, budget, cache=cache)
            assert result["status"] == "no_conflict_observed"
            costs.append(result["added_cost"])
    assert max(costs) > 0
