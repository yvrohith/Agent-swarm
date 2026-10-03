"""Score observed candidate edges against synthetic truth, outside inference."""

import hashlib
import random
from collections import defaultdict
from statistics import fmean

from .model import Edge

METRICS = (
    "precision", "recall", "f1", "theta", "theta_hat", "absolute_error",
    "false_attributed_target_fraction", "false_positive_edges_per_target",
    "false_positive_targets", "false_negative_targets", "signed_error", "target_disagreement",
)
GROUP_KEYS = ("transmission_probability", "shock_strength", "regime", "method")
STUDY_DIMENSIONS = ("profile", "retention", "policy")


def score_edges(
    predictions: frozenset[Edge], truth: frozenset[Edge], eligible: frozenset[str]
) -> dict:
    """Use a fixed write-level denominator and event-level edge matching."""
    if not eligible:
        raise ValueError("The eligible target universe must not be empty")
    if any(target not in eligible for _, target in predictions | truth):
        raise ValueError("An edge target is outside the eligible universe")
    tp, fp, fn = len(predictions & truth), len(predictions - truth), len(truth - predictions)
    true_targets = {target for _, target in truth}
    predicted_targets = {target for _, target in predictions}
    false_positive_targets = len(predicted_targets - true_targets)
    false_negative_targets = len(true_targets - predicted_targets)
    theta = len(true_targets) / len(eligible)
    theta_hat = len(predicted_targets) / len(eligible)
    return {
        "true_positive_edges": tp, "false_positive_edges": fp, "false_negative_edges": fn,
        "predicted_edges": len(predictions), "true_edges": len(truth),
        "eligible_targets": len(eligible),
        "precision": tp / len(predictions) if predictions else None,
        "recall": tp / len(truth) if truth else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if predictions or truth else None,
        "theta": theta, "theta_hat": theta_hat, "absolute_error": abs(theta_hat - theta),
        "false_positive_targets": false_positive_targets,
        "false_negative_targets": false_negative_targets,
        "signed_error": theta_hat - theta,
        "target_disagreement": (false_positive_targets + false_negative_targets) / len(eligible),
        "false_attributed_target_fraction": false_positive_targets / len(eligible),
        "false_positive_edges_per_target": fp / len(eligible),
    }


def _quantile(values: list[float], fraction: float) -> float:
    index = (len(values) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


def bootstrap_mean(values: list[float | None], *, seed: int, samples: int) -> dict:
    """Percentile bootstrap across worlds; undefined metrics stay undefined."""
    if samples < 100:
        raise ValueError("Use at least 100 bootstrap resamples")
    defined = [value for value in values if value is not None]
    result = {"mean": fmean(defined) if defined else None,
              "ci_low": None, "ci_high": None, "n": len(defined)}
    if len(defined) < 2:
        return result
    rng = random.Random(seed)
    draws = sorted(fmean(rng.choices(defined, k=len(defined))) for _ in range(samples))
    result.update(ci_low=_quantile(draws, 0.025), ci_high=_quantile(draws, 0.975))
    return result


def _validate_group_keys(rows: list[dict], group_keys: tuple[str, ...]) -> None:
    if len(set(group_keys)) != len(group_keys):
        raise ValueError("Grouping dimensions must be distinct")
    if {"seed", "mask_seed"} & set(group_keys):
        raise ValueError("Seeds identify worlds and masks, not summary groups")
    omitted = [key for key in STUDY_DIMENSIONS
               if key not in group_keys and any(key in row for row in rows)]
    if omitted:
        raise ValueError(f"Include all study dimensions in group_keys: {', '.join(omitted)}")


def summarize(
    rows: list[dict], bootstrap_samples: int = 2000, *,
    group_keys: tuple[str, ...] = GROUP_KEYS, metric_names: tuple[str, ...] = METRICS,
) -> list[dict]:
    """Summarize distinct worlds without pooling logging profiles or policies.

    Additional masks of a world are not additional independent worlds. Callers
    must first choose a single mask or explicitly aggregate within each world.
    """
    _validate_group_keys(rows, group_keys)
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
    result = []
    for group, members in sorted(groups.items()):
        if len({row["seed"] for row in members}) != len(members):
            raise ValueError("Each group requires independent, distinct simulation seeds")
        members.sort(key=lambda row: row["seed"])
        metrics = {}
        for metric in metric_names:
            # Share resampling indices across methods/regimes of the same scenario.
            # Identical per-seed values then receive identical interval endpoints.
            scenario = tuple(members[0].get(key) for key in GROUP_KEYS[:2])
            digest = hashlib.sha256(repr((scenario, metric)).encode()).digest()
            metrics[metric] = bootstrap_mean(
                [row[metric] for row in members], seed=int.from_bytes(digest[:8], "big"),
                samples=bootstrap_samples,
            )
        result.append(dict(zip(group_keys, group)) | {"n_seeds": len(members), "metrics": metrics})
    return result


def paired_differences(
    rows: list[dict], *, group_keys: tuple[str, ...], metric_names: tuple[str, ...],
    reference_policy: str = "conjunction", comparison_policy: str = "evidence_aware",
) -> list[dict]:
    """Return per-world comparison minus reference for exactly matched observations.

    Grouping dimensions describe the scenario, logging profile, retention and
    investigator. Policy may be supplied in group_keys but is the paired axis.
    Undefined metrics remain undefined; bootstrap these returned worlds with
    ``summarize`` rather than subtracting independently computed intervals.
    """
    if reference_policy == comparison_policy:
        raise ValueError("Reference and comparison policies must differ")
    _validate_group_keys(rows, tuple(group_keys) + (() if "policy" in group_keys else ("policy",)))
    keys = tuple(key for key in group_keys if key != "policy")
    groups = defaultdict(dict)
    for row in rows:
        policy = row["policy"]
        if policy not in (reference_policy, comparison_policy):
            raise ValueError(f"Unexpected comparison policy: {policy}")
        group = tuple(row[key] for key in keys) + (row["seed"],)
        if policy in groups[group]:
            raise ValueError("Each paired group requires distinct simulation seeds per policy")
        groups[group][policy] = row
    result = []
    for group, members in sorted(groups.items()):
        if set(members) != {reference_policy, comparison_policy}:
            raise ValueError("Every world requires both comparison policies")
        reference, comparison = members[reference_policy], members[comparison_policy]
        shared = {}
        for field in ("mask_seed", "observation_sha256"):
            if field in reference or field in comparison:
                if field not in reference or field not in comparison or reference[field] != comparison[field]:
                    raise ValueError(f"Paired policies require identical {field}")
                shared[field] = reference[field]
        differences = {
            metric: (comparison[metric] - reference[metric]
                     if comparison[metric] is not None and reference[metric] is not None else None)
            for metric in metric_names
        }
        result.append(dict(zip(keys, group[:-1])) | {
            "seed": group[-1], "reference_policy": reference_policy,
            "comparison_policy": comparison_policy,
        } | shared | differences)
    return result
