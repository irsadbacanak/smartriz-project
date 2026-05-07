"""
Tests for validate_complexity() in quality/complexity.py.

Boundary conditions for each complexity level:
  complex  → secondary_contradiction OR ≥3 principles OR ≥800 char reasoning
  simple   → ≤2 principles AND ≤500 char reasoning
  medium   → always accepted
"""
from __future__ import annotations

import pytest

from smartriz.data_generation.quality.complexity import (
    _COMPLEX_MIN_PRINCIPLES,
    _COMPLEX_MIN_REASONING,
    _SIMPLE_MAX_PRINCIPLES,
    _SIMPLE_MAX_REASONING,
    validate_complexity,
)


def _case(complexity: str, principles: list, reasoning: str, secondary=None) -> dict:
    c = {
        "complexity": complexity,
        "inventive_principles": principles,
        "reasoning_chain": reasoning,
    }
    if secondary is not None:
        c["secondary_contradiction"] = secondary
    return c


# ── complex ───────────────────────────────────────────────────────────────────

class TestComplexValidation:

    def test_complex_with_secondary_contradiction_passes(self):
        case = _case(
            "complex",
            ["#1 Segmentation", "#2 Taking Out"],  # only 2 — below threshold
            "short",  # below char threshold
            secondary={
                "improving_parameter": "Reliability (#27)",
                "worsening_parameter": "Device complexity (#36)",
            },
        )
        ok, reason = validate_complexity(case)
        assert ok is True, reason

    def test_complex_with_enough_principles_passes(self):
        principles = [f"#{i} X" for i in range(1, _COMPLEX_MIN_PRINCIPLES + 1)]
        case = _case("complex", principles, "short")
        ok, reason = validate_complexity(case)
        assert ok is True, reason

    def test_complex_with_long_reasoning_passes(self):
        reasoning = "A" * _COMPLEX_MIN_REASONING
        case = _case("complex", ["#1 Segmentation"], reasoning)
        ok, reason = validate_complexity(case)
        assert ok is True, reason

    def test_complex_without_any_indicator_fails(self):
        case = _case("complex", ["#1 Segmentation", "#2 Taking Out"], "short")
        ok, reason = validate_complexity(case)
        assert ok is False
        assert "complex" in reason

    def test_complex_with_empty_secondary_dict_fails(self):
        """secondary_contradiction={} (empty) must not count as evidence."""
        case = _case("complex", ["#1 Segmentation"], "short", secondary={})
        ok, reason = validate_complexity(case)
        assert ok is False

    def test_complex_reasoning_exactly_at_threshold_passes(self):
        reasoning = "A" * _COMPLEX_MIN_REASONING
        case = _case("complex", ["#1 Segmentation"], reasoning)
        ok, _ = validate_complexity(case)
        assert ok is True

    def test_complex_reasoning_one_below_threshold_without_other_indicators_fails(self):
        reasoning = "A" * (_COMPLEX_MIN_REASONING - 1)
        case = _case("complex", ["#1 Segmentation"], reasoning)  # only 1 principle
        ok, _ = validate_complexity(case)
        assert ok is False


# ── simple ────────────────────────────────────────────────────────────────────

class TestSimpleValidation:

    def test_simple_with_one_principle_short_reasoning_passes(self):
        case = _case("simple", ["#1 Segmentation"], "A concise reasoning.")
        ok, reason = validate_complexity(case)
        assert ok is True, reason

    def test_simple_with_two_principles_short_reasoning_passes(self):
        case = _case("simple", ["#1 Segmentation", "#2 Taking Out"], "Short.")
        ok, reason = validate_complexity(case)
        assert ok is True, reason

    def test_simple_with_three_principles_fails(self):
        principles = ["#1 Segmentation", "#2 Taking Out", "#3 Local Quality"]
        case = _case("simple", principles, "Short reasoning.")
        ok, reason = validate_complexity(case)
        assert ok is False
        assert "simple" in reason

    def test_simple_with_long_reasoning_fails(self):
        reasoning = "A" * (_SIMPLE_MAX_REASONING + 1)
        case = _case("simple", ["#1 Segmentation"], reasoning)
        ok, reason = validate_complexity(case)
        assert ok is False
        assert "simple" in reason

    def test_simple_reasoning_exactly_at_limit_passes(self):
        reasoning = "A" * _SIMPLE_MAX_REASONING
        case = _case("simple", ["#1 Segmentation"], reasoning)
        ok, _ = validate_complexity(case)
        assert ok is True

    def test_simple_both_violations_reports_both(self):
        principles = ["#1 X", "#2 X", "#3 X"]
        reasoning = "A" * (_SIMPLE_MAX_REASONING + 100)
        case = _case("simple", principles, reasoning)
        ok, reason = validate_complexity(case)
        assert ok is False
        assert "principles" in reason or "reasoning" in reason


# ── medium ────────────────────────────────────────────────────────────────────

class TestMediumValidation:

    def test_medium_always_accepted(self):
        for principals_count in (1, 5, 10):
            for reasoning_len in (0, 100, 2000):
                case = _case(
                    "medium",
                    [f"#{i} X" for i in range(1, principals_count + 1)],
                    "A" * reasoning_len,
                )
                ok, reason = validate_complexity(case)
                assert ok is True, f"medium should always pass, got: {reason}"

    def test_medium_with_no_principles_passes(self):
        case = _case("medium", [], "Some reasoning")
        ok, _ = validate_complexity(case)
        assert ok is True


# ── Unknown / edge cases ──────────────────────────────────────────────────────

class TestEdgeCases:

    def test_unknown_complexity_treated_as_medium(self):
        """Unrecognized labels default to the medium path (always accepted)."""
        case = _case("advanced", ["#1 X"], "reasoning")
        ok, _ = validate_complexity(case)
        assert ok is True

    def test_missing_complexity_field_defaults_to_medium_path(self):
        case = {"inventive_principles": ["#1 X"], "reasoning_chain": "reasoning"}
        ok, _ = validate_complexity(case)
        assert ok is True

    def test_missing_principles_and_reasoning_for_complex_fails(self):
        case = {"complexity": "complex"}
        ok, reason = validate_complexity(case)
        assert ok is False
