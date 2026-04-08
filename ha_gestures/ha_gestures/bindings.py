from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class GestureAction:
    type: str = "placeholder"
    label: str = ""
    domain: str = ""
    service: str = ""
    target: dict[str, object] | None = None
    data: dict[str, object] | None = None
    event_type: str = ""
    event_data: dict[str, object] | None = None
    return_response: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.target is None:
            payload.pop("target")
        if self.data is None:
            payload.pop("data")
        if self.event_data is None:
            payload.pop("event_data")
        return payload

    def summary(self) -> str:
        if self.label:
            return self.label
        if self.type == "service":
            service_name = ".".join(part for part in (self.domain, self.service) if part)
            entity_id = ""
            if isinstance(self.target, dict):
                entity_id = str(self.target.get("entity_id", "")).strip()
            if self.domain == "light" and self.service == "turn_on" and isinstance(self.data, dict):
                step = self.data.get("brightness_step_pct")
                if isinstance(step, int | float):
                    direction = "dim up" if step > 0 else "dim down"
                    amount = abs(int(step))
                    if entity_id:
                        return f"{direction} {amount}% -> {entity_id}"
                    return f"{direction} {amount}%"
            if entity_id:
                return f"{service_name} -> {entity_id}"
            return service_name or "service action"
        if self.type == "event":
            return self.event_type or "event action"
        return "placeholder"


@dataclass(slots=True)
class GestureExecution:
    mode: str = "instant"
    cooldown_ms: int = 800
    repeat_every_ms: int = 150

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class GestureBinding:
    mode: str
    trigger_id: str
    gesture_name: str
    action: GestureAction
    execution: GestureExecution

    @property
    def action_name(self) -> str:
        return self.action.summary()

    @action_name.setter
    def action_name(self, value: str) -> None:
        self.action.label = value

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "trigger_id": self.trigger_id,
            "gesture_name": self.gesture_name,
            "action": self.action.to_dict(),
            "execution": self.execution.to_dict(),
        }


def load_bindings(path: str | Path) -> list[GestureBinding]:
    bindings_path = Path(path)
    if not bindings_path.exists():
        return []

    payload = json.loads(bindings_path.read_text(encoding="utf-8"))
    return [_binding_from_payload(item) for item in payload.get("bindings", [])]


def save_bindings(path: str | Path, bindings: list[GestureBinding]) -> None:
    payload = {"bindings": [binding.to_dict() for binding in bindings]}
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def find_binding(bindings: list[GestureBinding], mode: str, trigger_id: str) -> GestureBinding | None:
    for binding in reversed(bindings):
        if binding.mode == mode and binding.trigger_id == trigger_id:
            return binding
    return None


class BindingRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._mtime_ns: int | None = None
        self._bindings: list[GestureBinding] = []
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            self._bindings = []
            self._mtime_ns = None
            return
        self._bindings = load_bindings(self.path)
        self._mtime_ns = self.path.stat().st_mtime_ns

    def maybe_reload(self) -> None:
        if not self.path.exists():
            if self._bindings:
                self._bindings = []
                self._mtime_ns = None
            return
        mtime_ns = self.path.stat().st_mtime_ns
        if self._mtime_ns != mtime_ns:
            self.reload()

    def find(self, mode: str, trigger_id: str) -> GestureBinding | None:
        self.maybe_reload()
        return find_binding(self._bindings, mode, trigger_id)

    def all(self) -> list[GestureBinding]:
        self.maybe_reload()
        return list(self._bindings)


def _binding_from_payload(item: dict[str, object]) -> GestureBinding:
    action_payload = item.get("action")
    if isinstance(action_payload, dict):
        action = GestureAction(
            type=str(action_payload.get("type", "placeholder")),
            label=str(action_payload.get("label", "")),
            domain=str(action_payload.get("domain", "")),
            service=str(action_payload.get("service", "")),
            target=action_payload.get("target") if isinstance(action_payload.get("target"), dict) else None,
            data=action_payload.get("data") if isinstance(action_payload.get("data"), dict) else None,
            event_type=str(action_payload.get("event_type", "")),
            event_data=action_payload.get("event_data") if isinstance(action_payload.get("event_data"), dict) else None,
            return_response=bool(action_payload.get("return_response", False)),
        )
    else:
        action = GestureAction(label=str(item.get("action_name", "")))

    execution_payload = item.get("execution")
    if isinstance(execution_payload, dict):
        execution = GestureExecution(
            mode=str(execution_payload.get("mode", "instant")),
            cooldown_ms=int(execution_payload.get("cooldown_ms", 800)),
            repeat_every_ms=int(execution_payload.get("repeat_every_ms", 150)),
        )
    else:
        execution = GestureExecution()

    return GestureBinding(
        mode=str(item["mode"]),
        trigger_id=str(item["trigger_id"]),
        gesture_name=str(item["gesture_name"]),
        action=action,
        execution=execution,
    )
