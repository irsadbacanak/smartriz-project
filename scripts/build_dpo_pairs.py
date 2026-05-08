#!/usr/bin/env python3
"""Build DPO preference pairs from judged.jsonl + rejected_dataset.jsonl.

Three streams (per the approved plan §2):

  A. Format-only rewrites (~50%)  — chosen = correctly-formatted PASS record;
     rejected = same record degraded by ONE rule:
         strip-think | strip-headings | inject-chat-preamble |
         hallucinate-principles | genericize-numerics
  B. Content-only mismatches (~30%) — chosen = PASS with matrix_check_passed;
     rejected = same parent_seed_id FAIL record, both formatted identically.
  C. Matrix-violation pairs (~20%) — chosen = PASS as-is; rejected = same
     content but principles swapped to two random matrix-fail principles.

Each pair is verified: chosen passes format_compliance score >= 0.8,
rejected fails ≥1 format/correctness check (or in stream B, content differs).

Output: data/dpo_pairs.jsonl (one JSON per line, TRL preference format).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

# Allow `python scripts/build_dpo_pairs.py` from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smartriz.training.formatter import format_assistant, format_from_case  # noqa: E402
from smartriz.eval.format_check import (  # noqa: E402
    score_format_compliance,
    score_principle_correctness,
)
from smartriz.data_generation.quality.matrix import MATRIX, parse_param_id  # noqa: E402
from smartriz.data_generation.quality.triz_kb import TRIZ_PRINCIPLES  # noqa: E402

# ── IO ──────────────────────────────────────────────────────────────────
def load_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ── Stream A — rule-based format-degrade rewrites ───────────────────────
_HEADING_RX = re.compile(
    r"(?:Contradiction\s*:|Improving\s*:|Worsening\s*:|"
    r"Inventive\s+Principles\s*:|Solution\s*:)",
    re.IGNORECASE,
)
_THINK_RX = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)

_NUMERIC_RX = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:°C|°F|K|kPa|MPa|GPa|Pa|kJ|J|µm|um|mm|nm|cm|m|kg|g|"
    r"kHz|Hz|MHz|GHz|%|W|kW|N|kN)\b"
)
_STANDARD_RX = re.compile(r"\b(?:ISO|ASTM|IEC|EN|DIN|ANSI|MIL-STD)[- ]?\d+[A-Z0-9\-]*\b")


def rule_strip_think(formatted: str) -> str:
    return _THINK_RX.sub("", formatted, count=1).lstrip()


def rule_strip_headings(formatted: str) -> str:
    body = _THINK_RX.sub("", formatted).strip()
    flat = _HEADING_RX.sub("", body)
    flat = re.sub(r"\n{2,}", " ", flat)
    flat = re.sub(r"\s{2,}", " ", flat).strip()
    return flat


def rule_chat_preamble(formatted: str) -> str:
    body = _THINK_RX.sub("", formatted).strip()
    body = re.sub(r"Contradiction\s*:", "### Step 1: Identify the Technical Contradiction",
                  body, count=1, flags=re.IGNORECASE)
    body = re.sub(r"Inventive\s+Principles\s*:",
                  "### Step 2: Apply TRIZ Principles\n\nInventive principles selected:",
                  body, count=1, flags=re.IGNORECASE)
    body = re.sub(r"Solution\s*:", "### Step 3: Propose a Solution",
                  body, count=1, flags=re.IGNORECASE)
    return ("Thank you for the detailed problem description. Let's break this "
            "down step-by-step using the TRIZ methodology.\n\n" + body)


def rule_hallucinate_principles(case: dict) -> str | None:
    """Return a rejected with principles replaced by ones outside the matrix cell."""
    cp = case.get("contradiction_pair", {}) or {}
    imp = parse_param_id(cp.get("improving_parameter", ""))
    wor = parse_param_id(cp.get("worsening_parameter", ""))
    if imp is None or wor is None or imp == wor:
        return None
    cell = set(MATRIX.get(imp, {}).get(wor, []) or [])
    if not cell:
        return None
    fail_pool = [n for n in TRIZ_PRINCIPLES if n not in cell]
    if len(fail_pool) < 3:
        return None
    bad_ids = random.sample(fail_pool, k=3)
    bad_principles = [f"#{n} {TRIZ_PRINCIPLES[n]}" for n in bad_ids]
    return format_assistant(
        reasoning_chain=case.get("reasoning_chain", ""),
        improving_parameter=cp.get("improving_parameter", ""),
        worsening_parameter=cp.get("worsening_parameter", ""),
        inventive_principles=bad_principles,
        solution=case.get("solution", ""),
    )


def rule_genericize(formatted: str) -> str:
    out = _NUMERIC_RX.sub("an appropriate value", formatted)
    out = _STANDARD_RX.sub("the relevant standard", out)
    out = re.sub(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\s+(?:alloy|steel|polymer|"
                 r"composite|ceramic|coating)\b", "a suitable material", out)
    return out


def stream_a_pair(case: dict, rng: random.Random) -> dict | None:
    """Format-degrading rewrites: rejected ALWAYS loses ≥1 format check.

    Content-degrade rules (hallucinate, genericize) belong in stream C and
    a future content stream — they preserve format and would slip past the
    rejected-too-strong validator.
    """
    chosen = format_from_case(case)
    rules = ["strip_think", "strip_headings", "chat_preamble"]
    rule = rng.choice(rules)
    if rule == "strip_think":
        rejected = rule_strip_think(chosen)
    elif rule == "strip_headings":
        rejected = rule_strip_headings(chosen)
    else:  # chat_preamble
        rejected = rule_chat_preamble(chosen)
    if not rejected or rejected.strip() == chosen.strip():
        return None
    return {"prompt": case.get("problem", ""), "chosen": chosen,
            "rejected": rejected, "source_stream": f"A:{rule}"}


# ── Stream B — PASS vs sibling FAIL on same parent_seed_id ──────────────
def stream_b_pairs(validated_pass: list[dict], judged: list[dict],
                   rng: random.Random, target: int) -> list[dict]:
    """Pair matrix_validated PASS records (chosen) with siblings that either
    judged FAIL or PASSed judge but failed the matrix sweep (rejected).
    Both groups share parent_seed_id with at least one validated PASS.
    """
    validated_ids = {j.get("id") for j in validated_pass}
    by_parent_pass: dict[str, list[dict]] = {}
    for j in validated_pass:
        pid = (j.get("meta", {}) or {}).get("parent_seed_id")
        if pid:
            by_parent_pass.setdefault(pid, []).append(j)

    by_parent_reject: dict[str, list[dict]] = {}
    for j in judged:
        if j.get("id") in validated_ids:
            continue
        meta = j.get("meta", {}) or {}
        scores = meta.get("judge_scores", {}) or {}
        pid = meta.get("parent_seed_id")
        if not pid or pid not in by_parent_pass:
            continue
        if not (j.get("problem") and j.get("solution") and j.get("reasoning_chain")):
            continue
        if scores.get("verdict") in ("FAIL", "PASS"):
            by_parent_reject.setdefault(pid, []).append(j)

    pids = [p for p in by_parent_pass if p in by_parent_reject]
    rng.shuffle(pids)
    pairs: list[dict] = []
    for pid in pids:
        pass_pool_local = by_parent_pass[pid]
        rej_pool = by_parent_reject[pid]
        passed = max(pass_pool_local,
                     key=lambda r: r.get("meta", {}).get("judge_scores", {})
                     .get("average", 0.0))
        failed = rng.choice(rej_pool)
        if passed.get("id") == failed.get("id"):
            continue
        chosen = format_from_case(passed)
        rejected = format_from_case(failed)
        if chosen.strip() == rejected.strip():
            continue
        pairs.append({"prompt": passed.get("problem", ""),
                      "chosen": chosen, "rejected": rejected,
                      "source_stream": "B"})
        if len(pairs) >= target:
            break
    return pairs


# ── Stream C — matrix-violation principle swap ──────────────────────────
def stream_c_pair(case: dict, rng: random.Random) -> dict | None:
    cp = case.get("contradiction_pair", {}) or {}
    imp = parse_param_id(cp.get("improving_parameter", ""))
    wor = parse_param_id(cp.get("worsening_parameter", ""))
    if imp is None or wor is None or imp == wor:
        return None
    cell = set(MATRIX.get(imp, {}).get(wor, []) or [])
    if not cell:
        return None
    fail_pool = [n for n in TRIZ_PRINCIPLES if n not in cell]
    if len(fail_pool) < 3:
        return None
    bad_ids = rng.sample(fail_pool, k=3)
    bad_principles = [f"#{n} {TRIZ_PRINCIPLES[n]}" for n in bad_ids]
    chosen = format_from_case(case)
    rejected = format_assistant(
        reasoning_chain=case.get("reasoning_chain", ""),
        improving_parameter=cp.get("improving_parameter", ""),
        worsening_parameter=cp.get("worsening_parameter", ""),
        inventive_principles=bad_principles,
        solution=case.get("solution", ""),
    )
    if chosen.strip() == rejected.strip():
        return None
    return {"prompt": case.get("problem", ""), "chosen": chosen,
            "rejected": rejected, "source_stream": "C"}


# ── Driver ──────────────────────────────────────────────────────────────
def build(judged_path: Path, validated_path: Path, out_path: Path,
          target_total: int, ratios: tuple[float, float, float],
          seed: int) -> dict:
    rng = random.Random(seed)
    judged = load_jsonl(judged_path)
    print(f"Loaded judged.jsonl: {len(judged)} records", file=sys.stderr)

    # Chosen pool comes from matrix_validated.jsonl — PASS verdict + matrix-OK +
    # principles_validated. judged.jsonl carries PASS records that may have
    # failed the matrix sweep, which is exactly what we want as rejected for B.
    validated = load_jsonl(validated_path)
    pass_pool = [
        j for j in validated
        if j.get("problem") and j.get("solution") and j.get("reasoning_chain")
    ]
    print(f"matrix_validated chosen pool: {len(pass_pool)}", file=sys.stderr)

    target_a = int(target_total * ratios[0])
    target_b = int(target_total * ratios[1])
    target_c = int(target_total * ratios[2])

    pairs: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()  # (prompt[:200], stream)

    def push(pair: dict | None) -> bool:
        if not pair:
            return False
        key = (pair["prompt"][:200], pair["source_stream"].split(":")[0])
        if key in seen_keys:
            return False
        seen_keys.add(key)
        pairs.append(pair)
        return True

    # Stream A — format degrades from the PASS pool
    pool_a = pass_pool.copy()
    rng.shuffle(pool_a)
    for case in pool_a:
        if sum(1 for p in pairs if p["source_stream"].startswith("A")) >= target_a:
            break
        push(stream_a_pair(case, rng))

    # Stream B — PASS vs sibling FAIL
    for p in stream_b_pairs(pass_pool, judged, rng, target_b):
        push(p)

    # Stream C — matrix-violation
    pool_c = [c for c in pass_pool
              if (c.get("problem", "")[:200], "C") not in seen_keys]
    rng.shuffle(pool_c)
    for case in pool_c:
        if sum(1 for p in pairs if p["source_stream"] == "C") >= target_c:
            break
        push(stream_c_pair(case, rng))

    # Validate: chosen MUST score >= 0.8, rejected MUST score < 1.0
    accepted: list[dict] = []
    drops = Counter()
    for p in pairs:
        cs = score_format_compliance(p["chosen"])["score"]
        rs = score_format_compliance(p["rejected"])["score"]
        if cs < 0.8:
            drops["chosen_low_format"] += 1
            continue
        if rs >= 1.0 and p["source_stream"].startswith("A"):
            drops["rejected_too_strong_A"] += 1
            continue
        if p["chosen"].strip() == p["rejected"].strip():
            drops["identical"] += 1
            continue
        accepted.append(p)

    # Token-length filter (rough char-based proxy: 1 token ≈ 4 chars)
    MAX_CHARS = 2048 * 4
    final: list[dict] = []
    for p in accepted:
        if (len(p["chosen"]) + len(p["prompt"]) > MAX_CHARS or
                len(p["rejected"]) + len(p["prompt"]) > MAX_CHARS):
            drops["over_length"] += 1
            continue
        final.append(p)

    # Write
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for p in final:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    by_stream = Counter(p["source_stream"].split(":")[0] for p in final)
    return {
        "total": len(final),
        "by_stream": dict(by_stream),
        "drops": dict(drops),
        "out_path": str(out_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judged", default="data/judged.jsonl")
    parser.add_argument("--validated", default="data/matrix_validated.jsonl")
    parser.add_argument("--out", default="data/dpo_pairs.jsonl")
    parser.add_argument("--total", type=int, default=3000)
    parser.add_argument("--ratios", default="0.5,0.3,0.2",
                        help="A,B,C ratios — must sum to 1.0")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ratios = tuple(float(x) for x in args.ratios.split(","))
    assert len(ratios) == 3 and abs(sum(ratios) - 1.0) < 1e-6, \
        "--ratios must be 3 floats summing to 1.0"

    report = build(Path(args.judged), Path(args.validated), Path(args.out),
                   args.total, ratios, args.seed)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
