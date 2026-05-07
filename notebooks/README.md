# SmarTRIZ Training Notebooks

Four sequential Colab Pro notebooks for training and evaluating SmarTRIZ on Qwen2.5-7B.

## Run Order

| # | Notebook | A100 GPU Time | Produces |
|---|----------|---------------|---------|
| 1 | `00_dataset_analysis.ipynb` | ~10 min | `training_dataset_clean.json`, `test_split.json` |
| 2 | `01_sft_training.ipynb` | ~4–6 hours | `checkpoints/sft-7b/merged/` |
| 3 | `02_dpo_training.ipynb` | ~1–2 hours | `checkpoints/dpo-7b/merged/` |
| 4 | `03_convert_and_eval.ipynb` | ~2–3 hours | `gguf/*.gguf`, `evaluation/results.json` |

For 14B models multiply GPU times by ~2.5× and set `MODEL_SIZE = '14b'` in each notebook's config cell.

---

## Setup

### 1. Upload data to Google Drive

Create this folder structure in your Google Drive before opening any notebook:

```
MyDrive/smartriz/
└── data/
    ├── training_dataset.json       ← from repo: data/training_dataset.json
    ├── rejected_dataset.jsonl      ← from repo: data/rejected_dataset.jsonl
    └── borderline.jsonl            ← from repo: data/borderline.jsonl
```

The remaining folders (`checkpoints/`, `gguf/`, `evaluation/`) are created automatically.

### 2. Set DRIVE_PATH

The first config cell in every notebook has:

```python
DRIVE_PATH = '/content/drive/MyDrive/smartriz/'
```

Change this if your Drive folder is at a different path.

### 3. API Keys

| Key | Notebook | Where to get |
|-----|----------|--------------|
| W&B API key | 01 | [wandb.ai](https://wandb.ai) → User Settings → API Keys |
| DeepInfra API key | 02, 03 | [deepinfra.com](https://deepinfra.com) → API Keys |

**W&B login** — run this once per Colab session in Notebook 01:
```python
import wandb
wandb.login()  # enter your key when prompted
```

**DeepInfra key** — paste directly into the config cell:
```python
DEEPINFRA_API_KEY = 'your_key_here'
```

---

## Checkpoint Resume

Every notebook detects prior work and skips it automatically:

- **Notebook 00:** Checks if `training_dataset_clean.json` already exists before re-cleaning.
- **Notebook 01:** Resumes from the latest `checkpoint-N` directory in `OUTPUT_DIR`.
- **Notebook 02:** Skips DPO pair building if `dpo_dataset.json` already exists; resumes DPO training from latest checkpoint.
- **Notebook 03:** Skips GGUF conversion if `.gguf` files exist; skips per-model scoring if already in `results.json`.

---

## Downloading GGUF to M1 Pro for Ollama

After Notebook 03 finishes, GGUF files are in `DRIVE_PATH/gguf/`.

### Option A — Google Drive for Desktop (easiest)

1. Install [Google Drive for Desktop](https://www.google.com/drive/download/)
2. Files appear at `~/Library/CloudStorage/GoogleDrive-you@gmail.com/My Drive/smartriz/gguf/`

### Option B — gdown from terminal

```bash
pip install gdown

# Get the file ID from the Google Drive share link, then:
gdown 'https://drive.google.com/uc?id=FILE_ID_HERE' \
      -O ~/models/smartriz-sft-7b-Q4_K_M.gguf
```

### Load in Ollama

```bash
# 1. Create a Modelfile
cat > ~/models/Modelfile-smartriz-sft << 'EOF'
FROM ~/models/smartriz-sft-7b-Q4_K_M.gguf
SYSTEM "You are SmarTRIZ, an expert engineering innovation assistant. Solve technical problems using TRIZ methodology. Identify the technical contradiction, select inventive principles from the Altshuller matrix, reason step by step, and propose a solution."
PARAMETER temperature 0
EOF

# 2. Register the model
ollama create smartriz-sft -f ~/models/Modelfile-smartriz-sft

# 3. Run it
ollama run smartriz-sft "A bicycle chain stretches under load..."
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `CUDA out of memory` | Halve `BATCH_SIZE` in the config cell |
| `FileNotFoundError: training_dataset_clean.json` | Run Notebook 00 first |
| DPO trainer crashes on `ref_model=None` | `!pip install trl==0.11.4` |
| GGUF conversion: `convert_hf_to_gguf.py not found` | Delete `/content/llama.cpp` and re-run the clone cell |
| W&B shows `offline` mode | Call `wandb.login()` before `trainer.train()` |
| Teacher API returns empty | Check `DEEPINFRA_API_KEY` is set in the config cell |
