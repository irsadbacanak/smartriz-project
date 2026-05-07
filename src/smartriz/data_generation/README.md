# SmarTRIZ — Synthetic Data Generation Pipeline

Generates ≥10,000 high-quality TRIZ training examples from the 86-case seed dataset using
Self-Instruct + Evol-Instruct with DeepSeek-V4-Pro (teacher) and Qwen2.5-72B-Instruct
(judge) via DeepInfra.

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
│   └── judge.py           # 4-criterion rubric prompt (schema + text)
├── pipeline/
│   ├── extractor.py       # reasoning_content + <think> extraction
│   ├── teacher.py         # DeepSeek async HTTP client
│   ├── judge.py           # Qwen async HTTP client
│   ├── io.py              # JSONL append + processed_keys checkpoint helpers
│   ├── seeds.py           # Seed loading, SeedScheduler, variation-history init
│   ├── sweeps.py          # Post-judge quality sweeps (matrix, principles, complexity, cp-copy)
│   └── orchestrator.py    # Teacher tasks, judge sweep, run_round (flow coordinator)
└── quality/
    ├── matrix.py          # 39×39 Altshuller matrix + parse helpers
    ├── triz_kb.py         # Canonical 40 principles + validate_principles
    ├── complexity.py      # Complexity label validator
    ├── deduplicator.py    # MiniLM cosine dedup at 0.85 threshold
    └── validator.py       # Pydantic schema validation + final JSON write
```

### Naming note: `prompts/judge.py` vs `pipeline/judge.py`

| File | Role |
|------|------|
| `prompts/judge.py` | Pure text — builds the 4-criterion rubric prompt string |
| `pipeline/judge.py` | HTTP client — sends requests to the judge model API |

## Data Files

Reference/knowledge files live in `data/knowledge/`; backup artifacts in `data/artifacts/`.
Active pipeline output files are written to `data/` (root).

| Path | Description |
|------|-------------|
| `data/knowledge/seed_dataset.json` | 86 hand-curated seed cases (input) |
| `data/knowledge/39_parameters.yaml` | 39 engineering parameters (reference) |
| `data/knowledge/40_principles.yaml` | 40 inventive principles (reference) |
| `data/knowledge/parameters.json` | Parameter data for ChromaDB init |
| `data/knowledge/principles.json` | Principle data for ChromaDB init |
| `data/knowledge/triz_matrix.xls` | Source XLS for matrix.py generation |
| `data/raw_generations.jsonl` | All teacher outputs (streamed, append-only) |
| `data/judged.jsonl` | Cases passing judge (PASS verdict) |
| `data/matrix_validated.jsonl` | Cases passing Altshuller matrix check |
| `data/deduplicated.jsonl` | Cases after cosine dedup |
| `data/processed_keys.txt` | Completed task keys (crash-safe restart) |
| `data/training_dataset.json` | Final ≥10K dataset (pipeline output) |
| `data/artifacts/` | Backup snapshots (not tracked by git) |

## Pipeline Stages

| Stage | Description | Pass Gate |
|-------|-------------|-----------|
| 1 | Self-Instruct: seeds × 5 variations | — |
| 2A | Evol-Deepening: add secondary contradiction | — |
| 2B | Evol-Constraint: add real-world constraint | — |
| 2C | Evol-Cross-Domain: transfer to new domain | — |
| 3 | Reasoning extraction (reasoning_content / \<think\>) | Drop if no reasoning |
| 4 | LLM-as-a-Judge (4 criteria, PASS/FAIL verdict) | FAIL → borderline.jsonl |
| 5.1 | Altshuller matrix sanity check + citation check | No matrix match → drop |
| 5.2 | Principle name validation (hard gate) | Hallucinated name → drop |
| 5.2b | Contradiction-copy sweep | CP copied from parent → drop |
| 5.2c | Complexity label validation | Mislabelled complexity → drop |
| 5.3 | Duplicate ID assertion | Collision → hard fail |
| 6 | MiniLM cosine deduplication (> 0.85) | Lower-scoring duplicate → drop |
| 7 | Pydantic schema validation | Invalid schema → drop |

## Cost Estimate

| Component | Cost / round |
|-----------|-------------|
| Teacher (1,720 calls × ~1K tokens in / ~800 out) | ~$1.50 |
| Judge (~860 calls × ~1K tokens in / ~50 out) | ~$0.25 |
| **Total / round** | **~$1.75** |
| **11 rounds** | **~$19.25** |

Hard-stop at $30 enforced in `config.py::CostTracker`.

## Hard Constraints

- No synchronous API loops — `asyncio` + `httpx` only
- No single-number judge score — 4-criterion rubric always
- Matrix sanity check is mandatory (no bypass)
- No silent drops — every dropped record is logged with reason
- `meta` field carries lineage; training schema stays clean
- Smoke test manual review required before full run
