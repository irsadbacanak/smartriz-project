"""
Reasoning chain extractor for DeepSeek-R1-Distill responses.

Handles two DeepInfra delivery modes:
  1. reasoning_content field on the message object (server-side stripped)
  2. <think>...</think> tags inline in message.content

If neither is present the example is dropped (no reasoning = no training value).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def extract_reasoning_and_content(message: Any) -> tuple[str | None, str]:
    """Return (reasoning, cleaned_content) from an API message object.

    Priority:
      1. reasoning_content field (DeepInfra-specific)
      2. <think>...</think> tag inside content
      3. Neither → (None, content)  — caller must drop the example
    """
    reasoning: str | None = getattr(message, "reasoning_content", None)
    content: str = getattr(message, "content", "") or ""

    if reasoning:
        # Server already separated reasoning; content may still have stale tags — clean it.
        content = _THINK_RE.sub("", content).strip()
        return reasoning.strip(), content

    m = _THINK_RE.search(content)
    if m:
        reasoning = m.group(1).strip()
        content = _THINK_RE.sub("", content).strip()
        return reasoning, content

    return None, content


def parse_json_content(content: str) -> dict | None:
    """Parse JSON from model content string.  Returns None on failure."""
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None


def extract_case(response: Any, parent_seed_id: str, generation_method: str,
                 generation_round: int, generation_temperature: float) -> dict | None:
    """Full extraction pipeline for one teacher API response.

    Returns a dict ready for JSONL append, or None if the example must be dropped.
    Each drop is logged with a reason.
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError) as exc:
        logger.warning("[drop] response parsing failed (%s) — seed=%s method=%s round=%d",
                       exc, parent_seed_id, generation_method, generation_round)
        return None

    reasoning, content = extract_reasoning_and_content(message)

    if reasoning is None:
        logger.warning("[drop] no reasoning extracted — seed=%s method=%s round=%d",
                       parent_seed_id, generation_method, generation_round)
        return None

    data = parse_json_content(content)
    if data is None:
        logger.warning("[drop] JSON parse failed — seed=%s method=%s round=%d content_preview=%.120r",
                       parent_seed_id, generation_method, generation_round, content)
        return None

    required = {"id", "source", "language", "domain", "problem",
                "contradiction_pair", "inventive_principles", "solution", "complexity"}
    missing = required - data.keys()
    if missing:
        logger.warning("[drop] missing fields %s — seed=%s method=%s round=%d",
                       missing, parent_seed_id, generation_method, generation_round)
        return None

    data["reasoning_chain"] = reasoning

    data["meta"] = {
        "parent_seed_id": parent_seed_id,
        "generation_method": generation_method,
        "generation_temperature": generation_temperature,
        "generation_round": generation_round,
        "judge_scores": None,
        "matrix_check_passed": None,
    }

    return data
