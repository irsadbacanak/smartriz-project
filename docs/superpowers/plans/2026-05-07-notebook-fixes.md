# Notebook Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 7 critical issues in the SmarTRIZ training notebooks that would silently produce wrong DPO pairs, leaky eval sets, and untrustworthy metrics.

**Architecture:** All fixes are isolated to notebook cells — no shared library code is changed. Execution order: nb02 cell-1 → nb01 cells 10-11 → nb02 cells 7-8 → nb02 cells 5-6 → nb03 cells 1,4,6,7,8,9.

**Tech Stack:** Python, Jupyter notebooks, HuggingFace Transformers/TRL/PEFT, llama.cpp, DeepInfra API

---

## Context

An independent review of the four Colab training notebooks revealed 7 issues:

1. **DPO pair matching broken** — `problem[:100]` key against `training_dataset_clean.json` produces 0 matches because rejected `case` objects don't have problems stored there. The notebook silently falls through to 1,500 teacher-only pairs, defeating the purpose of real rejection data.
2. **SFT eval leaks** — notebook 01 re-splits training data instead of loading the held-out `test_split.json` created by notebook 00.
3. **DPO ref_model=None** — known trl 0.11.4 + PEFT bug can produce inconsistent reference logprobs under gradient checkpointing.
4. **Eval metrics naïve** — `principle_accuracy` only catches `#N` format; `contradiction_accuracy` triggers false positives on 3-char words; no LLM-as-judge.
5. **No GPU cleanup** — 4 models evaluated sequentially without `del pipeline; torch.cuda.empty_cache()` → OOM on model 2.
6. **API key hardcoded** — `DEEPINFRA_API_KEY = ''` risks accidental commit; should use Colab secrets / env var.
7. **14B OOM risk + GGUF no imatrix** — no warning for memory limit; Q4_K_M without calibration loses ~2-5% quality on reasoning tasks.

**Status: ALL FIXES IMPLEMENTED** (2026-05-07)

---

## Files Modified

| File | Cells Changed |
|------|---------------|
| `notebooks/01_sft_training.ipynb` | cell-10, cell-11 |
| `notebooks/02_dpo_training.ipynb` | cell-1, cell-5, cell-6, cell-7, cell-8 |
| `notebooks/03_convert_and_eval.ipynb` | cell-1, cell-4, cell-6, cell-7, cell-8, cell-9 |

---

## Fix Summary

### Fix 1: API Key (nb02 cell-1, nb03 cell-1)
- `DEEPINFRA_API_KEY = ''` → `os.getenv` with `google.colab.userdata` fallback
- Added `JUDGED_PATH` config variable to nb02
- Added `RUN_LLM_JUDGE` and `JUDGE_MODEL` config variables to nb03

### Fix 2: SFT Eval (nb01 cells 10-11)
- Loads `test_split.json` as `hf_eval` (created by notebook 00, 10% held-out)
- Graceful `UserWarning` fallback to 5% train split if file missing
- SFTTrainer updated: `train_dataset=hf_train`, `eval_dataset=hf_eval`

### Fix 3: DPO ref_model (nb02 cells 7-8)
- Loads explicit frozen `ref_model` from `SFT_MODEL_DIR` in 4-bit
- `assert not any(p.requires_grad ...)` verifies it's frozen
- `DPOTrainer(ref_model=ref_model, ...)` instead of `None`

### Fix 4: DPO Pair Matching (nb02 cells 5-6)
- Reads `judged.jsonl` (not `training_dataset_clean.json`) as chosen source
- Cascade matching: `case.id` → `parent_seed_id` → skip (no 100-char truncation)
- Also uses `judged FAIL` records as rejected (46 additional pairs)
- Deduplication by prompt
- `unmatched` is now `[{'source': ..., 'record': ...}]` — cell-6 updated to unpack correctly
- Assertion: `len(dpo_pairs) > 0` and no identical chosen/rejected

### Fix 5: GPU Cleanup (nb03 cell-7)
- `run_hf_model` wraps inference in `try/finally`
- On exit: `del gen; gc.collect(); torch.cuda.empty_cache()`

### Fix 6: Eval Metrics (nb03 cells 6,8,9)
- `extract_principle_numbers()`: catches `#N`, `Principle N`, `N-Name`, and 40 named aliases
- `contradiction_accuracy()`: prefers `(#N)` ID match; fallback requires ≥60% of 5-char content words
- `llm_judge_score()`: calls DeepSeek via DeepInfra, returns 5-dimension scores
- `score_predictions()`: optional `run_llm_judge` param; aggregates `llm_judge_*` keys
- Comparison table shows LLM Overall column when available

### Fix 7: 14B Warning + GGUF imatrix (nb02 cell-1, nb03 cell-4)
- 14B memory banner in nb02 CONFIG cell (only prints when `MODEL_SIZE == '14b'`)
- GGUF conversion: `HF → F16 → imatrix → Q4_K_M` pipeline
- `GPU_LAYERS` auto-detected via `torch.cuda.is_available()`
- `KEEP_F16 = True` flag controls intermediate cleanup

---

## Verification

```python
# Test principle extraction
from notebooks.03_convert_and_eval import extract_principle_numbers
assert 35 in extract_principle_numbers('Use Principle 35 for parameter changes')
assert 40 in extract_principle_numbers('Apply #40 composite material approach')
assert 1  in extract_principle_numbers('segmentation technique applied')

# Test contradiction accuracy doesn't false-positive
ref_cp = {'improving_parameter': 'Ease of operation (#33)', 'worsening_parameter': 'Device complexity (#36)'}
assert not contradiction_accuracy('the device operates in a complex field', ref_cp)
assert contradiction_accuracy('Improving ease of operation (#33) while reducing device complexity (#36)', ref_cp)

# Test DPO assertion fires on empty pairs
# Run nb02 cell-5 → expect: 'Matched pairs: N' where N > 0
```
