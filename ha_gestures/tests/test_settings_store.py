from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ha_gestures.settings_store import default_settings, load_settings, save_settings


class SettingsStoreTests(unittest.TestCase):
    def test_save_and_load_settings_roundtrip(self) -> None:
        settings = default_settings()
        settings.ha.url = "http://ha.local:8123"
        settings.runtime.camera_index = 2
        settings.runtime.bindings_config = "custom_bindings.json"
        settings.recognition.listening_mode = "activation_required"
        settings.recognition.activation_mode = "two_hand"
        settings.recognition.activation_trigger_id = "both::left_front_0_11111::right_front_0_11111"
        settings.recognition.activation_hold_ms = 900
        settings.gui.window_maximized = False

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(settings, path)
            loaded = load_settings(path)

        self.assertEqual(loaded.ha.url, "http://ha.local:8123")
        self.assertEqual(loaded.runtime.camera_index, 2)
        self.assertEqual(loaded.runtime.bindings_config, "custom_bindings.json")
        self.assertEqual(loaded.recognition.listening_mode, "activation_required")
        self.assertEqual(loaded.recognition.activation_mode, "two_hand")
        self.assertEqual(loaded.recognition.activation_trigger_id, "both::left_front_0_11111::right_front_0_11111")
        self.assertEqual(loaded.recognition.activation_hold_ms, 900)
        self.assertFalse(loaded.gui.window_maximized)


if __name__ == "__main__":
    unittest.main()
