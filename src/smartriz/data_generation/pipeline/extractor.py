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


def parse_json_content(content: str) -> Any | None:
    """Parse JSON from model content string. Returns None on failure."""
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
    data = parse_json_content(content)
    if data is None:
        logger.warning("[drop] JSON parse failed — seed=%s method=%s round=%d content_preview=%.120r",
                       parent_seed_id, generation_method, generation_round, content)
        return None

    # Self-instruct is expected to return a wrapper with 5 variations, each
    # carrying its own reasoning_chain. Some providers omit reasoning_content
    # and <think>, so we allow that path and normalize list-shaped responses.
    if generation_method == "self_instruct":
        if isinstance(data, list):
            data = {"variations": data}
        if not isinstance(data, dict):
            logger.warning(
                "[drop] self-instruct payload is not dict/list — seed=%s round=%d",
                parent_seed_id,
                generation_round,
            )
            return None
        variations = data.get("variations")
        if not isinstance(variations, list):
            logger.warning(
                "[drop] self-instruct variations not a list (got %s) — seed=%s round=%d data_keys=%s",
                type(variations).__name__,
                parent_seed_id,
                generation_round,
                list(data.keys())[:10],
            )
            return None
        
        clean_variations = [v for v in variations if isinstance(v, dict)]
        if not clean_variations:
            logger.warning(
                "[drop] self-instruct variations empty after filter — seed=%s round=%d raw_types=%s",
                parent_seed_id,
                generation_round,
                [type(v).__name__ for v in variations[:5]],
            )
            return None
        
        data["variations"] = clean_variations
        if reasoning is not None and "reasoning_chain" not in data:
            data["reasoning_chain"] = reasoning
        return data

    required = {"id", "source", "language", "domain", "problem",
                "contradiction_pair", "inventive_principles", "solution", "complexity"}
    if not isinstance(data, dict):
        logger.warning("[drop] payload is not a dict — seed=%s method=%s round=%d",
                       parent_seed_id, generation_method, generation_round)
        return None
    missing = required - data.keys()
    if missing:
        logger.warning("[drop] missing fields %s — seed=%s method=%s round=%d",
                       missing, parent_seed_id, generation_method, generation_round)
        return None

    # For evol methods: allow reasoning_chain in JSON if reasoning_content/<think> absent
    if reasoning is None:
        json_reasoning = data.get("reasoning_chain")
        if isinstance(json_reasoning, str) and json_reasoning.strip():
            reasoning = json_reasoning.strip()
        else:
            logger.warning("[drop] no reasoning extracted — seed=%s method=%s round=%d",
                           parent_seed_id, generation_method, generation_round)
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
