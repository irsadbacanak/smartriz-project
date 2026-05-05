"""
Pydantic schema validation and final dataset assembly.

Validates every case in deduplicated.jsonl against the seed schema.
Writes survivors to data/training_dataset.json as a JSON array.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from smartriz.data_generation.config import DEDUPED_JSONL, FINAL_JSON

logger = logging.getLogger(__name__)


# ── Pydantic models ────────────────────────────────────────────────────────────

class ContradictionPair(BaseModel):
    improving_parameter: str = Field(..., min_length=3)
    worsening_parameter: str = Field(..., min_length=3)


class JudgeScores(BaseModel):
    contradiction_validity: float
    principle_correctness: float
    reasoning_coherence: float
    solution_feasibility: float
    average: float


class Meta(BaseModel):
    parent_seed_id: str
    generation_method: str
    generation_temperature: float
    generation_round: int
    judge_scores: JudgeScores | None = None
    matrix_check_passed: bool | None = None


class Case(BaseModel):
    id: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    language: Literal["en", "tr", "mixed"]
    domain: str = Field(..., min_length=1)
    problem: str = Field(..., min_length=10)
    contradiction_pair: ContradictionPair
    inventive_principles: list[str] = Field(..., min_length=1)
    reasoning_chain: str = Field(..., min_length=10)
    solution: str = Field(..., min_length=10)
    complexity: Literal["simple", "medium", "complex"]
    meta: Meta | None = None

    @field_validator("inventive_principles")
    @classmethod
    def at_least_one_principle(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("inventive_principles must contain at least one entry")
        return v


# ── Validation + assembly ──────────────────────────────────────────────────────

def validate_and_assemble(
    in_path: Path = DEDUPED_JSONL,
    out_path: Path = FINAL_JSON,
) -> int:
    """Validate all cases and write final training_dataset.json. Returns count."""
    if not in_path.exists():
        logger.warning("No deduplicated file at %s", in_path)
        return 0

    valid_cases: list[dict] = []
    drop_count = 0

    with open(in_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("[drop/schema] JSON parse error line %d: %s", lineno, exc)
                drop_count += 1
                continue

            try:
                case_obj = Case.model_validate(raw)
                # Re-serialise through pydantic to ensure clean output
                case_dict = case_obj.model_dump(exclude_none=False)
                valid_cases.append(case_dict)
            except ValidationError as exc:
                logger.warning("[drop/schema] validation failed line %d id=%s: %s",
                               lineno, raw.get("id", "?"), exc)
                drop_count += 1

    logger.info("Schema validation: %d valid, %d dropped", len(valid_cases), drop_count)

    final = {
        "dataset_name": "SmarTRIZ-Synthetic-v1",
        "total_cases": len(valid_cases),
        "cases": valid_cases,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    logger.info("Final dataset written to %s (%d cases)", out_path, len(valid_cases))
    return len(valid_cases)


def count_final_cases(path: Path = FINAL_JSON) -> int:
    """Return number of cases in the current final dataset file."""
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("total_cases", len(data.get("cases", [])))
    except (json.JSONDecodeError, KeyError):
        return 0
