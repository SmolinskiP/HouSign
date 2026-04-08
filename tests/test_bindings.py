from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ha_gestures.bindings import GestureAction, GestureBinding, GestureExecution, find_binding, load_bindings, save_bindings
from ha_gestures.gui_state import editor_state_from_binding


class BindingsTest(unittest.TestCase):
    def test_save_and_load_bindings(self) -> None:
        binding = GestureBinding(
            mode="one_hand",
            trigger_id="right_front_0_11111",
            gesture_name="open_right",
            action=GestureAction(type="placeholder", label="lights.toggle"),
            execution=GestureExecution(mode="instant", cooldown_ms=500, repeat_every_ms=100),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gesture_bindings.json"
            save_bindings(path, [binding])
            loaded = load_bindings(path)

        self.assertEqual(loaded, [binding])
        self.assertEqual(find_binding(loaded, "one_hand", binding.trigger_id), binding)

    def test_editor_state_from_two_hand_binding(self) -> None:
        binding = GestureBinding(
            mode="two_hand",
            trigger_id=(
                "both::"
                "left_front_90_10001::"
                "right_back_180_01100"
            ),
            gesture_name="party",
            action=GestureAction(type="placeholder", label="script.party_mode"),
            execution=GestureExecution(),
        )

        left, right, mode, active_hand = editor_state_from_binding(binding)

        self.assertEqual(mode, "two_hand")
        self.assertEqual(active_hand, "right")
        self.assertEqual(left.hand_id, "left")
        self.assertEqual(left.rotation_quadrant, 90)
        self.assertEqual(left.fingers["pinky"], "extended")
        self.assertEqual(right.hand_id, "right")
        self.assertEqual(right.palm_side, "back")
        self.assertEqual(right.rotation_quadrant, 180)
        self.assertEqual(right.fingers["middle"], "extended")

    def test_loads_legacy_action_name_payload(self) -> None:
        payload = {
            "bindings": [
                {
                    "mode": "one_hand",
                    "trigger_id": "right_back_0_00100",
                    "action_name": "legacy-action",
                    "gesture_name": "legacy-gesture",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gesture_bindings.json"
            path.write_text(__import__("json").dumps(payload), encoding="utf-8")
            loaded = load_bindings(path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].action.type, "placeholder")
        self.assertEqual(loaded[0].action.label, "legacy-action")

    def test_service_action_summary_describes_dimming(self) -> None:
        binding = GestureBinding(
            mode="one_hand",
            trigger_id="right_front_0_11111",
            gesture_name="dim_up",
            action=GestureAction(
                type="service",
                domain="light",
                service="turn_on",
                target={"entity_id": "light.living_room"},
                data={"brightness_step_pct": 10},
            ),
            execution=GestureExecution(mode="hold_repeat", cooldown_ms=0, repeat_every_ms=150),
        )

        self.assertEqual(binding.action_name, "dim up 10% -> light.living_room")


if __name__ == "__main__":
    unittest.main()
