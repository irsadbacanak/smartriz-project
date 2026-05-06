"""
JSONL append helpers and checkpoint (processed_keys) read/write utilities.
"""
from __future__ import annotations

import json
from pathlib import Path

from smartriz.data_generation.config import PROCESSED_KEYS


def load_processed_keys(path: Path = PROCESSED_KEYS) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_processed_key(key: str, path: Path = PROCESSED_KEYS) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def append_jsonl(record: dict, path: Path) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
