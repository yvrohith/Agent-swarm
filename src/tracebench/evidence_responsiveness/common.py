"""Small serialization helpers for the separate frozen study."""

import hashlib
import json
from pathlib import Path

SALT = "tracebench-evidence-responsiveness-v1-20261003"
ROLES = ("base", "irrelevant", "decisive")
ORDER_SEED = 84103
BOOTSTRAP_SEED = 84104
BOOTSTRAP_RESAMPLES = 2000
MAX_PUBLIC_BYTES = 48000


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def opaque(*parts):
    return "c_" + digest([SALT, *parts])[:24]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
