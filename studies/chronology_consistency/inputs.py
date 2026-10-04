"""Recover fixed published inputs without generating or evaluating any worlds.

Historical pins remain evidence, including known aggregate-source drift.  This
module never writes artifacts; the execution controller owns exclusive writes.
"""

from __future__ import annotations

import ast
import copy
import csv
import hashlib
import itertools
import json
import subprocess
from dataclasses import fields
from pathlib import Path

from tracebench.model import SimulationConfig

BENCHMARK = "results/benchmark.json"
RECEIPTS = "studies/missing_receipts/results/study.json"
BASELINE_COMMIT = "36be8fa3682b294462ac65f8c2f750119e75cdb2"
WORLD_KEYS = ("seed", "transmission_probability", "shock_strength")
BASE_GROUP_KEYS = ("transmission_probability", "shock_strength", "regime", "method")
RECEIPT_GROUP_KEYS = BASE_GROUP_KEYS + ("profile", "retention", "policy")
REGIMES = ("writes", "identity", "requests", "delivery", "context")
METHODS = ("temporal", "witness")
SCIENTIFIC_SOURCE_NAMES = (
    "__init__.py", "model.py", "simulate.py", "observe.py", "estimators.py",
    "evaluate.py", "corruption.py", "policies.py", "receipt_study.py",
)


