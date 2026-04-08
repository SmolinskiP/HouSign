from __future__ import annotations

import unittest

from ha_gestures.gesture_engine import GestureEngine
from ha_gestures.models import FramePrimitive, HandPrimitive, MotionPrimitive, Point3D, TwoHandPrimitive


class GestureEngineTests(unittest.TestCase):
    def make_hand(self, **kwargs) -> HandPrimitive:
        defaults = {
            "hand_id": "right",
            "handedness_score": 0.99,
            "palm_side": "back",
            "rotation_quadrant": 0,
            "fingers": {
                "thumb": "folded",
                "index": "folded",
                "middle": "folded",
                "ring": "folded",
                "pinky": "folded",
            },
            "position": Point3D(0.5, 0.5, 0.0),
            "motion": MotionPrimitive(),
            "confidence": 0.99,
            "gesture_hints": [],
        }
        defaults.update(kwargs)
        return HandPrimitive(**defaults)

    def make_engine(self, **kwargs) -> GestureEngine:
        return GestureEngine(config_path="gestures.yaml", **kwargs)

    def test_unmatched_pose_becomes_raw_compound(self) -> None:
        engine = self.make_engine(min_stable_frames=3)
        hand = self.make_hand(
            hand_id="right",
            palm_side="front",
            rotation_quadrant=0,
            fingers={
                "thumb": "folded",
                "index": "folded",
                "middle": "folded",
                "ring": "folded",
                "pinky": "extended",
            },
        )

        frame = engine.apply(FramePrimitive(timestamp_ms=0, hands=[hand]))

        expected = "right_front_0_00001"
        self.assertEqual(frame.active_gesture, expected)
        self.assertIsNone(frame.active_gesture_key)
        self.assertEqual(frame.active_gesture_compound_id, expected)
        self.assertEqual(frame.active_gestures_by_hand["right"].compound_id, expected)

    def test_fuck_you_keeps_name_and_raw_compound(self) -> None:
        engine = self.make_engine(min_stable_frames=3)
        hand = self.make_hand(
            hand_id="left",
            palm_side="back",
            rotation_quadrant=0,
            fingers={
                "thumb": "extended",
                "index": "folded",
                "middle": "extended",
                "ring": "folded",
                "pinky": "folded",
            },
        )

        frame = None
        for timestamp_ms in (0, 120, 240):
            frame = engine.apply(FramePrimitive(timestamp_ms=timestamp_ms, hands=[hand]))

        self.assertEqual(frame.active_gesture, "fuck_you")
        self.assertEqual(frame.active_gesture_key, "fuck_you")
        self.assertEqual(
            frame.active_gesture_compound_id,
            "left_back_0_10100",
        )

    def test_satan_keeps_name_and_raw_compound(self) -> None:
        engine = self.make_engine(min_stable_frames=3)
        hand = self.make_hand(
            hand_id="right",
            palm_side="front",
            rotation_quadrant=0,
            fingers={
                "thumb": "folded",
                "index": "extended",
                "middle": "folded",
                "ring": "folded",
                "pinky": "extended",
            },
        )

        frame = None
        for timestamp_ms in (0, 120, 240):
            frame = engine.apply(FramePrimitive(timestamp_ms=timestamp_ms, hands=[hand]))

        self.assertEqual(frame.active_gesture, "satan")
        self.assertEqual(frame.active_gesture_key, "satan")
        self.assertEqual(
            frame.active_gesture_compound_id,
            "right_front_0_01001",
        )

    def test_point_keeps_name_and_raw_compound(self) -> None:
        engine = self.make_engine(min_stable_frames=3)
        hand = self.make_hand(
            hand_id="right",
            palm_side="back",
            rotation_quadrant=90,
            fingers={
                "thumb": "folded",
                "index": "extended",
                "middle": "folded",
                "ring": "folded",
                "pinky": "folded",
            },
        )

        frame = None
        for timestamp_ms in (0, 120, 240):
            frame = engine.apply(FramePrimitive(timestamp_ms=timestamp_ms, hands=[hand]))

        self.assertEqual(frame.active_gesture, "point")
        self.assertEqual(frame.active_gesture_key, "point")
        self.assertEqual(
            frame.active_gesture_compound_id,
            "right_back_90_01000",
        )

    def test_swipe_left_compound_is_raw_pose(self) -> None:
        engine = self.make_engine(min_stable_frames=3)
        hand = self.make_hand(
            hand_id="right",
            fingers={
                "thumb": "extended",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "folded",
            },
            motion=MotionPrimitive(direction="right", speed=0.25, dx=0.12, dy=0.0),
        )

        frame = None
        for timestamp_ms in (0, 100, 200):
            frame = engine.apply(FramePrimitive(timestamp_ms=timestamp_ms, hands=[hand]))

        self.assertEqual(frame.active_gesture, "swipe_left")
        self.assertEqual(frame.active_gesture_key, "swipe_left")
        self.assertEqual(
            frame.active_gesture_compound_id,
            "right_back_0_11110",
        )

    def test_two_hand_expand_uses_two_hand_compound(self) -> None:
        engine = self.make_engine(min_stable_frames=2)
        left = self.make_hand(hand_id="left")
        right = self.make_hand(hand_id="right")

        frame = engine.apply(
            FramePrimitive(
                timestamp_ms=0,
                hands=[left, right],
                two_hand=TwoHandPrimitive(active=True, distance=0.4, motion="expanding"),
            )
        )
        frame = engine.apply(
            FramePrimitive(
                timestamp_ms=100,
                hands=[left, right],
                two_hand=TwoHandPrimitive(active=True, distance=0.45, motion="expanding"),
            )
        )

        self.assertEqual(frame.active_gesture, "two_hand_expand")
        self.assertEqual(frame.active_gesture_key, "two_hand_expand")
        self.assertEqual(frame.active_gesture_hand, "both")
        self.assertEqual(frame.active_gesture_compound_id, "both_expanding")

    def test_open_palm_keeps_name_and_raw_compound(self) -> None:
        engine = self.make_engine(min_stable_frames=3)
        hand = self.make_hand(
            hand_id="left",
            palm_side="front",
            rotation_quadrant=90,
            fingers={
                "thumb": "extended",
                "index": "extended",
                "middle": "extended",
                "ring": "extended",
                "pinky": "extended",
            },
        )

        frame = None
        for timestamp_ms in (0, 120, 240):
            frame = engine.apply(FramePrimitive(timestamp_ms=timestamp_ms, hands=[hand]))

        self.assertEqual(frame.active_gesture, "open_palm")
        self.assertEqual(
            frame.active_gesture_compound_id,
            "left_front_90_11111",
        )

    def test_tracks_both_hands_separately(self) -> None:
        engine = self.make_engine(min_stable_frames=2)
        left = self.make_hand(
            hand_id="left",
            palm_side="back",
            rotation_quadrant=0,
            fingers={
                "thumb": "extended",
                "index": "folded",
                "middle": "extended",
                "ring": "folded",
                "pinky": "folded",
            },
        )
        right = self.make_hand(
            hand_id="right",
            palm_side="front",
            rotation_quadrant=0,
            fingers={
                "thumb": "folded",
                "index": "extended",
                "middle": "folded",
                "ring": "folded",
                "pinky": "extended",
            },
        )

        engine.apply(FramePrimitive(timestamp_ms=0, hands=[left, right]))
        frame = engine.apply(FramePrimitive(timestamp_ms=100, hands=[left, right]))

        self.assertEqual(len(frame.active_gestures), 2)
        self.assertEqual(frame.active_gestures_by_hand["left"].key, "fuck_you")
        self.assertEqual(frame.active_gestures_by_hand["right"].key, "satan")
        compounds = {gesture.compound_id for gesture in frame.active_gestures}
        self.assertIn(
            "left_back_0_10100",
            compounds,
        )
        self.assertIn(
            "right_front_0_01001",
            compounds,
        )

    def test_active_gesture_holds_briefly_after_signal_drops(self) -> None:
        engine = self.make_engine(min_stable_frames=2, active_hold_ms=500)
        hand = self.make_hand(
            hand_id="right",
            palm_side="back",
            rotation_quadrant=0,
            fingers={
                "thumb": "extended",
                "index": "folded",
                "middle": "extended",
                "ring": "folded",
                "pinky": "folded",
            },
        )

        engine.apply(FramePrimitive(timestamp_ms=0, hands=[hand]))
        frame = engine.apply(FramePrimitive(timestamp_ms=100, hands=[hand]))
        self.assertEqual(frame.active_gesture_key, "fuck_you")

        follow_up = engine.apply(FramePrimitive(timestamp_ms=300, hands=[]))
        self.assertEqual(follow_up.active_gesture_key, "fuck_you")
        self.assertEqual(
            follow_up.active_gesture_compound_id,
            "right_back_0_10100",
        )


if __name__ == "__main__":
    unittest.main()
