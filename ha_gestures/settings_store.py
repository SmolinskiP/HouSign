from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class HASettings:
    url: str = ""
    token: str = ""


@dataclass(slots=True)
class RuntimeSettings:
    camera_index: int = 0
    model_path: str = "models/hand_landmarker.task"
    gestures_config: str = "gestures.yaml"
    bindings_config: str = "gesture_bindings.json"
    print_every: int = 10
    mirror: bool = True


@dataclass(slots=True)
class RecognitionSettings:
    listening_mode: str = "always_listening"
    activation_mode: str = "one_hand"
    activation_trigger_id: str = ""
    activation_gesture_name: str = ""
    activation_hold_ms: int = 600
    session_timeout_ms: int = 4000
    activation_sound_enabled: bool = True
    deactivation_sound_enabled: bool = True
    gesture_sound_enabled: bool = True
    gesture_hold_ms: int = 140
    gesture_gap_tolerance_ms: int = 100


@dataclass(slots=True)
class GUISettings:
    window_maximized: bool = True


@dataclass(slots=True)
class AppSettings:
    ha: HASettings
    runtime: RuntimeSettings
    recognition: RecognitionSettings
    gui: GUISettings

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_settings() -> AppSettings:
    return AppSettings(
        ha=HASettings(),
        runtime=RuntimeSettings(),
        recognition=RecognitionSettings(),
        gui=GUISettings(),
    )


def load_settings(path: str | Path = "settings.json") -> AppSettings:
    settings = default_settings()
    settings_path = Path(path)
    if settings_path.exists():
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        _merge_settings(settings, payload)
    return settings


def save_settings(settings: AppSettings, path: str | Path = "settings.json") -> None:
    Path(path).write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def _merge_settings(settings: AppSettings, payload: dict[str, object]) -> None:
    ha_payload = payload.get("ha", {})
    if isinstance(ha_payload, dict):
        settings.ha.url = str(ha_payload.get("url", settings.ha.url))
        settings.ha.token = str(ha_payload.get("token", settings.ha.token))

    runtime_payload = payload.get("runtime", {})
    if isinstance(runtime_payload, dict):
        settings.runtime.camera_index = int(runtime_payload.get("camera_index", settings.runtime.camera_index))
        settings.runtime.model_path = str(runtime_payload.get("model_path", settings.runtime.model_path))
        settings.runtime.gestures_config = str(runtime_payload.get("gestures_config", settings.runtime.gestures_config))
        settings.runtime.bindings_config = str(runtime_payload.get("bindings_config", settings.runtime.bindings_config))
        settings.runtime.print_every = int(runtime_payload.get("print_every", settings.runtime.print_every))
        settings.runtime.mirror = bool(runtime_payload.get("mirror", settings.runtime.mirror))

    recognition_payload = payload.get("recognition", {})
    if isinstance(recognition_payload, dict):
        legacy_sound_enabled = bool(
            recognition_payload.get("activation_sound_enabled", settings.recognition.activation_sound_enabled)
        )
        settings.recognition.listening_mode = str(
            recognition_payload.get("listening_mode", settings.recognition.listening_mode)
        )
        settings.recognition.activation_mode = str(
            recognition_payload.get("activation_mode", settings.recognition.activation_mode)
        )
        settings.recognition.activation_trigger_id = str(
            recognition_payload.get("activation_trigger_id", settings.recognition.activation_trigger_id)
        )
        settings.recognition.activation_gesture_name = str(
            recognition_payload.get("activation_gesture_name", settings.recognition.activation_gesture_name)
        )
        settings.recognition.activation_hold_ms = int(
            recognition_payload.get("activation_hold_ms", settings.recognition.activation_hold_ms)
        )
        settings.recognition.session_timeout_ms = int(
            recognition_payload.get("session_timeout_ms", settings.recognition.session_timeout_ms)
        )
        settings.recognition.activation_sound_enabled = bool(
            recognition_payload.get("activation_sound_enabled", legacy_sound_enabled)
        )
        settings.recognition.deactivation_sound_enabled = bool(
            recognition_payload.get("deactivation_sound_enabled", legacy_sound_enabled)
        )
        settings.recognition.gesture_sound_enabled = bool(
            recognition_payload.get("gesture_sound_enabled", settings.recognition.gesture_sound_enabled)
        )
        settings.recognition.gesture_hold_ms = int(
            recognition_payload.get("gesture_hold_ms", settings.recognition.gesture_hold_ms)
        )
        settings.recognition.gesture_gap_tolerance_ms = int(
            recognition_payload.get("gesture_gap_tolerance_ms", settings.recognition.gesture_gap_tolerance_ms)
        )

    gui_payload = payload.get("gui", {})
    if isinstance(gui_payload, dict):
        settings.gui.window_maximized = bool(gui_payload.get("window_maximized", settings.gui.window_maximized))
