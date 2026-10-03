"""Prepare and freeze bounded cases without exposing evaluator files to investigators."""

import copy
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..wiki_loader import load_release
from .prompts import (
    ARMS,
    assistance,
    build_prompt,
    canonical,
    digest,
    ordered_requests,
    prompt_manifest,
    validate_public_case,
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    """Never silently replace a prepared, frozen or completed artifact."""
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_preservation(root: Path) -> dict:
    manifest = read_json(root / "studies/investigator_utility/preservation.json")
    failed = [name for name, expected in manifest["files"].items()
              if not (root / name).is_file() or file_hash(root / name) != expected]
    if failed:
        raise ValueError(f"Protected baseline files changed: {failed}")
    return {"baseline_head": manifest["baseline_head"],
            "verified_files": len(manifest["files"]), "all_match": True,
            "dependency_lock_sha256": manifest["dependency_lock_sha256"]}


def ignored_output(root: Path, path: Path) -> None:
    if not path.resolve().is_relative_to((root / "artifacts").resolve()):
        raise ValueError("Raw cases, prompts and responses must stay in ignored artifacts/")
    check = subprocess.run(["git", "check-ignore", "--quiet", str(path.resolve())], cwd=root)
    if check.returncode != 0:
        raise ValueError("Raw output is not ignored by git")


def prepare(root: Path, archive: Path, supplement: Path, output: Path, config: dict) -> dict:
    from .synthetic_cases import build_synthetic_cases
    from .wiki_cases import build_wiki_cases

    verify_preservation(root)
    ignored_output(root, output)
    if output.exists():
        raise ValueError("Preparation output already exists; use a fresh directory")
    source = read_json(root / "studies/wiki_case_study/source_manifest.json")
    # The original loader checks member and body checksums. Pin the containers too.
    expected = {
        "archive": "eb68aa12d26bf189d8bfc4ce47f4d8af66ae5ba7ebbadd429738297a3cbb25ae",
        "supplement": "2047f3a2915fb3d237ed03d01deef306d11021a6ffc42a57a5f60918d850a5fd",
    }
    if file_hash(archive) != expected["archive"] or file_hash(supplement) != expected["supplement"]:
        raise ValueError("Raw containers differ from the existing pinned wiki release")
    loaded = load_release(archive, supplement)
    wiki_cases, wiki_gold, selection = build_wiki_cases(
        loaded, read_json(root / "studies/wiki_case_study/results/review_sheet.json"),
        evaluation_per_stratum=config["evaluation_wiki_cases"] // 2,
        development_per_stratum=config["development_wiki_cases"] // 2,
        max_text_chars=config["wiki_max_text_chars"],
    )
    synthetic_cases, synthetic_gold, synthetic_manifest = build_synthetic_cases()
    cases = wiki_cases + synthetic_cases
    gold = wiki_gold + synthetic_gold
    output.mkdir(parents=True)
    write_json(output / "public_cases.json", cases)
    write_json(output / "gold.json", gold)
    write_json(output / "selection.json", {
        "wiki": selection, "synthetic": synthetic_manifest,
        "source_container_sha256": expected,
        "existing_source_manifest_sha256": digest(source),
        "case_counts": dict(Counter(f"{c['split']}/{c['subset']}" for c in cases)),
    })
    return validate_prepared(output, config)


def validate_prepared(prepared: Path, config: dict) -> dict:
    from .synthetic_cases import validate_synthetic_gold
    from .wiki_cases import validate_wiki_gold

    cases = read_json(prepared / "public_cases.json")
    golds = read_json(prepared / "gold.json")
    by_gold = {g["case_id"]: g for g in golds}
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)) or len(by_gold) != len(golds) or set(ids) != set(by_gold):
        raise ValueError("Case/gold IDs are duplicated or do not match")
    counts = Counter((c["split"], c["subset"]) for c in cases)
    if counts[("development", "wiki")] + counts[("development", "synthetic")] > 4:
        raise ValueError("Development limit exceeded")
    dev_clusters = {c["cluster_id"] for c in cases if c["split"] == "development"}
    eval_clusters = {c["cluster_id"] for c in cases if c["split"] == "evaluation"}
    if dev_clusters & eval_clusters:
        raise ValueError("Development and evaluation histories overlap")
    prompts = []
    for case in cases:
        validate_public_case(case)
        gold = by_gold[case["case_id"]]
        validator = validate_wiki_gold if case["subset"] == "wiki" else validate_synthetic_gold
        validator(case, gold)
        rendered = {arm: build_prompt(case, arm) for arm in ARMS}
        raw = {prompt["user"].split("\nBEGIN_PUBLIC_CASE\n", 1)[1].split(
            "\nEND_PUBLIC_CASE\n", 1,
        )[0].encode("utf-8") for prompt in rendered.values()}
        if len(raw) != 1 or next(iter(raw)) != canonical(case).encode("utf-8"):
            raise ValueError("Arms differ in raw evidence")
        if not rendered["C"]["user"].startswith(rendered["B"]["user"]):
            raise ValueError("C does not preserve the entire B task and checklist")
        processed = assistance(case)
        forbidden = {"gold", "certificate", "status", "verdict", "truth_edges", "answer",
                     "exposure_status", "source_use_status", "inserted_count", "inherited_count"}

        def check_keys(value):
            if isinstance(value, dict):
                if set(value) & forbidden:
                    raise ValueError("Assistance contains forbidden verdict fields")
                for child in value.values():
                    check_keys(child)
            elif isinstance(value, list):
                for child in value:
                    check_keys(child)
        check_keys(processed)
        # An evaluator-only intervention must leave each serialized investigator view fixed.
        altered_gold = copy.deepcopy(gold)
        for claim in altered_gold["claims"]:
            claim["status"] = "ruled_out" if claim["status"] != "ruled_out" else "established"
            claim["certificate"] = {"changed_evaluator_only": True}
        if altered_gold == gold or any(build_prompt(case, arm) != rendered[arm] for arm in ARMS):
            raise ValueError("Evaluator-only intervention changed a prompt")
        manifest = prompt_manifest(case)
        if any(arm["utf8_bytes"] > config["max_prompt_utf8_bytes"]
               for arm in manifest["arms"].values()):
            raise ValueError("Oversized case: reject before inference, never truncate")
        prompts.append(manifest)
    return {
        "case_counts": {f"{split}/{subset}": count for (split, subset), count in sorted(counts.items())},
        "claims": sum(len(c["claims"]) for c in cases),
        "gold_certificate_checks": len(cases), "same_evidence_checks": len(cases),
        "label_invariance_checks": len(cases), "leakage_field_checks": len(cases),
        "independent_human_review": False, "prompt_manifests": prompts,
        "shortages": {f"{split}/{subset}": max(0, config[f"{split}_{subset}_cases"] - counts[(split, subset)])
                      for split in ("development", "evaluation") for subset in ("wiki", "synthetic")},
    }


