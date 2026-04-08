from __future__ import annotations

import unittest

from ha_gestures.ws_client import HomeAssistantWsError, _build_websocket_url


class HomeAssistantWsClientTests(unittest.TestCase):
    def test_builds_websocket_url_from_http(self) -> None:
        self.assertEqual(
            _build_websocket_url("http://ha.local:8123"),
            "ws://ha.local:8123/api/websocket",
        )

    def test_preserves_base_path(self) -> None:
        self.assertEqual(
            _build_websocket_url("https://example.com/homeassistant"),
            "wss://example.com/homeassistant/api/websocket",
        )

    def test_requires_scheme(self) -> None:
        with self.assertRaises(HomeAssistantWsError):
            _build_websocket_url("ha.local:8123")


if __name__ == "__main__":
    unittest.main()
