from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .log_capture import configure_process_logging
from .mediapipe_runtime import MediaPipeRuntime
from .settings_store import AppSettings, load_settings

_LOG = logging.getLogger(__name__)


def build_parser(settings: AppSettings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print hand primitives from a webcam feed.")
    parser.add_argument(
        "--settings",
        type=Path,
        default=Path("settings.json"),
        help="Path to application settings JSON.",
    )
    parser.add_argument("--camera", type=int, default=settings.runtime.camera_index, help="Camera index.")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(settings.runtime.model_path),
        help="Path to the MediaPipe hand landmarker .task model.",
    )
    parser.add_argument(
        "--gestures-config",
        type=Path,
        default=Path(settings.runtime.gestures_config),
        help="Path to gestures YAML config.",
    )
    parser.add_argument(
        "--bindings-config",
        type=Path,
        default=Path(settings.runtime.bindings_config),
        help="Path to saved gesture bindings JSON.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Stop after N frames.",
    )
    parser.add_argument(
        "--print-every",
        type=int,
        default=settings.runtime.print_every,
        help="Print every Nth frame to reduce console spam.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show camera window with debug overlay.",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="Disable preview mirroring.",
    )
    return parser


def main() -> int:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--settings", type=Path, default=Path("settings.json"))
    pre_args, _ = pre_parser.parse_known_args()
    configure_process_logging("cli")
    settings = load_settings(pre_args.settings)
    _LOG.info("CLI startup settings=%s", pre_args.settings)

    parser = build_parser(settings)
    args = parser.parse_args()
    runtime = MediaPipeRuntime(
        model_path=args.model,
        gestures_config_path=args.gestures_config,
        bindings_path=args.bindings_config,
    )

    try:
        if args.show:
            _LOG.info("CLI show mode camera=%s print_every=%s mirror=%s", args.camera, args.print_every, False if args.no_mirror else settings.runtime.mirror)
            return runtime.show_camera_debug(
                camera_index=args.camera,
                max_frames=args.max_frames,
                print_every=args.print_every,
                mirror=False if args.no_mirror else settings.runtime.mirror,
            )

        _LOG.info("CLI print mode camera=%s print_every=%s", args.camera, args.print_every)
        for frame_index, frame_state in enumerate(
            runtime.iter_camera(camera_index=args.camera, max_frames=args.max_frames),
            start=1,
        ):
            if frame_index % args.print_every == 0:
                print(json.dumps(frame_state.to_dict(), ensure_ascii=True))
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # pragma: no cover - exercised in runtime, not unit tests.
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
