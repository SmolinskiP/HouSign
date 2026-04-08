from __future__ import annotations

from dataclasses import dataclass

from .bindings import GestureBinding


@dataclass(slots=True)
class DispatchIntent:
    binding: GestureBinding
    phase: str


@dataclass(slots=True)
class _ExecutionState:
    active: bool = False
    last_started_ms: int | None = None
    last_dispatched_ms: int | None = None


class ExecutionCoordinator:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], _ExecutionState] = {}

    def evaluate(self, binding: GestureBinding, is_active: bool, timestamp_ms: int) -> list[DispatchIntent]:
        key = (binding.mode, binding.trigger_id)
        state = self._states.setdefault(key, _ExecutionState())
        execution = binding.execution
        intents: list[DispatchIntent] = []

        if is_active and not state.active:
            state.active = True
            state.last_started_ms = timestamp_ms
            if execution.mode == "instant":
                if self._passes_cooldown(state.last_dispatched_ms, execution.cooldown_ms, timestamp_ms):
                    intents.append(DispatchIntent(binding=binding, phase="instant"))
                    state.last_dispatched_ms = timestamp_ms
            elif execution.mode == "hold_start":
                intents.append(DispatchIntent(binding=binding, phase="hold_start"))
                state.last_dispatched_ms = timestamp_ms
            elif execution.mode == "hold_repeat":
                intents.append(DispatchIntent(binding=binding, phase="hold_start"))
                intents.append(DispatchIntent(binding=binding, phase="hold_repeat"))
                state.last_dispatched_ms = timestamp_ms
            return intents

        if is_active and state.active:
            if execution.mode == "hold_repeat":
                interval = max(execution.repeat_every_ms, 1)
                if state.last_dispatched_ms is None or timestamp_ms - state.last_dispatched_ms >= interval:
                    intents.append(DispatchIntent(binding=binding, phase="hold_repeat"))
                    state.last_dispatched_ms = timestamp_ms
            return intents

        if not is_active and state.active:
            state.active = False
            state.last_started_ms = None
            if execution.mode == "hold_end":
                intents.append(DispatchIntent(binding=binding, phase="hold_end"))
                state.last_dispatched_ms = timestamp_ms
            return intents

        return intents

    @staticmethod
    def _passes_cooldown(last_dispatched_ms: int | None, cooldown_ms: int, timestamp_ms: int) -> bool:
        if last_dispatched_ms is None:
            return True
        return timestamp_ms - last_dispatched_ms >= cooldown_ms
