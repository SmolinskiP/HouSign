from __future__ import annotations

import argparse
import logging
import platform
import sys
from pathlib import Path

import flet as ft

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ha_gestures.gui import main as gui_main
    from ha_gestures.log_capture import configure_process_logging
    from ha_gestures.mediapipe_runtime import MediaPipeRuntime
    from ha_gestures.runtime_controller import RuntimeController
    from ha_gestures.settings_store import load_settings
    from ha_gestures.tray import run_tray
else:
    from .gui import main as gui_main
    from .log_capture import configure_process_logging
    from .mediapipe_runtime import MediaPipeRuntime
    from .runtime_controller import RuntimeController
    from .settings_store import load_settings
    from .tray import run_tray

_LOG = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HouSign desktop entrypoint.")
    parser.add_argument("--settings", type=Path, default=Path("settings.json"), help="Path to application settings JSON.")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("settings", help="Open the Flet settings editor.")

    preview = subparsers.add_parser("preview", help="Open camera preview with overlays.")
    preview.add_argument("--camera", type=int, default=None, help="Override camera index from settings.")
    preview.add_argument("--print-every", type=int, default=None, help="Override print frequency.")
    preview.add_argument("--max-frames", type=int, default=None, help="Stop after N frames.")
    preview.add_argument("--no-mirror", action="store_true", help="Disable preview mirroring.")

    run = subparsers.add_parser("run", help="Run the main application. On Windows this starts the tray app.")
    run.add_argument("--max-frames", type=int, default=None, help="Only used outside Windows or in headless mode.")
    run.add_argument("--preview-only", action="store_true", help="Only used outside Windows or in headless mode.")

    runtime = subparsers.add_parser("runtime", help="Run the raw gesture runtime without tray.")
    runtime.add_argument("--max-frames", type=int, default=None, help="Stop after N frames.")
    runtime.add_argument("--preview-only", action="store_true", help="Evaluate policies without dispatching actions.")

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or [])
    if argv and argv[0] in {"ha_gestures.app", "ha_gestures\\app.py", "ha_gestures/app.py", "app.py"}:
        argv = argv[1:]
    if not argv:
        argv = ["run"]
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_process_logging(f"app:{args.command}")
    _LOG.info("Application entrypoint command=%s settings=%s", args.command, args.settings)
    settings = load_settings(args.settings)

    if args.command == "settings":
        _LOG.info("Opening settings window.")
        ft.app(target=gui_main, view=ft.AppView.FLET_APP)
        return 0

    if args.command == "preview":
        _LOG.info("Opening preview window camera=%s", settings.runtime.camera_index if args.camera is None else args.camera)
        runtime = MediaPipeRuntime(
            model_path=settings.runtime.model_path,
            gestures_config_path=settings.runtime.gestures_config,
            bindings_path=settings.runtime.bindings_config,
        )
        return runtime.show_camera_debug(
            camera_index=settings.runtime.camera_index if args.camera is None else args.camera,
            max_frames=args.max_frames,
            print_every=settings.runtime.print_every if args.print_every is None else args.print_every,
            mirror=False if args.no_mirror else settings.runtime.mirror,
        )

    if args.command == "run":
        if platform.system() == "Windows":
            _LOG.info("Windows detected, starting tray mode.")
            run_tray(args.settings)
            return 0
        _LOG.info("Non-Windows run command, starting runtime directly.")
        controller = RuntimeController(settings, preview_only=args.preview_only)
        result = controller.process_stream(max_frames=args.max_frames)
        if result.last_binding is not None:
            print(f"last_binding={result.last_binding.gesture_name} trigger={result.last_binding.trigger_id}")
        print(f"dispatched={len(result.dispatched)}")
        return 0

    if args.command == "runtime":
        _LOG.info("Starting raw runtime preview_only=%s", args.preview_only)
        controller = RuntimeController(settings, preview_only=args.preview_only)
        result = controller.process_stream(max_frames=args.max_frames)
        if result.last_binding is not None:
            print(f"last_binding={result.last_binding.gesture_name} trigger={result.last_binding.trigger_id}")
        print(f"dispatched={len(result.dispatched)}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
