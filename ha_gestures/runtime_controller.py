from __future__ import annotations

import logging
from dataclasses import dataclass

from .activation_sound import ActivationSoundPlayer
from .action_dispatcher import ActionDispatcher, DispatchRecord
from .bindings import BindingRegistry, GestureBinding
from .execution import ExecutionCoordinator
from .mediapipe_runtime import MediaPipeRuntime
from .settings_store import AppSettings
from .status_store import save_runtime_status
from .ws_client import HomeAssistantConnectionSettings, HomeAssistantWsClient

_LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class RuntimeResult:
    dispatched: list[DispatchRecord]
    last_trigger_id: str | None
    last_binding: GestureBinding | None


class RuntimeController:
    def __init__(self, settings: AppSettings, *, preview_only: bool = False) -> None:
        self.settings = settings
        self.preview_only = preview_only
        self.binding_registry = BindingRegistry(settings.runtime.bindings_config)
        self.execution = ExecutionCoordinator()
        self.ws_client = self._build_client(settings) if not preview_only else None
        self.dispatcher = ActionDispatcher(self.ws_client)
        self.activation_sound = ActivationSoundPlayer(
            activation_enabled=bool(settings.recognition.activation_sound_enabled and not preview_only),
            deactivation_enabled=bool(settings.recognition.deactivation_sound_enabled and not preview_only),
        )
        self.runtime = MediaPipeRuntime(
            model_path=settings.runtime.model_path,
            gestures_config_path=settings.runtime.gestures_config,
            bindings_path=settings.runtime.bindings_config,
        )

    def process_stream(self, *, max_frames: int | None = None) -> RuntimeResult:
        dispatched: list[DispatchRecord] = []
        last_trigger_id: str | None = None
        last_binding: GestureBinding | None = None
        ha_state = "not_configured"
        armed_until_ms: int | None = None
        activation_started_ms: int | None = None
        activation_logged_at_ms: int | None = None
        listening_mode = self.settings.recognition.listening_mode
        activation_hold_ms = self.settings.recognition.activation_hold_ms
        session_timeout_ms = self.settings.recognition.session_timeout_ms
        was_armed = listening_mode != "activation_required"

        _LOG.info(
            "Starting runtime controller preview_only=%s camera_index=%s model=%s bindings=%s listening_mode=%s",
            self.preview_only,
            self.settings.runtime.camera_index,
            self.settings.runtime.model_path,
            self.settings.runtime.bindings_config,
            listening_mode,
        )

        if self.ws_client is not None:
            try:
                self.ws_client.connect()
                ha_state = "connected"
                _LOG.info("Runtime connected to Home Assistant WebSocket.")
            except Exception as exc:
                ha_state = "not_connected"
                _LOG.error("Runtime failed to connect to Home Assistant: %s", exc)
                save_runtime_status(runtime_state="running", ha_state=ha_state, last_error=str(exc))
        save_runtime_status(runtime_state="running", ha_state=ha_state)

        try:
            for frame in self.runtime.iter_camera(
                camera_index=self.settings.runtime.camera_index,
                max_frames=max_frames,
            ):
                activation_active = any(
                    self._is_activation_match(
                        "two_hand" if gesture.hand == "both" else "one_hand",
                        gesture.compound_id,
                    )
                    for gesture in frame.active_gestures
                )
                if listening_mode == "activation_required":
                    if activation_active:
                        if activation_started_ms is None:
                            activation_started_ms = frame.timestamp_ms
                            _LOG.info("Activation gesture detected. Waiting for hold threshold.")
                        elif frame.timestamp_ms - activation_started_ms >= activation_hold_ms:
                            armed_until_ms = frame.timestamp_ms + session_timeout_ms
                            if activation_logged_at_ms != activation_started_ms:
                                activation_logged_at_ms = activation_started_ms
                                _LOG.info(
                                    "Recognition armed by activation gesture for %sms.",
                                    session_timeout_ms,
                                )
                    else:
                        activation_started_ms = None

                is_armed = listening_mode != "activation_required" or (
                    armed_until_ms is not None and frame.timestamp_ms <= armed_until_ms
                )
                if listening_mode == "activation_required":
                    if is_armed and not was_armed:
                        self.activation_sound.play_activation()
                    elif was_armed and not is_armed:
                        self.activation_sound.play_deactivation()
                was_armed = is_armed
                active_binding_keys: set[tuple[str, str]] = set()
                for gesture in frame.active_gestures:
                    gesture_mode = "two_hand" if gesture.hand == "both" else "one_hand"
                    if listening_mode == "activation_required" and self._is_activation_match(gesture_mode, gesture.compound_id):
                        continue
                    binding = self.binding_registry.find(gesture_mode, gesture.compound_id)
                    if binding is None:
                        continue
                    _LOG.info(
                        "Matched binding gesture=%s trigger=%s mode=%s compound=%s",
                        binding.gesture_name,
                        binding.trigger_id,
                        binding.mode,
                        gesture.compound_id,
                    )
                    active_binding_keys.add((binding.mode, binding.trigger_id))
                    last_trigger_id = binding.trigger_id
                    last_binding = binding
                    if self.preview_only or not is_armed:
                        continue
                    for intent in self.execution.evaluate(binding, True, frame.timestamp_ms):
                        dispatched.append(self.dispatcher.dispatch(intent.binding, intent.phase, timestamp_ms=frame.timestamp_ms))

                for binding in self.binding_registry.all():
                    key = (binding.mode, binding.trigger_id)
                    if key in active_binding_keys:
                        continue
                    if self.preview_only:
                        continue
                    for intent in self.execution.evaluate(binding, False, frame.timestamp_ms):
                        _LOG.info(
                            "Dispatch phase generated on release gesture=%s trigger=%s phase=%s",
                            binding.gesture_name,
                            binding.trigger_id,
                            intent.phase,
                        )
                        dispatched.append(self.dispatcher.dispatch(intent.binding, intent.phase, timestamp_ms=frame.timestamp_ms))
        except Exception as exc:
            _LOG.exception("Runtime controller crashed.")
            save_runtime_status(runtime_state="stopped", ha_state=ha_state, last_error=str(exc))
            raise

        try:
            _LOG.info(
                "Runtime controller finished dispatched=%s last_trigger=%s",
                len(dispatched),
                last_trigger_id,
            )
            return RuntimeResult(
                dispatched=dispatched,
                last_trigger_id=last_trigger_id,
                last_binding=last_binding,
            )
        finally:
            final_ha_state = "not_connected" if self.ws_client is not None else "not_configured"
            save_runtime_status(runtime_state="stopped", ha_state=final_ha_state)
            if self.ws_client is not None:
                self.ws_client.close()
            _LOG.info("Runtime controller stopped.")

    @staticmethod
    def _build_client(settings: AppSettings) -> HomeAssistantWsClient | None:
        if not settings.ha.url or not settings.ha.token:
            return None
        connection_settings = HomeAssistantConnectionSettings(
            url=settings.ha.url,
            token=settings.ha.token,
        )
        return HomeAssistantWsClient(connection_settings)

    def _is_activation_match(self, mode: str, trigger_id: str) -> bool:
        if self.settings.recognition.listening_mode != "activation_required":
            return False
        configured_trigger = self.settings.recognition.activation_trigger_id.strip()
        configured_mode = self.settings.recognition.activation_mode.strip()
        if not configured_trigger or not configured_mode:
            return False
        return mode == configured_mode and trigger_id == configured_trigger
