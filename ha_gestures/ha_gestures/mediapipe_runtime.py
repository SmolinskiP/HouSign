from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import numpy as np

from .bindings import BindingRegistry
from .gesture_engine import GestureEngine
from .models import FramePrimitive
from .primitives import PrimitiveExtractor

try:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    from mediapipe.tasks.python.components.containers.landmark import NormalizedLandmark
except ImportError:  # pragma: no cover - exercised in runtime, not unit tests.
    cv2 = None
    mp = None
    mp_python = None
    mp_vision = None
    NormalizedLandmark = None


class MediaPipeRuntime:
    def __init__(
        self,
        model_path: str | Path,
        gestures_config_path: str | Path | None = "gestures.yaml",
        bindings_path: str | Path | None = "gesture_bindings.json",
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
    ) -> None:
        self.model_path = Path(model_path)
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.min_presence_confidence = min_presence_confidence
        self.extractor = PrimitiveExtractor()
        self.gesture_engine = GestureEngine(config_path=gestures_config_path)
        self.binding_registry = BindingRegistry(bindings_path) if bindings_path is not None else None

    def iter_camera(
        self,
        camera_index: int = 0,
        max_frames: int | None = None,
    ) -> Iterator[FramePrimitive]:
        self._ensure_dependencies()
        capture = cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera_index}.")

        try:
            with self._create_landmarker() as landmarker:
                frame_count = 0
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break

                    frame_state = self._process_frame(frame, landmarker)
                    yield frame_state

                    frame_count += 1
                    if max_frames is not None and frame_count >= max_frames:
                        break
        finally:
            capture.release()

    def show_camera_debug(
        self,
        camera_index: int = 0,
        max_frames: int | None = None,
        print_every: int = 5,
        mirror: bool = True,
    ) -> int:
        self._ensure_dependencies()
        capture = cv2.VideoCapture(camera_index)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera_index}.")

        drawing = mp_vision.drawing_utils
        drawing_styles = mp_vision.drawing_styles
        connections = mp_vision.HandLandmarksConnections.HAND_CONNECTIONS
        debug_window = "HA Gestures Debug"
        status_window = "HA Gestures Status"
        windows_positioned = False

        cv2.namedWindow(debug_window, cv2.WINDOW_NORMAL)
        cv2.namedWindow(status_window, cv2.WINDOW_NORMAL)

        try:
            with self._create_landmarker() as landmarker:
                frame_count = 0
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break

                    try:
                        if windows_positioned:
                            debug_visible = cv2.getWindowProperty(debug_window, cv2.WND_PROP_VISIBLE)
                            status_visible = cv2.getWindowProperty(status_window, cv2.WND_PROP_VISIBLE)
                            if debug_visible < 1 or status_visible < 1:
                                return 0
                    except cv2.error:
                        return 0

                    frame_state, result = self._process_frame(frame, landmarker, return_result=True)
                    display_frame = cv2.flip(frame, 1) if mirror else frame.copy()

                    if frame_count % max(print_every, 1) == 0:
                        print(frame_state.to_dict())

                    self._draw_frame_overlay(display_frame, frame_state, mirror=mirror)
                    self._draw_landmarks(display_frame, result.hand_landmarks, drawing, drawing_styles, connections, mirror=mirror)
                    status_panel = self._build_status_panel(frame_state)

                    cv2.imshow(debug_window, display_frame)
                    cv2.imshow(status_window, status_panel)

                    if not windows_positioned:
                        self._position_windows(debug_window, status_window, display_frame, status_panel)
                        windows_positioned = True

                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        return 0

                    frame_count += 1
                    if max_frames is not None and frame_count >= max_frames:
                        return 0
        finally:
            capture.release()
            cv2.destroyAllWindows()

        return 0

    def _create_landmarker(self):
        if not self.model_path.exists():
            raise RuntimeError(
                f"Model file not found: {self.model_path}. Download hand_landmarker.task and pass --model or place it under models\\hand_landmarker.task"
            )

        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=self.max_num_hands,
            min_hand_detection_confidence=self.min_detection_confidence,
            min_hand_presence_confidence=self.min_presence_confidence,
            min_tracking_confidence=self.min_tracking_confidence,
        )
        return mp_vision.HandLandmarker.create_from_options(options)

    def _process_frame(self, frame, landmarker, return_result: bool = False):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = time.monotonic_ns() // 1_000_000
        result = landmarker.detect_for_video(mp_image, timestamp_ms)

        observations = []
        if result.hand_landmarks and result.handedness:
            for handedness, landmarks in zip(result.handedness, result.hand_landmarks, strict=True):
                classification = handedness[0]
                observations.append(
                    (
                        classification.category_name,
                        float(classification.score),
                        landmarks,
                    )
                )

        frame_state = self.extractor.extract_frame(observations, timestamp_s=timestamp_ms / 1000.0)
        frame_state = self.gesture_engine.apply(frame_state)
        self._apply_bindings(frame_state)
        if return_result:
            return frame_state, result
        return frame_state

    def _apply_bindings(self, frame_state: FramePrimitive) -> None:
        if self.binding_registry is None:
            return

        for gesture in frame_state.active_gestures:
            mode = "two_hand" if gesture.hand == "both" else "one_hand"
            binding = self.binding_registry.find(mode, gesture.compound_id)
            if binding is None:
                gesture.binding_name = None
                gesture.binding_action = None
                continue
            gesture.binding_name = binding.gesture_name
            gesture.binding_action = binding.action_name

        if frame_state.active_gestures:
            primary = frame_state.active_gestures[0]
            frame_state.active_binding_name = primary.binding_name
            frame_state.active_binding_action = primary.binding_action

    def _ensure_dependencies(self) -> None:
        if cv2 is None or mp is None or mp_python is None or mp_vision is None or NormalizedLandmark is None:
            raise RuntimeError(
                "Missing runtime dependencies. Install them with: "
                "python -m pip install -r requirements.txt"
            )

    def _draw_landmarks(self, frame, hand_landmarks_list, drawing, drawing_styles, connections, mirror: bool) -> None:
        for hand_landmarks in hand_landmarks_list:
            display_landmarks = self._mirror_landmarks(hand_landmarks) if mirror else hand_landmarks
            drawing.draw_landmarks(
                frame,
                display_landmarks,
                connections,
                drawing_styles.get_default_hand_landmarks_style(),
                drawing_styles.get_default_hand_connections_style(),
            )

    def _mirror_landmarks(self, hand_landmarks):
        return [
            NormalizedLandmark(
                x=1.0 - float(landmark.x),
                y=float(landmark.y),
                z=float(getattr(landmark, "z", 0.0)),
                visibility=getattr(landmark, "visibility", None),
                presence=getattr(landmark, "presence", None),
            )
            for landmark in hand_landmarks
        ]

    def _draw_frame_overlay(self, frame: object, frame_state: FramePrimitive, mirror: bool) -> None:
        _height, width = frame.shape[:2]
        cv2.putText(
            frame,
            f"HA Gestures Debug | model={self.model_path.name} | q / ESC to exit",
            (16, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

        primary_text = frame_state.active_gesture or "none"
        if frame_state.active_binding_name:
            primary_text = f"{primary_text} => {frame_state.active_binding_name}"
        cv2.putText(
            frame,
            f"primary={primary_text}",
            (16, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (0, 200, 255),
            2,
            cv2.LINE_AA,
        )

        if frame_state.active_gesture_compound_id:
            cv2.putText(
                frame,
                f"compound={frame_state.active_gesture_compound_id}",
                (16, 86),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (170, 170, 255),
                1,
                cv2.LINE_AA,
            )

        if frame_state.active_binding_action:
            cv2.putText(
                frame,
                f"action={frame_state.active_binding_action}",
                (16, 106),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (255, 210, 120),
                1,
                cv2.LINE_AA,
            )

        for owner in ("left", "right", "both"):
            gesture = frame_state.active_gestures_by_hand.get(owner)
            if gesture is None:
                continue
            y = {"left": 136, "right": 160, "both": 184}[owner]
            label = gesture.binding_name or gesture.key or "unnamed_pose"
            cv2.putText(
                frame,
                f"{owner}: {label}",
                (16, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (120, 220, 255),
                1,
                cv2.LINE_AA,
            )

        if frame_state.two_hand:
            two_hand = frame_state.two_hand
            cv2.putText(
                frame,
                f"two_hand: {two_hand.motion} dist={two_hand.distance:.3f}",
                (16, 192),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                1,
                cv2.LINE_AA,
            )

        for hand in frame_state.hands:
            anchor_x = int(hand.position.x * width)
            if mirror:
                anchor_x = width - anchor_x
            anchor_y = int(hand.position.y * frame.shape[0])
            lines = [
                f"{hand.hand_id} score={hand.handedness_score:.2f}",
                f"palm={hand.palm_side} rot={hand.rotation_quadrant}",
                f"move={hand.motion.direction} speed={hand.motion.speed:.2f}",
                "fingers="
                + ",".join(
                    f"{name[0].upper()}:{'E' if state == 'extended' else 'F'}"
                    for name, state in hand.fingers.items()
                ),
            ]

            if hand.gesture_hints:
                lines.append("hints=" + ",".join(hand.gesture_hints))

            active_hand_gesture = frame_state.active_gestures_by_hand.get(hand.hand_id)
            if active_hand_gesture is not None:
                lines.append(f"gesture={active_hand_gesture.binding_name or active_hand_gesture.key or 'unnamed'}")
                if active_hand_gesture.binding_action:
                    lines.append(f"action={active_hand_gesture.binding_action}")
                lines.append(f"pose={active_hand_gesture.compound_id}")

            box_top = max(anchor_y - 70, 210)
            text_x = min(max(anchor_x - 110, 10), width - 300)
            for index, line in enumerate(lines):
                cv2.putText(
                    frame,
                    line,
                    (text_x, box_top + index * 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (50, 255, 50),
                    1,
                    cv2.LINE_AA,
                )

    def _build_status_panel(self, frame_state: FramePrimitive):
        panel = np.zeros((360, 1050, 3), dtype=np.uint8)
        panel[:, :] = (18, 18, 18)

        primary_name = frame_state.active_gesture or "none"
        if frame_state.active_binding_name:
            primary_name = f"{primary_name} => {frame_state.active_binding_name}"
        primary_compound = frame_state.active_gesture_compound_id or "none"
        color = (0, 220, 120) if frame_state.active_gesture else (140, 140, 140)

        cv2.putText(panel, "Primary Gesture", (24, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(panel, primary_name, (24, 86), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv2.LINE_AA)
        cv2.putText(panel, f"compound: {primary_compound}", (24, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 255), 1, cv2.LINE_AA)
        if frame_state.active_binding_action:
            cv2.putText(panel, f"action: {frame_state.active_binding_action}", (24, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 210, 120), 1, cv2.LINE_AA)

        self._draw_owner_block(panel, "left", frame_state.active_gestures_by_hand.get("left"), 24, 176)
        self._draw_owner_block(panel, "right", frame_state.active_gestures_by_hand.get("right"), 360, 176)
        self._draw_owner_block(panel, "both", frame_state.active_gestures_by_hand.get("both"), 696, 176)

        candidates = ", ".join(frame_state.gesture_candidates) if frame_state.gesture_candidates else "none"
        cv2.putText(panel, f"Candidates: {candidates}", (24, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        return panel

    def _draw_owner_block(self, panel, owner: str, gesture, x: int, y: int) -> None:
        width = 300
        height = 140
        cv2.rectangle(panel, (x, y), (x + width, y + height), (70, 70, 70), 1)
        cv2.putText(panel, owner.upper(), (x + 12, y + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)

        if gesture is None:
            cv2.putText(panel, "none", (x + 12, y + 66), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (140, 140, 140), 2, cv2.LINE_AA)
            return

        label = gesture.binding_name or gesture.key or "unnamed_pose"
        color = (0, 220, 120) if gesture.key else (220, 220, 120)
        cv2.putText(panel, label, (x + 12, y + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)
        cv2.putText(panel, f"palm={gesture.palm_side} rot={gesture.rotation}", (x + 12, y + 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 220, 255), 1, cv2.LINE_AA)
        if gesture.binding_action:
            cv2.putText(panel, f"action={gesture.binding_action}", (x + 12, y + 112), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 210, 120), 1, cv2.LINE_AA)
            cv2.putText(panel, gesture.compound_id, (x + 12, y + 132), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 255), 1, cv2.LINE_AA)
        else:
            cv2.putText(panel, gesture.compound_id, (x + 12, y + 118), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 255), 1, cv2.LINE_AA)

    def _position_windows(self, debug_window: str, status_window: str, display_frame, status_panel) -> None:
        debug_height, debug_width = display_frame.shape[:2]
        status_height, status_width = status_panel.shape[:2]
        cv2.resizeWindow(debug_window, debug_width, debug_height)
        cv2.resizeWindow(status_window, status_width, status_height)
        cv2.moveWindow(debug_window, 40, 40)
        cv2.moveWindow(status_window, 60 + debug_width, 40)
