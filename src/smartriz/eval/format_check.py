"""Regex-based format compliance and principle correctness checks.

Lightweight evaluator used during DPO eval and the SFT-vs-DPO regression gate.
Does NOT depend on a tokenizer or model — pure string analysis.
"""
from __future__ import annotations

import re
from typing import Iterable

from smartriz.data_generation.quality.matrix import check as matrix_check
from smartriz.data_generation.quality.matrix import parse_param_id
from smartriz.data_generation.quality.triz_kb import TRIZ_PRINCIPLES, _ALIASES

# ── Regex assets ─────────────────────────────────────────────────────────
_THINK_RE = re.compile(r"<think>[\s\S]+?</think>", re.IGNORECASE)
_HEADINGS = (
    re.compile(r"\bContradiction\s*:"),
    re.compile(r"\bImproving\s*:"),
    re.compile(r"\bWorsening\s*:"),
    re.compile(r"\bInventive\s+Principles\s*:"),
    re.compile(r"\bSolution\s*:"),
)
_PRINCIPLE_HASH_RE = re.compile(r"#\s*(\d{1,2})\b")
_INVENTIVE_LINE_RE = re.compile(
    r"Inventive\s+Principles\s*:\s*(.+?)(?:\n\s*\n|\nSolution\s*:|$)",
    re.IGNORECASE | re.DOTALL,
)
_IMPROVING_LINE_RE = re.compile(r"Improving\s*:\s*([^\n]+)", re.IGNORECASE)
_WORSENING_LINE_RE = re.compile(r"Worsening\s*:\s*([^\n]+)", re.IGNORECASE)

_CHAT_PREAMBLE_RE = re.compile(
    r"^\s*(?:thank\s+you|let'?s\s+(?:break|dive|tackle|work)|here'?s\s+how|"
    r"let\s+me\s+(?:help|walk|guide|break)|i'?ll\s+(?:help|walk|break)|"
    r"to\s+(?:address|solve|tackle)\s+(?:this|the))",
    re.IGNORECASE,
)

PRINCIPLE_RANGE = (3, 5)


def _principle_ids_from_inventive_line(line: str) -> list[int]:
    """Parse principle IDs from an 'Inventive Principles:' line content.

    Accepts both '#N Name' and bare alias forms ('Segmentation', 'Local Quality').
    """
    ids: set[int] = set()
    for m in _PRINCIPLE_HASH_RE.finditer(line):
        n = int(m.group(1))
        if 1 <= n <= 40:
            ids.add(n)
    lower = line.lower()
    for alias, num in _ALIASES.items():
        if num is None:
            continue
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            ids.add(num)
    for num, name in TRIZ_PRINCIPLES.items():
        if re.search(rf"\b{re.escape(name.lower())}\b", lower):
            ids.add(num)
    return sorted(ids)


def score_format_compliance(text: str) -> dict:
    """Score five binary format indicators on `text`.

    Returns dict with per-field booleans and an aggregate `score` in [0, 1].
    """
    has_think = bool(_THINK_RE.search(text))
    has_all_5 = all(rx.search(text) for rx in _HEADINGS)

    inv_match = _INVENTIVE_LINE_RE.search(text)
    if inv_match:
        principle_ids = _principle_ids_from_inventive_line(inv_match.group(1))
    else:
        principle_ids = []
    principle_count = len(principle_ids)
    principle_in_range = PRINCIPLE_RANGE[0] <= principle_count <= PRINCIPLE_RANGE[1]

    head = text[:200].lstrip()
    no_chat_preamble = not bool(_CHAT_PREAMBLE_RE.match(head))

    fields = {
        "has_think_block": has_think,
        "has_all_5_headings": has_all_5,
        "principle_count": principle_count,
        "principle_count_in_range": principle_in_range,
        "no_chat_preamble": no_chat_preamble,
    }
    score = sum(
        1 for v in (
            has_think, has_all_5, principle_in_range, no_chat_preamble,
            principle_count > 0,
        ) if v
    ) / 5.0
    return {**fields, "score": score, "principle_ids": principle_ids}


def score_principle_correctness(
    text: str,
    expected_improving: str | None = None,
    expected_worsening: str | None = None,
    expected_principles: Iterable[str] | None = None,
) -> dict:
    """Cross-check claimed principles against the Altshuller matrix.

    Returns:
        matrix_pass: bool — at least one claimed principle is in the real cell
                     for the parameter pair derived from the model output.
        jaccard: float — overlap with `expected_principles` (if given), else None.
    """
    inv_match = _INVENTIVE_LINE_RE.search(text)
    claimed = (
        _principle_ids_from_inventive_line(inv_match.group(1)) if inv_match else []
    )

    imp_id = wor_id = None
    imp_line = _IMPROVING_LINE_RE.search(text)
    wor_line = _WORSENING_LINE_RE.search(text)
    if imp_line:
        imp_id = parse_param_id(imp_line.group(1))
    if wor_line:
        wor_id = parse_param_id(wor_line.group(1))

    if imp_id is None and expected_improving:
        imp_id = parse_param_id(expected_improving)
    if wor_id is None and expected_worsening:
        wor_id = parse_param_id(expected_worsening)

    matrix_pass = False
    if imp_id is not None and wor_id is not None and claimed:
        matrix_pass = matrix_check(imp_id, wor_id, claimed)

    jaccard: float | None = None
    if expected_principles is not None:
        expected_ids: set[int] = set()
        for p in expected_principles:
            for m in _PRINCIPLE_HASH_RE.finditer(p):
                n = int(m.group(1))
                if 1 <= n <= 40:
                    expected_ids.add(n)
            lower = p.lower()
            for alias, num in _ALIASES.items():
                if num is None:
                    continue
                if alias in lower:
                    expected_ids.add(num)
        claim_set = set(claimed)
        if claim_set or expected_ids:
            union = claim_set | expected_ids
            jaccard = len(claim_set & expected_ids) / len(union) if union else 0.0

    return {
        "matrix_pass": matrix_pass,
        "claimed_principles": claimed,
        "improving_id": imp_id,
        "worsening_id": wor_id,
        "jaccard": jaccard,
    }


def aggregate_scores(scores: list[dict]) -> dict:
    """Aggregate per-sample format scores into mean stats for results.json."""
    n = len(scores)
    if n == 0:
        return {}
    keys = ["has_think_block", "has_all_5_headings",
            "principle_count_in_range", "no_chat_preamble"]
    per_field = {k: sum(1 for s in scores if s[k]) / n for k in keys}
    mean_score = sum(s["score"] for s in scores) / n
    chat_leak = sum(1 for s in scores if not s["no_chat_preamble"]) / n
    samples_below = sum(1 for s in scores if s["score"] < 0.6)
    return {
        "mean": mean_score,
        "per_field": per_field,
        "samples_below_0.6": samples_below,
        "chat_preamble_leak_rate": chat_leak,
    }
