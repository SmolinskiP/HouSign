from __future__ import annotations
from dataclasses import dataclass, field
from math import cos, dist, radians, sin
from typing import Literal

import flet as ft
import flet.canvas as cv

from .bindings import GestureBinding
from .gesture_engine import GestureEngine
from .models import FramePrimitive, HandPrimitive, MotionPrimitive, Point3D

FingerName = Literal["thumb", "index", "middle", "ring", "pinky"]
FingerState = Literal["folded", "extended"]
PalmSide = Literal["front", "back"]
HandId = Literal["left", "right"]
GestureMode = Literal["one_hand", "two_hand"]

FINGER_ORDER: tuple[FingerName, ...] = ("thumb", "index", "middle", "ring", "pinky")
ROTATIONS = (0, 90, 180, 270)
CANVAS_WIDTH = 280
CANVAS_HEIGHT = 340


@dataclass(slots=True)
class EditableHandState:
    hand_id: HandId
    enabled: bool = True
    palm_side: PalmSide = "front"
    rotation_quadrant: int = 0
    fingers: dict[FingerName, FingerState] = field(
        default_factory=lambda: {finger: "extended" for finger in FINGER_ORDER}
    )

    def compound_id(self) -> str:
        bits = "".join("1" if self.fingers[finger] == "extended" else "0" for finger in FINGER_ORDER)
        return f"{self.hand_id}_{self.palm_side}_{self.rotation_quadrant}_{bits}"

    def toggle_finger(self, finger: FingerName) -> None:
        self.fingers[finger] = "extended" if self.fingers[finger] == "folded" else "folded"


def default_hand_state(hand_id: HandId) -> EditableHandState:
    return EditableHandState(hand_id=hand_id)


def build_frame(left: EditableHandState, right: EditableHandState, mode: GestureMode, one_hand_selection: HandId) -> FramePrimitive:
    hands: list[HandPrimitive] = []
    if mode == "one_hand":
        chosen = left if one_hand_selection == "left" else right
        hands.append(build_hand_primitive(chosen))
    else:
        hands.append(build_hand_primitive(left))
        hands.append(build_hand_primitive(right))
    return FramePrimitive(timestamp_ms=0, hands=hands)


def build_hand_primitive(state: EditableHandState) -> HandPrimitive:
    return HandPrimitive(
        hand_id=state.hand_id,
        handedness_score=1.0,
        palm_side=state.palm_side,
        rotation_quadrant=state.rotation_quadrant,
        fingers=dict(state.fingers),
        position=Point3D(0.35 if state.hand_id == "left" else 0.65, 0.58, 0.0),
        motion=MotionPrimitive(),
        confidence=1.0,
        gesture_hints=[],
    )


def preview_signature(left: EditableHandState, right: EditableHandState, mode: GestureMode, one_hand_selection: HandId) -> str:
    if mode == "one_hand":
        return (left if one_hand_selection == "left" else right).compound_id()
    return f"both::{left.compound_id()}::{right.compound_id()}"


def resolve_preview(
    left: EditableHandState,
    right: EditableHandState,
    mode: GestureMode,
    one_hand_selection: HandId,
    config_path: str,
) -> tuple[str, str, FramePrimitive]:
    engine = GestureEngine(config_path=config_path, stability_window_ms=1, min_stable_frames=1, active_hold_ms=0)
    frame = engine.apply(build_frame(left, right, mode, one_hand_selection))
    if mode == "one_hand":
        return frame.active_gesture or preview_signature(left, right, mode, one_hand_selection), preview_signature(left, right, mode, one_hand_selection), frame

    compound = preview_signature(left, right, mode, one_hand_selection)
    left_name = frame.active_gestures_by_hand.get("left")
    right_name = frame.active_gestures_by_hand.get("right")
    human_name = f"two_hand[{left_name.name if left_name else left.compound_id()} + {right_name.name if right_name else right.compound_id()}]"
    return human_name, compound, frame


