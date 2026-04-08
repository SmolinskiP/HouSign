from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Point3D:
    x: float
    y: float
    z: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class MotionPrimitive:
    direction: str = "steady"
    speed: float = 0.0
    dx: float = 0.0
    dy: float = 0.0

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


@dataclass(slots=True)
class HandPrimitive:
    hand_id: str
    handedness_score: float
    palm_side: str
    rotation_quadrant: int
    fingers: dict[str, str]
    position: Point3D
    motion: MotionPrimitive
    confidence: float
    gesture_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["position"] = self.position.to_dict()
        payload["motion"] = self.motion.to_dict()
        return payload


@dataclass(slots=True)
class TwoHandPrimitive:
    active: bool
    distance: float
    motion: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ActiveGesture:
    name: str
    key: str | None
    compound_id: str
    hand: str | None
    palm_side: str | None
    rotation: int | None
    binding_name: str | None = None
    binding_action: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class FramePrimitive:
    timestamp_ms: int
    hands: list[HandPrimitive]
    two_hand: TwoHandPrimitive | None = None
    active_gesture: str | None = None
    active_gesture_key: str | None = None
    active_gesture_compound_id: str | None = None
    active_gesture_hand: str | None = None
    active_gesture_palm_side: str | None = None
    active_gesture_rotation: int | None = None
    active_binding_name: str | None = None
    active_binding_action: str | None = None
    active_gestures: list[ActiveGesture] = field(default_factory=list)
    active_gestures_by_hand: dict[str, ActiveGesture] = field(default_factory=dict)
    gesture_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "hands": [hand.to_dict() for hand in self.hands],
            "two_hand": self.two_hand.to_dict() if self.two_hand else None,
            "active_gesture": self.active_gesture,
            "active_gesture_key": self.active_gesture_key,
            "active_gesture_compound_id": self.active_gesture_compound_id,
            "active_gesture_hand": self.active_gesture_hand,
            "active_gesture_palm_side": self.active_gesture_palm_side,
            "active_gesture_rotation": self.active_gesture_rotation,
            "active_binding_name": self.active_binding_name,
            "active_binding_action": self.active_binding_action,
            "active_gestures": [gesture.to_dict() for gesture in self.active_gestures],
            "active_gestures_by_hand": {owner: gesture.to_dict() for owner, gesture in self.active_gestures_by_hand.items()},
            "gesture_candidates": list(self.gesture_candidates),
        }
