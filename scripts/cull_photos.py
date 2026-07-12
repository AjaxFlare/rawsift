#!/usr/bin/env python3
"""Repository-local wrapper for the RAW Photo Culler CLI."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raw_photo_culler.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

