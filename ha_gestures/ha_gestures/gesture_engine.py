from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from .gesture_config import GestureConfig, GestureRule, load_gesture_config
from .models import ActiveGesture, FramePrimitive, HandPrimitive, TwoHandPrimitive

FingerSignature = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class GestureCandidate:
    key: str
    owner: str
    hand: str | None
    palm_side: str | None
    rotation: int | None
    finger_signature: FingerSignature
    compound_id: str
    priority: int


class GestureEngine:
    def __init__(
        self,
        config_path: str | Path | None = "gestures.yaml",
        stability_window_ms: int = 400,
        min_stable_frames: int = 3,
        active_hold_ms: int = 700,
    ) -> None:
        self.config: GestureConfig = load_gesture_config(config_path)
        self.stability_window_ms = stability_window_ms
        self.min_stable_frames = min_stable_frames
        self.active_hold_ms = active_hold_ms
        self._history_by_owner: dict[str, deque[tuple[int, set[GestureCandidate]]]] = defaultdict(deque)
        self._active_candidate_by_owner: dict[str, GestureCandidate] = {}
        self._active_until_by_owner: dict[str, int] = {}
        self._priority_map = {rule.key: rule.priority for rule in self.config.gestures}

    def apply(self, frame: FramePrimitive) -> FramePrimitive:
        named_candidates = self._detect_candidates(frame)
        raw_active_by_owner = self._build_raw_active_by_owner(frame)
        frame.gesture_candidates = self._build_candidate_labels(raw_active_by_owner, named_candidates)

        current_named_by_owner = self._group_by_owner(named_candidates)
        owners = set(raw_active_by_owner) | set(current_named_by_owner) | set(self._history_by_owner) | set(self._active_candidate_by_owner)
        active_by_owner: dict[str, ActiveGesture] = {}

        for owner in sorted(owners, key=_owner_sort_key):
            history = self._history_by_owner[owner]
            history.append((frame.timestamp_ms, current_named_by_owner.get(owner, set())))
            self._trim_history(history, frame.timestamp_ms)

            stable_named_candidates = self._stable_candidates(history)
            active_named_candidate = self._choose_active_gesture(owner, stable_named_candidates, frame.timestamp_ms)
            if active_named_candidate is not None:
                active_by_owner[owner] = self._to_named_active_gesture(active_named_candidate)
                continue

            raw_active = raw_active_by_owner.get(owner)
            if raw_active is not None:
                active_by_owner[owner] = raw_active

        frame.active_gestures = [active_by_owner[owner] for owner in sorted(active_by_owner, key=_owner_sort_key)]
        frame.active_gestures.sort(key=self._active_sort_key)
        frame.active_gestures_by_hand = {
            owner: active_by_owner[owner] for owner in sorted(active_by_owner, key=_owner_sort_key)
        }
        self._apply_primary_active_gesture(frame)
        return frame

    def _apply_primary_active_gesture(self, frame: FramePrimitive) -> None:
        if not frame.active_gestures:
            frame.active_gesture = None
            frame.active_gesture_key = None
            frame.active_gesture_compound_id = None
            frame.active_gesture_hand = None
            frame.active_gesture_palm_side = None
            frame.active_gesture_rotation = None
            frame.active_binding_name = None
            frame.active_binding_action = None
            return

        primary = frame.active_gestures[0]
        frame.active_gesture = primary.name
        frame.active_gesture_key = primary.key
        frame.active_gesture_compound_id = primary.compound_id
        frame.active_gesture_hand = primary.hand
        frame.active_gesture_palm_side = primary.palm_side
        frame.active_gesture_rotation = primary.rotation
        frame.active_binding_name = primary.binding_name
        frame.active_binding_action = primary.binding_action

    def _active_sort_key(self, gesture: ActiveGesture) -> tuple[int, int, int, str]:
        named_rank = 0 if gesture.key is not None else 1
        priority = -self._priority_map.get(gesture.key or "", -1)
        return (named_rank, priority, _owner_sort_key(gesture.hand or "none"), gesture.name)

    def _build_raw_active_by_owner(self, frame: FramePrimitive) -> dict[str, ActiveGesture]:
        active_by_owner: dict[str, ActiveGesture] = {}
        for hand in frame.hands:
            compound_id = _hand_compound_id(hand)
            active_by_owner[hand.hand_id] = ActiveGesture(
                name=compound_id,
                key=None,
                compound_id=compound_id,
                hand=hand.hand_id,
                palm_side=hand.palm_side,
                rotation=hand.rotation_quadrant,
            )

        if frame.two_hand is not None and frame.two_hand.active:
            compound_id = _two_hand_compound_id(frame.two_hand)
            active_by_owner["both"] = ActiveGesture(
                name=compound_id,
                key=None,
                compound_id=compound_id,
                hand="both",
                palm_side=None,
                rotation=None,
            )

        return active_by_owner

    def _build_candidate_labels(
        self,
        raw_active_by_owner: dict[str, ActiveGesture],
        named_candidates: set[GestureCandidate],
    ) -> list[str]:
        labels = [
            raw_active_by_owner[owner].compound_id
            for owner in sorted(raw_active_by_owner, key=_owner_sort_key)
        ]
        labels.extend(
            f"{candidate.key}@{candidate.compound_id}"
            for candidate in sorted(named_candidates, key=_candidate_sort_key)
        )
        return labels

    def _to_named_active_gesture(self, candidate: GestureCandidate) -> ActiveGesture:
        return ActiveGesture(
            name=candidate.key,
            key=candidate.key,
            compound_id=candidate.compound_id,
            hand=candidate.hand,
            palm_side=candidate.palm_side,
            rotation=candidate.rotation,
        )

    def _detect_candidates(self, frame: FramePrimitive) -> set[GestureCandidate]:
        candidates: set[GestureCandidate] = set()

        for rule in self.config.gestures:
            if rule.kind == "two_hand":
                candidate = self._match_two_hand_rule(rule, frame)
                if candidate is not None:
                    candidates.add(candidate)
                continue

            if rule.kind == "hand":
                for hand in frame.hands:
                    candidate = self._match_hand_rule(rule, hand)
                    if candidate is not None:
                        candidates.add(candidate)

        return candidates

    def _match_hand_rule(self, rule: GestureRule, hand: HandPrimitive) -> GestureCandidate | None:
        match = rule.match

        if not _match_hand_id(match, hand):
            return None
        if not _match_palm_side(match, hand):
            return None
        if not _match_rotation(match, hand.rotation_quadrant):
            return None
        if not _match_fingers(match, hand):
            return None
        if not _match_hints(match, hand):
            return None
        if not _match_min_extended_fingers(match, hand):
            return None
        if not _match_motion(match, hand):
            return None

        return GestureCandidate(
            key=rule.key,
            owner=hand.hand_id,
            hand=hand.hand_id,
            palm_side=hand.palm_side,
            rotation=hand.rotation_quadrant,
            finger_signature=_finger_signature(hand.fingers),
            compound_id=_hand_compound_id(hand),
            priority=rule.priority,
        )

    def _match_two_hand_rule(self, rule: GestureRule, frame: FramePrimitive) -> GestureCandidate | None:
        if frame.two_hand is None or not frame.two_hand.active:
            return None

        match = rule.match.get("two_hand", {})
        motion = match.get("motion")
        if motion is not None and frame.two_hand.motion != motion:
            return None

        min_distance = match.get("min_distance")
        if min_distance is not None and frame.two_hand.distance < min_distance:
            return None

        max_distance = match.get("max_distance")
        if max_distance is not None and frame.two_hand.distance > max_distance:
            return None

        return GestureCandidate(
            key=rule.key,
            owner="both",
            hand="both",
            palm_side=None,
            rotation=None,
            finger_signature=tuple(),
            compound_id=_two_hand_compound_id(frame.two_hand),
            priority=rule.priority,
        )

    def _group_by_owner(self, candidates: set[GestureCandidate]) -> dict[str, set[GestureCandidate]]:
        grouped: dict[str, set[GestureCandidate]] = defaultdict(set)
        for candidate in candidates:
            grouped[candidate.owner].add(candidate)
        return grouped

    def _trim_history(self, history: deque[tuple[int, set[GestureCandidate]]], now_ms: int) -> None:
        while history and now_ms - history[0][0] > self.stability_window_ms:
            history.popleft()

    def _stable_candidates(self, history: deque[tuple[int, set[GestureCandidate]]]) -> set[GestureCandidate]:
        counts: Counter[GestureCandidate] = Counter()
        for _, candidates in history:
            counts.update(candidates)
        return {candidate for candidate, count in counts.items() if count >= self.min_stable_frames}

    def _choose_active_gesture(
        self,
        owner: str,
        stable_candidates: set[GestureCandidate],
        now_ms: int,
    ) -> GestureCandidate | None:
        selected = None
        if stable_candidates:
            selected = max(stable_candidates, key=lambda candidate: (candidate.priority, candidate.key))

        if selected is not None:
            self._active_candidate_by_owner[owner] = selected
            self._active_until_by_owner[owner] = now_ms + self.active_hold_ms
            return selected

        active_candidate = self._active_candidate_by_owner.get(owner)
        active_until = self._active_until_by_owner.get(owner, 0)
        if active_candidate is not None and now_ms <= active_until:
            return active_candidate

        self._active_candidate_by_owner.pop(owner, None)
        self._active_until_by_owner.pop(owner, None)
        return None


