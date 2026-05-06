"""
Async judge client — wraps Qwen2.5-72B-Instruct via DeepInfra.

Features:
  - Binary pass/fail rubric (5 YES/NO questions: Q1-Q5)
  - Returns verdict dict with PASS/FAIL and per-question answers
  - None returned for FAIL cases — caller drops them from dataset
  - Same retry / concurrency / cost-tracking setup as teacher
  - Backward-compat fallback: old 0-10 numeric responses treated with 7.0 threshold
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

# Old-format keys (0-10 numeric scores) — used for backward-compat fallback
_OLD_REQUIRED_KEYS = {
    "contradiction_validity",
    "principle_correctness",
    "reasoning_coherence",
    "solution_feasibility",
}

# New binary question keys
_NEW_QUESTION_KEYS = {
    "Q1_principles_canonical",
    "Q2_reasoning_uses_all_principles",
    "Q3_contradiction_domain_match",
    "Q4_solution_not_forced_fit",
    "Q5_reasoning_not_template",
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
    """Async client for the binary pass/fail Qwen2.5-72B judge."""

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
        """Score a case dict.

        Returns:
            dict with 'verdict' == 'PASS' and per-question answers, or
            None if the case FAILS or the API call fails entirely.
        """
        async with _semaphore:
            system_msg, user_msg = build_prompt(case)
            result = await self._call_api(system_msg, user_msg)
            if result is None:
                # One retry with stricter instruction
                logger.info("[judge-retry] retrying at T=0.1 for case %s", case.get("id", "?"))
                result = await self._call_api(
                    system_msg,
                    "RESPOND ONLY WITH VALID JSON. NO PROSE.\n\n" + user_msg,
                    temperature=0.1,
                )
            if result is None:
                logger.warning("[judge-drop] failed to score case %s", case.get("id", "?"))
            return result

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
            result = json.loads(raw_content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("[judge] JSON parse failed — content=%.80r", raw_content)
            return None

        # ── New binary verdict schema ────────────────────────────────────────
        if "verdict" in result or _NEW_QUESTION_KEYS.intersection(result.keys()):
            verdict = result.get("verdict", "FAIL").upper().strip()

            if verdict == "FAIL":
                fail_reasons = result.get("fail_reasons", [])
                logger.info(
                    "[judge-fail] case rejected — reasons: %s",
                    fail_reasons if fail_reasons else "(none provided)",
                )
                return None  # Drop the case

            if verdict == "PASS":
                return {
                    "verdict": "PASS",
                    "Q1": result.get("Q1_principles_canonical", "?"),
                    "Q2": result.get("Q2_reasoning_uses_all_principles", "?"),
                    "Q3": result.get("Q3_contradiction_domain_match", "?"),
                    "Q4": result.get("Q4_solution_not_forced_fit", "?"),
                    "Q5": result.get("Q5_reasoning_not_template", "?"),
                    "fail_reasons": result.get("fail_reasons", []),
                    "average": 10.0,  # Backward compat: PASS cases get 10.0 for downstream meta
                }

            # Unknown verdict value — treat as FAIL for safety
            logger.warning("[judge] unknown verdict value %r — treating as FAIL", verdict)
            return None

        # ── Backward-compat fallback: old 0-10 numeric format ────────────────
        if _OLD_REQUIRED_KEYS.issubset(result.keys()):
            logger.info("[judge] received old 0-10 format response — applying 7.0 threshold")

            for key in _OLD_REQUIRED_KEYS:
                val = result[key]
                if not isinstance(val, (int, float)) or not (0 <= val <= 10):
                    logger.warning("[judge] out-of-range score %s=%s", key, val)
                    return None

            average = round(
                sum(result[k] for k in _OLD_REQUIRED_KEYS) / len(_OLD_REQUIRED_KEYS), 2
            )
            result["average"] = average

            if average < 7.0:
                logger.info("[judge-fail] old-format case rejected — average=%.2f < 7.0", average)
                return None

            return {
                **result,  # Keep original numeric scores for debugging
                "verdict": "PASS",
                "Q1": "YES",  # Inferred from passing threshold
                "Q2": "YES",
                "Q3": "YES",
                "Q4": "YES",
                "Q5": "YES",
                "fail_reasons": [],
                "average": average,
            }

        # No recognized schema
        missing_new = _NEW_QUESTION_KEYS - result.keys()
        missing_old = _OLD_REQUIRED_KEYS - result.keys()
        logger.warning(
            "[judge] unrecognized response schema — missing new keys %s, missing old keys %s",
            missing_new,
            missing_old,
        )
        return None


class _UsageProxy:
    def __init__(self, usage_dict: dict) -> None:
        self.prompt_tokens = usage_dict.get("prompt_tokens", 0)
        self.completion_tokens = usage_dict.get("completion_tokens", 0)
