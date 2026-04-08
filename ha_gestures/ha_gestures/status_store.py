from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

STATUS_PATH = Path.cwd() / "logs" / "runtime_status.json"


@dataclass(slots=True)
class RuntimeStatus:
    runtime_state: str = "stopped"
    ha_state: str = "not_configured"
    last_error: str = ""
    updated_at_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_runtime_status(path: str | Path = STATUS_PATH) -> RuntimeStatus:
    status_path = Path(path)
    if not status_path.exists():
        return RuntimeStatus()
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    return RuntimeStatus(
        runtime_state=str(payload.get("runtime_state", "stopped")),
        ha_state=str(payload.get("ha_state", "not_configured")),
        last_error=str(payload.get("last_error", "")),
        updated_at_ms=int(payload.get("updated_at_ms", 0)),
    )


def save_runtime_status(
    *,
    runtime_state: str,
    ha_state: str,
    last_error: str = "",
    path: str | Path = STATUS_PATH,
) -> RuntimeStatus:
    status = RuntimeStatus(
        runtime_state=runtime_state,
        ha_state=ha_state,
        last_error=last_error,
        updated_at_ms=int(time.time() * 1000),
    )
    status_path = Path(path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return status
