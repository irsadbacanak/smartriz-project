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
import time
from pathlib import Path

# ── Terminal logger (full verbosity) ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

# ── Summary file logger (özet, append) ───────────────────────────────────────
# Geç import: config modülünü en erken noktada yükle ki DATA_DIR hazır olsun
def _setup_summary_logger() -> logging.Logger:
    from smartriz.data_generation.config import SUMMARY_LOG
    summary_logger = logging.getLogger("pipeline.summary")
    summary_logger.setLevel(logging.INFO)
    summary_logger.propagate = False  # terminal'e tekrar yazmasın
    if not summary_logger.handlers:
        fh = logging.FileHandler(SUMMARY_LOG, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        summary_logger.addHandler(fh)
    return summary_logger


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


def _emit_round_summary(
    slog: logging.Logger,
    stats: dict,
    final_count: int,
    reject_count: int,
    run_duration_sec: float,
) -> None:
    """Tek satırlık özet logu yaz — hem terminal hem summary dosyası."""
    line = (
        f"[ROUND_SUMMARY] "
        f"round={stats.get('round')} "
        f"temp={stats.get('temperature')} "
        f"raw={stats.get('raw_generated')} "
        f"judge_passed={stats.get('judge_passed')} "
        f"borderline={stats.get('borderline_count')} "
        f"matrix_passed={stats.get('matrix_passed')} "
        f"final={final_count} "
        f"rejected={reject_count} "
        f"cost_usd={stats.get('total_cost_usd', 0):.4f} "
        f"calls={stats.get('total_calls')} "
        f"duration_sec={run_duration_sec:.1f} "
        f"stage_sec={json.dumps({k: v for k, v in stats.items() if k.endswith('_sec')})}"
    )
    logger.info(line)
    slog.info(line)


async def _run(args: argparse.Namespace) -> None:
    from smartriz.data_generation.pipeline.orchestrator import run_round
    from smartriz.data_generation.quality.deduplicator import deduplicate
    from smartriz.data_generation.quality.validator import validate_and_assemble, count_final_cases
    from smartriz.data_generation.config import TEMPERATURES, REJECTED_JSONL

    slog = _setup_summary_logger()

    def _count_rejected() -> int:
        p = REJECTED_JSONL
        if not p.exists():
            return 0
        return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())

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
        slog.info("[RUN_START] mode=smoke n=%d", args.n)
        t0 = time.monotonic()
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
        elapsed = time.monotonic() - t0
        reject_count = _count_rejected()
        _emit_round_summary(slog, stats, final_count, reject_count, elapsed)
        slog.info("[RUN_END] mode=smoke final=%d cost_usd=%.4f duration_sec=%.1f",
                  final_count, stats.get("total_cost_usd", 0), elapsed)
        logger.info("Smoke complete — %d final examples (after dedup+validate)", final_count)
        logger.info("MANUAL REVIEW REQUIRED before running full pipeline.")
        return

    if args.auto:
        gen_round = args.gen_round
        no_progress_rounds = 0
        run_t0 = time.monotonic()
        initial_count = count_final_cases()
        slog.info("[RUN_START] mode=auto target=%d current=%d", args.target, initial_count)

        while True:
            current = count_final_cases()
            if current >= args.target:
                logger.info("Target reached: %d >= %d examples", current, args.target)
                break

            temp = TEMPERATURES[(gen_round - 1) % len(TEMPERATURES)]
            logger.info("=== Round %d (T=%.1f) | current=%d target=%d ===",
                        gen_round, temp, current, args.target)
            round_t0 = time.monotonic()
            stats = await run_round(generation_round=gen_round, temperature=temp)
            dedup_count = deduplicate()
            final_count = validate_and_assemble()
            elapsed = time.monotonic() - round_t0
            reject_count = _count_rejected()
            _emit_round_summary(slog, stats, final_count, reject_count, elapsed)
            logger.info("Round %d done — final total: %d", gen_round, final_count)

            if final_count <= current:
                no_progress_rounds += 1
                logger.warning(
                    "No dataset growth in round %d (current=%d, final=%d).",
                    gen_round, current, final_count,
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

        total_elapsed = time.monotonic() - run_t0
        final_count = count_final_cases()
        slog.info("[RUN_END] mode=auto rounds_done=%d final=%d cost_cumulative=unknown duration_sec=%.1f",
                  gen_round - args.gen_round, final_count, total_elapsed)
        return

    # Single round
    t0 = time.monotonic()
    slog.info("[RUN_START] mode=single round=%d temp=%.1f", args.gen_round, args.temperature)
    stats = await run_round(generation_round=args.gen_round, temperature=args.temperature)
    logger.info("Round stats: %s", json.dumps(stats, indent=2))
    dedup_count = deduplicate()
    final_count = validate_and_assemble()
    elapsed = time.monotonic() - t0
    reject_count = _count_rejected()
    _emit_round_summary(slog, stats, final_count, reject_count, elapsed)
    slog.info("[RUN_END] mode=single final=%d cost_usd=%.4f duration_sec=%.1f",
              final_count, stats.get("total_cost_usd", 0), elapsed)
    logger.info("Final dataset: %d examples", final_count)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