def hand_state_from_compound(compound_id: str) -> EditableHandState:
    parts = compound_id.split("_")
    if len(parts) != 4:
        raise ValueError(f"Unsupported hand compound id: {compound_id}")

    hand_id = parts[0]
    palm_side = parts[1]
    rotation = int(parts[2])
    bitmask = parts[3]
    if len(bitmask) != len(FINGER_ORDER) or any(bit not in {"0", "1"} for bit in bitmask):
        raise ValueError(f"Unsupported hand bitmask in compound id: {compound_id}")
    fingers: dict[FingerName, FingerState] = {
        finger_name: ("extended" if bit == "1" else "folded")
        for finger_name, bit in zip(FINGER_ORDER, bitmask, strict=True)
    }

    return EditableHandState(
        hand_id=hand_id,  # type: ignore[arg-type]
        palm_side=palm_side,  # type: ignore[arg-type]
        rotation_quadrant=rotation,
        fingers=fingers,  # type: ignore[arg-type]
    )


def editor_state_from_binding(binding: GestureBinding) -> tuple[EditableHandState, EditableHandState, GestureMode, HandId]:
    left = default_hand_state("left")
    right = default_hand_state("right")

    if binding.mode == "two_hand":
        _, left_compound, right_compound = binding.trigger_id.split("::", 2)
        left = hand_state_from_compound(left_compound)
        right = hand_state_from_compound(right_compound)
        return left, right, "two_hand", "right"

    hand = hand_state_from_compound(binding.trigger_id)
    if hand.hand_id == "left":
        left = hand
        right = default_hand_state("right")
        return left, right, "one_hand", "left"

    right = hand
    left = default_hand_state("left")
    return left, right, "one_hand", "right"


def hand_canvas_shapes(state: EditableHandState, width: float = CANVAS_WIDTH, height: float = CANVAS_HEIGHT) -> list[cv.Shape]:
    palette = _palette(state.palm_side)
    skeleton = _hand_skeleton(state, width, height)
    shapes: list[cv.Shape] = []

    palm_outline = [
        skeleton["palm"]["thumb_root"],
        skeleton["palm"]["index_root"],
        skeleton["palm"]["middle_root"],
        skeleton["palm"]["ring_root"],
        skeleton["palm"]["pinky_root"],
        skeleton["palm"]["side"],
        skeleton["palm"]["wrist_right"],
        skeleton["palm"]["wrist_left"],
        skeleton["palm"]["thumb_base"],
    ]
    path = [cv.Path.MoveTo(*palm_outline[0])]
    path.extend(cv.Path.LineTo(*point) for point in palm_outline[1:])
    path.append(cv.Path.Close())
    shapes.append(
        cv.Path(
            elements=path,
            paint=ft.Paint(
                style=ft.PaintingStyle.STROKE,
                stroke_width=4,
                color=palette["palm"],
                stroke_cap=ft.StrokeCap.ROUND,
            ),
        )
    )

    wrist_y = max(skeleton["palm"]["wrist_left"][1], skeleton["palm"]["wrist_right"][1]) + 6
    shapes.append(
        cv.Line(
            skeleton["palm"]["wrist_left"][0],
            wrist_y,
            skeleton["palm"]["wrist_right"][0],
            wrist_y,
            paint=ft.Paint(color=palette["palm"], stroke_width=6, stroke_cap=ft.StrokeCap.ROUND),
        )
    )

    for finger in FINGER_ORDER:
        chain = skeleton["fingers"][finger]
        active = state.fingers[finger] == "extended"
        segment_color = palette["active"] if active else palette["folded"]
        joint_color = palette["joint_active"] if active else palette["joint_idle"]
        widths = {"thumb": 10, "index": 10, "middle": 11, "ring": 9, "pinky": 8}
        for start, end in zip(chain[:-1], chain[1:], strict=True):
            shapes.append(
                cv.Line(
                    start[0],
                    start[1],
                    end[0],
                    end[1],
                    paint=ft.Paint(color=segment_color, stroke_width=widths[finger], stroke_cap=ft.StrokeCap.ROUND),
                )
            )
        for idx, point in enumerate(chain):
            shapes.append(
                cv.Circle(
                    point[0],
                    point[1],
                    radius=6 if idx == 0 else 5,
                    paint=ft.Paint(
                        color=joint_color,
                        style=ft.PaintingStyle.FILL,
                    ),
                )
            )
    return shapes