def _owner_sort_key(owner: str) -> int:
    return {"left": 0, "right": 1, "both": 2}.get(owner, 99)


def _candidate_sort_key(candidate: GestureCandidate) -> tuple[int, int, str, str]:
    return (_owner_sort_key(candidate.owner), -candidate.priority, candidate.key, candidate.compound_id)


def _match_hand_id(match: dict, hand: HandPrimitive) -> bool:
    expected = match.get("hand")
    return expected is None or expected == hand.hand_id


def _match_palm_side(match: dict, hand: HandPrimitive) -> bool:
    expected = match.get("palm_side")
    return expected is None or expected == hand.palm_side


def _match_rotation(match: dict, rotation: int) -> bool:
    expected = match.get("rotation_quadrant")
    if expected is None:
        return True
    if not isinstance(expected, list):
        expected = [expected]
    return rotation in expected


def _match_fingers(match: dict, hand: HandPrimitive) -> bool:
    expected = match.get("fingers", {})
    for finger_name, state in expected.items():
        if hand.fingers.get(finger_name) != state:
            return False
    return True


def _match_hints(match: dict, hand: HandPrimitive) -> bool:
    expected = match.get("hints")
    if expected is None:
        return True
    if not isinstance(expected, list):
        expected = [expected]
    hints = set(hand.gesture_hints)
    return all(hint in hints for hint in expected)


