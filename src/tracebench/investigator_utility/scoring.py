"""Mechanical warranted-conclusion scoring, with cases as analysis units.

Primary status metrics require a valid claim-answer schema; citation existence is
audited separately and is not a semantic evidence-support grade. A schema-valid
answer with an unknown citation can count as status-correct, but never as a
successful unresolved answer. The unresolved certainty-or-invalid metric counts
both schema and citation failures. Empty citation lists are legal; explanations
are checked for a nonempty string, never judged by an LLM.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from statistics import mean

STATUSES = ("established", "ruled_out", "unresolved")
MAX_REASON_CHARS = 400
METRICS = (
    "unjustified_certainty",
    "warranted_answer_accuracy",
    "three_class_accuracy",
    "correct_unresolved",
    "invalid_missing_answer_rate",
    "evidence_citation_error_rate",
    "unjustified_certainty_or_invalid",
)
COMPARISONS = (("C", "B"), ("B", "A"), ("C", "A"))


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _metric(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _validate_case_gold(case: dict, gold: dict) -> tuple[list[str], dict, set[str]]:
    ids = [claim["id"] for claim in case["claims"]]
    if not ids or len(set(ids)) != len(ids) or not all(isinstance(i, str) for i in ids):
        raise ValueError("case must contain nonempty, distinct string claim IDs")
    if case["subset"] not in {"wiki", "synthetic"}:
        raise ValueError("case subset must be wiki or synthetic")
    labels = {claim["id"]: claim["status"] for claim in gold["claims"]}
    if (gold["case_id"] != case["case_id"] or set(labels) != set(ids)
            or len(labels) != len(gold["claims"])):
        raise ValueError("gold must match exactly the supplied case and claim IDs")
    if any(status not in STATUSES for status in labels.values()):
        raise ValueError("gold contains an unsupported status")
    evidence = [record["id"] for record in case["records"] + case.get("assumptions", [])]
    if len(set(evidence)) != len(evidence) or not all(isinstance(i, str) for i in evidence):
        raise ValueError("record and assumption evidence IDs must be distinct strings")
    return ids, labels, set(evidence)


def score_response(case: dict, gold: dict, response: dict | str | None) -> dict:
    """Score exactly one supplied case without repairing or dropping bad answers.

    Structural root errors (including an unknown claim) invalidate the response.
    A missing or duplicate expected claim invalidates that claim. Other valid
    expected claims remain scoreable. Counts always use the frozen gold universe.
    """
    ids, labels, evidence_ids = _validate_case_gold(case, gold)
    response_errors = []
    if isinstance(response, str):
        try:
            response = json.loads(response, object_pairs_hook=_unique_object)
        except (ValueError, TypeError):
            response_errors.append("malformed_json")
            response = None
    if response is None:
        response_errors.append("missing_response")
        response = {}
    if not isinstance(response, dict):
        response_errors.append("response_not_object")
        response = {}
    if set(response) != {"case_id", "answers"}:
        response_errors.append("invalid_response_fields")
    if response.get("case_id") != case["case_id"]:
        response_errors.append("wrong_case_id")
    answers = response.get("answers")
    if not isinstance(answers, list):
        response_errors.append("answers_not_list")
        answers = []
    by_id = defaultdict(list)
    for answer in answers:
        if not isinstance(answer, dict):
            response_errors.append("answer_not_object")
        elif not isinstance(answer.get("claim_id"), str) or answer["claim_id"] not in ids:
            response_errors.append("unknown_claim_id")
        else:
            by_id[answer["claim_id"]].append(answer)

    scored = []
    for claim_id in ids:
        schema_errors = list(response_errors)
        citation_errors = []
        matching = by_id[claim_id]
        answer = matching[0] if len(matching) == 1 else {}
        if not matching:
            schema_errors.append("missing_claim")
        elif len(matching) > 1:
            schema_errors.append("duplicate_claim")
        if answer:
            if set(answer) != {"claim_id", "status", "evidence_ids", "reason"}:
                schema_errors.append("invalid_answer_fields")
            if not isinstance(answer.get("status"), str) or answer["status"] not in STATUSES:
                schema_errors.append("invalid_status")
            if not isinstance(answer.get("reason"), str) or not answer["reason"].strip():
                schema_errors.append("invalid_reason")
            elif len(answer["reason"]) > MAX_REASON_CHARS:
                schema_errors.append("invalid_reason_length")
            citations = answer.get("evidence_ids")
            if not isinstance(citations, list) or not all(isinstance(i, str) for i in citations):
                schema_errors.append("invalid_evidence_ids")
                citation_errors.append("invalid_evidence_ids")
            else:
                citation_errors.extend(f"unknown_evidence_id:{i}" for i in citations
                                       if i not in evidence_ids)
        status = answer.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            status = None
        schema_valid = not schema_errors
        scored.append({
            "claim_id": claim_id,
            "gold_status": labels[claim_id],
            "status": status,
            "schema_valid": schema_valid,
            "citation_valid": not citation_errors,
            "schema_errors": sorted(set(schema_errors)),
            "citation_errors": sorted(set(citation_errors)),
            "status_correct": schema_valid and status == labels[claim_id],
        })

    unresolved = [claim for claim in scored if claim["gold_status"] == "unresolved"]
    answerable = [claim for claim in scored if claim["gold_status"] != "unresolved"]
    def certainty(claim: dict) -> bool:
        return claim["schema_valid"] and claim["status"] in {"established", "ruled_out"}

    def invalid(claim: dict) -> bool:
        return not claim["schema_valid"] or not claim["citation_valid"]
    metrics = {
        "unjustified_certainty": _metric(sum(certainty(c) for c in unresolved), len(unresolved)),
        "warranted_answer_accuracy": _metric(sum(c["status_correct"] for c in answerable),
                                             len(answerable)),
        "three_class_accuracy": _metric(sum(c["status_correct"] for c in scored), len(scored)),
        "correct_unresolved": _metric(sum(c["status_correct"] and not invalid(c)
                                          for c in unresolved), len(unresolved)),
        "invalid_missing_answer_rate": _metric(sum(not c["schema_valid"] for c in scored),
                                                len(scored)),
        "evidence_citation_error_rate": _metric(sum(not c["citation_valid"] for c in scored),
                                                len(scored)),
        "unjustified_certainty_or_invalid": _metric(
            sum(certainty(c) or invalid(c) for c in unresolved), len(unresolved)),
    }
    return {
        "case_id": case["case_id"],
        "subset": case["subset"],
        "split": case.get("split", "evaluation"),
        "cluster_id": case["cluster_id"],
        "claims": scored,
        "metrics": metrics,
        "response_errors": sorted(set(response_errors)),
        "claim_count": len(scored),
        "answerable_claim_count": len(answerable),
        "unresolved_claim_count": len(unresolved),
    }


def _stable_seed(seed: int, *parts: str) -> int:
    payload = json.dumps([seed, *parts], separators=(",", ":"))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def _quantile(ordered: list[float], probability: float) -> float:
    position = (len(ordered) - 1) * probability
    low = int(position)
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[min(low + 1, len(ordered) - 1)] * fraction


def _bootstrap(values: list[tuple[str, float]], *, seed: int, resamples: int) -> dict:
    """Case-weighted mean; resample whole histories, retaining each case inside."""
    clusters = defaultdict(list)
    for cluster_id, value in values:
        clusters[cluster_id].append(value)
    keys = sorted(clusters)
    result = {
        "mean": mean(value for _, value in values) if values else None,
        "ci_low": None,
        "ci_high": None,
        "n_cases": len(values),
        "n_clusters": len(keys),
    }
    if len(keys) < 2:
        return result
    rng = random.Random(seed)
    samples = sorted(mean(value for key in rng.choices(keys, k=len(keys))
                          for value in clusters[key]) for _ in range(resamples))
    result["ci_low"] = _quantile(samples, 0.025)
    result["ci_high"] = _quantile(samples, 0.975)
    return result


def summarize_scores(rows: list[dict], *, bootstrap_seed: int = 73021,
                     resamples: int = 2000) -> dict:
    """Summarize score_response rows augmented with model_id and arm A/B/C.

    Missing attempts must be supplied as score_response(..., None); an absent
    row cannot be silently imputed without its gold. Unmatched row IDs are
    explicitly listed. No model, subset, arm, claim, or retry is an extra case.
    """
    if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples <= 0:
        raise ValueError("resamples must be a positive integer")
    grouped = defaultdict(list)
    observed = set()
    metadata = {}
    for row in rows:
        key = (row["model_id"], row["subset"], row["arm"], row["case_id"])
        if row["arm"] not in {"A", "B", "C"} or row["subset"] not in {"wiki", "synthetic"}:
            raise ValueError("unknown arm or subset")
        if key in observed:
            raise ValueError("duplicate case/model/arm score; retries are not observations")
        observed.add(key)
        case_key = (row["subset"], row["case_id"])
        case_metadata = (
            row["cluster_id"],
            tuple((m, row["metrics"][m]["denominator"]) for m in METRICS),
            tuple((claim["claim_id"], claim["gold_status"]) for claim in row["claims"]),
        )
        if case_key in metadata and metadata[case_key] != case_metadata:
            raise ValueError("case clusters and frozen denominators must match across arms/models")
        metadata[case_key] = case_metadata
        grouped[key[:3]].append(row)
    groups = []
    for (model_id, subset, arm), group in sorted(grouped.items()):
        group = sorted(group, key=lambda row: row["case_id"])
        metrics = {}
        for metric in METRICS:
            values = [(row["cluster_id"], row["metrics"][metric]["value"]) for row in group
                      if row["metrics"][metric]["value"] is not None]
            metrics[metric] = _bootstrap(
                values, seed=_stable_seed(bootstrap_seed, model_id, subset, arm, metric),
                resamples=resamples,
            )
            metrics[metric]["numerator"] = sum(row["metrics"][metric]["numerator"] for row in group)
            metrics[metric]["denominator"] = sum(row["metrics"][metric]["denominator"]
                                                   for row in group)
        groups.append({"model_id": model_id, "subset": subset, "arm": arm,
                       "case_count": len(group), "metrics": metrics})
    paired = []
    for model_id, subset in sorted({key[:2] for key in grouped}):
        for treatment, control in COMPARISONS:
            left = {r["case_id"]: r for r in grouped.get((model_id, subset, treatment), [])}
            right = {r["case_id"]: r for r in grouped.get((model_id, subset, control), [])}
            common = sorted(set(left) & set(right))
            metrics = {}
            for metric in METRICS:
                values = []
                for case_id in common:
                    lhs, rhs = left[case_id], right[case_id]
                    lv, rv = lhs["metrics"][metric]["value"], rhs["metrics"][metric]["value"]
                    if lv is not None and rv is not None:
                        values.append((lhs["cluster_id"], lv - rv))
                metrics[metric] = _bootstrap(
                    values, seed=_stable_seed(bootstrap_seed, model_id, subset,
                                             f"{treatment}-{control}", metric),
                    resamples=resamples,
                )
            paired.append({
                "model_id": model_id, "subset": subset,
                "comparison": f"{treatment}-{control}",
                "primary": (treatment, control) == ("C", "B"),
                "paired_case_count": len(common),
                "missing_treatment_case_ids": sorted(set(right) - set(left)),
                "missing_control_case_ids": sorted(set(left) - set(right)),
                "metrics": metrics,
            })
    return {
        "bootstrap_seed": bootstrap_seed, "resamples": resamples,
        "analysis_unit": "case; whole page/history clusters resampled together",
        "groups": groups, "paired": paired,
        "case_counts": {subset: len({r["case_id"] for r in rows if r["subset"] == subset})
                        for subset in ("wiki", "synthetic")},
    }


def constant_response(case: dict, status: str) -> dict:
    """Analytic sanity baseline, never an API response or an investigator result."""
    if status not in STATUSES:
        raise ValueError("unsupported constant status")
    return {"case_id": case["case_id"], "answers": [
        {"claim_id": claim["id"], "status": status, "evidence_ids": [],
         "reason": "Constant-answer sanity baseline; no model call."}
        for claim in case["claims"]
    ]}


def sanity_scores(cases: list[dict], golds: list[dict]) -> list[dict]:
    """Return baseline-tagged case scores, not rows for model summarize_scores."""
    gold_by_id = {gold["case_id"]: gold for gold in golds}
    if len(gold_by_id) != len(golds) or set(gold_by_id) != {case["case_id"] for case in cases}:
        raise ValueError("sanity baseline cases and gold must match exactly")
    return [{**score_response(case, gold_by_id[case["case_id"]], constant_response(case, status)),
             "baseline": f"always_{status}"}
            for status in STATUSES for case in sorted(cases, key=lambda c: c["case_id"])]


def select_examples(rows: list[dict]) -> list[dict]:
    """Frozen C/B selection: SHA(case_id), after eligibility; no favorable cherry-picking.

    An improvement needs lower certainty or higher warranted accuracy, with no
    deterioration in either and no increase in schema/citation error. The other
    example is any C/B status/schema/citation disagreement not meeting that rule.
    Select separately for each model and subset; explicitly record absence.
    """
    indexed = {(row["model_id"], row["subset"], row["case_id"], row["arm"]): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("duplicate score row")
    result = []
    for model, subset in sorted({key[:2] for key in indexed}):
        eligible = {"improvement": [], "unsuccessful_or_disagreeing": []}
        case_ids = {key[2] for key in indexed if key[:2] == (model, subset)}
        for case_id in case_ids:
            control = indexed.get((model, subset, case_id, "B"))
            treatment = indexed.get((model, subset, case_id, "C"))
            if control is None or treatment is None:
                continue
            differences = {}
            for metric in METRICS:
                cv = treatment["metrics"][metric]["value"]
                bv = control["metrics"][metric]["value"]
                differences[metric] = cv - bv if cv is not None and bv is not None else None
            uc, wa = (differences[m] for m in ("unjustified_certainty", "warranted_answer_accuracy"))
            no_primary_loss = (uc is None or uc <= 0) and (wa is None or wa >= 0)
            no_failure_gain = all(differences[m] <= 0 for m in
                                  ("invalid_missing_answer_rate", "evidence_citation_error_rate"))
            improvement = (no_primary_loss and no_failure_gain
                           and ((uc is not None and uc < 0) or (wa is not None and wa > 0)))
            def signature(row: dict) -> list:
                return [(c["claim_id"], c["status"], c["schema_valid"], c["citation_valid"])
                        for c in row["claims"]]
            category = "improvement" if improvement else "unsuccessful_or_disagreeing"
            if improvement or signature(control) != signature(treatment):
                eligible[category].append({"case_id": case_id, "differences": differences})
        for category, candidates in eligible.items():
            chosen = min(candidates, key=lambda c: (hashlib.sha256(c["case_id"].encode()).hexdigest(),
                                                   c["case_id"]), default=None)
            result.append({"model_id": model, "subset": subset, "category": category,
                           "selection": chosen,
                           "absence": None if chosen else "No qualifying paired case exists."})
    return result