def hit_test_finger(
    state: EditableHandState,
    x: float,
    y: float,
    width: float = CANVAS_WIDTH,
    height: float = CANVAS_HEIGHT,
) -> FingerName | None:
    skeleton = _hand_skeleton(state, width, height)
    best: tuple[FingerName, float] | None = None
    for finger in FINGER_ORDER:
        chain = skeleton["fingers"][finger]
        distance = min(_distance_to_segment((x, y), start, end) for start, end in zip(chain[:-1], chain[1:], strict=True))
        threshold = 24 if finger == "thumb" else 20
        if distance <= threshold and (best is None or distance < best[1]):
            best = (finger, distance)
    return best[0] if best else None


def _finger_points(finger: FingerName, state: FingerState) -> list[tuple[float, float]]:
    extended = {
        "thumb": [(106, 188), (80, 170), (54, 148), (28, 124)],
        "index": [(124, 136), (124, 94), (124, 48), (124, 4)],
        "middle": [(154, 124), (154, 78), (154, 28), (154, -16)],
        "ring": [(184, 132), (184, 90), (184, 48), (184, 12)],
        "pinky": [(210, 148), (212, 118), (214, 88), (216, 60)],
    }
    folded = {
        "thumb": [(106, 188), (128, 198), (150, 208), (172, 216)],
        "index": [(124, 136), (134, 168), (142, 198), (148, 226)],
        "middle": [(154, 124), (158, 162), (160, 196), (158, 228)],
        "ring": [(184, 132), (178, 168), (168, 198), (156, 224)],
        "pinky": [(210, 148), (194, 176), (176, 202), (156, 224)],
    }
    return extended[finger] if state == "extended" else folded[finger]


def _palette(palm_side: PalmSide) -> dict[str, str]:
    if palm_side == "front":
        return {
            "palm": "#f4b26b",
            "active": "#ff8a2a",
            "folded": "#7390b4",
            "joint_active": "#fff0da",
            "joint_idle": "#dbe7f4",
        }
    return {
        "palm": "#9bb7d5",
        "active": "#4fc3f7",
        "folded": "#6f86a8",
        "joint_active": "#edf7ff",
        "joint_idle": "#d8e7f8",
    }


def _hand_skeleton(state: EditableHandState, width: float, height: float) -> dict[str, dict[str, list[tuple[float, float]] | tuple[float, float]]]:
    sx = width / CANVAS_WIDTH
    sy = height / CANVAS_HEIGHT
    palm = {
        "thumb_base": (84, 196),
        "thumb_root": (104, 174),
        "index_root": (122, 138),
        "middle_root": (154, 126),
        "ring_root": (184, 134),
        "pinky_root": (210, 150),
        "side": (216, 212),
        "wrist_right": (184, 274),
        "wrist_left": (118, 274),
    }
    fingers = {
        finger: _finger_points(finger, state.fingers[finger])
        for finger in FINGER_ORDER
    }

    transformed_palm = {name: _transform_point(point, state, sx, sy) for name, point in palm.items()}
    transformed_fingers = {
        finger: [_transform_point(point, state, sx, sy) for point in chain]
        for finger, chain in fingers.items()
    }
    return {"palm": transformed_palm, "fingers": transformed_fingers}


def _transform_point(point: tuple[float, float], state: EditableHandState, sx: float, sy: float) -> tuple[float, float]:
    x, y = point
    x *= sx
    y *= sy
    y += 18 * sy
    center_x = (CANVAS_WIDTH * sx) / 2
    center_y = (CANVAS_HEIGHT * sy) / 2
    if state.hand_id == "left":
        x = 2 * center_x - x
    if state.rotation_quadrant:
        angle = radians(state.rotation_quadrant)
        rel_x = x - center_x
        rel_y = y - center_y
        x = center_x + rel_x * cos(angle) - rel_y * sin(angle)
        y = center_y + rel_x * sin(angle) + rel_y * cos(angle)
    return (x, y)


def _distance_to_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return dist(point, start)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    projection = (x1 + t * dx, y1 + t * dy)
    return dist(point, projection)
