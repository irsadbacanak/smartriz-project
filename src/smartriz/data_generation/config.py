"""
Pipeline configuration: API keys, model names, paths, hyperparameters, cost tracking.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from dotenv import load_dotenv

# ── Environment ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

DEEPINFRA_API_KEY: str = os.environ["DEEPINFRA_API_KEY"]

# ── API ──────────────────────────────────────────────────────────────────────
BASE_URL = "https://api.deepinfra.com/v1/openai"
TEACHER_MODEL = "deepseek-ai/DeepSeek-V4-Pro"  # Top reasoning model (Quality: 51.51)
JUDGE_MODEL = "Qwen/Qwen2.5-72B-Instruct"  # Different family from DeepSeek teacher

# ── Pricing (USD per 1M tokens) ───────────────────────────────────────────────
TEACHER_IN_PER_M = 1.40  # DeepSeek-V4-Pro pricing
TEACHER_OUT_PER_M = 1.40
JUDGE_IN_PER_M = 0.35   # Qwen2.5-72B DeepInfra pricing
JUDGE_OUT_PER_M = 0.40

# ── Hyperparameters ───────────────────────────────────────────────────────────
MAX_CONCURRENCY = 15
JUDGE_THRESHOLD = 7.0
DEDUP_COSINE = 0.85
TEMPERATURES = [0.7, 0.9, 1.1, 1.3]
HARD_STOP_USD = 30.0

# ── Data paths ────────────────────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
SEED_PATH = DATA_DIR / "seed_dataset.json"
RAW_JSONL = DATA_DIR / "raw_generations.jsonl"
JUDGED_JSONL = DATA_DIR / "judged.jsonl"
MATRIX_VALIDATED_JSONL = DATA_DIR / "matrix_validated.jsonl"
DEDUPED_JSONL = DATA_DIR / "deduplicated.jsonl"
FINAL_JSON = DATA_DIR / "training_dataset.json"
PROCESSED_KEYS = DATA_DIR / "processed_keys.txt"


# ── Cost tracker ──────────────────────────────────────────────────────────────
class CostTracker:
    """Thread-safe running cost accumulator.

    Usage::

        tracker = CostTracker()
        total = tracker.add(usage, model_kind="teacher")
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_usd: float = 0.0
        self._call_count: int = 0

    def add(self, usage, model_kind: str) -> float:
        """Add cost from one API response's usage object and return running total.

        Raises RuntimeError if HARD_STOP_USD is reached.
        """
        prompt_tokens: int = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens: int = getattr(usage, "completion_tokens", 0) or 0

        if model_kind == "teacher":
            cost = (prompt_tokens * TEACHER_IN_PER_M + completion_tokens * TEACHER_OUT_PER_M) / 1_000_000
        elif model_kind == "judge":
            cost = (prompt_tokens * JUDGE_IN_PER_M + completion_tokens * JUDGE_OUT_PER_M) / 1_000_000
        else:
            raise ValueError(f"Unknown model_kind: {model_kind!r}")

        with self._lock:
            self._total_usd += cost
            self._call_count += 1
            total = self._total_usd
            count = self._call_count

        if count % 100 == 0:
            print(f"[cost] {count} çağrı tamamlandı — toplam: ${total:.4f}")

        if total >= HARD_STOP_USD:
            raise RuntimeError(
                f"Hard stop: toplam maliyet ${total:.4f} >= ${HARD_STOP_USD}. Pipeline durduruldu."
            )

        return total

    @property
    def total(self) -> float:
        with self._lock:
            return self._total_usd

    @property
    def call_count(self) -> int:
        with self._lock:
            return self._call_count
