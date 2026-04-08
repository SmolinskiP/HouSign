from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import pystray
from PIL import Image

from .status_store import load_runtime_status, save_runtime_status

_LOG = logging.getLogger(__name__)


class TrayApp:
    def __init__(self, settings_path: str | Path = "settings.json") -> None:
        self.settings_path = Path(settings_path).resolve()
        self._runtime_process: subprocess.Popen[str] | None = None
        self._preview_process: subprocess.Popen[str] | None = None
        self._settings_process: subprocess.Popen[str] | None = None
        self._stop_event = threading.Event()
        self._refresh_thread: threading.Thread | None = None
        self._resume_runtime_after_preview = False
        self._icon = pystray.Icon("HouSign", self._load_icon(), "HouSign", self._build_menu())

    def run(self) -> None:
        _LOG.info("Starting tray application with settings=%s", self.settings_path)
        self._start_runtime_worker()
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()
        self._icon.run()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _item: f"Runtime: {self._runtime_status_label()}", self._noop, enabled=False),
            pystray.MenuItem(lambda _item: f"HA: {self._ha_status_label()}", self._noop, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings", self._open_settings),
            pystray.MenuItem("Preview", self._open_preview),
            pystray.MenuItem("Reload Settings", self._reload_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _load_icon(self) -> Image.Image:
        logo_path = Path.cwd() / "logo.png"
        if logo_path.exists():
            return Image.open(logo_path)
        return Image.new("RGBA", (64, 64), (15, 125, 255, 255))

    def _runtime_status_label(self) -> str:
        if self._runtime_process is not None:
            if self._runtime_process.poll() is None:
                return "running"
            return "stopped"
        return load_runtime_status().runtime_state

    def _ha_status_label(self) -> str:
        return load_runtime_status().ha_state

    def _base_command(self) -> list[str]:
        return [sys.executable, "-m", "ha_gestures.app", "--settings", str(self.settings_path)]

    def _spawn(self, command: list[str]) -> subprocess.Popen[str]:
        return subprocess.Popen(command, cwd=str(Path.cwd()), text=True)

    def _ensure_menu_refresh(self) -> None:
        try:
            self._icon.update_menu()
            self._icon.title = f"HouSign | Runtime: {self._runtime_status_label()} | HA: {self._ha_status_label()}"
        except Exception:
            pass

    def _noop(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        return

    def _refresh_loop(self) -> None:
        while not self._stop_event.wait(1.5):
            self._ensure_menu_refresh()

    def _start_runtime_worker(self) -> None:
        if self._runtime_process is not None and self._runtime_process.poll() is None:
            return
        _LOG.info("Tray runtime bootstrap: starting worker")
        save_runtime_status(runtime_state="starting", ha_state=load_runtime_status().ha_state)
        self._runtime_process = self._spawn([*self._base_command(), "runtime"])
        self._ensure_menu_refresh()

    def _open_settings(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _LOG.info("Tray action: open settings")
        if self._settings_process is None or self._settings_process.poll() is not None:
            self._settings_process = self._spawn([*self._base_command(), "settings"])
        self._ensure_menu_refresh()

    def _open_preview(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _LOG.info("Tray action: open preview")
        if self._preview_process is not None and self._preview_process.poll() is None:
            self._ensure_menu_refresh()
            return

        runtime_was_running = self._runtime_process is not None and self._runtime_process.poll() is None
        self._resume_runtime_after_preview = runtime_was_running
        if runtime_was_running:
            _LOG.info("Pausing runtime while preview window is open.")
            self._runtime_process.terminate()
            self._runtime_process.wait(timeout=5)
            save_runtime_status(runtime_state="paused_preview", ha_state=load_runtime_status().ha_state)

        if self._preview_process is None or self._preview_process.poll() is not None:
            self._preview_process = self._spawn([*self._base_command(), "preview"])
            watcher = threading.Thread(target=self._watch_preview_process, daemon=True)
            watcher.start()
        self._ensure_menu_refresh()

    def _watch_preview_process(self) -> None:
        preview_process = self._preview_process
        if preview_process is None:
            return
        preview_process.wait()
        _LOG.info("Preview process exited.")
        self._preview_process = None
        if self._resume_runtime_after_preview and not self._stop_event.is_set():
            _LOG.info("Resuming runtime after preview window closed.")
            self._resume_runtime_after_preview = False
            self._start_runtime_worker()
        self._ensure_menu_refresh()

    def _reload_settings(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _LOG.info("Tray action: reload settings")
        self._resume_runtime_after_preview = False
        if self._runtime_process is not None and self._runtime_process.poll() is None:
            self._runtime_process.terminate()
            self._runtime_process.wait(timeout=5)
        self._start_runtime_worker()
        self._ensure_menu_refresh()

    def _quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _LOG.info("Tray action: quit")
        self._stop_event.set()
        self._resume_runtime_after_preview = False
        for process in (self._runtime_process, self._preview_process, self._settings_process):
            if process is not None and process.poll() is None:
                process.terminate()
        if self._refresh_thread is not None and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2)
        self._icon.stop()


def run_tray(settings_path: str | Path = "settings.json") -> None:
    save_runtime_status(runtime_state="stopped", ha_state=load_runtime_status().ha_state)
    app = TrayApp(settings_path=settings_path)
    thread = threading.Thread(target=app.run, daemon=False)
    thread.start()
    thread.join()
