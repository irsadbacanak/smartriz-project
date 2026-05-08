"""Shared TRIZ assistant-output formatter.

Single source of truth for how a structured TRIZ response is rendered in
SFT / DPO datasets and at inference time. Keeping this in one place prevents
the SFT and DPO notebooks from drifting on the exact <think> / heading layout.
"""
from __future__ import annotations

from typing import Iterable

SYSTEM_PROMPT = (
    "You are SmarTRIZ, an expert engineering innovation assistant. "
    "Solve technical problems using TRIZ methodology. Identify the "
    "technical contradiction, select inventive principles from the "
    "Altshuller matrix, reason step by step, and propose a solution. "
    "Output strictly in the structured TRIZ format with a <think> block "
    "and the headings Contradiction / Improving / Worsening / Inventive "
    "Principles / Solution. No conversational preamble."
)


def _join_principles(principles: Iterable[str]) -> str:
    return ", ".join(p.strip() for p in principles if p and p.strip())


def format_assistant(
    reasoning_chain: str,
    improving_parameter: str,
    worsening_parameter: str,
    inventive_principles: Iterable[str],
    solution: str,
) -> str:
    """Render a structured TRIZ assistant turn.

    The resulting string is what `chosen` and SFT targets look like.
    """
    return (
        f"<think>\n{reasoning_chain}\n</think>\n"
        f"Contradiction:\n\n"
        f"Improving: {improving_parameter}\n"
        f"Worsening: {worsening_parameter}\n\n"
        f"Inventive Principles: {_join_principles(inventive_principles)}\n"
        f"Solution:\n{solution}"
    )


def format_from_case(case: dict) -> str:
    """Convenience wrapper for a judged.jsonl / training_dataset.json record."""
    cp = case.get("contradiction_pair", {}) or {}
    return format_assistant(
        reasoning_chain=case.get("reasoning_chain", ""),
        improving_parameter=cp.get("improving_parameter", ""),
        worsening_parameter=cp.get("worsening_parameter", ""),
        inventive_principles=case.get("inventive_principles", []) or [],
        solution=case.get("solution", ""),
    )
