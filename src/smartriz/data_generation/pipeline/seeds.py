"""
Seed dataset loading, round-robin scheduling, and variation-history initialisation.
"""
from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from pathlib import Path

from smartriz.data_generation.config import SEED_PATH

logger = logging.getLogger(__name__)


def load_seeds(path: Path = SEED_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", data) if isinstance(data, dict) else data
    logger.info("Loaded %d seed cases from %s", len(cases), path)
    return cases


class SeedScheduler:
    """Round-robin seed selector with per-seed usage cap.

    Ensures uniform seed coverage before any seed is selected a second time.
    Uses least-used-first policy within each tier.
    """

    def __init__(self, seeds: list[dict], max_per_seed: int = 3) -> None:
        self.seeds = seeds
        self.max_per_seed = max_per_seed
        self.usage: dict[str, int] = defaultdict(int)

    def next_seed(self) -> dict | None:
        """Return next seed. Returns None when all seeds have reached max_per_seed."""
        available = [s for s in self.seeds if self.usage[s["id"]] < self.max_per_seed]
        if not available:
            return None
        min_usage = min(self.usage[s["id"]] for s in available)
        candidates = [s for s in available if self.usage[s["id"]] == min_usage]
        chosen = random.choice(candidates)
        self.usage[chosen["id"]] += 1
        return chosen

    def all_seeds_for_round(self) -> list[dict]:
        """Return all available seeds for one full round (each selected once)."""
        available = [s for s in self.seeds if self.usage[s["id"]] < self.max_per_seed]
        random.shuffle(available)
        for s in available:
            self.usage[s["id"]] += 1
        return available


def build_initial_variation_history(seeds: list[dict]) -> dict[str, list[str]]:
    """
    Pre-seed variation_history so the very first SI call per seed already
    treats the seed's own contradiction pair as 'used'.

    Without this, the first call has an empty used_contradictions list and the
    generator sees the seed's contradiction pair in the JSON payload with nothing
    blocking it from copying it verbatim.

    Returns: seed_id → list of "imp|wor" strings (one entry per seed).
    """
    history: dict[str, list[str]] = defaultdict(list)
    for seed in seeds:
        cp = seed.get("contradiction_pair", {})
        imp = cp.get("improving_parameter", "").strip()
        wor = cp.get("worsening_parameter", "").strip()
        if imp and wor:
            history[seed["id"]].append(f"{imp}|{wor}")
    return history


def build_tasks(seeds: list[dict], generation_round: int) -> list[dict]:
    """Return list of task descriptors for one pipeline round."""
    tasks = []
    for seed in seeds:
        # Stage 1: self-instruct (5 variations generated in one call, split below)
        tasks.append({
            "seed": seed,
            "method": "self_instruct",
            "round": generation_round,
        })
        # Stages 2A/2B/2C are scheduled after self-instruct results arrive
    return tasks
