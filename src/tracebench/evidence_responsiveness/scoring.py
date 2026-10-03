"""Frozen, mechanical triplet scoring; no answer repair or rationale grading.

The unchanged utility scorer validates the one-claim response contract. Evidence
ID existence and nonempty support are reported separately from status accuracy.
Bootstrap units are whole families, grouped by shared source-history clusters.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from tracebench.investigator_utility.scoring import (
    STATUSES,
    _bootstrap,
    _stable_seed,
    constant_response,
    score_response,
)

from .common import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, ROLES

SUBSETS = {"receipt": "synthetic", "wiki_derived": "wiki"}
PRIMARY_METRICS = (
    "decisive_pair_correct", "invariant_pair_correct", "whole_family_correct",
)
FAMILY_METRICS = (
    *PRIMARY_METRICS,
    *(f"strict_{metric}" for metric in PRIMARY_METRICS),
    "incorrect_stability_decisive", "incorrect_change_irrelevant",
)
VARIANT_DIAGNOSTICS = (
    "invalid", "missing", "refused", "truncated", "citation_error", "nonempty_valid_support",
)


def score_variant(case: dict, gold: dict, completion: dict | str | None, model_id: str,
                  finish_reason: str | None = None, *, refused: bool = False) -> dict:
    """Score one exact completion, retaining invalid/refused outputs as failures.

Subset remapping is private compatibility data for the unchanged utility scorer;
the returned row retains this study's receipt/wiki-derived substrate identity.
Refusal metadata is provider supplied, never inferred by a semantic grader.
"""
    if case.get("subset") not in SUBSETS:
        raise ValueError("unknown responsiveness subset")
    if [claim["id"] for claim in case["claims"]] != ["q0"]:
        raise ValueError("responsiveness cases must have exactly the primary claim q0")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("model_id must be a nonempty string")
    scored = score_response({**case, "subset": SUBSETS[case["subset"]]}, gold, completion)
    claim = scored["claims"][0]
    refused = bool(refused or finish_reason in {"content_filter", "refusal"})
    truncated = finish_reason in {"length", "max_tokens"}
    # Parsing here only extracts IDs from a response already accepted by the
    # unchanged strict parser, including its duplicate-JSON-key prohibition.
    citations = []
    if claim["schema_valid"]:
        parsed = json.loads(completion) if isinstance(completion, str) else completion
        citations = parsed["answers"][0]["evidence_ids"]
    known_ids = {item["id"] for item in case["records"] + case.get("assumptions", [])}
    valid_ids = sorted(set(citations) & known_ids)
    support = bool(valid_ids) and claim["citation_valid"] and claim["schema_valid"]
    completion_valid = claim["schema_valid"] and not refused and not truncated
    correct = claim["status_correct"] and completion_valid
    return {
        "case_id": case["case_id"], "model_id": model_id, "subset": case["subset"],
        "split": case.get("split", "evaluation"), "cluster_id": case["cluster_id"],
        "gold_status": claim["gold_status"], "status": claim["status"],
        "schema_valid": claim["schema_valid"], "citation_valid": claim["citation_valid"],
        "completion_valid": completion_valid,
        "status_correct": correct, "strict_correct": correct and support,
        "nonempty_valid_support": support, "valid_evidence_ids": valid_ids,
        "schema_errors": claim["schema_errors"], "citation_errors": claim["citation_errors"],
        "response_errors": scored["response_errors"], "finish_reason": finish_reason,
        "invalid": not claim["schema_valid"],
        "missing": completion is None or completion == "", "refused": refused,
        "truncated": truncated,
        "citation_error": not claim["citation_valid"],
    }


def _missing_variant(case_id: str) -> dict:
    """A missing score row is an explicit failure, never denominator deletion."""
    return {
        "case_id": case_id, "gold_status": None, "status": None,
        "schema_valid": False, "citation_valid": True, "status_correct": False,
        "completion_valid": False,
        "strict_correct": False, "nonempty_valid_support": False,
        "valid_evidence_ids": [], "schema_errors": ["missing_score_row"],
        "citation_errors": [], "response_errors": ["missing_score_row"],
        "finish_reason": None, "invalid": True, "missing": True, "refused": False,
        "truncated": False,
        "citation_error": False,
    }


def score_families(rows: list[dict], families: list[dict], *,
                   model_ids: list[str] | None = None) -> list[dict]:
    """Pair frozen mappings; every family remains in every declared model's N.

