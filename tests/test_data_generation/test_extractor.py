"""
Unit tests for pipeline/extractor.py.

Four mock scenarios:
  1. Only <think> tag in content
  2. Only reasoning_content field (DeepInfra-specific)
  3. Both present — reasoning_content wins; <think> still stripped from content
  4. Neither — extract_reasoning_and_content returns (None, content)
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from smartriz.data_generation.pipeline.extractor import (
    extract_reasoning_and_content,
    extract_case,
    parse_json_content,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_message(*, content: str = "", reasoning_content: str | None = None) -> SimpleNamespace:
    msg = SimpleNamespace(content=content)
    if reasoning_content is not None:
        msg.reasoning_content = reasoning_content
    # deliberately do NOT set reasoning_content when it's None → tests getattr fallback
    return msg


def _make_response(message: SimpleNamespace) -> SimpleNamespace:
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


_VALID_CASE_JSON = json.dumps({
    "id": "TEST-01",
    "source": "unit-test",
    "language": "en",
    "domain": "test",
    "problem": "A widget must be fast yet light.",
    "contradiction_pair": {
        "improving_parameter": "Speed (#9)",
        "worsening_parameter": "Weight of moving object (#1)",
    },
    "inventive_principles": ["#35 Parameter changes"],
    "solution": "Use a lighter composite material.",
    "complexity": "simple",
})


# ── Scenario 1: only <think> tag ─────────────────────────────────────────────

class TestScenario1OnlyThinkTag:
    def setup_method(self):
        raw_content = f"<think>step-by-step reasoning here</think>\n{_VALID_CASE_JSON}"
        self.msg = _make_message(content=raw_content)

    def test_reasoning_extracted(self):
        reasoning, _ = extract_reasoning_and_content(self.msg)
        assert reasoning == "step-by-step reasoning here"

    def test_think_tag_stripped_from_content(self):
        _, content = extract_reasoning_and_content(self.msg)
        assert "<think>" not in content
        assert "</think>" not in content

    def test_content_is_valid_json(self):
        _, content = extract_reasoning_and_content(self.msg)
        data = parse_json_content(content)
        assert data is not None
        assert data["id"] == "TEST-01"

    def test_full_extract_case_succeeds(self):
        resp = _make_response(self.msg)
        result = extract_case(resp, "SEED-01", "self_instruct", 1, 0.7)
        assert result is not None
        assert result["reasoning_chain"] == "step-by-step reasoning here"
        assert result["meta"]["parent_seed_id"] == "SEED-01"


# ── Scenario 2: only reasoning_content field ──────────────────────────────────

class TestScenario2OnlyReasoningContent:
    def setup_method(self):
        self.msg = _make_message(
            content=_VALID_CASE_JSON,
            reasoning_content="server-side reasoning text",
        )

    def test_reasoning_content_wins(self):
        reasoning, _ = extract_reasoning_and_content(self.msg)
        assert reasoning == "server-side reasoning text"

    def test_content_unchanged(self):
        _, content = extract_reasoning_and_content(self.msg)
        data = parse_json_content(content)
        assert data is not None

    def test_full_extract_case_succeeds(self):
        resp = _make_response(self.msg)
        result = extract_case(resp, "SEED-02", "evol_deepening", 2, 0.9)
        assert result is not None
        assert result["reasoning_chain"] == "server-side reasoning text"
        assert result["meta"]["generation_method"] == "evol_deepening"


# ── Scenario 3: both present — reasoning_content wins ────────────────────────

class TestScenario3Both:
    def setup_method(self):
        content_with_think = f"<think>inline reasoning</think>\n{_VALID_CASE_JSON}"
        self.msg = _make_message(
            content=content_with_think,
            reasoning_content="priority reasoning from server",
        )

    def test_reasoning_content_takes_priority(self):
        reasoning, _ = extract_reasoning_and_content(self.msg)
        assert reasoning == "priority reasoning from server"

    def test_think_tags_stripped_even_when_reasoning_content_present(self):
        _, content = extract_reasoning_and_content(self.msg)
        assert "<think>" not in content
        assert "</think>" not in content

    def test_content_still_valid_json(self):
        _, content = extract_reasoning_and_content(self.msg)
        data = parse_json_content(content)
        assert data is not None

    def test_full_extract_case_uses_server_reasoning(self):
        resp = _make_response(self.msg)
        result = extract_case(resp, "SEED-03", "evol_constraint", 3, 1.1)
        assert result is not None
        assert result["reasoning_chain"] == "priority reasoning from server"


# ── Scenario 4: neither present → None ───────────────────────────────────────

class TestScenario4Neither:
    def setup_method(self):
        self.msg = _make_message(content=_VALID_CASE_JSON)

    def test_reasoning_is_none(self):
        reasoning, _ = extract_reasoning_and_content(self.msg)
        assert reasoning is None

    def test_content_returned_as_is(self):
        _, content = extract_reasoning_and_content(self.msg)
        assert content == _VALID_CASE_JSON

    def test_full_extract_case_returns_none(self):
        resp = _make_response(self.msg)
        result = extract_case(resp, "SEED-04", "evol_cross_domain", 4, 1.3)
        assert result is None


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_think_tag_drops(self):
        msg = _make_message(content=f"<think>   </think>\n{_VALID_CASE_JSON}")
        reasoning, _ = extract_reasoning_and_content(msg)
        # strip() of whitespace-only string gives ""
        assert reasoning == ""

    def test_malformed_json_drops_case(self):
        msg = _make_message(
            content="not-json",
            reasoning_content="good reasoning",
        )
        resp = _make_response(msg)
        result = extract_case(resp, "SEED-05", "self_instruct", 1, 0.7)
        assert result is None

    def test_missing_required_field_drops_case(self):
        incomplete = json.loads(_VALID_CASE_JSON)
        del incomplete["problem"]
        msg = _make_message(
            content=json.dumps(incomplete),
            reasoning_content="good reasoning",
        )
        resp = _make_response(msg)
        result = extract_case(resp, "SEED-06", "self_instruct", 1, 0.7)
        assert result is None
