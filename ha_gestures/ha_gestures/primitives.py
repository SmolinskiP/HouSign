from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from typing import Iterable, Sequence

from .models import FramePrimitive, HandPrimitive, MotionPrimitive, Point3D, TwoHandPrimitive

WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

FINGER_JOINTS = {
    "thumb": (THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP),
    "index": (INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_DIP, RING_TIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
}


class PrimitiveExtractor:
    def __init__(
        self,
        history_window_s: float = 0.4,
        motion_deadzone: float = 0.035,
        pair_deadzone: float = 0.025,
    ) -> None:
        self.history_window_s = history_window_s
        self.motion_deadzone = motion_deadzone
        self.pair_deadzone = pair_deadzone
        self._hand_history: dict[str, deque[tuple[float, Point3D]]] = defaultdict(deque)
        self._pair_history: deque[tuple[float, float]] = deque()

    def extract_frame(
        self,
        observations: Iterable[tuple[str, float, Sequence[object]]],
        timestamp_s: float | None = None,
    ) -> FramePrimitive:
        timestamp_s = timestamp_s if timestamp_s is not None else time.monotonic()
        hands = [
            self._extract_hand(hand_id, score, landmarks, timestamp_s)
            for hand_id, score, landmarks in observations
        ]
        hands.sort(key=lambda hand: hand.hand_id)
        two_hand = self._extract_two_hand(hands, timestamp_s)
        return FramePrimitive(
            timestamp_ms=int(timestamp_s * 1000),
            hands=hands,
            two_hand=two_hand,
        )

    def _extract_hand(
        self,
        hand_id: str,
        score: float,
        landmarks: Sequence[object],
        timestamp_s: float,
    ) -> HandPrimitive:
        points = [_point_from_landmark(landmark) for landmark in landmarks]
        center = _palm_center(points)
        motion = self._motion_for(hand_id, center, timestamp_s)
        fingers = _finger_states(points)
        return HandPrimitive(
            hand_id=hand_id.lower(),
            handedness_score=score,
            palm_side=_palm_side(points, hand_id),
            rotation_quadrant=_rotation_quadrant(points),
            fingers=fingers,
            position=center,
            motion=motion,
            confidence=score,
            gesture_hints=_gesture_hints(points, fingers),
        )

    def _motion_for(self, hand_id: str, center: Point3D, timestamp_s: float) -> MotionPrimitive:
        history = self._hand_history[hand_id.lower()]
        history.append((timestamp_s, center))
        self._trim_history(history, timestamp_s)
        if len(history) < 2:
            return MotionPrimitive()

        start_ts, start_point = history[0]
        end_ts, end_point = history[-1]
        dt = max(end_ts - start_ts, 1e-6)
        dx = end_point.x - start_point.x
        dy = end_point.y - start_point.y
        speed = math.sqrt(dx * dx + dy * dy) / dt

        if abs(dx) < self.motion_deadzone and abs(dy) < self.motion_deadzone:
            direction = "steady"
        elif abs(dx) >= abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy > 0 else "up"

        return MotionPrimitive(direction=direction, speed=speed, dx=dx, dy=dy)

    def _extract_two_hand(
        self,
        hands: Sequence[HandPrimitive],
        timestamp_s: float,
    ) -> TwoHandPrimitive | None:
        if len(hands) < 2:
            self._pair_history.clear()
            return None

        first = hands[0].position
        second = hands[1].position
        distance = _distance(first, second)

        self._pair_history.append((timestamp_s, distance))
        self._trim_history(self._pair_history, timestamp_s)

        motion = "steady"
        if len(self._pair_history) >= 2:
            _, start_distance = self._pair_history[0]
            delta = distance - start_distance
            if delta > self.pair_deadzone:
                motion = "expanding"
            elif delta < -self.pair_deadzone:
                motion = "contracting"

        return TwoHandPrimitive(active=True, distance=distance, motion=motion)

    def _trim_history(self, history: deque, timestamp_s: float) -> None:
        while history and timestamp_s - history[0][0] > self.history_window_s:
            history.popleft()


def _point_from_landmark(landmark: object) -> Point3D:
    if isinstance(landmark, Point3D):
        return landmark
    return Point3D(
        x=float(getattr(landmark, "x")),
        y=float(getattr(landmark, "y")),
        z=float(getattr(landmark, "z", 0.0)),
    )


def _palm_center(points: Sequence[Point3D]) -> Point3D:
    anchors = (WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP)
    x = sum(points[index].x for index in anchors) / len(anchors)
    y = sum(points[index].y for index in anchors) / len(anchors)
    z = sum(points[index].z for index in anchors) / len(anchors)
    return Point3D(x=x, y=y, z=z)


def _rotation_quadrant(points: Sequence[Point3D]) -> int:
    wrist = points[WRIST]
    middle = points[MIDDLE_MCP]
    dx = middle.x - wrist.x
    dy = middle.y - wrist.y
    angle = (math.degrees(math.atan2(dx, -dy)) + 360.0) % 360.0
    return int((round(angle / 90.0) * 90) % 360)


def _palm_side(points: Sequence[Point3D], hand_id: str) -> str:
    wrist = points[WRIST]
    index = points[INDEX_MCP]
    pinky = points[PINKY_MCP]
    cross_z = (index.x - wrist.x) * (pinky.y - wrist.y) - (index.y - wrist.y) * (pinky.x - wrist.x)
    right_hand = hand_id.lower() == "right"
    front = cross_z < 0 if right_hand else cross_z > 0
    return "front" if front else "back"


def _finger_states(points: Sequence[Point3D]) -> dict[str, str]:
    states: dict[str, str] = {}
    palm_width = max(_distance(points[INDEX_MCP], points[PINKY_MCP]), 1e-6)
    wrist = points[WRIST]

    for finger_name, (mcp, pip, dip, tip) in FINGER_JOINTS.items():
        pip_angle = _joint_angle(points[mcp], points[pip], points[dip])
        dip_angle = _joint_angle(points[pip], points[dip], points[tip])
        reach_ratio = _distance(points[tip], wrist) / max(_distance(points[mcp], wrist), 1e-6)
        extended = pip_angle > 160.0 and dip_angle > 150.0 and reach_ratio > 1.15

        if finger_name == "thumb":
            thumb_span = _distance(points[tip], points[INDEX_MCP]) / palm_width
            extended = extended and thumb_span > 0.55

        states[finger_name] = "extended" if extended else "folded"

    return states


def _gesture_hints(points: Sequence[Point3D], fingers: dict[str, str]) -> list[str]:
    hints: list[str] = []
    extended = {name for name, state in fingers.items() if state == "extended"}

    if len(extended) == 5:
        hints.append("open_palm")
    if not extended:
        hints.append("closed_fist")
    if extended == {"index"}:
        hints.append("pointing_up")
    if extended == {"thumb"}:
        hints.append("thumb_only")
    if extended == {"index", "middle"}:
        hints.append("victory_like")

    thumb_index_gap = _distance(points[THUMB_TIP], points[INDEX_TIP])
    palm_width = max(_distance(points[INDEX_MCP], points[PINKY_MCP]), 1e-6)
    if thumb_index_gap / palm_width < 0.28 and {"middle", "ring", "pinky"}.issubset(extended):
        hints.append("ok_like")

    return hints


def _joint_angle(a: Point3D, b: Point3D, c: Point3D) -> float:
    ab = (a.x - b.x, a.y - b.y, a.z - b.z)
    cb = (c.x - b.x, c.y - b.y, c.z - b.z)
    dot = sum(left * right for left, right in zip(ab, cb, strict=True))
    ab_norm = math.sqrt(sum(value * value for value in ab))
    cb_norm = math.sqrt(sum(value * value for value in cb))
    if ab_norm == 0.0 or cb_norm == 0.0:
        return 0.0
    cosine = max(-1.0, min(1.0, dot / (ab_norm * cb_norm)))
    return math.degrees(math.acos(cosine))


def _distance(left: Point3D, right: Point3D) -> float:
    dx = left.x - right.x
    dy = left.y - right.y
    dz = left.z - right.z
    return math.sqrt(dx * dx + dy * dy + dz * dz)

