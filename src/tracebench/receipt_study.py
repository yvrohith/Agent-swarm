"""Bounded observation-only receipt-loss experiment, separate from the baseline."""

import csv
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .corruption import PROFILES, corrupt
from .estimators import METHODS
from .evaluate import METRICS, paired_differences, score_edges, summarize
from .model import SimulationConfig
from .observe import Telemetry, observe
from .policies import POLICIES, infer
from .simulate import simulate

GROUP_KEYS = (
    "transmission_probability", "shock_strength", "regime", "method",
    "profile", "retention", "policy",
)
PAIR_KEYS = tuple(key for key in GROUP_KEYS if key != "policy")
STUDY_METRICS = tuple(dict.fromkeys((*METRICS,
    "true_positive_edges", "false_positive_edges", "false_negative_edges",
    "unresolved_edges", "unresolved_targets", "unresolved_target_fraction",
    "unresolved_edges_per_target", "unresolved_candidate_fraction",
    "request_record_retention", "delivery_record_retention", "context_record_retention",
)))
PAIRED_METRICS = tuple(metric for metric in STUDY_METRICS if not metric.endswith("record_retention"))


def _json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _digest(value) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def validate_config(config: dict) -> None:
    """Validate a supplied protocol; no hidden simulator parameters can be overridden."""
    required = {
        "study_id", "study_type", "reviewed_baseline_commit", "world_seeds", "n_runs",
        "writes_per_run", "transmission_probabilities", "shock_strengths", "retentions",
        "profiles", "methods", "policies", "mask_seed_base", "bootstrap_samples",
        "regime", "policy_assumptions", "freeze",
    }
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Configuration must contain exactly the documented receipt-study fields")
    if config["study_type"] != "follow-up stress test informed by review; not preregistered":
        raise ValueError("The study must be labeled as a follow-up stress test")
    if config["regime"] != "context":
        raise ValueError("The missing-receipt study keeps all five telemetry types available")
    seeds = config["world_seeds"]
    if not isinstance(seeds, list) or not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError("world_seeds must be a nonempty list of integer seeds")
    if len(seeds) != len(set(seeds)):
        raise ValueError("world_seeds must be distinct; masks are not independent worlds")
    if type(config["mask_seed_base"]) is not int:
        raise ValueError("mask_seed_base must be an integer")
    for key in ("n_runs", "writes_per_run", "bootstrap_samples"):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if config["bootstrap_samples"] < 100:
        raise ValueError("At least 100 bootstrap resamples are required")
    for key in ("transmission_probabilities", "shock_strengths", "retentions"):
        values = config[key]
        if (not isinstance(values, list) or not values
                or any(type(v) not in (int, float) or not 0 <= v <= 1 for v in values)
                or len(values) != len(set(values))):
            raise ValueError(f"{key} must contain distinct finite probabilities")
    if len(config["shock_strengths"]) != 1:
        raise ValueError("This bounded receipt study reports one fixed shock strength")
    for key, supported in (("profiles", PROFILES), ("methods", METHODS), ("policies", POLICIES)):
        if not isinstance(config[key], list) or set(config[key]) != set(supported):
            raise ValueError(f"{key} must include each supported value exactly once")
        if len(config[key]) != len(supported):
            raise ValueError(f"{key} must not contain duplicate values")


