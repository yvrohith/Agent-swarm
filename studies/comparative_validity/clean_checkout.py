"""Exercise the public console entry points in a disposable, offline Git checkout.

Uses only public Git objects, tracked files and explicitly bounded pending files.
No source checkout mutation, remote access, inherited environment or PYTHONPATH.
The Linux seccomp guard applies to every subprocess, including the real console
entry points; it does not change Python imports or monkeypatch application code.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PENDING_ROOTS = ("studies/chronology_consistency/", "studies/comparative_validity/", "tests/")


def no_network() -> None:
    """Deny new sockets/connections in subprocesses without altering Python paths."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "Cannot enable no-new-privileges")
    lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                    ctypes.c_uint]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("Cannot initialize offline syscall guard")
    try:
        for name in (b"socket", b"connect"):
            number = lib.seccomp_syscall_resolve_name(name)
            if number < 0 or lib.seccomp_rule_add(context, 0x00050000 | errno.EPERM,
                                                number, 0) != 0:
                raise RuntimeError("Cannot install offline syscall guard")
        if lib.seccomp_load(context) != 0:
            raise RuntimeError("Cannot load offline syscall guard")
    finally:
        lib.seccomp_release(context)


def environment(cache: Path) -> dict[str, str]:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv must already be installed")
    return {
        "PATH": str(Path(uv).parent) + ":/usr/bin:/bin",
        "UV_CACHE_DIR": str(cache),
        "UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never", "UV_NO_CONFIG": "1",
        "UV_FROZEN": "1", "UV_LINK_MODE": "copy",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def command(args: list[str], cwd: Path, env: dict, *, required: bool = False) -> dict:
    start = time.perf_counter()
    completed = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True,
                               check=False, preexec_fn=no_network)
    row = {"command": args, "exit_code": completed.returncode,
           "wall_seconds": time.perf_counter() - start,
           "stdout": completed.stdout, "stderr": completed.stderr}
    if required and completed.returncode:
        raise RuntimeError(json.dumps(row))
    return row


def public_snapshot(source: Path, target: Path, env: dict, *, shallow: bool) -> dict:
    if target.exists():
        raise FileExistsError(target)
    template = target.parent / (target.name + "-empty-template")
    template.mkdir(exist_ok=False)
    clone_args = ["git", "clone", "--no-checkout", "--no-hardlinks", "--no-local",
                  "--template=" + str(template)]
    if shallow:
        clone_args += ["--depth", "1"]
    clone_args += [source.as_uri(), str(target)]
    clone = command(clone_args, source, env, required=True)
    # Keep public objects and HEAD; discard the local remote location and all hooks.
    (target / ".git/config").write_text(
        "[core]\n\trepositoryformatversion = 0\n\tbare = false\n\tfilemode = true\n")
    command(["git", "read-tree", "HEAD"], target, env, required=True)
    tracked = command(["git", "ls-files", "-z"], source, env, required=True)["stdout"]
    pending = command(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                      source, env, required=True)["stdout"]
    names = set(filter(None, tracked.split("\0")))
    intended = {name for name in pending.split("\0") if name.startswith(PENDING_ROOTS)}
    names |= intended
    hashes = {}
    for name in sorted(names):
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source path")
        path = source / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("Source path is missing or not a regular file: " + name)
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[name] = hashlib.sha256(dest.read_bytes()).hexdigest()
    if (target / "artifacts").exists() or (target / ".venv").exists():
        raise ValueError("Historical artifacts or virtual environment entered the snapshot")
    head = command(["git", "rev-parse", "HEAD"], target, env, required=True)["stdout"].strip()
    return {"head": head, "history": "shallow" if shallow else "full_public_local_history",
            "files_sha256": hashes, "pending_intended_paths": sorted(intended),
            "copied_file_count": len(hashes), "clone": clone,
            "excluded": ["historical artifacts", "private inputs", "source .git/config",
                         "source Git hooks", "source virtual environment", "shell environment",
                         "credentials", "PYTHONPATH"]}


def nodes(row: dict) -> list[str]:
    return sorted(line.strip() for line in row["stdout"].splitlines()
                  if line.startswith("tests/") and "::" in line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--shallow", action="store_true")
    parser.add_argument("--run-full", action="store_true")
    args = parser.parse_args()
    if args.record.exists():
        raise FileExistsError(args.record)
    env = environment(args.cache.resolve())
    record = {"schema_version": 1, "network_control": "seccomp denies socket/connect",
              "environment": sorted(env), "pythonpath_set": False,
              "remote_workflow_status": "not_run", "commands": []}
    try:
        record["snapshot"] = public_snapshot(args.source.resolve(), args.directory.resolve(), env,
                                             shallow=args.shallow)
        record["commands"].append(command(["uv", "--version"], args.directory, env))
        sync = command(["uv", "sync", "--frozen", "--extra", "dev"], args.directory, env)
        record["commands"].append(sync)
        if sync["exit_code"]:
            record["status"] = "offline_install_blocked"
        else:
            record["commands"].append(command(["uv", "run", "python", "--version"],
                                               args.directory, env))
            console = command(["uv", "run", "pytest", "--collect-only", "-q"],
                              args.directory, env)
            module = command(["uv", "run", "python", "-m", "pytest", "--collect-only", "-q"],
                             args.directory, env)
            record["commands"] += [console, module]
            console_nodes, module_nodes = nodes(console), nodes(module)
            record["collection"] = {
                "console_count": len(console_nodes), "module_count": len(module_nodes),
                "same_intended_test_set": console_nodes == module_nodes,
                "console_only": sorted(set(console_nodes) - set(module_nodes)),
                "module_only": sorted(set(module_nodes) - set(console_nodes)),
                "console_node_ids": console_nodes, "module_node_ids": module_nodes}
            record["status"] = ("collection_passed" if not console["exit_code"] and
                                not module["exit_code"] and console_nodes == module_nodes
                                else "collection_failed")
            if args.run_full and record["status"] == "collection_passed":
                test = command(["uv", "run", "pytest"], args.directory, env)
                lint = command(["uv", "run", "ruff", "check", "."], args.directory, env)
                record["commands"] += [test, lint]
                record["status"] = ("passed" if not test["exit_code"] and not lint["exit_code"]
                                    else "validation_failed")
    finally:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        with args.record.open("x") as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps({"status": record.get("status"),
                      "collection": {key: record.get("collection", {}).get(key) for key in
                                     ("console_count", "module_count", "same_intended_test_set")}},
                     sort_keys=True))
    if record.get("status") not in ("collection_passed", "passed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
