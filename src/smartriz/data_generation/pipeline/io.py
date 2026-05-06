"""
JSONL append helpers and checkpoint (processed_keys) read/write utilities.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smartriz.data_generation.config import PROCESSED_KEYS, REJECTED_JSONL

# ── Reason codes (exhaustive list) ───────────────────────────────────────────
# Stage: teacher
REASON_TEACHER_TASK_ERROR = "teacher_task_error"
REASON_PARSE_ERROR = "parse_error"
REASON_CP_COPY = "copy_from_seed"

# Stage: judge
REASON_JUDGE_FAIL = "judge_fail_high_confidence"
REASON_JUDGE_SCORING_ERROR = "judge_scoring_error"

# Stage: matrix
REASON_MATRIX_STRUCTURAL = "matrix_structural"
REASON_MATRIX_CITATION = "matrix_citation"

# Stage: principle
REASON_PRINCIPLE_INVALID = "principle_invalid"

# Stage: complexity
REASON_COMPLEXITY_INVALID = "complexity_invalid"


def load_processed_keys(path: Path = PROCESSED_KEYS) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_processed_key(key: str, path: Path = PROCESSED_KEYS) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def append_jsonl(record: dict, path: Path) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_reject(
    case: dict | None,
    *,
    stage: str,
    reason_code: str,
    reason_text: str,
    extra_meta: dict[str, Any] | None = None,
    path: Path = REJECTED_JSONL,
) -> None:
    """Write a rejected case to the centralised rejected_dataset.jsonl.

    Schema (every field always present):
      id            – case id or '' if unavailable
      stage         – pipeline stage that rejected (e.g. 'judge', 'matrix', ...)
      reason_code   – stable code from the REASON_* constants above
      reason_text   – human-readable explanation
      timestamp     – ISO-8601 UTC
      case          – the full case dict (may be None / empty if not available)
      extra_meta    – arbitrary stage-specific info (fail_reasons, confidence, …)
    """
    record: dict[str, Any] = {
        "id": (case or {}).get("id", ""),
        "stage": stage,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case": case or {},
        "extra_meta": extra_meta or {},
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
