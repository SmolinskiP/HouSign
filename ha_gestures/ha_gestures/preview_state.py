from __future__ import annotations

from dataclasses import dataclass

from .models import FramePrimitive, HandPrimitive, MotionPrimitive, Point3D, TwoHandPrimitive

FINGER_ORDER = ("thumb", "index", "middle", "ring", "pinky")


class EditableSingleHandState:
    def __init__(self, hand_id: str) -> None:
        self.hand_id = hand_id
        self.enabled = True
        self.palm_side = "front"
        self.rotation_quadrant = 0
        self.fingers: dict[str, str] = {f: "extended" for f in FINGER_ORDER}
        self.motion_direction = "steady"
        self.motion_speed = 0.0
        self.motion_dx = 0.0
        self.motion_dy = 0.0

    def toggle_finger(self, finger: str) -> None:
        self.fingers[finger] = "folded" if self.fingers[finger] == "extended" else "extended"


@dataclass
class EditableTwoHandState:
    active: bool = False
    motion: str = "steady"
    distance: float = 0.5


def default_hand_state(hand_id: str) -> EditableSingleHandState:
    return EditableSingleHandState(hand_id)


def build_preview_frame(
    hand_states: list[EditableSingleHandState],
    two_hand_state: EditableTwoHandState,
    timestamp_ms: int,
) -> FramePrimitive:
    hands = [
        HandPrimitive(
            hand_id=hs.hand_id,
            handedness_score=1.0,
            palm_side=hs.palm_side,
            rotation_quadrant=hs.rotation_quadrant,
            fingers=dict(hs.fingers),
            position=Point3D(0.3 if hs.hand_id == "left" else 0.7, 0.5),
            motion=MotionPrimitive(
                direction=hs.motion_direction,
                speed=hs.motion_speed,
                dx=hs.motion_dx,
                dy=hs.motion_dy,
            ),
            confidence=1.0,
        )
        for hs in hand_states
        if hs.enabled
    ]

    two_hand = None
    if two_hand_state.active and len(hands) >= 2:
        two_hand = TwoHandPrimitive(
            active=True,
            distance=two_hand_state.distance,
            motion=two_hand_state.motion,
        )

    return FramePrimitive(timestamp_ms=timestamp_ms, hands=hands, two_hand=two_hand)
