"""Reproducible experiment runner. No network access or model API is required."""

import argparse
import csv
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .estimators import METHODS, estimate
from .evaluate import METRICS, score_edges, summarize
from .model import SimulationConfig
from .observe import Telemetry, observe
from .simulate import observational_equivalence_pair, simulate


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _probabilities(value: str) -> list[float]:
    try:
        numbers = [float(v) for v in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated probabilities") from error
    if not numbers or any(not 0 <= v <= 1 for v in numbers) or len(set(numbers)) != len(numbers):
        raise argparse.ArgumentTypeError("use distinct finite probabilities between 0 and 1")
    return numbers


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _source_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_benchmark(args: argparse.Namespace) -> None:
    from .reporting import write_figure, write_report

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    expected = ("benchmark.json", "runs.csv", "summary.csv", "REPORT.md",
                "trace_completeness.png", "trace_completeness.svg", "manifest.json")
    if not args.overwrite and any((output / name).exists() for name in expected):
        raise ValueError("Output artifacts already exist; choose another directory or --overwrite")
    rows = []
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
    for probability in args.transmission:
        for shock in args.shocks:
            for seed in seeds:
                config = SimulationConfig(
                    seed=seed, n_runs=args.runs, writes_per_run=args.writes_per_run,
                    transmission_probability=probability, shock_strength=shock,
                )
                world = simulate(config)
                for regime in Telemetry:
                    observation = observe(world, regime)
                    for method in METHODS:
                        predictions = estimate(observation, method)
                        row = {"seed": seed, "transmission_probability": probability,
                               "shock_strength": shock, "regime": regime.value, "method": method}
                        row.update(score_edges(predictions, world.truth_edges,
                                               world.eligible_target_ids))
                        rows.append(row)
            print(f"Evaluated p={probability:g}, shock={shock:g}, {len(seeds)} seeds", flush=True)
    summaries = summarize(rows, args.bootstrap_samples)
    result = {
        "schema_version": 1,
        "metadata": {
            "title": "Trace Completeness Curves", "study_type": "synthetic",
            "n_worlds": len(seeds) * len(args.transmission) * len(args.shocks),
            "seeds": seeds, "n_runs": args.runs, "writes_per_run": args.writes_per_run,
            "transmission_probabilities": args.transmission, "shock_strengths": args.shocks,
            "bootstrap_samples": args.bootstrap_samples,
            "ci_method": "95% percentile bootstrap over independent world seeds; undefined excluded",
            "package_version": __version__, "python_version": platform.python_version(),
            "source_sha256": _source_digest(), "default_generator_config": asdict(SimulationConfig()),
            "estimand": "realized cross-run source-use target fraction over all generated writes",
            "caution": "Exposure is not use; source use is not counterfactual necessity.",
        },
        "summary": summaries, "runs": rows,
    }
    _write_json(output / "benchmark.json", result)
    _write_csv(output / "runs.csv", rows)
    flat = []
    for summary in summaries:
        item = {key: value for key, value in summary.items() if key != "metrics"}
        for metric in METRICS:
            for statistic, value in summary["metrics"][metric].items():
                item[f"{metric}_{statistic}"] = value
        flat.append(item)
    _write_csv(output / "summary.csv", flat)
    write_figure(result, output)
    write_report(result, output)
    _write_json(output / "manifest.json", {
        "algorithm": "sha256", "source_sha256": result["metadata"]["source_sha256"],
        "files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                  for name in expected if name != "manifest.json"},
    })
    print(f"Wrote {len(rows)} evaluations from {result['metadata']['n_worlds']} worlds to {output}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    benchmark = commands.add_parser("benchmark", help="Run the synthetic telemetry-ablation study")
    benchmark.add_argument("--output", type=Path, default=Path("artifacts/benchmark"))
    benchmark.add_argument("--seeds", type=_positive, default=12)
    benchmark.add_argument("--seed-start", type=int, default=0)
    benchmark.add_argument("--runs", type=_positive, default=120)
    benchmark.add_argument("--writes-per-run", type=_positive, default=3)
    benchmark.add_argument("--transmission", type=_probabilities, default=[0.0, 0.1, 0.3, 0.5])
    benchmark.add_argument("--shocks", type=_probabilities, default=[0.0, 0.5, 0.9])
    benchmark.add_argument("--bootstrap-samples", type=_positive, default=2000)
    benchmark.add_argument("--overwrite", action="store_true", help="Replace prior generated artifacts")
    commands.add_parser("equivalence", help="Verify equal observations with different source-use truth")
    args = parser.parse_args(argv)
    if args.command == "equivalence":
        left, right = observational_equivalence_pair()
        equality = {regime.value: observe(left, regime) == observe(right, regime)
                    for regime in Telemetry}
        if not all(equality.values()) or left.truth_edges == right.truth_edges:
            parser.error("Observational equivalence check failed")
        print(json.dumps({"observations_equal": equality,
                          "world_a_truth_edges": sorted(left.truth_edges),
                          "world_b_truth_edges": sorted(right.truth_edges),
                          "conclusion": "Even channel context provenance need not identify source use."},
                         indent=2))
        return
    if args.bootstrap_samples < 100:
        parser.error("--bootstrap-samples must be at least 100")
    try:
        run_benchmark(args)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
