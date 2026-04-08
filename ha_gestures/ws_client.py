from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from websockets.sync.client import ClientConnection, connect

_LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class HomeAssistantConnectionSettings:
    url: str
    token: str
    open_timeout: float = 10.0
    ping_interval: float = 20.0
    ping_timeout: float = 20.0


class HomeAssistantWsError(RuntimeError):
    """Raised when Home Assistant WebSocket operations fail."""


class HomeAssistantWsClient:
    def __init__(self, settings: HomeAssistantConnectionSettings) -> None:
        self.settings = settings
        self._connection: ClientConnection | None = None
        self._message_id = 0

    def connect(self) -> None:
        self.close()
        websocket_url = _build_websocket_url(self.settings.url)
        _LOG.info("Connecting to Home Assistant WebSocket: %s", websocket_url)
        self._connection = connect(
            websocket_url,
            open_timeout=self.settings.open_timeout,
            ping_interval=self.settings.ping_interval,
            ping_timeout=self.settings.ping_timeout,
        )

        first_message = self._recv_json()
        _LOG.info("Home Assistant handshake message: %s", first_message.get("type"))
        if first_message.get("type") != "auth_required":
            raise HomeAssistantWsError(f"Unexpected Home Assistant auth handshake: {first_message}")

        self._send_json({"type": "auth", "access_token": self.settings.token})
        _LOG.info("Sent Home Assistant auth payload.")
        auth_result = self._recv_json()
        if auth_result.get("type") == "auth_ok":
            _LOG.info("Home Assistant authentication succeeded.")
            return
        if auth_result.get("type") == "auth_invalid":
            _LOG.error("Home Assistant authentication failed: %s", auth_result.get("message", "Invalid access token or password."))
            raise HomeAssistantWsError(auth_result.get("message", "Invalid Home Assistant token."))
        raise HomeAssistantWsError(f"Unexpected Home Assistant auth response: {auth_result}")

    def ensure_connected(self) -> None:
        if self._connection is None:
            self.connect()

    def close(self) -> None:
        if self._connection is not None:
            _LOG.info("Closing Home Assistant WebSocket connection.")
            self._connection.close()
            self._connection = None

    def fire_event(self, event_type: str, event_data: dict[str, object] | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "fire_event",
            "event_type": event_type,
        }
        if event_data:
            payload["event_data"] = event_data
        result = self._call(payload)
        return result if isinstance(result, dict) else {}

    def call_service(
        self,
        domain: str,
        service: str,
        *,
        service_data: dict[str, object] | None = None,
        target: dict[str, object] | None = None,
        return_response: bool = False,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "call_service",
            "domain": domain,
            "service": service,
            "return_response": return_response,
        }
        if service_data:
            payload["service_data"] = service_data
        if target:
            payload["target"] = target
        result = self._call(payload)
        return result if isinstance(result, dict) else {}

    def get_states(self) -> list[dict[str, object]]:
        _LOG.info("Requesting Home Assistant states list.")
        result = self._call({"type": "get_states"})
        if isinstance(result, list):
            _LOG.info("Loaded %s Home Assistant states.", len(result))
            return [item for item in result if isinstance(item, dict)]
        raise HomeAssistantWsError(f"Unexpected get_states payload: {result!r}")

    def get_services(self) -> dict[str, object]:
        _LOG.info("Requesting Home Assistant services list.")
        result = self._call({"type": "get_services"})
        if isinstance(result, dict):
            _LOG.info("Loaded Home Assistant services list.")
            return result
        raise HomeAssistantWsError(f"Unexpected get_services payload: {result!r}")

    def _call(self, payload: dict[str, object]) -> object:
        self.ensure_connected()
        message_id = self._next_message_id()
        envelope = {"id": message_id, **payload}
        self._send_json(envelope)

        while True:
            message = self._recv_json()
            if message.get("id") != message_id:
                continue
            if message.get("type") != "result":
                raise HomeAssistantWsError(f"Unexpected Home Assistant result payload: {message}")
            if not message.get("success", False):
                raise HomeAssistantWsError(str(message.get("error", message)))
            return message.get("result")

    def _next_message_id(self) -> int:
        self._message_id += 1
        return self._message_id

    def _send_json(self, payload: dict[str, object]) -> None:
        if self._connection is None:
            raise HomeAssistantWsError("Home Assistant WebSocket is not connected.")
        self._connection.send(json.dumps(payload))

    def _recv_json(self) -> dict[str, object]:
        if self._connection is None:
            raise HomeAssistantWsError("Home Assistant WebSocket is not connected.")
        raw = self._connection.recv()
        if not isinstance(raw, str):
            raise HomeAssistantWsError("Expected textual JSON response from Home Assistant.")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise HomeAssistantWsError(f"Expected dict response from Home Assistant, got: {payload!r}")
        return payload


def _build_websocket_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme:
        raise HomeAssistantWsError("Home Assistant URL must include http:// or https://")

    if parsed.scheme == "http":
        scheme = "ws"
    elif parsed.scheme == "https":
        scheme = "wss"
    elif parsed.scheme in {"ws", "wss"}:
        scheme = parsed.scheme
    else:
        raise HomeAssistantWsError(f"Unsupported Home Assistant URL scheme: {parsed.scheme}")

    path = parsed.path.rstrip("/")
    if path.endswith("/api/websocket"):
        websocket_path = path
    elif path:
        websocket_path = f"{path}/api/websocket"
    else:
        websocket_path = "/api/websocket"

    return urlunparse((scheme, parsed.netloc, websocket_path, "", "", ""))
