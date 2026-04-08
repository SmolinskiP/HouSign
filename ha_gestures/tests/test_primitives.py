from __future__ import annotations

import unittest

from ha_gestures.models import Point3D
from ha_gestures.primitives import (
    INDEX_DIP,
    INDEX_MCP,
    INDEX_PIP,
    INDEX_TIP,
    MIDDLE_MCP,
    PrimitiveExtractor,
    WRIST,
    _finger_states,
    _rotation_quadrant,
)


def make_hand() -> list[Point3D]:
    return [Point3D(0.5, 0.5, 0.0) for _ in range(21)]


class PrimitiveGeometryTests(unittest.TestCase):
    def test_rotation_quantizes_up(self) -> None:
        hand = make_hand()
        hand[WRIST] = Point3D(0.5, 0.8, 0.0)
        hand[MIDDLE_MCP] = Point3D(0.5, 0.5, 0.0)
        self.assertEqual(_rotation_quadrant(hand), 0)

    def test_rotation_quantizes_right(self) -> None:
        hand = make_hand()
        hand[WRIST] = Point3D(0.4, 0.5, 0.0)
        hand[MIDDLE_MCP] = Point3D(0.7, 0.5, 0.0)
        self.assertEqual(_rotation_quadrant(hand), 90)

    def test_index_finger_detected_as_extended(self) -> None:
        hand = make_hand()
        hand[WRIST] = Point3D(0.5, 0.9, 0.0)
        hand[INDEX_MCP] = Point3D(0.5, 0.7, 0.0)
        hand[INDEX_PIP] = Point3D(0.5, 0.55, 0.0)
        hand[INDEX_DIP] = Point3D(0.5, 0.4, 0.0)
        hand[INDEX_TIP] = Point3D(0.5, 0.2, 0.0)
        states = _finger_states(hand)
        self.assertEqual(states["index"], "extended")

    def test_motion_direction_detects_right(self) -> None:
        extractor = PrimitiveExtractor(history_window_s=1.0, motion_deadzone=0.01)
        hand = make_hand()
        hand[WRIST] = Point3D(0.3, 0.6, 0.0)
        hand[INDEX_MCP] = Point3D(0.4, 0.5, 0.0)
        hand[MIDDLE_MCP] = Point3D(0.45, 0.5, 0.0)

        first = extractor.extract_frame([("Right", 0.95, hand)], timestamp_s=0.0)

        hand[WRIST] = Point3D(0.55, 0.6, 0.0)
        hand[INDEX_MCP] = Point3D(0.65, 0.5, 0.0)
        hand[MIDDLE_MCP] = Point3D(0.7, 0.5, 0.0)
        second = extractor.extract_frame([("Right", 0.95, hand)], timestamp_s=0.3)

        self.assertEqual(first.hands[0].motion.direction, "steady")
        self.assertEqual(second.hands[0].motion.direction, "right")


if __name__ == "__main__":
    unittest.main()
