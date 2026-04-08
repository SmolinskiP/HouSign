from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .bindings import GestureAction, GestureBinding
from .ws_client import HomeAssistantWsClient

_LOG = logging.getLogger(__name__)


ExecutionPhase = str


@dataclass(slots=True)
class DispatchRecord:
    trigger_id: str
    phase: ExecutionPhase
    action_type: str
    started_at_ms: int


class ActionDispatcher:
    def __init__(self, client: HomeAssistantWsClient | None = None) -> None:
        self.client = client

    def dispatch(self, binding: GestureBinding, phase: ExecutionPhase, timestamp_ms: int | None = None) -> DispatchRecord:
        current_ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        action = binding.action
        _LOG.info(
            "Dispatching binding '%s' [%s] for trigger=%s action_type=%s action=%s",
            binding.gesture_name,
            phase,
            binding.trigger_id,
            action.type,
            action.summary(),
        )
        if action.type == "placeholder":
            _LOG.info("Placeholder action for %s [%s]: %s", binding.trigger_id, phase, action.label or binding.gesture_name)
        elif action.type == "service":
            self._dispatch_service(action)
        elif action.type == "event":
            self._dispatch_event(action)
        else:
            raise ValueError(f"Unsupported action type: {action.type}")

        return DispatchRecord(
            trigger_id=binding.trigger_id,
            phase=phase,
            action_type=action.type,
            started_at_ms=current_ts,
        )

    def _dispatch_service(self, action: GestureAction) -> None:
        if self.client is None:
            raise RuntimeError("Cannot dispatch Home Assistant service without an active WebSocket client.")
        if not action.domain or not action.service:
            raise ValueError("Service action requires both domain and service.")
        _LOG.info(
            "Calling Home Assistant service %s.%s target=%s data=%s return_response=%s",
            action.domain,
            action.service,
            action.target,
            action.data,
            action.return_response,
        )
        self.client.call_service(
            action.domain,
            action.service,
            service_data=action.data or None,
            target=action.target or None,
            return_response=action.return_response,
        )

    def _dispatch_event(self, action: GestureAction) -> None:
        if self.client is None:
            raise RuntimeError("Cannot dispatch Home Assistant event without an active WebSocket client.")
        if not action.event_type:
            raise ValueError("Event action requires event_type.")
        _LOG.info("Firing Home Assistant event %s event_data=%s", action.event_type, action.event_data)
        self.client.fire_event(action.event_type, action.event_data or None)
