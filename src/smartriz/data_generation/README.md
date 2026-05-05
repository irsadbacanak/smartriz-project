# SmarTRIZ — Synthetic Data Generation Pipeline

Generates ≥10,000 high-quality TRIZ training examples from the 86-case seed dataset using
Self-Instruct + Evol-Instruct with DeepSeek-R1-Distill-Llama-70B (teacher) and
DeepSeek-V3 (judge) via DeepInfra.

## Quick Start

```bash
# 1. Install dependencies
pip install httpx tenacity sentence-transformers numpy pydantic python-dotenv pytest

# 2. Set your DeepInfra API key in project root .env
echo "DEEPINFRA_API_KEY=your_key_here" > .env

# 3. Smoke test (5 seeds, inspect output manually before full run)
python -m smartriz.data_generation.main --smoke --n 5

# 4. Full round 1
python -m smartriz.data_generation.main --round 1 --temperature 0.7

# 5. Auto-run until 10K examples
python -m smartriz.data_generation.main --auto --target 10000

# 6. Run unit tests
python -m pytest tests/test_data_generation -v
```

## File Structure

```
src/smartriz/data_generation/
├── config.py              # API keys, model names, hyperparams, cost tracker
├── main.py                # Entry point (--smoke / --round / --auto)
├── prompts/
│   ├── self_instruct.py   # 1 seed → 5 style variations
│   ├── evol_deepening.py  # Add secondary contradiction (+complexity)
│   ├── evol_constraint.py # Add real-world constraint
│   ├── evol_cross_domain.py  # Transfer to different domain
│   └── judge.py           # 4-criterion rubric (no single-number scoring)
├── pipeline/
│   ├── extractor.py       # reasoning_content + <think> extraction
│   ├── teacher.py         # DeepSeek-R1 async client
│   ├── judge.py           # DeepSeek-V3 async client
│   └── orchestrator.py    # Full pipeline with checkpointing
├── quality/
│   ├── matrix.py          # 39×39 Altshuller matrix + parse helpers
│   ├── deduplicator.py    # MiniLM cosine dedup at 0.85 threshold
│   └── validator.py       # Pydantic schema validation + final JSON write
└── ../tests/test_data_generation/
    └── test_extractor.py  # 17 unit tests (4 scenarios + edge cases)
```

## Pipeline Stages

| Stage | Description | Pass Gate |
|-------|-------------|-----------|
| 1 | Self-Instruct: 86 seeds × 5 variations | — |
| 2A | Evol-Deepening: add secondary contradiction | — |
| 2B | Evol-Constraint: add real-world constraint | — |
| 2C | Evol-Cross-Domain: transfer to new domain | — |
| 3 | Reasoning extraction (reasoning_content / \<think\>) | Drop if no reasoning |
| 4 | LLM-as-a-Judge (4 criteria, avg ≥ 7.0) | avg < 7.0 → drop |
| 5.1 | Altshuller matrix sanity check | No matrix match → drop |
| 5.2 | MiniLM cosine deduplication (> 0.85) | Lower-scoring duplicate → drop |
| 5.3 | Pydantic schema validation | Invalid schema → drop |

## Math

- 86 seeds × 5 SI × 3 evol = **1,720 raw / round**
- Expected pass rate 50–60% → **~860–1,030 net / round**
- Temperature rotation: `[0.7, 0.9, 1.1, 1.3]`
- **10–12 rounds** to reach ≥10,000 examples

## Cost Estimate

| Component | Cost / round |
|-----------|-------------|
| Teacher (1,720 calls × ~1K tokens in / ~800 out) | ~$1.50 |
| Judge (~860 calls × ~1K tokens in / ~50 out) | ~$0.25 |
| **Total / round** | **~$1.75** |
| **11 rounds** | **~$19.25** |

Hard-stop at $30 enforced in `config.py::CostTracker`.

## Data Files (in `data/`)

| File | Description |
|------|-------------|
| `seed_dataset.json` | 86 hand-curated seed cases (input) |
| `raw_generations.jsonl` | All teacher outputs (streamed, append-only) |
| `judged.jsonl` | Cases passing judge avg ≥ 7.0 |
| `matrix_validated.jsonl` | Cases passing Altshuller matrix check |
| `deduplicated.jsonl` | Cases after cosine dedup |
| `processed_keys.txt` | Completed task keys (crash-safe restart) |
| `training_dataset.json` | Final ≥10K dataset (pipeline output) |

## Hard Constraints

- No synchronous API loops — `asyncio` + `httpx` only
- No single-number judge score — 4-criterion rubric always
- Matrix sanity check is mandatory (no bypass)
- No silent drops — every dropped record is logged with reason
- `meta` field carries lineage; training schema stays clean
- Smoke test manual review required before full run
