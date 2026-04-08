from __future__ import annotations

import logging
import threading
import wave
from pathlib import Path

_LOG = logging.getLogger(__name__)


class ActivationSoundPlayer:
    def __init__(self, *, activation_enabled: bool = True, deactivation_enabled: bool = True, gesture_enabled: bool = True) -> None:
        self.activation_enabled = activation_enabled
        self.deactivation_enabled = deactivation_enabled
        self.gesture_enabled = gesture_enabled
        self._warned_missing_dependency = False
        self._warned_runtime_failure = False
        self._sound_dir = Path(__file__).resolve().parent / "sound"
        self._gesture_last_played_ms: int = 0
        self._gesture_cooldown_ms: int = 1500

    def play_activation(self) -> None:
        if not self.activation_enabled:
            return
        self._play_async("activation.wav")

    def play_deactivation(self) -> None:
        if not self.deactivation_enabled:
            return
        self._play_async("deactivation.wav")

    def play_gesture_detected(self, timestamp_ms: int) -> None:
        if not self.gesture_enabled:
            return
        if timestamp_ms - self._gesture_last_played_ms < self._gesture_cooldown_ms:
            return
        self._gesture_last_played_ms = timestamp_ms
        self._play_async("gesture_detection.wav")

    def _play_async(self, filename: str) -> None:
        threading.Thread(target=self._play_file, args=(filename,), daemon=True).start()

    def _play_file(self, filename: str) -> None:
        try:
            import pyaudio
        except Exception as exc:
            if not self._warned_missing_dependency:
                self._warned_missing_dependency = True
                _LOG.warning("Activation sound unavailable because PyAudio could not be imported: %s", exc)
            return

        sound_path = self._sound_dir / filename
        if not sound_path.exists():
            if not self._warned_runtime_failure:
                self._warned_runtime_failure = True
                _LOG.warning("Activation sound file is missing: %s", sound_path)
            return

        audio = pyaudio.PyAudio()
        stream = None
        wav_file = None
        try:
            wav_file = wave.open(str(sound_path), "rb")
            stream = audio.open(
                format=audio.get_format_from_width(wav_file.getsampwidth()),
                channels=wav_file.getnchannels(),
                rate=wav_file.getframerate(),
                output=True,
            )
            chunk_size = 1024
            chunk = wav_file.readframes(chunk_size)
            while chunk:
                stream.write(chunk)
                chunk = wav_file.readframes(chunk_size)
        except Exception as exc:
            if not self._warned_runtime_failure:
                self._warned_runtime_failure = True
                _LOG.warning("Activation sound playback failed: %s", exc)
        finally:
            if wav_file is not None:
                wav_file.close()
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    _LOG.debug("Failed to close PyAudio stream cleanly.", exc_info=True)
            audio.terminate()
