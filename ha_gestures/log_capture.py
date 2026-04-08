from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

_CONFIGURED = False
_LOG_DIR = Path.cwd() / "logs"
_LOG_FILE = _LOG_DIR / "housign.log"


class _TeeStream:
    def __init__(self, original: TextIO, log_path: Path) -> None:
        self._original = original
        self._log_path = log_path

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._original.write(data)
        self._original.flush()
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(data)
        return len(data)

    def flush(self) -> None:
        self._original.flush()

    def isatty(self) -> bool:
        return getattr(self._original, "isatty", lambda: False)()


def configure_process_logging(process_name: str) -> Path:
    global _CONFIGURED
    if _CONFIGURED:
        return _LOG_FILE

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    sys.stdout = _TeeStream(sys.__stdout__, _LOG_FILE)
    sys.stderr = _TeeStream(sys.__stderr__, _LOG_FILE)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    print(f"\n===== {datetime.now().isoformat(timespec='seconds')} | {process_name} started =====")
    _CONFIGURED = True
    return _LOG_FILE


def get_log_path() -> Path:
    return _LOG_FILE
