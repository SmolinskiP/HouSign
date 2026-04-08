from __future__ import annotations

import sys
from pathlib import Path


def app_dir() -> Path:
    """Return the application root directory — always reliable, even on autostart."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
