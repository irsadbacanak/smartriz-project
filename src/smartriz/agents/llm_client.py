"""Ollama LLM client via OpenAI-compatible API."""
from __future__ import annotations

import json
import os
import re

import openai

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
MODEL = os.getenv("SMARTRIZ_LOCAL_MODEL", "qwen2.5:7b-instruct")

_client = openai.OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama",
    timeout=120,
)

_OLLAMA_OPTIONS = {"num_ctx": 4096, "num_predict": 1024}


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` code fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def chat_json(system: str, user: str, schema_hint: str = "") -> dict:
    """Call the model expecting a JSON object response. Retries once on parse failure."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user + (f"\n\nRespond with JSON matching: {schema_hint}" if schema_hint else "")},
    ]

    for attempt, temperature in enumerate([0.2, 0.1]):
        response = _client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            extra_body={"options": _OLLAMA_OPTIONS},
        )
        raw = response.choices[0].message.content or ""
        try:
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError:
            if attempt == 1:
                raise RuntimeError(f"Model returned invalid JSON after retry: {raw[:300]}")

    raise RuntimeError("Unreachable")


def chat_text(system: str, user: str) -> str:
    """Call the model expecting a plain text response."""
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        extra_body={"options": _OLLAMA_OPTIONS},
    )
    return (response.choices[0].message.content or "").strip()
