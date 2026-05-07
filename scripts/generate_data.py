#!/usr/bin/env python3
"""Synthetic data pipeline wrapper."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from smartriz.data_generation.main import main


if __name__ == "__main__":
    main()
