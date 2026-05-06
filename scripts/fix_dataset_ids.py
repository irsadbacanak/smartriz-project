#!/usr/bin/env python3
"""
One-shot migration: flag legacy (pre-UUID) IDs in training_dataset.json.

Adds {"meta": {"legacy_v0": true}} to old-format records.
Does NOT delete — manual review required before deletion.

Run: python scripts/fix_dataset_ids.py
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINAL_JSON = PROJECT_ROOT / "data" / "training_dataset.json"


def is_legacy_id(id_str: str) -> bool:
    """Legacy IDs have no UUID suffix (8-char hex at end)."""
    parts = id_str.split("-")
    if parts:
        last = parts[-1]
        if len(last) == 8:
            try:
                int(last, 16)
                return False  # Has UUID suffix — new format
            except ValueError:
                pass
    return True


def main() -> None:
    if not FINAL_JSON.exists():
        print(f"Not found: {FINAL_JSON}")
        return

    with open(FINAL_JSON, encoding="utf-8") as f:
        cases = json.load(f)

    flagged = 0
    for case in cases:
        if is_legacy_id(case.get("id", "")):
            case.setdefault("meta", {})["legacy_v0"] = True
            flagged += 1

    with open(FINAL_JSON, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    print(f"Flagged {flagged}/{len(cases)} cases as legacy_v0.")
    print("Review and delete legacy cases manually before next pipeline run.")


if __name__ == "__main__":
    main()
