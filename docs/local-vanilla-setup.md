# Local Vanilla Setup (Ollama + 7B Model)

Run SmarTRIZ end-to-end with a local model — no cloud API required for the agent pipeline.

## Prerequisites

### 1. Install Ollama (macOS)
```bash
brew install ollama
```

### 2. Pull the model (Q4_K_M quantization, ~4.7 GB)
```bash
ollama pull qwen2.5:7b-instruct
ollama list   # verify it appears
```

### 3. Environment
```bash
cp .env.example .env
# Edit .env — DEEPINFRA_API_KEY is only needed for data generation scripts
```

### 4. Python dependencies
```bash
pip install -e .
```

### 5. Frontend dependencies
```bash
cd ui && npm install
```

---

## Running (3 terminals)

**Terminal 1 — Ollama:**
```bash
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_KEEP_ALIVE=10m
ollama serve
```

**Terminal 2 — API (port 8000):**
```bash
python scripts/run_api.py
```

**Terminal 3 — UI (port 5173):**
```bash
cd ui && npm run dev
```

Open http://localhost:5173, type a problem, click Analyze.

---

## Verification

```bash
# Smoke test — pipeline only (no server needed)
python scripts/run_graph_test.py

# API health
curl http://localhost:8000/health

# SSE stream
curl -N "http://localhost:8000/api/stream?problem=A%20heavy%20bridge%20component%20must%20remain%20strong%20while%20reducing%20weight."
```

---

## Switching Models

Set `SMARTRIZ_LOCAL_MODEL` in `.env` before starting the API:

```
# Faster, slightly lower JSON discipline
SMARTRIZ_LOCAL_MODEL=llama3.1:8b-instruct

# Smallest footprint, lowest quality
SMARTRIZ_LOCAL_MODEL=mistral:7b-instruct-q4_K_M
```

Pull the model first: `ollama pull <model-name>`

**12B+ models are not recommended** on 16 GB RAM — they will swap and degrade performance.

---

## Performance Check

```bash
ollama run qwen2.5:7b-instruct --verbose "Explain TRIZ principle 35 in two sentences." 2>&1 | tail -5
```

If `eval rate` is below 25 token/s and Activity Monitor shows 4 GB+ swap, close other apps or switch to a smaller model.

---

## Known Limitations

- **TRIZ quality**: A vanilla 7B model has no TRIZ-specific fine-tuning. It understands general engineering reasoning but may select generic principles rather than the most contextually appropriate ones.
- **JSON parse robustness**: The client strips markdown fences and retries once at lower temperature (0.1). Persistent failures raise an exception with the raw output for debugging.
- **`selected_principles` consistency**: The model may use slightly different principle numbering or names across runs. Numbers 1–40 are generally stable; names vary.
- **First-request latency**: Model cold-start takes 5–10 seconds. Subsequent calls are fast (context stays loaded via `OLLAMA_KEEP_ALIVE`).
- **No concurrency**: The LangGraph pipeline is sequential (4 nodes in order). Do not submit multiple problems simultaneously from the UI.
