"""
Pipeline orchestrator — wires teacher → judge → quality sweeps → JSONL streaming.

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
import random
import sys
import time
import uuid
from collections import Counter, defaultdict

import httpx

from smartriz.data_generation.config import (
    BASE_URL,
    BORDERLINE_JSONL,
    DEEPINFRA_API_KEY,
    JUDGED_JSONL,
    MATRIX_VALIDATED_JSONL,
    RAW_JSONL,
    CostTracker,
)
from smartriz.data_generation.pipeline.io import (
    append_jsonl,
    append_processed_key,
    append_reject,
    load_processed_keys,
    REASON_TEACHER_TASK_ERROR,
    REASON_CP_COPY,
    REASON_JUDGE_FAIL,
    REASON_JUDGE_SCORING_ERROR,
)
from smartriz.data_generation.pipeline.seeds import (
    SeedScheduler,
    build_initial_variation_history,
    load_seeds,
)
from smartriz.data_generation.pipeline.sweeps import (
    complexity_validation_sweep,
    contradiction_copy_sweep,
    matrix_check_sweep,
    principle_validation_sweep,
)
from smartriz.data_generation.pipeline.teacher import TeacherClient
from smartriz.data_generation.pipeline.judge import JudgeClient
from smartriz.data_generation.quality.triz_kb import validate_no_contradiction_copying

logger = logging.getLogger(__name__)


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
    variation = task.get("variation")

    seed_id = seed.get("id", "UNKNOWN")
    key = f"{seed_id}_{method}_{gen_round}"
    if variation:
        key += f"_{variation.get('id', '')}"

    if key in processed_keys:
        logger.debug("[skip] already processed: %s", key)
        return []

    if method == "self_instruct":
        used_c = task.get("used_contradictions", [])
        used_s = task.get("used_solutions", [])
        sys_msg, user_msg = si_prompt(
            seed,
            temperature_hint=temperature,
            used_contradictions=used_c,
            used_solutions=used_s,
        )
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
            raw = await teacher.generate(sys_msg, user_msg, temperature, seed_id, method, gen_round)
            cases = _split_self_instruct(raw, seed, gen_round, temperature)
        else:
            raw = await teacher.generate(sys_msg, user_msg, temperature, seed_id, method, gen_round)
            cases = [raw] if raw is not None else []
            for c in cases:
                if isinstance(c, dict):
                    existing_id = c.get("id", "")
                    short_uuid = str(uuid.uuid4())[:8]
                    c["id"] = f"{existing_id}-R{gen_round:02d}-{short_uuid}" if existing_id else f"GEN-UNKNOWN-R{gen_round:02d}-{short_uuid}"
    except RuntimeError as exc:
        logger.critical("HARD STOP: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.warning("[error] task %s failed: %r", key, exc, exc_info=True)
        append_reject(
            None,
            stage="teacher",
            reason_code=REASON_TEACHER_TASK_ERROR,
            reason_text=repr(exc),
            extra_meta={"key": key, "method": method, "seed_id": seed_id},
        )
        cases = []

    # Hard-gate: drop cases that copied the parent seed's contradiction pair.
    parent_for_copy_check = variation if variation is not None else seed
    filtered_cases = []
    for c in cases:
        if isinstance(c, dict):
            is_valid, reason = validate_no_contradiction_copying(c, parent_for_copy_check, method)
            if not is_valid:
                logger.info("[drop/cp-copy] id=%s method=%s — %s", c.get("id", "?"), method, reason)
                append_reject(
                    c,
                    stage="teacher",
                    reason_code=REASON_CP_COPY,
                    reason_text=reason,
                    extra_meta={"method": method, "key": key},
                )
                continue
        filtered_cases.append(c)
    cases = filtered_cases

    for c in cases:
        append_jsonl(c, RAW_JSONL)

    if cases:
        append_processed_key(key)
    return cases


def _split_self_instruct(raw: dict | None, seed: dict, gen_round: int, temperature: float) -> list[dict]:
    """Split a self-instruct response ({"variations": [...]}) into individual case dicts."""
    if raw is None:
        return []

    seed_id = seed.get("id", "UNKNOWN")

    if "variations" in raw:
        variations = raw["variations"]
    else:
        variations = [raw]

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
        short_uuid = str(uuid.uuid4())[:8]
        var["id"] = f"GEN-{seed_id}-SI-{i:02d}-R{gen_round:02d}-{short_uuid}"
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
            rc = raw.get("reasoning_chain", "")
            var["reasoning_chain"] = rc
        results.append(var)

    return results


# ── Judge sweep ───────────────────────────────────────────────────────────────

async def judge_sweep(
    judge: JudgeClient,
    in_path=RAW_JSONL,
    out_path=JUDGED_JSONL,
    borderline_path=BORDERLINE_JSONL,
) -> tuple[int, int]:
    """Read raw_generations.jsonl line-by-line, judge, route to judged.jsonl or borderline.jsonl.

    Returns (pass_count, borderline_count).

    - PASS cases                          → out_path (judged.jsonl)
    - FAIL + confidence==BORDERLINE cases → out_path (judged.jsonl) with complexity downgraded
    - FAIL + confidence==HIGH cases       → borderline_path (borderline.jsonl)
    - None (API/parse error)              → dropped entirely, not written anywhere
    """
    if not in_path.exists():
        logger.warning("No raw generations file at %s", in_path)
        return 0, 0

    already_processed: set[str] = set()
    for path in (out_path, borderline_path):
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(line)
                    already_processed.add(d.get("id", ""))
                except json.JSONDecodeError:
                    pass

    pass_count = 0
    borderline_count = 0
    CHUNK = 50

    _COMPLEXITY_DOWNGRADE = {"complex": "medium", "medium": "simple", "simple": "simple"}

    async def _judge_one(case: dict) -> tuple[dict | None, str]:
        scores = await judge.score(case)
        if scores is None:
            logger.warning("[drop/judge] scoring failed — id=%s", case.get("id", "?"))
            append_reject(
                case,
                stage="judge",
                reason_code=REASON_JUDGE_SCORING_ERROR,
                reason_text="Judge API/parse error — scoring returned None",
            )
            return None, "error"
        case_copy = dict(case)
        case_copy.setdefault("meta", {})["judge_scores"] = scores
        if scores.get("verdict") == "PASS":
            return case_copy, "pass"

        # BORDERLINE FAIL: salvage by downgrading complexity instead of discarding
        if scores.get("confidence") == "BORDERLINE":
            old_complexity = case_copy.get("complexity", "medium")
            new_complexity = _COMPLEXITY_DOWNGRADE.get(old_complexity, "simple")
            case_copy["complexity"] = new_complexity
            logger.info(
                "[borderline-soft] id=%s — complexity %s→%s, fail_reasons=%s",
                case.get("id", "?"),
                old_complexity,
                new_complexity,
                scores.get("fail_reasons", []),
            )
            return case_copy, "soft_pass"

        logger.info(
            "[borderline] id=%s — fail_reasons=%s",
            case.get("id", "?"),
            scores.get("fail_reasons", []),
        )
        append_reject(
            case_copy,
            stage="judge",
            reason_code=REASON_JUDGE_FAIL,
            reason_text="; ".join(scores.get("fail_reasons", [])) or "judge FAIL HIGH confidence",
            extra_meta={
                "confidence": scores.get("confidence"),
                "fail_reasons": scores.get("fail_reasons", []),
                "verdict": scores.get("verdict"),
            },
        )
        return case_copy, "fail"

    buffer: list[dict] = []

    async def _flush(buf: list[dict]) -> tuple[int, int]:
        results = await asyncio.gather(*[_judge_one(c) for c in buf])
        pc = bc = 0
        for case_out, outcome in results:
            if case_out is None:
                continue
            if outcome in ("pass", "soft_pass"):
                append_jsonl(case_out, out_path)
                pc += 1
            else:
                append_jsonl(case_out, borderline_path)
                bc += 1
        return pc, bc

    with open(in_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue

            if case.get("id", "") in already_processed:
                continue

            buffer.append(case)
            if len(buffer) >= CHUNK:
                pc, bc = await _flush(buffer)
                pass_count += pc
                borderline_count += bc
                buffer = []

    if buffer:
        pc, bc = await _flush(buffer)
        pass_count += pc
        borderline_count += bc

    logger.info("Judge sweep: %d passed, %d borderline", pass_count, borderline_count)
    return pass_count, borderline_count


# ── Main orchestration entry point ────────────────────────────────────────────

async def run_round(
    generation_round: int,
    temperature: float,
    smoke: bool = False,
    smoke_n: int = 5,
    seed_ids: list[str] | None = None,
) -> dict:
    """Run a full pipeline round. Returns stats dict.

    Args:
        seed_ids: If provided, restrict run to exactly these seed IDs (overrides
                  smoke random selection while still running in smoke-style mode).
    """
    all_seeds = load_seeds()
    if seed_ids:
        seeds = [s for s in all_seeds if s["id"] in seed_ids]
        missing = set(seed_ids) - {s["id"] for s in seeds}
        if missing:
            logger.warning("Requested seed IDs not found in dataset: %s", missing)
        logger.info("TARGETED MODE: using %d specified seeds %s", len(seeds), seed_ids)
    elif smoke:
        seeds = random.sample(all_seeds, min(smoke_n, len(all_seeds)))
        logger.info("SMOKE MODE: using %d randomly selected seeds from %d total",
                    len(seeds), len(all_seeds))
    else:
        scheduler = SeedScheduler(all_seeds, max_per_seed=1)
        seeds = scheduler.all_seeds_for_round()
        logger.info("Full round: %d seeds selected via SeedScheduler", len(seeds))

    processed_keys = load_processed_keys()
    cost_tracker = CostTracker()

    variation_history: dict[str, list[str]] = build_initial_variation_history(seeds)
    solution_history: dict[str, list[str]] = defaultdict(list)

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {DEEPINFRA_API_KEY}"},
        timeout=httpx.Timeout(300.0, connect=15.0),
    ) as http_client:
        teacher = TeacherClient(cost_tracker, client=http_client)

        logger.info("Stage 1: self-instruct for %d seeds (T=%.1f, round=%d)",
                    len(seeds), temperature, generation_round)
        _t_stage1 = time.monotonic()
        si_tasks = [
            _run_teacher_task(
                {
                    "seed": s,
                    "method": "self_instruct",
                    "round": generation_round,
                    "used_contradictions": variation_history[s["id"]],
                    "used_solutions": solution_history[s["id"]],
                },
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
                for case in r:
                    seed_id = case.get("meta", {}).get("parent_seed_id", "")
                    cp = case.get("contradiction_pair", {})
                    imp = cp.get("improving_parameter", "")
                    wor = cp.get("worsening_parameter", "")
                    if imp and wor:
                        variation_history[seed_id].append(f"{imp}|{wor}")
                    sol = case.get("solution", "")[:80]
                    if sol:
                        solution_history[seed_id].append(sol)
        stage1_sec = time.monotonic() - _t_stage1
        logger.info("Stage 1 complete: %d variations (%.1fs)", len(si_variations), stage1_sec)

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
        _t_stage2 = time.monotonic()
        evol_results_nested = await asyncio.gather(*evol_tasks, return_exceptions=True)
        evol_count = 0
        for r in evol_results_nested:
            if isinstance(r, BaseException):
                logger.warning("[error] evol task exception: %s", r)
            else:
                evol_count += len(r)
        stage2_sec = time.monotonic() - _t_stage2
        logger.info("Stage 2 complete: %d evol cases raw (%.1fs)", evol_count, stage2_sec)

    total_raw = len(si_variations) + evol_count

    logger.info("Stage 4: judge sweep")
    _t_judge = time.monotonic()
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {DEEPINFRA_API_KEY}"},
        timeout=httpx.Timeout(120.0, connect=15.0),
    ) as http_client2:
        judge = JudgeClient(cost_tracker, client=http_client2)
        judged_count, borderline_count = await judge_sweep(judge)
    judge_sec = time.monotonic() - _t_judge
    logger.info("Stage 4 complete: judge (%.1fs)", judge_sec)

    logger.info("Stage 5.1: matrix check")
    _t_matrix = time.monotonic()
    matrix_count, matrix_citation_drops = matrix_check_sweep(JUDGED_JSONL, MATRIX_VALIDATED_JSONL)
    matrix_sec = time.monotonic() - _t_matrix

    logger.info("Stage 5.2: principle validation sweep")
    _t_principle = time.monotonic()
    principle_count = principle_validation_sweep(MATRIX_VALIDATED_JSONL)
    principle_sec = time.monotonic() - _t_principle

    logger.info("Stage 5.2b: contradiction-copy sweep")
    _t_copy = time.monotonic()
    cp_copy_count = contradiction_copy_sweep(MATRIX_VALIDATED_JSONL)
    copy_sec = time.monotonic() - _t_copy

    logger.info("Stage 5.2c: complexity validation sweep")
    _t_complexity = time.monotonic()
    complexity_count = complexity_validation_sweep(MATRIX_VALIDATED_JSONL)
    complexity_sec = time.monotonic() - _t_complexity

    # Stage 5.3: Duplicate ID assertion (hard fail if IDs collide)
    if MATRIX_VALIDATED_JSONL.exists():
        all_ids_in_file: list[str] = []
        for line in MATRIX_VALIDATED_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                all_ids_in_file.append(d.get("id", ""))
            except json.JSONDecodeError:
                pass
        if len(all_ids_in_file) != len(set(all_ids_in_file)):
            dups = [id_ for id_, cnt in Counter(all_ids_in_file).items() if cnt > 1]
            logger.error("DUPLICATE IDs in matrix_validated.jsonl: %s", dups)
            raise RuntimeError(f"Duplicate IDs detected — fix before saving: {dups}")
        logger.info("Stage 5.3: ID uniqueness check passed (%d unique IDs)", len(all_ids_in_file))

    seed_dist: dict[str, int] = {}
    domain_dist: dict[str, int] = {}
    complexity_dist: dict[str, int] = {}
    if MATRIX_VALIDATED_JSONL.exists():
        for line in MATRIX_VALIDATED_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            seed_id = d.get("meta", {}).get("parent_seed_id", "unknown")
            seed_dist[seed_id] = seed_dist.get(seed_id, 0) + 1
            domain = d.get("domain", "unknown")
            domain_dist[domain] = domain_dist.get(domain, 0) + 1
            comp = d.get("complexity", "unknown")
            complexity_dist[comp] = complexity_dist.get(comp, 0) + 1

    top_seeds = sorted(seed_dist.items(), key=lambda x: -x[1])[:5]
    top_domains = sorted(domain_dist.items(), key=lambda x: -x[1])[:5]

    stats = {
        "round": generation_round,
        "temperature": temperature,
        "seeds_used": len(seeds),
        "raw_generated": total_raw,
        "judge_passed": judged_count,
        "borderline_count": borderline_count,
        "matrix_passed": matrix_count,
        "matrix_citation_drops": matrix_citation_drops,
        "principle_passed": principle_count,
        "cp_copy_passed": cp_copy_count,
        "complexity_passed": complexity_count,
        "complexity_distribution": complexity_dist,
        "top5_seeds": dict(top_seeds),
        "top5_domains": dict(top_domains),
        "total_cost_usd": cost_tracker.total,
        "total_calls": cost_tracker.call_count,
        # stage timing metrics
        "stage1_sec": round(stage1_sec, 2),
        "stage2_sec": round(stage2_sec, 2),
        "judge_sec": round(judge_sec, 2),
        "matrix_sec": round(matrix_sec, 2),
        "principle_sec": round(principle_sec, 2),
        "copy_sec": round(copy_sec, 2),
        "complexity_sec": round(complexity_sec, 2),
    }
    logger.info("Round %d done — %s", generation_round, stats)
    return stats
