"""A missing published predecessor is never replaced with empty historical text."""

import runpy
from pathlib import Path

import pytest

from tracebench.wiki_model import Revision

MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1]
                          / "studies/evidence_acquisition/wiki_applicability.py"))


@pytest.mark.parametrize("text,status", [("A prior Source title", "insufficient_data"),
                                         ("No such title", "ruled_out")])
def test_history_gap_and_absence_of_target_literal_are_distinct(text, status):
    source = Revision("dse", "Source", "s1", "2026-01-01T00:00:00Z", None, None,
                      is_creation=True)
    target = Revision("dse", "Target", "t5", "2026-01-01T00:01:00Z", "label", text,
                      flags=("missing_predecessor",))
    result = MODULE["assess"](target, [target], source)
    assert result["status"] == status
    assert not result["comparison_eligible"]
    assert result["gap_is_not_empty_predecessor"]
    assert "missing_predecessor" in result["exclusion_reasons"]
    assert result["inserted_spans"] == []


def test_selection_rejects_access_to_text_even_before_ranking():
    record = Revision("dse", "Page", "p1", "2026-01-01T00:00:00Z", None, "private text")
    with pytest.raises(ValueError, match="metadata only"):
        MODULE["select"]([record])
