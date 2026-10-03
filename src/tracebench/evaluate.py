"""Score observed candidate edges against synthetic truth, outside inference."""

import hashlib
import random
from collections import defaultdict
from statistics import fmean

from .model import Edge

METRICS = (
    "precision", "recall", "f1", "theta", "theta_hat", "absolute_error",
    "false_attributed_target_fraction", "false_positive_edges_per_target",
)


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
        "false_attributed_target_fraction": len(predicted_targets - true_targets) / len(eligible),
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


def summarize(rows: list[dict], bootstrap_samples: int = 2000) -> list[dict]:
    groups = defaultdict(list)
    keys = ("transmission_probability", "shock_strength", "regime", "method")
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    result = []
    for group, members in sorted(groups.items()):
        if len({row["seed"] for row in members}) != len(members):
            raise ValueError("Each group requires independent, distinct simulation seeds")
        metrics = {}
        for metric in METRICS:
            # Share resampling indices across methods/regimes of the same scenario.
            # Identical per-seed values then receive identical interval endpoints.
            digest = hashlib.sha256(repr((group[:2], metric)).encode()).digest()
            metrics[metric] = bootstrap_mean(
                [row[metric] for row in members], seed=int.from_bytes(digest[:8], "big"),
                samples=bootstrap_samples,
            )
        result.append(dict(zip(keys, group)) | {"n_seeds": len(members), "metrics": metrics})
    return result
