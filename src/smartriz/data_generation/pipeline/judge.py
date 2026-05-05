"""
Async judge client — wraps DeepSeek-V3 via DeepInfra.

Features:
  - Four-criterion rubric (contradiction_validity, principle_correctness,
    reasoning_coherence, solution_feasibility)
  - Returns score dict with computed average
  - Same retry / concurrency / cost-tracking setup as teacher
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from smartriz.data_generation.config import (
    BASE_URL,
    DEEPINFRA_API_KEY,
    JUDGE_MODEL,
    MAX_CONCURRENCY,
    CostTracker,
)
from smartriz.data_generation.prompts.judge import build_prompt

logger = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

_REQUIRED_KEYS = {
    "contradiction_validity",
    "principle_correctness",
    "reasoning_coherence",
    "solution_feasibility",
}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError))


def _make_retry():
    return retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )


class JudgeClient:
    """Async client for the four-criterion DeepSeek-V3 judge."""

    def __init__(self, cost_tracker: CostTracker, client: httpx.AsyncClient | None = None) -> None:
        self._cost_tracker = cost_tracker
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {DEEPINFRA_API_KEY}"},
            timeout=httpx.Timeout(90.0, connect=15.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def score(self, case: dict) -> dict | None:
        """Score a case dict. Returns score dict with 'average' or None on failure."""
        async with _semaphore:
            system_msg, user_msg = build_prompt(case)
            scores = await self._call_api(system_msg, user_msg)
            if scores is None:
                # One retry with stricter instruction
                logger.info("[judge-retry] retrying at T=0.1 for case %s", case.get("id", "?"))
                scores = await self._call_api(
                    system_msg,
                    "RESPOND ONLY WITH VALID JSON. NO PROSE.\n\n" + user_msg,
                    temperature=0.1,
                )
            if scores is None:
                logger.warning("[judge-drop] failed to score case %s", case.get("id", "?"))
            return scores

    @_make_retry()
    async def _call_api(
        self, system_msg: str, user_msg: str, temperature: float = 0.3
    ) -> dict | None:
        payload = {
            "model": JUDGE_MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        resp = await self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        self._cost_tracker.add(_UsageProxy(usage), model_kind="judge")

        raw_content = data["choices"][0]["message"].get("content", "")
        try:
            scores = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("[judge] JSON parse failed — content=%.80r", raw_content)
            return None

        if not _REQUIRED_KEYS.issubset(scores.keys()):
            missing = _REQUIRED_KEYS - scores.keys()
            logger.warning("[judge] missing score keys %s for case content=%.80r", missing, raw_content)
            return None

        # Validate range
        for key in _REQUIRED_KEYS:
            val = scores[key]
            if not isinstance(val, (int, float)) or not (0 <= val <= 10):
                logger.warning("[judge] out-of-range score %s=%s", key, val)
                return None

        scores["average"] = round(
            sum(scores[k] for k in _REQUIRED_KEYS) / len(_REQUIRED_KEYS), 2
        )
        return scores


class _UsageProxy:
    def __init__(self, usage_dict: dict) -> None:
        self.prompt_tokens = usage_dict.get("prompt_tokens", 0)
        self.completion_tokens = usage_dict.get("completion_tokens", 0)
