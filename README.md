# SmarTRIZ

SmarTRIZ is a TRIZ-driven AI project that includes:
- agent-based problem analysis workflows,
- a FastAPI backend for serving results,
- a synthetic data generation pipeline,
- and a React UI.

## Project Structure

```text
smartriz-project/
├── src/smartriz/
│   ├── agents/
│   ├── api/
│   ├── data_generation/
│   ├── core/
│   ├── models/
│   ├── evaluation/
│   └── utils/
├── tests/
├── scripts/
├── data/
└── ui/
```

## Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Optional: install as editable package
pip install -e .

# Run graph smoke test
.venv/bin/python scripts/run_graph_test.py

# Run synthetic data CLI help
.venv/bin/python scripts/generate_data.py -h

# Run API
.venv/bin/python scripts/run_api.py
```

## Testing

```bash
.venv/bin/python -m pytest -q
```
