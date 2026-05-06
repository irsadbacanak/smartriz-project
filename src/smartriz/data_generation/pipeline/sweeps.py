"""
Post-judge quality sweep functions: matrix check, principle validation,
contradiction-copy, and complexity validation.

All sweeps operate on JSONL files and either filter in-place (atomic temp-file
swap) or write to a separate output path.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from smartriz.data_generation.pipeline.io import append_jsonl
from smartriz.data_generation.pipeline.seeds import load_seeds
from smartriz.data_generation.quality.matrix import (
    check,
    check_matrix_citations,
    parse_param_id,
    parse_principle_id,
)
from smartriz.data_generation.quality.triz_kb import validate_principles, validate_no_contradiction_copying

logger = logging.getLogger(__name__)


# ── Matrix check sweep ────────────────────────────────────────────────────────

def matrix_check_sweep(
    in_path: Path,
    out_path: Path,
) -> tuple[int, int]:
    """Apply Altshuller matrix sanity check (including in-text citation check).

    Returns (pass_count, citation_drop_count).
    citation_drop_count counts cases dropped specifically due to hallucinated
    matrix citations in reasoning_chain (for stats reporting).
    """
    if not in_path.exists():
        return 0, 0

    already_validated: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                already_validated.add(d.get("id", ""))
            except json.JSONDecodeError:
                pass

    count = 0
    citation_drops = 0
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

            passed, is_citation_drop = _run_matrix_check_with_detail(case)
            if not passed:
                logger.info("[drop/matrix] matrix check failed — id=%s", case.get("id", "?"))
                if is_citation_drop:
                    citation_drops += 1
                continue

            case["meta"]["matrix_check_passed"] = True
            append_jsonl(case, out_path)
            count += 1

    logger.info("Matrix check: %d cases passed, %d citation drops", count, citation_drops)
    return count, citation_drops


def _run_matrix_check_with_detail(case: dict) -> tuple[bool, bool]:
    """Run full matrix check including citation verification.

    Returns (passed, is_citation_drop).
    - passed=False, is_citation_drop=True  → dropped due to hallucinated citation
    - passed=False, is_citation_drop=False → dropped for another structural reason
    - passed=True                          → case is ok
    """
    cp = case.get("contradiction_pair", {})
    imp_str = cp.get("improving_parameter", "")
    wor_str = cp.get("worsening_parameter", "")
    imp_id = parse_param_id(imp_str)
    wor_id = parse_param_id(wor_str)

    if imp_id is None or wor_id is None:
        logger.warning("[drop/matrix] cannot parse param ids — imp=%r wor=%r id=%s",
                       imp_str, wor_str, case.get("id", "?"))
        return False, False

    principles_raw = case.get("inventive_principles", [])
    principle_ids = [parse_principle_id(p) for p in principles_raw]
    principle_ids = [p for p in principle_ids if p is not None]

    if not principle_ids:
        logger.warning("[drop/matrix] no parseable principle ids — id=%s", case.get("id", "?"))
        return False, False

    primary_passed = check(imp_id, wor_id, principle_ids)
    if not primary_passed:
        return False, False

    sec = case.get("secondary_contradiction", {})
    if isinstance(sec, dict):
        sec_imp_str = sec.get("improving_parameter", "").strip()
        sec_wor_str = sec.get("worsening_parameter", "").strip()
        if sec_imp_str and sec_wor_str:
            sec_imp_id = parse_param_id(sec_imp_str)
            sec_wor_id = parse_param_id(sec_wor_str)
            if sec_imp_id is None or sec_wor_id is None:
                logger.warning(
                    "[drop/matrix] cannot parse secondary param ids — imp=%r wor=%r id=%s",
                    sec_imp_str, sec_wor_str, case.get("id", "?"),
                )
                return False, False
            sec_passed = check(sec_imp_id, sec_wor_id, principle_ids)
            if not sec_passed:
                logger.info(
                    "[drop/matrix] secondary matrix check failed — id=%s cell=(%d,%d)",
                    case.get("id", "?"), sec_imp_id, sec_wor_id,
                )
                return False, False

    cite_ok, cite_errors = check_matrix_citations(case)
    if not cite_ok:
        for err in cite_errors:
            logger.info("[drop/matrix-cite] id=%s — %s", case.get("id", "?"), err)
        return False, True

    return True, False


def _run_matrix_check(case: dict) -> bool:
    """Thin wrapper preserved for any external callers."""
    passed, _ = _run_matrix_check_with_detail(case)
    return passed


# ── Principle validation sweep ────────────────────────────────────────────────

def principle_validation_sweep(in_path: Path) -> int:
    """Hard-gate: reject cases whose inventive_principles contain hallucinated
    or incorrectly named principles. Overwrites in_path in-place (temp file swap).
    Returns count of cases that passed.
    """
    if not in_path.exists():
        logger.warning("principle_validation_sweep: no file at %s", in_path)
        return 0

    tmp_path = in_path.with_suffix(".tmp")
    count_pass = 0
    count_fail = 0

    with open(in_path, encoding="utf-8") as fin, \
         open(tmp_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue

            principles = case.get("inventive_principles", [])
            result = validate_principles(principles)

            if not result["valid"]:
                for r in result["rejected"]:
                    logger.info(
                        "[drop/principles] id=%s — rejected '%s': %s",
                        case.get("id", "?"), r["original"], r["reason"],
                    )
                count_fail += 1
                continue

            case["inventive_principles"] = result["normalized"]
            case.setdefault("meta", {})["principles_validated"] = True
            fout.write(json.dumps(case, ensure_ascii=False) + "\n")
            count_pass += 1

    tmp_path.replace(in_path)
    logger.info("Principle validation: %d passed, %d rejected", count_pass, count_fail)
    return count_pass


# ── Complexity validation sweep ──────────────────────────────────────────────

def complexity_validation_sweep(in_path: Path) -> int:
    """Hard-gate: reject cases whose 'complexity' label is not supported by
    structural evidence. Runs in-place (atomic temp-file swap).
    Returns count of cases that passed.
    """
    from smartriz.data_generation.quality.complexity import validate_complexity

    if not in_path.exists():
        logger.warning("complexity_validation_sweep: no file at %s", in_path)
        return 0

    tmp_path = in_path.with_suffix(".tmp")
    count_pass = 0
    count_fail = 0

    with open(in_path, encoding="utf-8") as fin, \
         open(tmp_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue

            ok, reason = validate_complexity(case)
            if not ok:
                logger.info(
                    "[drop/complexity] id=%s — %s",
                    case.get("id", "?"), reason,
                )
                count_fail += 1
                continue

            fout.write(json.dumps(case, ensure_ascii=False) + "\n")
            count_pass += 1

    tmp_path.replace(in_path)
    logger.info("Complexity validation: %d passed, %d rejected", count_pass, count_fail)
    return count_pass


# ── Contradiction-copy sweep ──────────────────────────────────────────────────

def contradiction_copy_sweep(
    in_path: Path,
    seed_lookup: dict | None = None,
) -> int:
    """Post-hoc hard-gate: remove cases where SI/XDOM generator copied the
    parent seed's contradiction pair verbatim.

    Runs in-place (atomic temp-file swap).
    Accepts an optional seed_lookup dict (seed_id → seed dict) for testing;
    loads seeds from SEED_PATH if not provided.

    Returns count of surviving cases.
    """
    if not in_path.exists():
        logger.warning("contradiction_copy_sweep: no file at %s", in_path)
        return 0

    if seed_lookup is None:
        seed_lookup = {s["id"]: s for s in load_seeds()}

    tmp_path = in_path.with_suffix(".tmp")
    count_pass = 0
    count_fail = 0

    with open(in_path, encoding="utf-8") as fin, \
         open(tmp_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError:
                continue

            meta = case.get("meta", {})
            seed_id = meta.get("parent_seed_id", "")
            method = meta.get("generation_method", "")
            parent_seed = seed_lookup.get(seed_id, {})

            is_valid, reason = validate_no_contradiction_copying(case, parent_seed, method)
            if not is_valid:
                logger.info(
                    "[drop/cp-copy-sweep] id=%s method=%s — %s",
                    case.get("id", "?"), method, reason,
                )
                count_fail += 1
                continue

            fout.write(json.dumps(case, ensure_ascii=False) + "\n")
            count_pass += 1

    tmp_path.replace(in_path)
    logger.info("Contradiction-copy sweep: %d passed, %d rejected", count_pass, count_fail)
    return count_pass
