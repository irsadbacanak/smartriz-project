#!/usr/bin/env python3
"""FastAPI server wrapper — paket `pip install -e .` ile yüklü olmalı."""
import uvicorn

from smartriz.api.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
