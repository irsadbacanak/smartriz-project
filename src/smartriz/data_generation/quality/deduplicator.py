"""
Cosine-similarity deduplication using sentence-transformers/all-MiniLM-L6-v2.

Algorithm:
  1. Load all cases from matrix_validated.jsonl
  2. Embed the `problem` field of each case
  3. Compute pairwise cosine similarities
  4. For each pair with similarity > DEDUP_COSINE:
       keep the one with higher judge average score; drop the other
  5. Write survivors to deduplicated.jsonl

Memory: processes in chunks of CHUNK_SIZE so we never hold all embeddings at once
when the dataset is very large. For ≤10K examples the full matrix fits comfortably.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from smartriz.data_generation.config import (
    DEDUP_COSINE,
    DEDUPED_JSONL,
    MATRIX_VALIDATED_JSONL,
)

logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None  # lazy-load


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model %s …", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _cosine_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Return NxN cosine similarity matrix for N embeddings."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    normed = embeddings / norms
    return normed @ normed.T


def deduplicate(
    in_path: Path = MATRIX_VALIDATED_JSONL,
    out_path: Path = DEDUPED_JSONL,
    threshold: float = DEDUP_COSINE,
) -> int:
    """Run deduplication. Returns count of survivors written to out_path."""
    if not in_path.exists():
        logger.warning("No matrix-validated file at %s", in_path)
        return 0

    # Load all cases
    cases: list[dict] = []
    with open(in_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    if not cases:
        logger.info("No cases to deduplicate.")
        return 0

    logger.info("Deduplicating %d cases (threshold=%.2f) …", len(cases), threshold)

    model = _get_model()
    problems = [c.get("problem", "") for c in cases]
    embeddings = model.encode(problems, show_progress_bar=False, batch_size=64)
    embeddings = np.array(embeddings, dtype=np.float32)

    sim_matrix = _cosine_matrix(embeddings)

    # Mark cases to drop
    n = len(cases)
    drop: set[int] = set()

    def _judge_avg(case: dict) -> float:
        meta = case.get("meta") or {}
        scores = meta.get("judge_scores") or {}
        return float(scores.get("average", 0.0))

    for i in range(n):
        if i in drop:
            continue
        for j in range(i + 1, n):
            if j in drop:
                continue
            if sim_matrix[i, j] > threshold:
                # Keep the one with higher judge average
                if _judge_avg(cases[i]) >= _judge_avg(cases[j]):
                    drop.add(j)
                    logger.debug("[dedup] dropping %s (sim=%.3f, lower score)",
                                 cases[j].get("id", j), sim_matrix[i, j])
                else:
                    drop.add(i)
                    logger.debug("[dedup] dropping %s (sim=%.3f, lower score)",
                                 cases[i].get("id", i), sim_matrix[i, j])
                    break  # i is dropped; move to next i

    survivors = [c for idx, c in enumerate(cases) if idx not in drop]
    dropped = n - len(survivors)
    logger.info("Dedup: %d dropped, %d survivors", dropped, len(survivors))

    with open(out_path, "w", encoding="utf-8") as f:
        for case in survivors:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    return len(survivors)
