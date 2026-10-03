"""Build or verify an offline review ZIP; never include raw data or Git history.

Run from any directory. Building captures the current files, including uncommitted
research code. The archive's manifest pins bytes, not Git publication or authorship.
"""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FIXED = (
    ".gitignore", ".python-version", ".github/workflows/checks.yml",
    "pyproject.toml", "uv.lock", "CLAIMS.md", "README.md", "EVIDENCE_CARD.md",
    "LIMITATIONS.md", "case_study/README.md", "docs/HACKATHON.md",
    "docs/RELATED_WORK.md", "docs/SUBMISSION.md", "demo/app.js", "demo/index.html",
    "demo/style.css", "tests/fixtures/wiki/manifest.json",
    "tests/fixtures/wiki/synthetic_revisions.jsonl", "scripts/review_snapshot.py",
    "review/RESEARCHER_HANDOFF.md", "review/VALIDATION.json",
)
PATTERNS = (
    "src/tracebench/*.py", "tests/test_*.py", "results/*",
    "studies/missing_receipts/*", "studies/missing_receipts/results/*",
    "studies/wiki_case_study/*", "studies/wiki_case_study/results/*",
)
SUFFIXES = {".py", ".md", ".json", ".csv", ".png", ".svg"}
MANIFEST = "REVIEW_MANIFEST.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def build(output: Path) -> dict:
    if output.exists():
        raise ValueError("Output already exists; choose a fresh archive path")
    selected = {ROOT / name for name in FIXED}
    for pattern in PATTERNS:
        selected.update(p for p in ROOT.glob(pattern) if p.is_file() and p.suffix in SUFFIXES)
    contents = {}
    for path in sorted(selected):
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing file or unsupported link: {path.relative_to(ROOT)}")
        contents[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    files = {name: {"sha256": sha(data), "bytes": len(data)} for name, data in contents.items()}
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    manifest = {
        "schema_version": 1, "algorithm": "sha256", "snapshot_kind": "working_tree",
        "base_git_commit": git.stdout.strip() if git.returncode == 0 else None,
        "base_commit_meaning": "Historical base only; file hashes identify the uncommitted snapshot",
        "files": files, "file_table_sha256": sha(canonical(files)),
        "excluded": ["raw public corpus", ".git", "credentials and local configuration",
                     "virtual environments and caches", "unrelated files and generated raw runs"],
        "entrypoint": "review/RESEARCHER_HANDOFF.md",
    }
    contents[MANIFEST] = json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    return verify(output)


def verify(archive_path: Path) -> dict:
    """Check archive names and bytes in place; do not extract or execute contents."""
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or MANIFEST not in names:
            raise ValueError("Missing manifest or duplicate archive members")
        if sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024:
            raise ValueError("Review archive exceeds the bounded size limit")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                raise ValueError("Unsafe archive member name")
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get("schema_version") != 1 or manifest.get("algorithm") != "sha256":
            raise ValueError("Unsupported review manifest")
        files = manifest["files"]
        if set(names) != set(files) | {MANIFEST}:
            raise ValueError("Manifest does not cover exactly the archive members")
        if sha(canonical(files)) != manifest["file_table_sha256"]:
            raise ValueError("File table checksum mismatch")
        for name, pin in files.items():
            data = archive.read(name)
            if len(data) != pin["bytes"] or sha(data) != pin["sha256"]:
                raise ValueError(f"File checksum mismatch: {name}")
    return {"files_verified": len(files), "archive_sha256": sha(archive_path.read_bytes()),
            "file_table_sha256": manifest["file_table_sha256"],
            "archive_bytes": archive_path.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--build", type=Path, metavar="OUTPUT_ZIP")
    options.add_argument("--verify", type=Path, metavar="EXISTING_ZIP")
    args = parser.parse_args()
    try:
        result = build(args.build) if args.build else verify(args.verify)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