def _match_min_extended_fingers(match: dict, hand: HandPrimitive) -> bool:
    minimum = match.get("min_extended_fingers")
    if minimum is None:
        return True
    extended = sum(state == "extended" for state in hand.fingers.values())
    return extended >= minimum


def _match_motion(match: dict, hand: HandPrimitive) -> bool:
    expected = match.get("motion")
    if expected is None:
        return True

    motion = hand.motion
    direction = expected.get("direction")
    if direction is not None and motion.direction != direction:
        return False

    min_speed = expected.get("min_speed")
    if min_speed is not None and motion.speed < min_speed:
        return False

    max_speed = expected.get("max_speed")
    if max_speed is not None and motion.speed > max_speed:
        return False

    min_dx = expected.get("min_dx")
    if min_dx is not None and motion.dx < min_dx:
        return False

    max_dx = expected.get("max_dx")
    if max_dx is not None and motion.dx > max_dx:
        return False

    min_dy = expected.get("min_dy")
    if min_dy is not None and motion.dy < min_dy:
        return False

    max_dy = expected.get("max_dy")
    if max_dy is not None and motion.dy > max_dy:
        return False

    return True


def _finger_signature(fingers: dict[str, str]) -> FingerSignature:
    order = ("thumb", "index", "middle", "ring", "pinky")
    return tuple((finger, fingers[finger]) for finger in order)


def _hand_compound_id(hand: HandPrimitive) -> str:
    return _hand_compound_from_parts(hand.hand_id, hand.palm_side, hand.rotation_quadrant, _finger_signature(hand.fingers))


def _hand_compound_from_parts(
    hand: str,
    palm_side: str | None,
    rotation: int | None,
    finger_signature: FingerSignature,
) -> str:
    parts = [hand]
    if palm_side:
        parts.append(palm_side)
    if rotation is not None:
        parts.append(str(rotation))
    bits = "".join("1" if state == "extended" else "0" for _, state in finger_signature)
    parts.append(bits)
    return "_".join(parts)


def _two_hand_compound_id(two_hand: TwoHandPrimitive) -> str:
    return f"both_{two_hand.motion}"