Pass the frozen model IDs even when an entire model produced no score rows.
Otherwise models are inferred from rows. Missing completions should normally be
scored with ``score_variant(..., None)`` so their gold labels remain visible.
"""
    models = sorted(set(model_ids) if model_ids is not None
                    else {row["model_id"] for row in rows})
    if not models and families:
        raise ValueError("model_ids required when no score rows exist")
    if any(not isinstance(model, str) or not model for model in models):
        raise ValueError("model IDs must be nonempty strings")
    family_ids = set()
    case_metadata = {}
    for family in families:
        if family["family_id"] in family_ids:
            raise ValueError("duplicate family ID")
        family_ids.add(family["family_id"])
        if family["subset"] not in SUBSETS or set(family["variants"]) != set(ROLES):
            raise ValueError("unknown family subset or invalid triplet roles")
        for case_id in family["variants"].values():
            if case_id in case_metadata:
                raise ValueError("case may belong to exactly one family/variant")
            case_metadata[case_id] = (
                family["subset"], family.get("split", "evaluation"), family["cluster_id"],
            )
    indexed = {}
    gold_by_case = {}
    for row in rows:
        key = (row["model_id"], row["case_id"])
        if key in indexed:
            raise ValueError("duplicate model/case score; retries are not observations")
        if row["model_id"] not in models or row["case_id"] not in case_metadata:
            raise ValueError("score row not in frozen model/family universe")
        if (row["subset"], row["split"], row["cluster_id"]) != case_metadata[row["case_id"]]:
            raise ValueError("score row disagrees with frozen family metadata")
        if row["case_id"] in gold_by_case and gold_by_case[row["case_id"]] != row["gold_status"]:
            raise ValueError("gold status changed across models")
        gold_by_case[row["case_id"]] = row["gold_status"]
        indexed[key] = row
    output = []
    for model in models:
        for family in sorted(families, key=lambda item: item["family_id"]):
            variants = {
                role: indexed.get((model, case_id), _missing_variant(case_id))
                for role, case_id in family["variants"].items()
            }
            base, irrelevant, decisive = (variants[role] for role in ROLES)
            gold = {role: gold_by_case.get(row["case_id"]) for role, row in variants.items()}
            if gold["base"] is not None and gold["irrelevant"] is not None:
                if gold["base"] != gold["irrelevant"]:
                    raise ValueError("invariant pair has different gold statuses")
            if gold["base"] is not None and gold["decisive"] is not None:
                if gold["base"] == gold["decisive"]:
                    raise ValueError("decisive pair has identical gold statuses")
            observed_decisive = all(v["completion_valid"]
                                    for v in (base, decisive))
            observed_invariant = all(v["completion_valid"]
                                     for v in (base, irrelevant))
            metrics = {}
            for prefix, field in (("", "status_correct"), ("strict_", "strict_correct")):
                metrics[f"{prefix}decisive_pair_correct"] = base[field] and decisive[field]
                metrics[f"{prefix}invariant_pair_correct"] = base[field] and irrelevant[field]
                metrics[f"{prefix}whole_family_correct"] = all(v[field] for v in variants.values())
            metrics["incorrect_stability_decisive"] = bool(
                observed_decisive and base["status"] == decisive["status"])
            metrics["incorrect_change_irrelevant"] = bool(
                observed_invariant and base["status"] != irrelevant["status"])
            output.append({
                "model_id": model, "family_id": family["family_id"],
                "subset": family["subset"], "split": family.get("split", "evaluation"),
                "cluster_id": family["cluster_id"], "motif": family.get("motif"),
                "variants": variants, "metrics": metrics,
                "observed_decisive_pair": observed_decisive,
                "observed_invariant_pair": observed_invariant,
                "missing_score_rows": [role for role, row in variants.items()
                                       if "missing_score_row" in row["schema_errors"]],
            })
    return output


def _interval(values: list[tuple[str, float]], seed: int, resamples: int) -> dict:
    interval = _bootstrap(values, seed=seed, resamples=resamples)
    interval["n_families"] = interval.pop("n_cases")
    interval["numerator"] = sum(value for _, value in values)
    interval["denominator"] = len(values)
    return interval


def summarize(familyrows: list[dict], seed: int = BOOTSTRAP_SEED,
              resamples: int = BOOTSTRAP_RESAMPLES) -> dict:
    """Family-weighted estimates with whole-history bootstrap triplets intact."""
    if not isinstance(resamples, int) or isinstance(resamples, bool) or resamples <= 0:
        raise ValueError("resamples must be a positive integer")
    grouped = defaultdict(list)
    seen = set()
    for row in familyrows:
        key = (row["model_id"], row["subset"], row["split"], row["family_id"])
        if key in seen:
            raise ValueError("duplicate model/family row")
        seen.add(key)
        if row["subset"] not in SUBSETS:
            raise ValueError("unknown responsiveness subset")
        grouped[key[:3]].append(row)
    groups = []
    for key, group in sorted(grouped.items()):
        group = sorted(group, key=lambda row: row["family_id"])
        conditional = {
            "incorrect_stability_decisive": "observed_decisive_pair",
            "incorrect_change_irrelevant": "observed_invariant_pair",
        }
        metrics = {}
        for metric in FAMILY_METRICS:
            eligible = [row for row in group if metric not in conditional or row[conditional[metric]]]
            metrics[metric] = _interval(
                [(row["cluster_id"], int(row["metrics"][metric])) for row in eligible],
                _stable_seed(seed, *key, metric), resamples,
            )
            metrics[metric]["eligibility"] = (
                "both pair responses schema-valid, non-refused, and non-truncated"
                if metric in conditional else "all frozen families"
            )
        per_variant = {}
        for role in ROLES:
            role_metrics = {}
            for field in ("status_correct", "strict_correct", *VARIANT_DIAGNOSTICS):
                role_metrics[field] = _interval(
                    [(row["cluster_id"], int(row["variants"][role][field])) for row in group],
                    _stable_seed(seed, *key, role, field), resamples,
                )
            per_variant[role] = role_metrics
        diagnostics = {
            field: {"numerator": sum(row["variants"][role][field]
                                     for row in group for role in ROLES),
                    "denominator": 3 * len(group)}
            for field in VARIANT_DIAGNOSTICS
        }
        for metric in diagnostics.values():
            metric["value"] = metric["numerator"] / metric["denominator"]
        groups.append({
            "model_id": key[0], "subset": key[1], "split": key[2],
            "n_families": len(group), "n_clusters": len({r["cluster_id"] for r in group}),
            "n_variants": 3 * len(group), "metrics": metrics, "per_variant": per_variant,
            "diagnostics": diagnostics,
            "observed_decisive_pairs": sum(r["observed_decisive_pair"] for r in group),
            "observed_invariant_pairs": sum(r["observed_invariant_pair"] for r in group),
        })
    return {
        "bootstrap_seed": seed, "bootstrap_resamples": resamples,
        "unit": "family; shared source histories form bootstrap clusters",
        "estimand": "family-weighted mean; all frozen families retain their denominators",
        "confidence_interval": "descriptive 95% percentile cluster bootstrap",
        "support_check": "at least one valid supplied ID and no nonexistent IDs; not entailment",
        "groups": groups,
    }


def constant_baselines(cases: list[dict], golds: list[dict], families: list[dict]) -> dict:
    """Three analytic constant answers; no model calls and no fabricated support."""
    indexed_cases = {case["case_id"]: case for case in cases}
    indexed_gold = {gold["case_id"]: gold for gold in golds}
    if (len(indexed_cases) != len(cases) or len(indexed_gold) != len(golds)
            or set(indexed_cases) != set(indexed_gold)):
        raise ValueError("constant baseline cases and gold must be distinct and match exactly")
    universe = {case_id for family in families for case_id in family["variants"].values()}
    if set(indexed_cases) != universe:
        raise ValueError("constant baseline cases must cover the complete family universe")
    rows = [score_variant(case, indexed_gold[case_id], constant_response(case, status),
                          f"always_{status}")
            for status in STATUSES for case_id, case in sorted(indexed_cases.items())]
    family_rows = score_families(rows, families)
    return {"variant_rows": rows, "family_rows": family_rows, "summary": summarize(family_rows)}


def select_examples(familyrows: list[dict]) -> list[dict]:
    """First failed pair by SHA256(base case ID); explicit absence on all-pass."""
    grouped = defaultdict(list)
    seen = set()
    for row in familyrows:
        identity = (row["model_id"], row["subset"], row["split"], row["family_id"])
        if identity in seen:
            raise ValueError("duplicate model/family row")
        seen.add(identity)
        grouped[identity[:3]].append(row)
    examples = []
    for key, group in sorted(grouped.items()):
        for pair in ("decisive", "invariant"):
            failed = [row for row in group if not row["metrics"][f"{pair}_pair_correct"]]
            chosen = min(failed, key=lambda row: (
                hashlib.sha256(row["variants"]["base"]["case_id"].encode()).hexdigest(),
                row["family_id"],
            ), default=None)
            examples.append({
                "model_id": key[0], "subset": key[1], "split": key[2],
                "category": f"first_failed_{pair}_pair",
                "selection": chosen,
                "absence": None if chosen else f"No failed {pair} pair was observed.",
            })
    return examples
