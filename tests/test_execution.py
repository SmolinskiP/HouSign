from __future__ import annotations

import unittest

from ha_gestures.bindings import GestureAction, GestureBinding, GestureExecution
from ha_gestures.execution import ExecutionCoordinator


class ExecutionCoordinatorTests(unittest.TestCase):
    def make_binding(self, *, mode: str = "instant") -> GestureBinding:
        return GestureBinding(
            mode="one_hand",
            trigger_id="right_back_0_00100",
            gesture_name="test",
            action=GestureAction(type="placeholder", label="noop"),
            execution=GestureExecution(mode=mode, cooldown_ms=500, repeat_every_ms=100),
        )

    def test_instant_dispatches_once_until_cooldown_passes(self) -> None:
        coordinator = ExecutionCoordinator()
        binding = self.make_binding(mode="instant")

        first = coordinator.evaluate(binding, True, 1000)
        second = coordinator.evaluate(binding, True, 1100)
        third = coordinator.evaluate(binding, False, 1200)
        fourth = coordinator.evaluate(binding, True, 1700)

        self.assertEqual([intent.phase for intent in first], ["instant"])
        self.assertEqual(second, [])
        self.assertEqual(third, [])
        self.assertEqual([intent.phase for intent in fourth], ["instant"])

    def test_hold_repeat_starts_and_repeats(self) -> None:
        coordinator = ExecutionCoordinator()
        binding = self.make_binding(mode="hold_repeat")

        first = coordinator.evaluate(binding, True, 1000)
        second = coordinator.evaluate(binding, True, 1050)
        third = coordinator.evaluate(binding, True, 1110)

        self.assertEqual([intent.phase for intent in first], ["hold_start", "hold_repeat"])
        self.assertEqual(second, [])
        self.assertEqual([intent.phase for intent in third], ["hold_repeat"])

    def test_hold_end_dispatches_on_release(self) -> None:
        coordinator = ExecutionCoordinator()
        binding = self.make_binding(mode="hold_end")

        coordinator.evaluate(binding, True, 1000)
        release = coordinator.evaluate(binding, False, 1200)

        self.assertEqual([intent.phase for intent in release], ["hold_end"])


if __name__ == "__main__":
    unittest.main()
