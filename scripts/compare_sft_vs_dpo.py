#!/usr/bin/env python3
"""Side-by-side SFT vs DPO inference on a fixed 5-problem set.

Runs both merged models on the same prompts, prints outputs head-to-head,
and writes per-sample format / chat-preamble / matrix-pass metrics to
`evaluation/sft_vs_dpo.json`. Intended for the post-DPO sanity check.

Usage:
    python scripts/compare_sft_vs_dpo.py \\
        --sft  checkpoints/sft-7b/merged \\
        --dpo  checkpoints/dpo-7b/merged \\
        --out  evaluation/sft_vs_dpo.json
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path
from textwrap import shorten

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smartriz.eval.format_check import (  # noqa: E402
    aggregate_scores,
    score_format_compliance,
    score_principle_correctness,
)
from smartriz.training.formatter import SYSTEM_PROMPT  # noqa: E402

# Five fixed problems hand-picked to span domains and contradictions
FIXED_PROBLEMS: list[dict] = [
    {
        "problem": (
            "A bicycle chain stretches under repeated load and loses transmission "
            "efficiency. How can we improve durability without significantly "
            "increasing weight?"
        ),
        "improving": "Durability of moving object (#15)",
        "worsening": "Weight of moving object (#1)",
    },
    {
        "problem": (
            "A glass facade in a tropical office building must let in daylight but "
            "cause severe overheating in summer. How can we keep daylight quality "
            "while reducing solar gain — without active blinds?"
        ),
        "improving": "Illumination intensity (#18)",
        "worsening": "Temperature (#17)",
    },
    {
        "problem": (
            "An ablation catheter must heat tissue rapidly while keeping electrode "
            "temperature within safe limits to avoid char and clot formation."
        ),
        "improving": "Power (#21)",
        "worsening": "Temperature (#17)",
    },
    {
        "problem": (
            "Li-S battery cells need recyclable separators while still preventing "
            "polysulfide shuttle and meeting EU Ecodesign disassembly requirements."
        ),
        "improving": "Adaptability or versatility (#35)",
        "worsening": "Manufacturability (#32)",
    },
    {
        "problem": (
            "Aircraft galley overhead bins are heavy to open during pressurization "
            "shifts. Make opening force consistent without adding latch complexity."
        ),
        "improving": "Ease of operation (#33)",
        "worsening": "Force (#10)",
    },
]


def run_model(model_path: Path, prompts: list[str], label: str) -> list[str]:
    import torch
    from transformers import AutoTokenizer, pipeline as hf_pipeline

    tok = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    gen = hf_pipeline(
        "text-generation", model=str(model_path), tokenizer=tok,
        device_map="auto", max_new_tokens=1024, do_sample=False,
    )
    outs: list[str] = []
    try:
        for p in prompts:
            chat = tok.apply_chat_template(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user",   "content": p}],
                tokenize=False, add_generation_prompt=True,
            )
            full = gen(chat)[0]["generated_text"]
            outs.append(full[len(chat):].strip())
    finally:
        del gen
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(f"  freed GPU memory after {label}", file=sys.stderr)
    return outs


def evaluate(outputs: list[str], problems: list[dict]) -> dict:
    fmts = [score_format_compliance(o) for o in outputs]
    pcs = [
        score_principle_correctness(
            o,
            expected_improving=p["improving"],
            expected_worsening=p["worsening"],
        )
        for o, p in zip(outputs, problems)
    ]
    return {
        "format": aggregate_scores(fmts),
        "matrix_pass_rate": sum(1 for x in pcs if x["matrix_pass"]) / len(pcs),
        "per_sample": [
            {"format_score": f["score"], "matrix_pass": pc["matrix_pass"],
             "claimed_principles": pc["claimed_principles"]}
            for f, pc in zip(fmts, pcs)
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sft", default="checkpoints/sft-7b/merged")
    ap.add_argument("--dpo", default="checkpoints/dpo-7b/merged")
    ap.add_argument("--out", default="evaluation/sft_vs_dpo.json")
    args = ap.parse_args()

    sft_path = Path(args.sft)
    dpo_path = Path(args.dpo)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prompts = [p["problem"] for p in FIXED_PROBLEMS]

    print("Running SFT model …", file=sys.stderr)
    sft_outs = run_model(sft_path, prompts, "sft")
    print("Running DPO model …", file=sys.stderr)
    dpo_outs = run_model(dpo_path, prompts, "dpo")

    sft_eval = evaluate(sft_outs, FIXED_PROBLEMS)
    dpo_eval = evaluate(dpo_outs, FIXED_PROBLEMS)

    # Side-by-side terminal output
    for i, p in enumerate(FIXED_PROBLEMS):
        print("=" * 80)
        print(f"[{i+1}] {shorten(p['problem'], width=120, placeholder='…')}")
        for label, outs, ev in (("SFT", sft_outs, sft_eval),
                                 ("DPO", dpo_outs, dpo_eval)):
            sample = ev["per_sample"][i]
            print(f"\n--- {label} (format={sample['format_score']:.2f} "
                  f"matrix={sample['matrix_pass']} "
                  f"principles={sample['claimed_principles']}) ---")
            print(shorten(outs[i].replace("\n", " ⏎ "), width=600,
                          placeholder="…"))
        print()

    summary = {
        "fixed_problems": [p["problem"] for p in FIXED_PROBLEMS],
        "sft": {**sft_eval, "outputs": sft_outs},
        "dpo": {**dpo_eval, "outputs": dpo_outs},
        "delta_format_mean": (dpo_eval["format"]["mean"]
                              - sft_eval["format"]["mean"]),
        "delta_chat_preamble_leak": (
            dpo_eval["format"]["chat_preamble_leak_rate"]
            - sft_eval["format"]["chat_preamble_leak_rate"]
        ),
    }
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")
    print(f"Δ format mean (DPO−SFT): {summary['delta_format_mean']:+.3f}")
    print(f"Δ chat-preamble leak:    {summary['delta_chat_preamble_leak']:+.3f}")


if __name__ == "__main__":
    main()
