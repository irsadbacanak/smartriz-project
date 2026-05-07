# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python)
```bash
# Setup
pip install -e .

# Run API server (port 8000)
python scripts/run_api.py

# Run LangGraph workflow smoke test
python scripts/run_graph_test.py

# Generate synthetic training data
python scripts/generate_data.py --help

# Tests
.venv/bin/python -m pytest -q
# Single test file:
.venv/bin/python -m pytest tests/test_agents.py -q

# Lint / format
ruff check src/
black src/
mypy src/
```

### Frontend (in `ui/`)
```bash
npm install
npm run dev      # Vite dev server → http://localhost:5173
npm run build
npm run lint
```

## Architecture

SmarTRIZ applies TRIZ (Theory of Inventive Problem Solving) to analyze problems using a multi-agent LangGraph pipeline.

### Agent Pipeline (`src/smartriz/agents/`)
Four sequential nodes defined in `graph.py`, sharing state via `state.py` (TypedDict):
1. **Problem Analyst** — structures and contextualizes the problem
2. **Contradiction Detector** — identifies technical/physical contradictions
3. **ReAct Solver** — generates TRIZ-based solutions using inventive principles
4. **Reflexion Critic** — evaluates and refines solution quality

### API (`src/smartriz/api/main.py`)
FastAPI app with two endpoints:
- `POST /api/analyze` — synchronous analysis, returns full result
- `GET /api/stream` — Server-Sent Events, emits agent node outputs as they complete
- CORS enabled for `http://localhost:5173`

### Frontend (`ui/src/`)
React 19 + Vite SPA. State flows through 6 screens (`screens/`):
- `ProblemInput` → `AgentPipeline` (live SSE) → results screens
- `useTrizStream.js` hook handles SSE connection and dispatches agent events
- No routing library — screen transitions via `useState` in `App.jsx`

### Data Generation (`src/smartriz/data_generation/`)
Synthetic TRIZ training data pipeline using a Teacher-Judge pattern:
- `config.py` — DeepSeek model config, cost tracking, API settings
- `pipeline/` — Teacher (generates), Judge (evaluates), Extractor, Orchestrator
- `quality/` — deduplication and validation
- Controlled by YAML configs; run via `scripts/generate_data.py`

### Key Design Rules
- Agent state is a single `TypedDict` passed through the graph — add fields to `state.py` first when extending the pipeline
- `api/main.py` imports and invokes the graph directly — no service abstraction layer between them
- ChromaDB in `data/` is used for semantic retrieval during solving; uses in-memory client in tests

## Environment

Create `.env` in the project root:
```
DEEPINFRA_API_KEY=your_key_here
```

All DeepSeek model calls route through DeepInfra API. Check `src/smartriz/data_generation/config.py` for model names and cost-tracking settings.

Run `python scripts/check_setup.py` to verify all dependencies are properly installed.