def json_bytes(value) -> bytes:
    """Match the saved receipt-study JSON digest convention exactly."""
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def digest(value) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_strict(path: Path):
    def reject(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(path.read_text(), object_pairs_hook=_unique_object, parse_constant=reject)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _key(row: dict, keys: tuple[str, ...]) -> tuple:
    return tuple(row[key] for key in keys)


def _complete_config(config: dict) -> None:
    _require(set(config) == {field.name for field in fields(SimulationConfig)},
             "Saved configuration is not complete")
    SimulationConfig(**config)  # Validate only; no simulator or investigator is invoked.


def configuration_id(config: dict) -> str:
    """Stable exact serialized complete-configuration identity (historical convention)."""
    _complete_config(config)
    return digest(config)


def _semantic_key(config: dict) -> tuple:
    # Python numeric equality makes saved 0 and 0.0 the same configuration, while
    # the first stored complete configuration retains its original JSON spelling.
    return tuple(sorted(config.items()))


def validate_csv_rows(path: Path, expected: list[dict]) -> None:
    """Require every cell, row, and field to agree with the authoritative JSON."""
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        actual = list(reader)
        names = reader.fieldnames
    _require(bool(expected), f"Empty authoritative table: {path}")
    _require(names is not None and len(names) == len(set(names)), f"Duplicate CSV fields: {path}")
    _require(set(names) == set(expected[0]), f"CSV columns differ: {path}")
    _require(len(actual) == len(expected), f"CSV row count differs: {path}")
    for index, (observed, saved) in enumerate(zip(actual, expected)):
        _require(set(saved) == set(names), f"JSON row schema differs at {index}: {path}")
        encoded = {key: "" if value is None else str(value) for key, value in saved.items()}
        _require(observed == encoded, f"CSV differs at data row {index}: {path}")


def _unique_rows(rows: list[dict], keys: tuple[str, ...], label: str) -> dict:
    result = {}
    for index, row in enumerate(rows):
        key = _key(row, keys)
        _require(key not in result, f"Duplicate {label} identity: {key}")
        result[key] = index
    return result


def _validate_summaries(saved: dict, group_keys: tuple[str, ...], rows_name="runs",
                        summary_name="summary") -> None:
    groups = {}
    for row in saved[rows_name]:
        groups.setdefault(_key(row, group_keys), []).append(row)
    summaries = _unique_rows(saved[summary_name], group_keys, summary_name)
    _require(set(summaries) == set(groups), f"{summary_name} group coverage differs")
    for key, members in groups.items():
        summary = saved[summary_name][summaries[key]]
        _require(summary["n_seeds"] == len(members), f"{summary_name} world denominator differs")
        _require(len({row['seed'] for row in members}) == len(members),
                 f"{summary_name} repeats a world within a group")
        for metric, values in summary["metrics"].items():
            count = sum(row[metric] is not None for row in members)
            _require(values["n"] == count, f"Undefined denominator differs: {metric}")


def discover_configurations(root: Path) -> dict:
    """Recover and cross-check the complete finite saved cohort, with all origins."""
    benchmark = load_json_strict(root / BENCHMARK)
    receipts = load_json_strict(root / RECEIPTS)
    metadata = benchmark["metadata"]
    receipt_config = receipts["metadata"]["config"]
    _require(benchmark["schema_version"] == receipts["schema_version"] == 1,
             "Unsupported historical result schema")
    validate_csv_rows(root / "results/runs.csv", benchmark["runs"])
    for name, key in (("runs", "runs"), ("paired_runs", "paired_runs"),
                      ("retention", "retention_audit")):
        validate_csv_rows(root / f"studies/missing_receipts/results/{name}.csv", receipts[key])
    config_paths = ("studies/missing_receipts/config.json",
                    "studies/missing_receipts/results/config.json")
    for path in config_paths:
        _require(load_json_strict(root / path) == receipt_config, f"Configuration differs: {path}")
    _require(digest(receipt_config) == receipts["metadata"]["config_sha256"],
             "Receipt configuration digest differs")
    _complete_config(metadata["default_generator_config"])
    original = {}
    configurations = []

    def add(config, origin):
        _complete_config(config)
        key = _semantic_key(config)
        if key not in original:
            item = {"configuration_id": configuration_id(config), "config": config, "origins": []}
            original[key] = item
            configurations.append(item)
        original[key]["origins"].append(origin)

    benchmark_rows = _unique_rows(benchmark["runs"], WORLD_KEYS + ("regime", "method"),
                                  "benchmark evaluation")
    world_values = list(itertools.product(metadata["seeds"],
                                         metadata["transmission_probabilities"],
                                         metadata["shock_strengths"]))
    _require(len(world_values) == len(set(world_values)) == metadata["n_worlds"],
             "Benchmark saved metadata world count differs")
    expected_rows = {world + (regime, method) for world in world_values
                     for regime in REGIMES for method in METHODS}
    _require(set(benchmark_rows) == expected_rows, "Benchmark saved grid is incomplete or expanded")
    for seed, probability, shock in world_values:
        config = metadata["default_generator_config"] | {
            "seed": seed, "transmission_probability": probability, "shock_strength": shock,
            "n_runs": metadata["n_runs"], "writes_per_run": metadata["writes_per_run"],
        }
        indices = sorted(benchmark_rows[(seed, probability, shock, regime, method)]
                         for regime in REGIMES for method in METHODS)
        _require(all(benchmark["runs"][i]["eligible_targets"] ==
                     config["n_runs"] * config["writes_per_run"] for i in indices),
                 "Benchmark denominator differs from complete configuration")
        add(config, {
            "cohort": "benchmark", "result_locator": BENCHMARK,
            "config_locator": BENCHMARK + "#/metadata/default_generator_config",
            "overrides_locator": BENCHMARK + f"#/runs/{indices[0]}",
            "size_overrides_locator": BENCHMARK + "#/metadata",
            "run_indices": indices, "saved_world_index": None,
        })

    receipt_rows = _unique_rows(receipts["runs"], WORLD_KEYS +
                               ("regime", "method", "profile", "retention", "policy"),
                               "receipt evaluation")
    receipt_worlds = _unique_rows([world["config"] for world in receipts["worlds"]],
                                 WORLD_KEYS, "receipt world")
    declared_worlds = set(itertools.product(receipt_config["world_seeds"],
                         receipt_config["transmission_probabilities"],
                         receipt_config["shock_strengths"]))
    _require(set(receipt_worlds) == declared_worlds, "Receipt world grid differs from protocol")
    dimensions = list(itertools.product([receipt_config["regime"]], receipt_config["methods"],
                      receipt_config["profiles"], receipt_config["retentions"],
                      receipt_config["policies"]))
    _require(len(dimensions) == len(set(dimensions)), "Duplicate receipt protocol dimensions")
    _require(set(receipt_rows) == {world + dims for world in declared_worlds for dims in dimensions},
             "Receipt evaluation grid is incomplete or expanded")
    for index, world in enumerate(receipts["worlds"]):
        config = world["config"]
        _complete_config(config)
        expected_config = metadata["default_generator_config"] | {
            "seed": config["seed"], "transmission_probability": config["transmission_probability"],
            "shock_strength": config["shock_strength"], "n_runs": receipt_config["n_runs"],
            "writes_per_run": receipt_config["writes_per_run"],
        }
        _require(config == expected_config, "Receipt complete configuration differs from saved defaults")
        _require(world["world_id"] == digest(config), "Receipt world ID differs from saved config")
        _require(world["mask_seed"] == receipt_config["mask_seed_base"] + config["seed"],
                 "Receipt mask seed differs")
        indices = sorted(receipt_rows[_key(config, WORLD_KEYS) + dims] for dims in dimensions)
        for row_index in indices:
            row = receipts["runs"][row_index]
            _require(all(row[name] == world[name] for name in
                         ("world_id", "mask_seed", "true_edges", "eligible_targets")),
                     "Receipt world metadata differs between saved tables")
        add(config, {
            "cohort": "missing_receipts", "result_locator": RECEIPTS,
            "config_locator": RECEIPTS + f"#/worlds/{index}/config",
            "run_indices": indices, "saved_world_index": index,
        })
    _validate_summaries(benchmark, BASE_GROUP_KEYS)
    _validate_summaries(receipts, RECEIPT_GROUP_KEYS)
    _validate_summaries(receipts, RECEIPT_GROUP_KEYS[:-1], "paired_runs", "paired_summary")
    expected_masks = {world + (receipt_config["regime"], profile, retention)
                      for world in declared_worlds for profile in receipt_config["profiles"]
                      for retention in receipt_config["retentions"]}
    mask_keys = WORLD_KEYS + ("regime", "profile", "retention")
    mask_rows = _unique_rows(receipts["retention_audit"], mask_keys, "receipt mask")
    _require(set(mask_rows) == expected_masks, "Receipt mask grid differs")
    paired_keys = WORLD_KEYS + ("regime", "method", "profile", "retention")
    paired_rows = _unique_rows(receipts["paired_runs"], paired_keys, "paired receipt evaluation")
    _require(set(paired_rows) == {key[:-1] for key in receipt_rows}, "Receipt paired grid differs")
    _require(receipts["metadata"]["n_worlds"] == len(receipt_worlds) and
             receipts["metadata"]["n_evaluations"] == len(receipt_rows) and
             receipts["metadata"]["n_masked_observations"] == len(mask_rows),
             "Receipt declared result counts differ")
    reported = len(world_values) + len(receipt_worlds)
    return {
        "schema_version": 1, "configurations": configurations,
        "distinct_configuration_count": len(configurations),
        "reported_configuration_count": reported,
        "duplicate_configuration_count": reported - len(configurations),
        "cohorts": {
            "benchmark": {"configuration_count": len(world_values),
                          "evaluation_count": len(benchmark_rows),
                          "summary_group_count": len(benchmark["summary"]),
                          "group_keys": list(BASE_GROUP_KEYS),
                          "world_hashes_available": False,
                          "world_hash_note": "No saved per-world generation hashes in benchmark.json"},
            "missing_receipts": {"configuration_count": len(receipt_worlds),
                                 "evaluation_count": len(receipt_rows),
                                 "masked_observation_count": len(mask_rows),
                                 "paired_evaluation_count": len(paired_rows),
                                 "summary_group_count": len(receipts["summary"]),
                                 "paired_summary_group_count": len(receipts["paired_summary"]),
                                 "group_keys": list(RECEIPT_GROUP_KEYS),
                                 "world_hashes_available": True},
        },
    }


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def _function_ast(source: bytes, name: str) -> str:
    node = next(node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.dump(node, include_attributes=False)


def _score_compatibility(old_source: bytes, current_source: bytes) -> dict:
    """Check original scoring formulas syntactically after the one local factoring."""
    def function(source):
        return next(node for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name == "score_edges")

    old, current = function(old_source), function(current_source)
    old_return, current_return = old.body[-1].value, current.body[-1].value
    old_fields = {key.value: value for key, value in zip(old_return.keys, old_return.values)}
    current_fields = {key.value: value for key, value in
                      zip(current_return.keys, current_return.values)}

    class Unfactor(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id == "false_positive_targets":
                return ast.parse("len(predicted_targets - true_targets)", mode="eval").body
            return node

    field_checks = {
        name: ast.dump(expression, include_attributes=False) ==
        ast.dump(Unfactor().visit(copy.deepcopy(current_fields[name])), include_attributes=False)
        for name, expression in old_fields.items()
    }
    removed_names = {"false_positive_targets", "false_negative_targets"}
    current_prefix = [node for node in current.body[:-1]
                      if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and
                              isinstance(node.targets[0], ast.Name) and
                              node.targets[0].id in removed_names)]
    prefix_equal = ([ast.dump(node, include_attributes=False) for node in old.body[:-1]] ==
                    [ast.dump(node, include_attributes=False) for node in current_prefix])
    _require(all(field_checks.values()) and prefix_equal,
             "An original score expression or validation rule changed")
    return {"old_score_field_ast_equal_after_local_factoring": field_checks,
            "old_scoring_guards_and_counts_ast_unchanged": prefix_equal,
            "added_score_fields": sorted(set(current_fields) - set(old_fields))}


def source_pin_audit(root: Path) -> dict:
    """Resolve old aggregate pins from local immutable Git objects, never repin."""
    old_names = _git(root, "ls-tree", "-r", "--name-only", BASELINE_COMMIT,
                     "src/tracebench").decode().splitlines()
    old_names = sorted(name for name in old_names if name.endswith(".py") and name.count("/") == 2)
    aggregate = hashlib.sha256()
    records = []
    historical_sources = {}
    for name in old_names:
        contents = _git(root, "show", f"{BASELINE_COMMIT}:{name}")
        historical_sources[name] = contents
        aggregate.update(Path(name).name.encode())
        aggregate.update(contents)
        old_hash = hashlib.sha256(contents).hexdigest()
        current_hash = file_digest(root / name)
        records.append({"path": name, "historical_sha256": old_hash,
                        "current_sha256": current_hash, "matches": old_hash == current_hash})
    old_manifest = load_json_strict(root / "results/manifest.json")
    benchmark = load_json_strict(root / BENCHMARK)
    _require(aggregate.hexdigest() == old_manifest["source_sha256"] ==
             benchmark["metadata"]["source_sha256"], "Historical benchmark source pin unresolved")
    changed = {row["path"] for row in records if not row["matches"]}
    _require(changed == {"src/tracebench/cli.py", "src/tracebench/evaluate.py"},
             "Unexpected benchmark source drift")
    cli_equal = (_function_ast(historical_sources["src/tracebench/cli.py"], "run_benchmark") ==
                 _function_ast((root / "src/tracebench/cli.py").read_bytes(), "run_benchmark"))
    _require(cli_equal, "Original benchmark execution function changed")
    old_evaluator = historical_sources["src/tracebench/evaluate.py"]
    current_evaluator = (root / "src/tracebench/evaluate.py").read_bytes()
    score_checks = _score_compatibility(old_evaluator, current_evaluator)
    ast_fingerprints = {}
    for name in ("bootstrap_mean", "_quantile"):
        old_ast, current_ast = (_function_ast(source, name)
                                for source in (old_evaluator, current_evaluator))
        _require(old_ast == current_ast, f"Historical {name} changed")
        ast_fingerprints[name] = hashlib.sha256(old_ast.encode()).hexdigest()
    ast_fingerprints["run_benchmark"] = hashlib.sha256(
        _function_ast(historical_sources["src/tracebench/cli.py"], "run_benchmark").encode()
    ).hexdigest()
    receipt_manifest = load_json_strict(root / "studies/missing_receipts/results/manifest.json")
    receipt_records = []
    for name, historical in receipt_manifest["source_files_sha256"].items():
        current = file_digest(root / "src/tracebench" / name)
        receipt_records.append({"path": "src/tracebench/" + name,
                                "historical_sha256": historical, "current_sha256": current,
                                "matches": historical == current})
    _require({row['path'] for row in receipt_records if not row['matches']} ==
             {"src/tracebench/cli.py"}, "Unexpected missing-receipt scientific-source drift")
    # The receipt publication preceded the wiki CLI additions within the same
    # later commit. Recover that exact historical byte pin by omitting only the
    # two identifiable wiki parser/dispatch blocks; no source file is modified.
    receipt_cli = (root / "src/tracebench/cli.py").read_text()
    start = receipt_cli.index('    wiki = commands.add_parser')
    end = receipt_cli.index('    args = parser.parse_args(argv)', start)
    receipt_cli = receipt_cli[:start] + receipt_cli[end:]
    start = receipt_cli.index('    if args.command in ("wiki-audit", "wiki-fixture-audit"):')
    end = receipt_cli.index('    if args.command == "receipt-study":', start)
    receipt_cli = receipt_cli[:start] + receipt_cli[end:]
    receipt_cli_hash = hashlib.sha256(receipt_cli.encode()).hexdigest()
    _require(receipt_cli_hash == receipt_manifest["source_files_sha256"]["cli.py"],
             "Receipt CLI historical pin cannot be recovered by removing wiki additions")
    current_aggregate = hashlib.sha256()
    for path in sorted((root / "src/tracebench").glob("*.py")):
        current_aggregate.update(path.name.encode())
        current_aggregate.update(path.read_bytes())
    diff = _git(root, "diff", BASELINE_COMMIT, "--", "src/tracebench/cli.py",
                "src/tracebench/evaluate.py").decode()
    return {
        "benchmark": {"historical_commit": BASELINE_COMMIT,
                      "historical_aggregate_sha256": old_manifest["source_sha256"],
                      "historical_aggregate_reconstructed": True,
                      "current_aggregate_sha256": current_aggregate.hexdigest(),
                      "aggregate_pin_matches_current": current_aggregate.hexdigest() ==
                                                       old_manifest["source_sha256"],
                      "historical_files": records,
                      "run_benchmark_ast_unchanged": cli_equal,
                      "preserved_function_ast_sha256": ast_fingerprints,
                      "score_compatibility": score_checks,
                      "exact_existing_source_diff": diff,
                      "explanation": "cli.py adds receipt/wiki commands; evaluate.py adds target "
                      "FP/FN, signed error, disagreement, grouping guards and policy pairs. "
                      "Original score expressions retain their definitions (false-target count "
                      "is factored into a local variable); all old saved fields must reproduce. "
                      "Additional top-level modules also change the package aggregate."},
        "missing_receipts": {"historical_files": receipt_records,
                             "cli_without_wiki_additions_sha256": receipt_cli_hash,
                             "cli_historical_pin_reconstructed": True,
                             "explanation": "Only CLI source pin differs; the current CLI adds "
                             "wiki command dispatch. Every receipt scientific calculation "
                             "module matches its historical byte hash."},
        "historical_pins_refreshed": False,
    }


def build_input_manifest(root: Path) -> dict:
    """Build freeze-ready input payload, including exact configuration origins."""
    cohorts = discover_configurations(root)
    artifacts = []
    for manifest_name in ("results/manifest.json", "studies/missing_receipts/results/manifest.json"):
        manifest_path = root / manifest_name
        saved = load_json_strict(manifest_path)
        artifacts.append({"path": manifest_name, "sha256": file_digest(manifest_path),
                          "role": "historical_integrity_manifest"})
        for name, expected in saved["files"].items():
            relative = str(Path(manifest_name).parent / name)
            actual = file_digest(root / relative)
            _require(actual == expected, f"Historical artifact pin mismatch: {relative}")
            artifacts.append({"path": relative, "sha256": actual,
                              "historical_sha256": expected, "historical_pin_matches": True,
                              "role": ("presentation_history" if Path(name).suffix in
                                       (".md", ".png", ".svg") else "scientific_result_input")})
    supporting = ("studies/missing_receipts/config.json", "studies/missing_receipts/ANALYSIS.md",
                  "studies/review_remediation/REVIEW.md", "studies/review_remediation/chronology.json",
                  "studies/review_remediation/chronology_audit.py",
                  "studies/review_remediation/derived_target_errors.json",
                  "studies/review_remediation/derived_target_errors.csv",
                  "studies/review_remediation/target_errors.py")
    dependencies = [{"path": path, "sha256": file_digest(root / path),
                     "role": "protocol_or_development_evidence"} for path in supporting]
    dependencies += [{"path": "src/tracebench/" + name,
                      "sha256": file_digest(root / "src/tracebench" / name),
                      "role": "scientific_execution_dependency"} for name in SCIENTIFIC_SOURCE_NAMES]
    dependencies += [{"path": "src/tracebench/" + name,
                      "sha256": file_digest(root / "src/tracebench" / name),
                      "role": "historical_driver_or_presentation_only"}
                     for name in ("cli.py", "reporting.py", "receipt_reporting.py")]
    return {"schema_version": 1, "study_type": "review-informed correction sensitivity",
            "configuration_manifest": cohorts, "artifacts": artifacts,
            "dependencies": dependencies, "historical_source_audit": source_pin_audit(root),
            "dependency_scope": "Scientific inputs and saved numerical rows are checked apart "
            "from presentation history; every listed artifact still retains its original pin. "
            "No historical manifest is refreshed and no published world is generated here."}


def verify_input_manifest(root: Path, manifest: dict) -> None:
    """Refuse missing or changed frozen dependencies before any computation."""
    _require(manifest.get("schema_version") == 1, "Unsupported input manifest schema")
    for entry in manifest["artifacts"] + manifest["dependencies"]:
        path = Path(entry["path"])
        _require(not path.is_absolute() and ".." not in path.parts, "Unsafe frozen input path")
        _require(file_digest(root / path) == entry["sha256"], f"Frozen input changed: {path}")
    _require(discover_configurations(root) == manifest["configuration_manifest"],
             "Frozen complete configuration manifest changed")
