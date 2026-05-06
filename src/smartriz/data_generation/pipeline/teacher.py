"""
Async teacher client — wraps DeepSeek-V4-Pro via DeepInfra.

Features:
  - httpx.AsyncClient with connection pooling
  - asyncio.Semaphore for max concurrency
  - Streaming SSE — server sends headers immediately, eliminating ReadTimeout
    on slow/queued models; read timeout applies only between chunks (~seconds)
  - tenacity exponential backoff on 429 / 5xx / timeout (2 attempts)
  - JSON parse failure retry at temperature=0.3 with stricter prompt
  - Cost tracking on every successful call via stream_options include_usage
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
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
    MAX_CONCURRENCY,
    TEACHER_MODEL,
    CostTracker,
)
from smartriz.data_generation.pipeline.extractor import extract_case

logger = logging.getLogger(__name__)

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, TimeoutError))


def _make_retry():
    return retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(2),
        reraise=True,
    )


class TeacherClient:
    """Async streaming client for DeepSeek-V4-Pro."""

    def __init__(self, cost_tracker: CostTracker, client: httpx.AsyncClient | None = None) -> None:
        self._cost_tracker = cost_tracker
        self._client = client or httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {DEEPINFRA_API_KEY}"},
            timeout=httpx.Timeout(300.0, connect=15.0),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate(
        self,
        system_msg: str,
        user_msg: str,
        temperature: float,
        seed_id: str,
        method: str,
        generation_round: int,
    ) -> dict | None:
        """Generate one case. Returns extracted dict or None on irrecoverable failure."""
        async with _semaphore:
            raw = await self._call_api(system_msg, user_msg, temperature)
            if raw is None:
                return None

            case = extract_case(raw, seed_id, method, generation_round, temperature)

            if case is None:
                # One JSON-parse retry at lower temperature with stricter instruction
                logger.info("[retry] JSON/reasoning failure — retrying at T=0.3 for %s %s r%d",
                            seed_id, method, generation_round)
                raw2 = await self._call_api(
                    system_msg,
                    "RESPOND ONLY WITH VALID JSON. NO PROSE.\n\n" + user_msg,
                    temperature=0.3,
                )
                if raw2 is None:
                    return None
                case = extract_case(raw2, seed_id, method, generation_round, temperature)
                if case is None:
                    logger.warning("[drop] second attempt failed — %s %s r%d", seed_id, method, generation_round)

            return case

    @_make_retry()
    async def _call_api(self, system_msg: str, user_msg: str, temperature: float) -> Any | None:
        """Call the API using SSE streaming.

        Streaming means the server sends HTTP 200 headers immediately and then
        streams tokens. The read timeout applies between chunks, not to the full
        response time — eliminating ReadTimeout on slow/queued models.
        Usage stats are delivered in the final chunk via stream_options.
        """
        payload = {
            "model": TEACHER_MODEL,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        content_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        usage_dict: dict = {}

        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    if chunk.get("usage"):
                        usage_dict = chunk["usage"]
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    if delta.get("content"):
                        content_chunks.append(delta["content"])
                    if delta.get("reasoning_content"):
                        reasoning_chunks.append(delta["reasoning_content"])
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

        full_content = "".join(content_chunks)
        full_reasoning = "".join(reasoning_chunks) or None

        message = _MessageProxy(
            content=full_content,
            reasoning_content=full_reasoning,
        )
        result = _ResponseProxy(message=message, usage=_UsageProxy(usage_dict))
        self._cost_tracker.add(result.usage, model_kind="teacher")
        return result


class _MessageProxy:
    def __init__(self, content: str, reasoning_content: str | None) -> None:
        self.content = content
        if reasoning_content is not None:
            self.reasoning_content = reasoning_content


class _ResponseProxy:
    def __init__(self, message: _MessageProxy, usage: Any) -> None:
        self.choices = [_ChoiceProxy(message)]
        self.usage = usage


class _ChoiceProxy:
    def __init__(self, message: _MessageProxy) -> None:
        self.message = message


class _UsageProxy:
    def __init__(self, usage_dict: dict) -> None:
        self.prompt_tokens = usage_dict.get("prompt_tokens", 0)
        self.completion_tokens = usage_dict.get("completion_tokens", 0)
