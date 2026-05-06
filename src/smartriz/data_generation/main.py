"""
SmarTRIZ Week 4 — Synthetic Data Generation Pipeline Entry Point.

Usage:
  # Smoke test (5 seeds, 1 round, fast)
  python -m smartriz.data_generation.main --smoke --n 5

  # Full single round
  python -m smartriz.data_generation.main --round 1 --temperature 0.7

  # Multi-round until ≥10K
  python -m smartriz.data_generation.main --auto --target 10000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SmarTRIZ synthetic data pipeline")
    p.add_argument("--smoke", action="store_true", help="Smoke-test mode (5 seeds, 1 round)")
    p.add_argument("--n", type=int, default=5, help="Number of seeds for smoke test")
    p.add_argument("--round", type=int, default=1, dest="gen_round", help="Round number")
    p.add_argument("--temperature", type=float, default=0.7, help="Generation temperature")
    p.add_argument("--auto", action="store_true", help="Run rounds until --target examples reached")
    p.add_argument("--target", type=int, default=10000, help="Target example count")
    p.add_argument("--dedup-only", action="store_true", help="Skip generation; run dedup+validate only")
    p.add_argument("--seeds", type=str, default=None,
                   help="Comma-separated seed IDs to run (e.g. AT-01,AT-02). Overrides random smoke selection.")
    return p.parse_args()


async def _run(args: argparse.Namespace) -> None:
    from smartriz.data_generation.pipeline.orchestrator import run_round
    from smartriz.data_generation.quality.deduplicator import deduplicate
    from smartriz.data_generation.quality.validator import validate_and_assemble, count_final_cases
    from smartriz.data_generation.config import TEMPERATURES

    if args.dedup_only:
        logger.info("Dedup-only mode")
        dedup_count = deduplicate()
        final_count = validate_and_assemble()
        logger.info("Dedup → %d, Final → %d", dedup_count, final_count)
        return

    seed_ids = [s.strip() for s in args.seeds.split(",")] if args.seeds else None

    if args.smoke:
        logger.info("=== SMOKE TEST (n=%d seeds%s) ===", args.n,
                    f", seeds={seed_ids}" if seed_ids else "")
        stats = await run_round(
            generation_round=args.gen_round,
            temperature=args.temperature,
            smoke=True,
            smoke_n=args.n,
            seed_ids=seed_ids,
        )
        logger.info("Smoke stats: %s", json.dumps(stats, indent=2))
        dedup_count = deduplicate()
        final_count = validate_and_assemble()
        logger.info("Smoke complete — %d final examples (after dedup+validate)", final_count)
        logger.info("MANUAL REVIEW REQUIRED before running full pipeline.")
        return

    if args.auto:
        gen_round = args.gen_round
        no_progress_rounds = 0
        while True:
            current = count_final_cases()
            if current >= args.target:
                logger.info("Target reached: %d >= %d examples", current, args.target)
                break

            temp = TEMPERATURES[(gen_round - 1) % len(TEMPERATURES)]
            logger.info("=== Round %d (T=%.1f) | current=%d target=%d ===",
                        gen_round, temp, current, args.target)
            stats = await run_round(generation_round=gen_round, temperature=temp)
            dedup_count = deduplicate()
            final_count = validate_and_assemble()
            logger.info("Round %d done — final total: %d", gen_round, final_count)
            if final_count <= current:
                no_progress_rounds += 1
                logger.warning(
                    "No dataset growth in round %d (current=%d, final=%d).",
                    gen_round,
                    current,
                    final_count,
                )
                if no_progress_rounds >= 2:
                    logger.error(
                        "Stopping auto mode after %d no-progress rounds. "
                        "Check API billing/access (e.g., HTTP 402).",
                        no_progress_rounds,
                    )
                    break
            else:
                no_progress_rounds = 0
            gen_round += 1
        return

    # Single round
    stats = await run_round(generation_round=args.gen_round, temperature=args.temperature)
    logger.info("Round stats: %s", json.dumps(stats, indent=2))
    dedup_count = deduplicate()
    final_count = validate_and_assemble()
    logger.info("Final dataset: %d examples", final_count)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
