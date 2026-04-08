from __future__ import annotations

import unittest

from ha_gestures.bindings import GestureAction, GestureBinding, GestureExecution
from ha_gestures.models import ActiveGesture, FramePrimitive
from ha_gestures.runtime_controller import RuntimeController
from ha_gestures.settings_store import default_settings


class _FakeRuntime:
    def __init__(self, frames: list[FramePrimitive]) -> None:
        self._frames = frames

    def iter_camera(self, camera_index: int, max_frames: int | None = None):  # noqa: ANN001
        del camera_index, max_frames
        yield from self._frames


class _FakeBindingRegistry:
    def __init__(self, binding: GestureBinding) -> None:
        self.binding = binding

    def find(self, mode: str, trigger_id: str) -> GestureBinding | None:
        if mode == self.binding.mode and trigger_id == self.binding.trigger_id:
            return self.binding
        return None

    def all(self) -> list[GestureBinding]:
        return [self.binding]


class _FakeActivationSound:
    def __init__(self) -> None:
        self.activation_count = 0
        self.deactivation_count = 0

    def play_activation(self) -> None:
        self.activation_count += 1

    def play_deactivation(self) -> None:
        self.deactivation_count += 1


class RuntimeControllerTests(unittest.TestCase):
    def test_activation_required_arms_before_dispatch(self) -> None:
        settings = default_settings()
        settings.recognition.listening_mode = "activation_required"
        settings.recognition.activation_mode = "one_hand"
        settings.recognition.activation_trigger_id = "right_front_0_11111"
        settings.recognition.activation_hold_ms = 600
        settings.recognition.session_timeout_ms = 4000

        binding = GestureBinding(
            mode="one_hand",
            trigger_id="right_back_0_00100",
            gesture_name="middle_finger",
            action=GestureAction(type="placeholder", label="test"),
            execution=GestureExecution(mode="instant", cooldown_ms=0, repeat_every_ms=100),
        )

        controller = RuntimeController(settings, preview_only=False)
        controller.runtime = _FakeRuntime(
            [
                FramePrimitive(
                    timestamp_ms=1000,
                    hands=[],
                    active_gestures=[
                        ActiveGesture(
                            name="open_palm",
                            key="open_palm",
                            compound_id="right_front_0_11111",
                            hand="right",
                            palm_side="front",
                            rotation=0,
                        )
                    ],
                ),
                FramePrimitive(
                    timestamp_ms=1700,
                    hands=[],
                    active_gestures=[
                        ActiveGesture(
                            name="open_palm",
                            key="open_palm",
                            compound_id="right_front_0_11111",
                            hand="right",
                            palm_side="front",
                            rotation=0,
                        )
                    ],
                ),
                FramePrimitive(
                    timestamp_ms=1800,
                    hands=[],
                    active_gestures=[
                        ActiveGesture(
                            name="shy_fuck_you",
                            key="shy_fuck_you",
                            compound_id="right_back_0_00100",
                            hand="right",
                            palm_side="back",
                            rotation=0,
                        )
                    ],
                ),
            ]
        )
        controller.binding_registry = _FakeBindingRegistry(binding)
        controller.activation_sound = _FakeActivationSound()

        result = controller.process_stream()

        self.assertEqual(len(result.dispatched), 1)
        self.assertEqual(result.dispatched[0].trigger_id, "right_back_0_00100")
        self.assertEqual(controller.activation_sound.activation_count, 1)
        self.assertEqual(controller.activation_sound.deactivation_count, 0)

    def test_activation_session_plays_deactivation_sound_after_timeout(self) -> None:
        settings = default_settings()
        settings.recognition.listening_mode = "activation_required"
        settings.recognition.activation_mode = "one_hand"
        settings.recognition.activation_trigger_id = "right_front_0_11111"
        settings.recognition.activation_hold_ms = 600
        settings.recognition.session_timeout_ms = 4000

        binding = GestureBinding(
            mode="one_hand",
            trigger_id="right_back_0_00100",
            gesture_name="middle_finger",
            action=GestureAction(type="placeholder", label="test"),
            execution=GestureExecution(mode="instant", cooldown_ms=0, repeat_every_ms=100),
        )

        controller = RuntimeController(settings, preview_only=False)
        controller.runtime = _FakeRuntime(
            [
                FramePrimitive(
                    timestamp_ms=1000,
                    hands=[],
                    active_gestures=[
                        ActiveGesture(
                            name="open_palm",
                            key="open_palm",
                            compound_id="right_front_0_11111",
                            hand="right",
                            palm_side="front",
                            rotation=0,
                        )
                    ],
                ),
                FramePrimitive(
                    timestamp_ms=1700,
                    hands=[],
                    active_gestures=[
                        ActiveGesture(
                            name="open_palm",
                            key="open_palm",
                            compound_id="right_front_0_11111",
                            hand="right",
                            palm_side="front",
                            rotation=0,
                        )
                    ],
                ),
                FramePrimitive(
                    timestamp_ms=5801,
                    hands=[],
                    active_gestures=[],
                ),
            ]
        )
        controller.binding_registry = _FakeBindingRegistry(binding)
        controller.activation_sound = _FakeActivationSound()

        controller.process_stream()

        self.assertEqual(controller.activation_sound.activation_count, 1)
        self.assertEqual(controller.activation_sound.deactivation_count, 1)


if __name__ == "__main__":
    unittest.main()
