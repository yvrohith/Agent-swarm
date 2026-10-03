"""Canonical public-revision observations; no synthetic truth or inferred receipts.

This is an explicitly declared interchange model, not a claim about an uninspected
publisher schema. Source text and page titles are retained verbatim. Offsets are
Python Unicode code-point offsets in decoded source text, never byte offsets.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Revision:
    site: str
    page: str
    revision_id: str
    timestamp: str | None
    author: str | None
    text: str | None
    parent_id: str | None = None
    is_creation: bool = False
    source_file: str = ""
    source_line: int = 0
    record_sha256: str = ""
    flags: tuple[str, ...] = ()
    timestamp_uncertainty_seconds: float | None = 0
    source_json_pointer: str = ""
    text_kind: str = "full_revision"
