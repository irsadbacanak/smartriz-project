"""
Pipeline orchestrator — wires teacher → judge → matrix → JSONL streaming.

Design principles:
  - asyncio.gather for teacher calls (up to MAX_CONCURRENCY concurrent)
  - JSONL append immediately on receipt — no in-memory accumulation >100 records
  - processed_keys.txt for crash-safe restart (skips already-completed tasks)
  - Lineage meta on every record
  - $30 hard-stop propagated from CostTracker
  - Drop logging: every dropped record is logged with a reason
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import AsyncIterator

import httpx

from smartriz.data_generation.config import (
    BASE_URL,
    DATA_DIR,
    DEEPINFRA_API_KEY,
    JUDGE_THRESHOLD,
    PROCESSED_KEYS,
    RAW_JSONL,
    JUDGED_JSONL,
    MATRIX_VALIDATED_JSONL,
    SEED_PATH,
    CostTracker,
)
from smartriz.data_generation.pipeline.teacher import TeacherClient
from smartriz.data_generation.pipeline.judge import JudgeClient
from smartriz.data_generation.quality.matrix import check, parse_param_id, parse_principle_id

logger = logging.getLogger(__name__)


# ── Seed loading ──────────────────────────────────────────────────────────────

def load_seeds(path: Path = SEED_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", data) if isinstance(data, dict) else data
    logger.info("Loaded %d seed cases from %s", len(cases), path)
    return cases


# ── Checkpoint helpers ────────────────────────────────────────────────────────

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


# ── Task generation ────────────────────────────────────────────────────────────

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


# ── Single teacher call ────────────────────────────────────────────────────────

async def _run_teacher_task(
    task: dict,
    teacher: TeacherClient,
    processed_keys: set[str],
    temperature: float,
) -> list[dict]:
    """Execute one teacher task (self-instruct or evol). Returns list of produced cases."""
    from smartriz.data_generation.prompts.self_instruct import build_prompt as si_prompt
    from smartriz.data_generation.prompts.evol_deepening import build_prompt as deep_prompt
    from smartriz.data_generation.prompts.evol_constraint import build_prompt as const_prompt
    from smartriz.data_generation.prompts.evol_cross_domain import build_prompt as xdom_prompt

    seed = task["seed"]
    method = task["method"]
    gen_round = task["round"]
    variation = task.get("variation")  # present for evol tasks

    seed_id = seed.get("id", "UNKNOWN")
    key = f"{seed_id}_{method}_{gen_round}"
    if variation:
        key += f"_{variation.get('id', '')}"

    if key in processed_keys:
        logger.debug("[skip] already processed: %s", key)
        return []

    # Build prompt
    if method == "self_instruct":
        sys_msg, user_msg = si_prompt(seed, temperature_hint=temperature)
    elif method == "evol_deepening":
        sys_msg, user_msg = deep_prompt(variation)
    elif method == "evol_constraint":
        sys_msg, user_msg = const_prompt(variation)
    elif method == "evol_cross_domain":
        sys_msg, user_msg = xdom_prompt(variation)
    else:
        logger.error("Unknown method: %s", method)
        return []

    try:
        if method == "self_instruct":
            # Teacher returns {"variations": [...]} — split into individual cases
            raw = await teacher.generate(sys_msg, user_msg, temperature, seed_id, method, gen_round)
            cases = _split_self_instruct(raw, seed, gen_round, temperature)
        else:
            raw = await teacher.generate(sys_msg, user_msg, temperature, seed_id, method, gen_round)
            cases = [raw] if raw is not None else []
    except RuntimeError as exc:
        # Hard-stop from cost tracker
        logger.critical("HARD STOP: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.warning("[error] task %s failed: %s", key, exc)
        cases = []

    for c in cases:
        append_jsonl(c, RAW_JSONL)

    if cases:
        append_processed_key(key, PROCESSED_KEYS)
    return cases


def _split_self_instruct(raw: dict | None, seed: dict, gen_round: int, temperature: float) -> list[dict]:
    """Split a self-instruct response ({"variations": [...]}) into individual case dicts."""
    if raw is None:
        return []

    # The extractor already ran on the outer JSON — but for self-instruct the
    # model returns a wrapper object. We need to handle both cases:
    # Case A: extractor found a top-level "variations" key in the JSON content
    # Case B: extractor returned the raw dict (which may contain "variations")

    seed_id = seed.get("id", "UNKNOWN")

    # If the dict itself has "variations", use that
    if "variations" in raw:
        variations = raw["variations"]
    else:
        # Wrap it as a single variation
        variations = [raw]

    # Normalize model output shape drift:
    # - {"variations": {...}}  -> wrap single object into list
    # - {"variations": "<json>"} -> best-effort parse JSON string payload
    if isinstance(variations, dict):
        variations = [variations]
    elif isinstance(variations, str):
        try:
            parsed = json.loads(variations)
            if isinstance(parsed, dict):
                variations = [parsed]
            elif isinstance(parsed, list):
                variations = parsed
            else:
                variations = []
        except json.JSONDecodeError:
            variations = []

    results = []
    for i, var in enumerate(variations, start=1):
        if isinstance(var, str):
            try:
                parsed_var = json.loads(var)
                var = parsed_var
            except json.JSONDecodeError:
                pass
        if not isinstance(var, dict):
            logger.warning("[drop] variation %d is not a dict — seed=%s", i, seed_id)
            continue
        var.setdefault("id", f"GEN-{seed_id}-SI-{i}")
        var.setdefault("source", "self_instruct_generated")
        var["meta"] = {
            "parent_seed_id": seed_id,
            "generation_method": "self_instruct",
            "generation_temperature": temperature,
            "generation_round": gen_round,
            "judge_scores": None,
            "matrix_check_passed": None,
        }
        if "reasoning_chain" not in var:
            # reasoning may be in the outer raw's reasoning_chain if extractor put it there
            rc = raw.get("reasoning_chain", "")
            var["reasoning_chain"] = rc
        results.append(var)

    return results


# ── Judge sweep ───────────────────────────────────────────────────────────────

async def judge_sweep(
    judge: JudgeClient,
    in_path: Path = RAW_JSONL,
    out_path: Path = JUDGED_JSONL,
) -> int:
    """Read raw_generations.jsonl line-by-line, judge, write to judged.jsonl. Returns count."""
    if not in_path.exists():
        logger.warning("No raw generations file at %s", in_path)
        return 0

    # Track which case IDs have already been judged
    already_judged: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                already_judged.add(d.get("id", ""))
            except json.JSONDecodeError:
                pass

    count = 0
    CHUNK = 50  # judge in batches of 50

    async def _judge_one(case: dict) -> dict | None:
        scores = await judge.score(case)
        if scores is None:
            logger.warning("[drop/judge] scoring failed — id=%s", case.get("id", "?"))
            return None
        if scores["average"] < JUDGE_THRESHOLD:
            logger.info("[drop/judge] avg=%.2f < %.1f — id=%s", scores["average"], JUDGE_THRESHOLD, case.get("id", "?"))
            return None
        case["meta"]["judge_scores"] = scores
        return case

    buffer: list[dict] = []

    with open(in_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue

            case_id = case.get("id", "")
            if case_id in already_judged:
                continue

            buffer.append(case)
            if len(buffer) >= CHUNK:
                results = await asyncio.gather(*[_judge_one(c) for c in buffer])
                for r in results:
                    if r is not None:
                        append_jsonl(r, out_path)
                        count += 1
                buffer = []

    if buffer:
        results = await asyncio.gather(*[_judge_one(c) for c in buffer])
        for r in results:
            if r is not None:
                append_jsonl(r, out_path)
                count += 1

    logger.info("Judge sweep: %d cases passed", count)
    return count


# ── Matrix check sweep ────────────────────────────────────────────────────────

def matrix_check_sweep(
    in_path: Path = JUDGED_JSONL,
    out_path: Path = MATRIX_VALIDATED_JSONL,
) -> int:
    """Apply Altshuller matrix sanity check. Returns count of passing cases."""
    if not in_path.exists():
        return 0

    already_validated: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                already_validated.add(d.get("id", ""))
            except json.JSONDecodeError:
                pass

    count = 0
    with open(in_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue

            if case.get("id", "") in already_validated:
                continue

            if not _run_matrix_check(case):
                logger.info("[drop/matrix] matrix check failed — id=%s", case.get("id", "?"))
                continue

            case["meta"]["matrix_check_passed"] = True
            append_jsonl(case, out_path)
            count += 1

    logger.info("Matrix check: %d cases passed", count)
    return count


def _run_matrix_check(case: dict) -> bool:
    cp = case.get("contradiction_pair", {})
    imp_str = cp.get("improving_parameter", "")
    wor_str = cp.get("worsening_parameter", "")
    imp_id = parse_param_id(imp_str)
    wor_id = parse_param_id(wor_str)

    if imp_id is None or wor_id is None:
        logger.warning("[drop/matrix] cannot parse param ids — imp=%r wor=%r id=%s",
                       imp_str, wor_str, case.get("id", "?"))
        return False

    principles_raw = case.get("inventive_principles", [])
    principle_ids = [parse_principle_id(p) for p in principles_raw]
    principle_ids = [p for p in principle_ids if p is not None]

    if not principle_ids:
        logger.warning("[drop/matrix] no parseable principle ids — id=%s", case.get("id", "?"))
        return False

    return check(imp_id, wor_id, principle_ids)


# ── Main orchestration entry point ────────────────────────────────────────────

async def run_round(
    generation_round: int,
    temperature: float,
    smoke: bool = False,
    smoke_n: int = 5,
) -> dict:
    """Run a full pipeline round. Returns stats dict."""
    seeds = load_seeds()
    if smoke:
        seeds = seeds[:smoke_n]
        logger.info("SMOKE MODE: using %d seeds", len(seeds))

    processed_keys = load_processed_keys()
    cost_tracker = CostTracker()

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {DEEPINFRA_API_KEY}"},
        timeout=httpx.Timeout(120.0, connect=15.0),
    ) as http_client:
        teacher = TeacherClient(cost_tracker, client=http_client)

        # Stage 1: self-instruct (all seeds in parallel)
        logger.info("Stage 1: self-instruct for %d seeds (T=%.1f, round=%d)",
                    len(seeds), temperature, generation_round)
        si_tasks = [
            _run_teacher_task(
                {"seed": s, "method": "self_instruct", "round": generation_round},
                teacher, processed_keys, temperature,
            )
            for s in seeds
        ]
        si_results_nested = await asyncio.gather(*si_tasks, return_exceptions=True)
        si_variations: list[dict] = []
        for r in si_results_nested:
            if isinstance(r, BaseException):
                logger.warning("[error] self-instruct task exception: %s", r)
            else:
                si_variations.extend(r)

        logger.info("Stage 1 complete: %d variations", len(si_variations))

        # Stage 2: evol tasks (deepening, constraint, cross-domain) per variation
        evol_tasks = []
        for var in si_variations:
            seed_id = var.get("meta", {}).get("parent_seed_id", "UNKNOWN")
            seed = next((s for s in seeds if s["id"] == seed_id), seeds[0])
            for method in ("evol_deepening", "evol_constraint", "evol_cross_domain"):
                evol_tasks.append(
                    _run_teacher_task(
                        {"seed": seed, "method": method, "round": generation_round, "variation": var},
                        teacher, processed_keys, temperature,
                    )
                )

        logger.info("Stage 2: %d evol tasks (T=%.1f)", len(evol_tasks), temperature)
        evol_results_nested = await asyncio.gather(*evol_tasks, return_exceptions=True)
        evol_count = 0
        for r in evol_results_nested:
            if isinstance(r, BaseException):
                logger.warning("[error] evol task exception: %s", r)
            else:
                evol_count += len(r)

        logger.info("Stage 2 complete: %d evol cases raw", evol_count)

    total_raw = si_variations.__len__() + evol_count

    # Stage 4: judge sweep
    logger.info("Stage 4: judge sweep")
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {DEEPINFRA_API_KEY}"},
        timeout=httpx.Timeout(90.0, connect=15.0),
    ) as http_client2:
        judge = JudgeClient(cost_tracker, client=http_client2)
        judged_count = await judge_sweep(judge)

    # Stage 5.1: matrix check
    logger.info("Stage 5.1: matrix check")
    matrix_count = matrix_check_sweep()

    stats = {
        "round": generation_round,
        "temperature": temperature,
        "seeds_used": len(seeds),
        "raw_generated": total_raw,
        "judge_passed": judged_count,
        "matrix_passed": matrix_count,
        "total_cost_usd": cost_tracker.total,
        "total_calls": cost_tracker.call_count,
    }
    logger.info("Round %d done — %s", generation_round, stats)
    return stats