def freeze(root: Path, prepared: Path, config_path: Path, protocol_path: Path,
           output: Path) -> dict:
    if output.exists():
        raise ValueError("Freeze already exists; no silent correction or refreeze")
    config = read_json(config_path)
    models = config["models"]
    if len(models) > 2 or len({m["model_id"] for m in models}) != len(models):
        raise ValueError("At most two distinct models may be frozen")
    if len(models) == 2 and len({m["family"] for m in models}) != 2:
        raise ValueError("Two-model design requires different families")
    validation = validate_prepared(prepared, config)
    preservation = verify_preservation(root)
    cases = read_json(prepared / "public_cases.json")
    code = {str(path.relative_to(root)): file_hash(path)
            for path in sorted((root / "src/tracebench/investigator_utility").glob("*.py"))}
    inputs = {str(path.resolve().relative_to(root.resolve())): file_hash(path) for path in (
        prepared / "public_cases.json", prepared / "gold.json", prepared / "selection.json",
        config_path, protocol_path,
    )}
    output.mkdir(parents=True)
    write_json(output / "config.json", config)
    write_json(output / "case_manifest.json", [{
        "case_id": c["case_id"], "subset": c["subset"], "split": c["split"],
        "cluster_id": c["cluster_id"], "claim_ids": [q["id"] for q in c["claims"]],
        "record_ids": [r["id"] for r in c["records"]],
        "public_case_sha256": digest(c),
    } for c in cases])
    write_json(output / "view_manifest.json", validation["prompt_manifests"])
    write_json(output / "gold_certificates.json", read_json(prepared / "gold.json"))
    write_json(output / "selection.json", read_json(prepared / "selection.json"))
    write_json(output / "validation.json", {k: v for k, v in validation.items()
                                            if k != "prompt_manifests"})
    requests = ordered_requests(cases, [m["model_id"] for m in models], "evaluation",
                                config["order_seed"])
    write_json(output / "prompt_manifest.json", [
        {key: request[key] for key in ("attempt_key", "case_id", "arm", "model_id", "split")}
        | {"request_sha256": digest(request)} for request in requests
    ])
    record = {
        "schema_version": 1, "study_id": config["study_id"],
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if models else "cases_frozen_execution_blocked",
        "models": [m["model_id"] for m in models],
        "evaluation_calls_planned": len(requests),
        "raw_execution_directory": config["raw_execution_directory"],
        "potential_evaluation_calls": 72 if len(models) == 1 else 144,
        "code_sha256": code, "input_sha256": inputs, "preservation": preservation,
        "artifacts_sha256": {p.name: file_hash(p) for p in sorted(output.glob("*.json"))},
        "execution_blockers": config.get("access_inspection", {}).get("blockers", []) if not models else [],
        "model_freeze_note": "No model chosen without authorized access and verified pricing. "
                             "A future model execution requires a new, explicitly versioned freeze "
                             "before any evaluation response; this blocked freeze permits zero calls.",
    }
    write_json(output / "freeze.json", record)
    return record


def verify_freeze(root: Path, directory: Path) -> dict:
    record = read_json(directory / "freeze.json")
    for name, expected in record["code_sha256"].items():
        if file_hash(root / name) != expected:
            raise ValueError(f"Frozen implementation changed: {name}")
    for name, expected in record["input_sha256"].items():
        if file_hash(root / name) != expected:
            raise ValueError(f"Frozen input changed: {name}")
    for name, expected in record["artifacts_sha256"].items():
        if file_hash(directory / name) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")
    verify_preservation(root)
    return record