def evaluate_study(config: dict) -> dict:
    validate_config(config)
    rows, worlds, retention_rows = [], [], []
    for probability in config["transmission_probabilities"]:
        for shock in config["shock_strengths"]:
            for seed in config["world_seeds"]:
                # Generate once. Receipt loss never changes generation probabilities.
                world_config = SimulationConfig(
                    seed=seed, n_runs=config["n_runs"], writes_per_run=config["writes_per_run"],
                    transmission_probability=probability, shock_strength=shock,
                )
                world = simulate(world_config)
                full = observe(world, Telemetry.CONTEXT)
                mask_seed = config["mask_seed_base"] + seed
                world_id = _digest(asdict(world_config))
                truth_digest = _digest(sorted(world.truth_edges))
                worlds.append({
                    "world_id": world_id, "config": asdict(world_config), "mask_seed": mask_seed,
                    "truth_sha256": truth_digest,
                    "eligible_targets_sha256": _digest(sorted(world.eligible_target_ids)),
                    "writes_sha256": _digest([asdict(w) for w in world.writes]),
                    "true_edges": len(world.truth_edges), "eligible_targets": len(world.writes),
                })
                for profile in config["profiles"]:
                    for retention in config["retentions"]:
                        masked = corrupt(full, profile, retention, mask_seed)
                        observation_sha = _digest(asdict(masked))
                        audit = {
                            "seed": seed, "world_id": world_id, "mask_seed": mask_seed,
                            "transmission_probability": probability, "shock_strength": shock,
                            "regime": "context", "profile": profile, "retention": retention,
                            "observation_sha256": observation_sha,
                        }
                        for singular, plural in (("request", "requests"),
                                                 ("delivery", "deliveries"),
                                                 ("context", "contexts")):
                            original = len(getattr(full, plural))
                            retained = len(getattr(masked.observation, plural))
                            audit[f"{singular}_records_original"] = original
                            audit[f"{singular}_records_retained"] = retained
                            audit[f"{singular}_record_retention"] = retained / original if original else None
                        retention_rows.append(audit)
                        for method in config["methods"]:
                            for policy in config["policies"]:
                                # Both policies receive the very same object, not regenerated masks.
                                inference = infer(masked, method, policy)
                                row = audit | {"method": method, "policy": policy}
                                row.update(score_edges(inference.predictions, world.truth_edges,
                                                       world.eligible_target_ids))
                                unknown_targets = {target for _, target in inference.unresolved}
                                row.update({
                                    "candidate_edges": len(inference.candidates),
                                    "excluded_or_rejected_edges": len(inference.excluded),
                                    "unresolved_edges": len(inference.unresolved),
                                    "unresolved_targets": len(unknown_targets),
                                    "unresolved_target_fraction": len(unknown_targets) / len(world.writes),
                                    "unresolved_edges_per_target": len(inference.unresolved) / len(world.writes),
                                    "unresolved_candidate_fraction": (
                                        len(inference.unresolved) / len(inference.candidates)
                                        if inference.candidates else None
                                    ),
                                })
                                rows.append(row)
            print(f"Evaluated receipt loss: p={probability:g}, shock={shock:g}, "
                  f"{len(config['world_seeds'])} worlds", flush=True)
    paired = paired_differences(rows, group_keys=PAIR_KEYS, metric_names=PAIRED_METRICS)
    source_files = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(Path(__file__).parent.glob("*.py"))}
    return {
        "schema_version": 1,
        "metadata": {
            "study_type": config["study_type"], "config": config, "config_sha256": _digest(config),
            "n_worlds": len(worlds), "n_masked_observations": len(retention_rows),
            "n_evaluations": len(rows), "source_files_sha256": source_files,
            "python_version": platform.python_version(), "package_version": __version__,
            "pairing": "evidence_aware minus conjunction, matched seed and identical observation",
            "uncertainty": "95% percentile bootstrap of independent worlds within each group; "
                           "paired differences are formed before bootstrapping; null pairs excluded",
            "mask_seed_rule": "mask_seed_base + world_seed; reused across retention levels",
            "predictions": "heuristic source-attribution candidates supported by exposure, not verified use",
            "unresolved": "unknown exposure, excluded from scored predictions; target burden may "
                          "overlap targets with another supported candidate",
            "baseline_rejection": "conjunction rejects missing stages without an unknown category; "
                                  "its rejection is not a completeness-justified exclusion",
        },
        "worlds": worlds, "retention_audit": retention_rows, "runs": rows,
        "summary": summarize(rows, config["bootstrap_samples"],
                             group_keys=GROUP_KEYS, metric_names=STUDY_METRICS),
        "paired_runs": paired,
        "paired_summary": summarize(paired, config["bootstrap_samples"],
                                    group_keys=PAIR_KEYS, metric_names=PAIRED_METRICS),
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def run_study(config_path: Path, output: Path) -> dict:
    """Run a frozen protocol into a fresh directory; never overwrite baseline results."""
    from .receipt_reporting import write_receipt_figure, write_receipt_report

    output = output.resolve()
    baseline = Path(__file__).resolve().parents[2] / "results"
    if output == baseline or baseline in output.parents:
        raise ValueError("Follow-up output must remain outside the curated baseline results directory")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; choose a fresh follow-up directory")
    config = json.loads(config_path.read_text())
    result = evaluate_study(config)
    output.mkdir(parents=True, exist_ok=True)
    (output / "study.json").write_bytes(_json_bytes(result))
    (output / "config.json").write_bytes(_json_bytes(config))
    _write_csv(output / "runs.csv", result["runs"])
    _write_csv(output / "paired_runs.csv", result["paired_runs"])
    _write_csv(output / "retention.csv", result["retention_audit"])
    write_receipt_figure(result, output)
    write_receipt_report(result, output)
    manifest = {
        "algorithm": "sha256", "config_sha256": result["metadata"]["config_sha256"],
        "source_files_sha256": result["metadata"]["source_files_sha256"],
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(output.iterdir()) if p.is_file()},
    }
    (output / "manifest.json").write_bytes(_json_bytes(manifest))
    print(f"Wrote {len(result['runs'])} evaluations and {len(result['paired_runs'])} paired "
          f"contrasts from {len(result['worlds'])} worlds to {output}")
    return result
