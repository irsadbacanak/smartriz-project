"""
Tests for extract_matrix_citations() and check_matrix_citations() in matrix.py.

Covers:
  - Positive: well-formed citation matching the real matrix cell → ok=True
  - Negative: hallucinated principle NOT in the real cell → ok=False
  - Edge: cited principle list correct but extra principle added → ok=False
  - Edge: model cites empty cell with no principles → ok=True (nothing to verify)
  - Edge: no citation trigger in text → ok=True (nothing to verify)
  - Edge: parameter IDs out of range (1-39) → citation ignored
  - Cell truly empty in MATRIX → citation skipped (honest "no entry")
"""
from __future__ import annotations

import pytest

from smartriz.data_generation.quality.matrix import (
    MATRIX,
    check_matrix_citations,
    extract_matrix_citations,
)


# ── extract_matrix_citations ──────────────────────────────────────────────────

class TestExtractMatrixCitations:
    def test_finds_standard_phrasing(self):
        text = "The matrix lookup for (9,31) yields principles #15, #35."
        citations = extract_matrix_citations(text)
        assert len(citations) == 1
        imp, wor, cited = citations[0]
        assert imp == 9
        assert wor == 31
        assert set(cited) == {15, 35}

    def test_finds_cell_phrasing(self):
        text = "Looking at cell (12, 32) suggests #1, #2, #27."
        citations = extract_matrix_citations(text)
        # The "suggests" keyword isn't a trigger; only matrix/cell/lookup keyword is
        # "cell (12, 32)" matches the 'cell' trigger
        assert any(c[0] == 12 and c[1] == 32 for c in citations)

    def test_no_trigger_keyword_not_captured(self):
        # Generic sentence without matrix/cell/lookup should NOT be captured
        text = "Parameters (5,10) are important and principle #3 is used."
        citations = extract_matrix_citations(text)
        assert citations == []

    def test_out_of_range_params_ignored(self):
        text = "matrix lookup for (0, 40) yields #1"
        citations = extract_matrix_citations(text)
        assert citations == []

    def test_principle_out_of_range_discarded_from_list(self):
        text = "matrix lookup for (9,31) yields principles #15, #99."
        citations = extract_matrix_citations(text)
        assert len(citations) == 1
        _, _, cited = citations[0]
        assert 99 not in cited
        assert 15 in cited

    def test_multiple_citations_in_text(self):
        text = (
            "For the primary contradiction: matrix lookup for (9,31) yields #15, #35. "
            "For the secondary: matrix lookup for (27,36) yields #13."
        )
        citations = extract_matrix_citations(text)
        assert len(citations) == 2


# ── check_matrix_citations ───────────────────────────────────────────────────

class TestCheckMatrixCitations:

    def _case_with_reasoning(self, text: str) -> dict:
        return {"id": "TEST", "reasoning_chain": text}

    def test_no_citation_in_text_is_ok(self):
        ok, errors = check_matrix_citations(self._case_with_reasoning(
            "The contradiction between speed and accuracy is resolved by segmentation."
        ))
        assert ok is True
        assert errors == []

    def test_correct_citation_passes(self):
        # Find a non-empty cell to build a valid citation
        imp, wor, real_principles = _find_nonempty_cell()
        text = f"matrix lookup for ({imp},{wor}) yields #{real_principles[0]}."
        ok, errors = check_matrix_citations(self._case_with_reasoning(text))
        assert ok is True, f"Expected ok=True but got errors: {errors}"

    def test_hallucinated_principle_fails(self):
        # Find a non-empty cell and pick a principle NOT in it
        imp, wor, real_principles = _find_nonempty_cell()
        hallucinated = _find_principle_not_in(real_principles)
        text = f"matrix lookup for ({imp},{wor}) yields #{hallucinated}."
        ok, errors = check_matrix_citations(self._case_with_reasoning(text))
        assert ok is False
        assert len(errors) >= 1
        assert "hallucinated" in errors[0]

    def test_extra_hallucinated_principle_among_correct_fails(self):
        imp, wor, real_principles = _find_nonempty_cell()
        hallucinated = _find_principle_not_in(real_principles)
        # Mix one correct + one hallucinated
        text = (
            f"matrix lookup for ({imp},{wor}) yields #{real_principles[0]}, #{hallucinated}."
        )
        ok, errors = check_matrix_citations(self._case_with_reasoning(text))
        assert ok is False

    def test_empty_cell_citation_is_skipped(self):
        # Find a cell that IS empty in the matrix
        imp, wor = _find_empty_cell()
        if imp is None:
            pytest.skip("No empty cell found in MATRIX — cannot test this edge case")
        # Even if the model claims a principle for an empty cell, we skip (can't verify)
        text = f"matrix lookup for ({imp},{wor}) yields #1."
        ok, errors = check_matrix_citations(self._case_with_reasoning(text))
        assert ok is True  # Empty cell → citation is skipped


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_nonempty_cell() -> tuple[int, int, list[int]]:
    """Return (imp, wor, principles) for any non-empty, non-diagonal cell."""
    for imp in range(1, 40):
        for wor in range(1, 40):
            if imp == wor:
                continue
            cell = MATRIX.get(imp, {}).get(wor, [])
            if cell:
                return imp, wor, list(cell)
    raise RuntimeError("No non-empty cell found in MATRIX — unexpected")


def _find_empty_cell() -> tuple[int | None, int | None]:
    """Return (imp, wor) for a cell that exists but is empty ([]). Returns (None,None) if none."""
    for imp in range(1, 40):
        for wor in range(1, 40):
            if imp == wor:
                continue
            cell = MATRIX.get(imp, {}).get(wor, [])
            if cell == []:
                return imp, wor
    return None, None


def _find_principle_not_in(principles: list[int]) -> int:
    """Return a principle ID (1-40) that is NOT in the provided list."""
    principle_set = set(principles)
    for p in range(1, 41):
        if p not in principle_set:
            return p
    raise RuntimeError("All 40 principles are in the cell — impossible")
