from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path

import flet as ft
import flet.canvas as cv
import pyperclip

from .bindings import GestureAction, GestureBinding, GestureExecution, find_binding, load_bindings, save_bindings
from .gui_state import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FINGER_ORDER,
    ROTATIONS,
    EditableHandState,
    default_hand_state,
    editor_state_from_binding,
    hand_canvas_shapes,
    hit_test_finger,
    resolve_preview,
)
from .log_capture import get_log_path
from .paths import app_dir
from .settings_store import load_settings
from .ws_client import HomeAssistantConnectionSettings, HomeAssistantWsClient, HomeAssistantWsError

CARD_BG = "#111a2d"
CARD_BG_ALT = "#16243b"
BORDER = "#2b4261"
TEXT = "#e8effc"
MUTED = "#8da5c7"
ACCENT = "#f07d24"
ACCENT_ALT = "#23c483"
DANGER = "#f06c6c"
SURFACE = "#08111d"
_LOG = logging.getLogger(__name__)
ACTION_PRESETS: dict[str, dict[str, object]] = {
    "placeholder": {
        "label": "Placeholder only",
        "action_type": "placeholder",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "custom_service": {
        "label": "Custom service",
        "action_type": "service",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "light_turn_on": {
        "label": "Light turn on",
        "action_type": "service",
        "domain": "light",
        "service": "turn_on",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "light_turn_off": {
        "label": "Light turn off",
        "action_type": "service",
        "domain": "light",
        "service": "turn_off",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "light_toggle": {
        "label": "Light toggle",
        "action_type": "service",
        "domain": "light",
        "service": "toggle",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "script_turn_on": {
        "label": "Script turn on",
        "action_type": "service",
        "domain": "script",
        "service": "turn_on",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "scene_turn_on": {
        "label": "Scene turn on",
        "action_type": "service",
        "domain": "scene",
        "service": "turn_on",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
    "light_dim_up": {
        "label": "Light dim up",
        "action_type": "service",
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_step_pct": 10},
        "execution_mode": "hold_repeat",
        "cooldown_ms": 0,
        "repeat_every_ms": 150,
    },
    "light_dim_down": {
        "label": "Light dim down",
        "action_type": "service",
        "domain": "light",
        "service": "turn_on",
        "service_data": {"brightness_step_pct": -10},
        "execution_mode": "hold_repeat",
        "cooldown_ms": 0,
        "repeat_every_ms": 150,
    },
    "volume_up": {
        "label": "Volume up",
        "action_type": "service",
        "domain": "media_player",
        "service": "volume_up",
        "execution_mode": "hold_repeat",
        "cooldown_ms": 0,
        "repeat_every_ms": 200,
    },
    "volume_down": {
        "label": "Volume down",
        "action_type": "service",
        "domain": "media_player",
        "service": "volume_down",
        "execution_mode": "hold_repeat",
        "cooldown_ms": 0,
        "repeat_every_ms": 200,
    },
    "custom_event": {
        "label": "Custom event",
        "action_type": "event",
        "execution_mode": "instant",
        "cooldown_ms": 800,
        "repeat_every_ms": 150,
    },
}


class GestureStudio:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.settings_path = (app_dir() / "settings.json").resolve()
        self.settings = load_settings(self.settings_path)
        self.gestures_path = str((app_dir() / self.settings.runtime.gestures_config).resolve())
        self.bindings_path = (app_dir() / self.settings.runtime.bindings_config).resolve()
        self.left_hand = default_hand_state("left")
        self.right_hand = default_hand_state("right")
        self.mode = "one_hand"
        self.one_hand_selection = "right"
        self.selected_tab = "editor"
        self.bindings: list[GestureBinding] = []
        self.ha_entities: list[dict[str, str]] = []
        self.status_message = ""

        self.binding_name = ft.TextField(label="Display name", hint_text="Optional human name for this trigger")
        self.binding_action = ft.TextField(label="Action label", hint_text="Optional short label shown in preview and debug")
        self.action_preset = ft.Dropdown(
            label="Action preset",
            value="placeholder",
            options=[ft.dropdown.Option(key, preset["label"]) for key, preset in ACTION_PRESETS.items()],
            on_select=self._on_action_preset_change,
        )
        self.action_type = ft.Dropdown(
            label="Action type",
            value="placeholder",
            options=[
                ft.dropdown.Option("placeholder"),
                ft.dropdown.Option("service"),
                ft.dropdown.Option("event"),
            ],
            on_select=self._on_action_type_change,
        )
        self.service_domain = ft.TextField(label="Service domain", hint_text="light", on_change=self._on_service_fields_changed)
        self.service_name = ft.TextField(label="Service name", hint_text="turn_on", on_change=self._on_service_fields_changed)
        self.entity_dropdown = ft.Dropdown(
            label="Suggested entity",
            on_select=self._on_entity_selected,
            enable_filter=True,
            enable_search=True,
            editable=True,
            menu_height=420,
        )
        self.service_entity_id = ft.TextField(label="Target entity_id", hint_text="light.living_room")
        self.service_data = ft.TextField(label="Service data (JSON)", multiline=True, min_lines=2, max_lines=5, hint_text='{"brightness_step_pct": 10}')
        self.return_response = ft.Switch(label="Request service response")
        self.event_type = ft.TextField(label="Event type", hint_text="housign_gesture")
        self.event_data = ft.TextField(label="Event data (JSON)", multiline=True, min_lines=2, max_lines=5, hint_text='{"gesture": "light_dim_up"}')
        self.execution_mode = ft.Dropdown(
            label="Execution mode",
            value="instant",
            options=[
                ft.dropdown.Option("instant"),
                ft.dropdown.Option("hold_start"),
                ft.dropdown.Option("hold_repeat"),
                ft.dropdown.Option("hold_end"),
            ],
            on_select=self._on_execution_mode_change,
        )
        self.cooldown_ms = ft.TextField(label="Cooldown ms", value="800")
        self.repeat_every_ms = ft.TextField(label="Repeat every ms", value="150")
        self.ha_url = ft.TextField(label="Home Assistant URL", hint_text="http://homeassistant.local:8123")
        self.ha_token = ft.TextField(label="Long-lived access token", password=True, can_reveal_password=True)
        self.ha_connection_status = ft.Text(color=MUTED)
        self.camera_index = ft.TextField(label="Camera index")
        self.model_path = ft.TextField(label="Model path")
        self.gestures_config = ft.TextField(label="Gestures config")
        self.bindings_config = ft.TextField(label="Bindings config")
        self.print_every = ft.TextField(label="Console print every N frames")
        self.runtime_mirror = ft.Switch(label="Mirror preview")
        self.listening_mode = ft.Dropdown(
            label="Listening mode",
            value="always_listening",
            options=[
                ft.dropdown.Option("always_listening", "Always listening"),
                ft.dropdown.Option("activation_required", "Activation required"),
            ],
            on_select=self._on_listening_mode_change,
        )
        self.activation_mode = ft.Dropdown(
            label="Activation gesture mode",
            value="one_hand",
            options=[
                ft.dropdown.Option("one_hand", "One hand"),
                ft.dropdown.Option("two_hand", "Two hands"),
            ],
            on_select=lambda _event: self._refresh_view(),
        )
        self.activation_gesture_name = ft.TextField(
            label="Activation gesture name",
            hint_text="Optional label for the activation gesture",
        )
        self.activation_trigger_id = ft.TextField(
            label="Activation trigger id",
            read_only=True,
        )
        self.activation_hold_ms = ft.TextField(label="Activation hold ms", value="600")
        self.session_timeout_ms = ft.TextField(label="Session timeout ms", value="4000")
        self.gesture_hold_ms = ft.TextField(label="Gesture hold ms", value="140")
        self.gesture_gap_tolerance_ms = ft.TextField(label="Gesture gap tolerance ms", value="100")
        self.activation_sound_enabled = ft.Switch(label="Play activation sound")
        self.deactivation_sound_enabled = ft.Switch(label="Play deactivation sound")
        self.gesture_sound_enabled = ft.Switch(label="Play gesture detection sound")
        self.window_maximized = ft.Switch(label="Start window maximized")
        self.mode_selector = ft.RadioGroup(
            value=self.mode,
            content=ft.Row(
                [
                    ft.Radio(value="one_hand", label="One hand"),
                    ft.Radio(value="two_hand", label="Two hands"),
                ],
                spacing=24,
            ),
            on_change=self._on_mode_change,
        )
        self.one_hand_dropdown = ft.Dropdown(
            label="Active hand in one-hand mode",
            width=220,
            value=self.one_hand_selection,
            options=[ft.dropdown.Option("left"), ft.dropdown.Option("right")],
            on_select=self._on_selection_change,
        )

        self.preview_title = ft.Text(size=26, weight=ft.FontWeight.W_700, color=TEXT)
        self.preview_compound = ft.Text(color="#ffd6b2", selectable=True)
        self.preview_details = ft.Text(color=MUTED)
        self.storage_status_value = ""
        self.debug_console = ft.TextField(
            label="Application log",
            multiline=True,
            min_lines=20,
            max_lines=30,
            read_only=True,
            expand=True,
            value="",
        )
        self.bindings_column = ft.Column(spacing=10)

        self.left_card = ft.Container(expand=1)
        self.center_card = ft.Container(width=430)
        self.right_card = ft.Container(expand=1)
        self.content_host = ft.Container(expand=True)
        self._apply_action_preset("placeholder", refresh=False)
        self._load_settings_into_controls()
        self._load_debug_console()
        self._load_bindings()

    def build(self) -> ft.Control:
        self.page.title = "HA Gestures Studio"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = SURFACE
        self.page.padding = 16
        self.page.scroll = ft.ScrollMode.AUTO
        try:
            self.page.window.icon = str((app_dir() / "logo.png").resolve())
            self.page.window.maximized = self.settings.gui.window_maximized
            self.page.window.min_width = 1280
            self.page.window.min_height = 860
        except AttributeError:
            pass

        root = ft.Column(
            expand=True,
            spacing=12,
            controls=[
                ft.Container(
                    padding=18,
                    border_radius=20,
                    border=ft.border.all(1, BORDER),
                    bgcolor=CARD_BG,
                    content=ft.Container(
                        expand=True,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            wrap=True,
                            spacing=10,
                            run_spacing=10,
                            controls=[
                                self._tab_button("editor", "Editor", ft.Icons.GESTURE),
                                self._tab_button("bindings", "Bindings", ft.Icons.DATA_ARRAY),
                                self._tab_button("home_assistant", "Home Assistant", ft.Icons.HOME),
                                self._tab_button("runtime", "Runtime", ft.Icons.TUNE),
                                self._tab_button("activation", "Activation", ft.Icons.NOTIFICATIONS_ACTIVE),
                                self._tab_button("debug", "Debug", ft.Icons.TERMINAL),
                                self._tab_button("about", "About", ft.Icons.INFO_OUTLINE),
                            ],
                        ),
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=8,
                    border_radius=20,
                    bgcolor=SURFACE,
                    content=self.content_host,
                ),
            ],
        )
        return root

    def _tab_button(self, key: str, label: str, icon: str) -> ft.Control:
        active = self.selected_tab == key
        return ft.ElevatedButton(
            label,
            icon=icon,
            style=ft.ButtonStyle(
                bgcolor=ACCENT if active else CARD_BG_ALT,
                color=TEXT,
                side=ft.border.BorderSide(1, ACCENT if active else BORDER),
                shape=ft.RoundedRectangleBorder(radius=14),
            ),
            on_click=lambda _event, target=key: self._set_tab(target),
        )

    def _set_tab(self, key: str) -> None:
        self.selected_tab = key
        _LOG.info("GUI tab selected: %s", key)
        self._refresh_view()

    def _current_tab_content(self) -> ft.Control:
        if self.selected_tab == "bindings":
            return self._build_bindings_tab()
        if self.selected_tab == "home_assistant":
            return self._build_home_assistant_tab()
        if self.selected_tab == "runtime":
            return self._build_runtime_tab()
        if self.selected_tab == "activation":
            return self._build_activation_tab()
        if self.selected_tab == "debug":
            return self._build_debug_tab()
        if self.selected_tab == "about":
            return self._build_about_tab()
        return self._build_editor_tab()

    def _refresh_view(self) -> None:
        preview_name, preview_compound, frame = resolve_preview(
            self.left_hand,
            self.right_hand,
            self.mode,
            self.one_hand_selection,
            self.gestures_path,
        )
        matched_binding = self._find_binding(preview_compound)
        self.preview_title.value = preview_name
        self.preview_compound.value = preview_compound
        self.storage_status_value = self.status_message or f"Bindings file: {self.bindings_path}"
        if self.mode == "one_hand":
            active_hand = self.left_hand if self.one_hand_selection == "left" else self.right_hand
            self.preview_details.value = (
                f"Mode: one hand ({self.one_hand_selection}) | Raw pose: {active_hand.compound_id()} | "
                f"Resolved key: {frame.active_gesture_key or 'unnamed_pose'}"
            )
        else:
            left_active = frame.active_gestures_by_hand.get("left")
            right_active = frame.active_gestures_by_hand.get("right")
            self.preview_details.value = (
                f"Mode: two hands | Left: {(left_active.name if left_active else self.left_hand.compound_id())} | "
                f"Right: {(right_active.name if right_active else self.right_hand.compound_id())}"
            )

        self.left_card.content = self._build_hand_card(self.left_hand)
        self.left_card.col = {"xs": 12, "md": 6, "xl": 4}
        self.center_card.content = self._build_center_card(preview_name, preview_compound, matched_binding)
        self.center_card.col = {"xs": 12, "xl": 4}
        self.right_card.content = self._build_hand_card(self.right_hand)
        self.right_card.col = {"xs": 12, "md": 6, "xl": 4}
        self.bindings_column.controls = [self._build_binding_row(binding, idx) for idx, binding in enumerate(self.bindings)] or [
            ft.Container(
                padding=16,
                border_radius=16,
                border=ft.border.all(1, BORDER),
                bgcolor=CARD_BG_ALT,
                content=ft.Text("No gesture bindings yet.", color=MUTED),
            )
        ]
        self._refresh_entity_dropdown()
        self.content_host.content = self._current_tab_content()
        self.one_hand_dropdown.disabled = self.mode != "one_hand"
        self.page.update()

    def _build_editor_tab(self) -> ft.Control:
        return ft.Container(
            padding=ft.padding.only(top=12),
            content=ft.ResponsiveRow(
                columns=12,
                spacing=16,
                run_spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[self.left_card, self.center_card, self.right_card],
            ),
        )

    def _build_hand_card(self, hand: EditableHandState) -> ft.Control:
        active_in_mode = self.mode == "two_hand" or self.one_hand_selection == hand.hand_id
        skeleton = ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.CLICK,
            on_tap_down=lambda event, owner=hand.hand_id: self._on_hand_tap(owner, event),
            content=cv.Canvas(
                width=CANVAS_WIDTH,
                height=CANVAS_HEIGHT,
                shapes=hand_canvas_shapes(hand),
            ),
        )

        finger_buttons = ft.ResponsiveRow(
            spacing=8,
            run_spacing=8,
            controls=[
                ft.ElevatedButton(
                    content=f"{finger}: {hand.fingers[finger]}",
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT_ALT if hand.fingers[finger] == "extended" else CARD_BG_ALT,
                        color=TEXT,
                        side=ft.border.BorderSide(1, ACCENT_ALT if hand.fingers[finger] == "extended" else BORDER),
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                    on_click=lambda _event, target=finger, owner=hand.hand_id: self._toggle_finger(owner, target),
                    col={"sm": 6, "md": 4},
                )
                for finger in FINGER_ORDER
            ],
        )

        return ft.Container(
            padding=18,
            border_radius=20,
            border=ft.border.all(1, BORDER),
            bgcolor=CARD_BG,
            opacity=1.0 if active_in_mode else 0.45,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(f"{hand.hand_id.upper()} hand", size=22, weight=ft.FontWeight.W_700, color=TEXT),
                                    ft.Text(
                                        hand.compound_id(),
                                        size=12,
                                        color=MUTED,
                                        selectable=True,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                bgcolor=ACCENT_ALT if active_in_mode else CARD_BG_ALT,
                                border_radius=999,
                                content=ft.Text("active" if active_in_mode else "inactive", color=TEXT, size=12),
                            ),
                        ],
                    ),
                    ft.Container(
                        alignment=ft.Alignment(0, 0),
                        border_radius=18,
                        bgcolor=CARD_BG_ALT,
                        padding=12,
                        content=skeleton,
                    ),
                    ft.ResponsiveRow(
                        columns=12,
                        spacing=10,
                        run_spacing=10,
                        controls=[
                            ft.Dropdown(
                                label="Palm side",
                                value=hand.palm_side,
                                options=[ft.dropdown.Option("front"), ft.dropdown.Option("back")],
                                on_select=lambda event, owner=hand.hand_id: self._set_palm(owner, event.control.value),
                                col={"xs": 12, "sm": 6},
                            ),
                            ft.Dropdown(
                                label="Rotation",
                                value=str(hand.rotation_quadrant),
                                options=[ft.dropdown.Option(str(rotation)) for rotation in ROTATIONS],
                                on_select=lambda event, owner=hand.hand_id: self._set_rotation(owner, int(event.control.value)),
                                col={"xs": 12, "sm": 6},
                            ),
                        ],
                    ),
                    finger_buttons,
                ],
            ),
        )

    def _build_center_card(
        self,
        preview_name: str,
        preview_compound: str,
        matched_binding: GestureBinding | None,
    ) -> ft.Control:
        return ft.Container(
            padding=18,
            border_radius=20,
            border=ft.border.all(1, BORDER),
            bgcolor=CARD_BG,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.ResponsiveRow(
                        columns=12,
                        spacing=12,
                        run_spacing=12,
                        controls=[
                            ft.Column(
                                col={"xs": 12, "lg": 7},
                                spacing=4,
                                controls=[
                                    ft.Text("Binding Preview", size=24, weight=ft.FontWeight.W_700, color=TEXT),
                                    ft.Text("Use one hand or two. Display name is optional. Action is a placeholder for the future Home Assistant binding.", size=13, color=MUTED),
                                ],
                            ),
                            ft.ElevatedButton(
                                "Add binding",
                                icon=ft.Icons.ADD,
                                style=ft.ButtonStyle(
                                    bgcolor=ACCENT,
                                    color=TEXT,
                                    shape=ft.RoundedRectangleBorder(radius=14),
                                ),
                                on_click=self._add_binding,
                                col={"xs": 12, "lg": 5},
                            ),
                        ],
                    ),
                    ft.ResponsiveRow(
                        columns=12,
                        spacing=12,
                        run_spacing=12,
                        controls=[
                            ft.Container(
                                col={"xs": 12},
                                padding=16,
                                border_radius=18,
                                bgcolor=CARD_BG_ALT,
                                border=ft.border.all(1, BORDER),
                                content=ft.Column(
                                    spacing=12,
                                    controls=[
                                        ft.Text("Gesture mode", size=12, color=MUTED, weight=ft.FontWeight.W_600),
                                        self.mode_selector,
                                        self.one_hand_dropdown,
                                    ],
                                ),
                            ),
                            ft.Container(
                                col={"xs": 12},
                                padding=18,
                                border_radius=18,
                                bgcolor="#1a2437",
                                border=ft.border.all(1, "#4a566f"),
                                content=ft.Column(
                                    spacing=10,
                                    controls=[
                                        ft.Text("Current resolved gesture", size=12, color=MUTED, weight=ft.FontWeight.W_600),
                                        self.preview_title,
                                        ft.Text(
                                            preview_compound,
                                            color="#ffd6b2",
                                            selectable=True,
                                            max_lines=3,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        self.preview_details,
                                    ],
                                ),
                            ),
                            ft.Container(
                                col={"xs": 12},
                                padding=18,
                                border_radius=18,
                                bgcolor="#182235",
                                border=ft.border.all(1, ACCENT if matched_binding else BORDER),
                                content=ft.Column(
                                    spacing=10,
                                    controls=[
                                        ft.Text("Assigned binding", size=12, color=MUTED, weight=ft.FontWeight.W_600),
                                        ft.Text(
                                            matched_binding.gesture_name if matched_binding else "No name assigned",
                                            size=22,
                                            weight=ft.FontWeight.W_700,
                                            color=TEXT if matched_binding else MUTED,
                                        ),
                                        ft.Text(
                                            matched_binding.action_name if matched_binding else "No action assigned to this pose yet.",
                                            color="#ffd6b2" if matched_binding else MUTED,
                                            selectable=bool(matched_binding),
                                        ),
                                        ft.Text(
                                            f"Source trigger: {matched_binding.trigger_id}" if matched_binding else "Save this pose to attach a display name and action placeholder.",
                                            size=12,
                                            color=MUTED,
                                            max_lines=2,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                    self.binding_name,
                    self.binding_action,
                    self._build_action_editor(),
                    self._status_control(),
                ],
            ),
        )

    def _build_action_editor(self) -> ft.Control:
        show_service = self.action_type.value == "service"
        show_event = self.action_type.value == "event"
        show_repeat = self.execution_mode.value == "hold_repeat"

        return ft.Container(
            padding=18,
            border_radius=18,
            bgcolor=CARD_BG_ALT,
            border=ft.border.all(1, BORDER),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Action", size=12, color=MUTED, weight=ft.FontWeight.W_600),
                    self.action_preset,
                    self.action_type,
                    ft.Container(
                        visible=show_service,
                        content=ft.Column(
                            spacing=10,
                            controls=[
                                self.service_domain,
                                self.service_name,
                                self.entity_dropdown,
                                self.service_entity_id,
                                self.service_data,
                                self.return_response,
                            ],
                        ),
                    ),
                    ft.Container(
                        visible=show_event,
                        content=ft.Column(
                            spacing=10,
                            controls=[
                                self.event_type,
                                self.event_data,
                            ],
                        ),
                    ),
                    ft.Divider(color=BORDER),
                    ft.Text("Execution policy", size=12, color=MUTED, weight=ft.FontWeight.W_600),
                    self.execution_mode,
                    self.cooldown_ms,
                    ft.Container(visible=show_repeat, content=self.repeat_every_ms),
                ],
            ),
        )

    def _build_bindings_tab(self) -> ft.Control:
        return ft.Container(
            padding=20,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Text("Saved bindings", size=24, weight=ft.FontWeight.W_700, color=TEXT),
                    ft.Text(
                        "Click a saved binding to restore it into the editor. Delete still works from the trash icon.",
                        color=MUTED,
                    ),
                    self._status_control(),
                    self.bindings_column,
                ],
            ),
        )

    def _build_home_assistant_tab(self) -> ft.Control:
        return ft.Container(
            padding=20,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Text("Home Assistant", size=24, weight=ft.FontWeight.W_700, color=TEXT),
                    ft.Text(
                        "WebSocket connection settings. The runtime can pick them up after reloading settings without closing the GUI.",
                        color=MUTED,
                    ),
                    ft.Container(
                        padding=20,
                        border_radius=18,
                        bgcolor=CARD_BG_ALT,
                        border=ft.border.all(1, BORDER),
                        content=ft.Column(
                            spacing=14,
                            controls=[
                                self.ha_url,
                                self.ha_token,
                                ft.Row(
                                    spacing=12,
                                    controls=[
                                        ft.ElevatedButton(
                                            "Test connection & load entities",
                                            icon=ft.Icons.WIFI_FIND,
                                            on_click=self._test_connection_and_load_entities,
                                        ),
                                        ft.ElevatedButton(
                                            "Save settings",
                                            icon=ft.Icons.SAVE,
                                            style=ft.ButtonStyle(bgcolor=ACCENT, color=TEXT),
                                            on_click=self._save_settings,
                                        ),
                                        ft.ElevatedButton(
                                            "Reload from disk",
                                            icon=ft.Icons.REFRESH,
                                            on_click=self._reload_settings,
                                        ),
                                    ],
                                ),
                                self.ha_connection_status,
                                ft.Text(str(self.settings_path), color="#ffd6b2", selectable=True),
                            ],
                        ),
                    ),
                    self._status_control(),
                ],
            ),
        )

    def _build_runtime_tab(self) -> ft.Control:
        return ft.Container(
            padding=20,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Text("Runtime", size=24, weight=ft.FontWeight.W_700, color=TEXT),
                    ft.Text(
                        "Camera, model, config files and window behavior. These values are written directly to settings.json.",
                        color=MUTED,
                    ),
                    ft.Container(
                        padding=20,
                        border_radius=18,
                        bgcolor=CARD_BG_ALT,
                        border=ft.border.all(1, BORDER),
                        content=ft.Column(
                            spacing=14,
                            controls=[
                                self.camera_index,
                                self.model_path,
                                self.gestures_config,
                                self.bindings_config,
                                self.print_every,
                                self.runtime_mirror,
                                self.window_maximized,
                            ],
                        ),
                    ),
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.ElevatedButton(
                                "Save settings",
                                icon=ft.Icons.SAVE,
                                style=ft.ButtonStyle(bgcolor=ACCENT, color=TEXT),
                                on_click=self._save_settings,
                            ),
                            ft.ElevatedButton(
                                "Reload from disk",
                                icon=ft.Icons.REFRESH,
                                on_click=self._reload_settings,
                            ),
                        ],
                    ),
                    self._status_control(),
                ],
            ),
        )

    def _build_activation_tab(self) -> ft.Control:
        activation_enabled = (self.listening_mode.value or "always_listening") == "activation_required"
        return ft.Container(
            padding=20,
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Text("Activation", size=24, weight=ft.FontWeight.W_700, color=TEXT),
                    ft.Text(
                        "Control whether gesture recognition is always on or unlocked by a dedicated activation pose, with optional sound feedback.",
                        color=MUTED,
                    ),
                    ft.Container(
                        padding=20,
                        border_radius=18,
                        bgcolor=CARD_BG_ALT,
                        border=ft.border.all(1, BORDER),
                        content=ft.Column(
                            spacing=14,
                            controls=[
                                ft.Text("Recognition mode", size=18, weight=ft.FontWeight.W_700, color=TEXT),
                                ft.Text(
                                    "Choose whether commands are always active or unlocked by a dedicated activation gesture first.",
                                    color=MUTED,
                                ),
                                self.listening_mode,
                                ft.Container(
                                    visible=activation_enabled,
                                    content=ft.Column(
                                        spacing=14,
                                        controls=[
                                            self.activation_mode,
                                            self.activation_gesture_name,
                                            self.activation_trigger_id,
                                            self.activation_hold_ms,
                                            self.session_timeout_ms,
                                            self.gesture_hold_ms,
                                            self.gesture_gap_tolerance_ms,
                                            self.activation_sound_enabled,
                                            self.deactivation_sound_enabled,
                                            self.gesture_sound_enabled,
                                            ft.Row(
                                                spacing=12,
                                                wrap=True,
                                                controls=[
                                                    ft.ElevatedButton(
                                                        "Use current editor pose",
                                                        icon=ft.Icons.GESTURE,
                                                        style=ft.ButtonStyle(bgcolor=ACCENT_ALT, color=TEXT),
                                                        on_click=self._use_current_pose_as_activation,
                                                    ),
                                                    ft.ElevatedButton(
                                                        "Clear activation gesture",
                                                        icon=ft.Icons.CLEAR,
                                                        on_click=self._clear_activation_gesture,
                                                    ),
                                                    ft.ElevatedButton(
                                                        "Open sound folder",
                                                        icon=ft.Icons.FOLDER_OPEN,
                                                        on_click=self._open_sound_folder,
                                                    ),
                                                ],
                                            ),
                                            ft.Text(
                                                "The activation gesture is stored as a regular trigger id, but it opens a short control session instead of calling an action directly.",
                                                color=MUTED,
                                                size=12,
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ),
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.ElevatedButton(
                                "Save settings",
                                icon=ft.Icons.SAVE,
                                style=ft.ButtonStyle(bgcolor=ACCENT, color=TEXT),
                                on_click=self._save_settings,
                            ),
                            ft.ElevatedButton(
                                "Reload from disk",
                                icon=ft.Icons.REFRESH,
                                on_click=self._reload_settings,
                            ),
                        ],
                    ),
                    self._status_control(),
                ],
            ),
        )

    def _build_debug_tab(self) -> ft.Control:
        return ft.Container(
            padding=20,
            content=ft.Column(
                expand=True,
                spacing=16,
                controls=[
                    ft.Text("Debug", size=24, weight=ft.FontWeight.W_700, color=TEXT),
                    ft.Text("Captured output from the Python processes goes here.", color=MUTED),
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.ElevatedButton("Refresh", icon=ft.Icons.REFRESH, on_click=self._refresh_debug_console),
                            ft.ElevatedButton("Copy all", icon=ft.Icons.CONTENT_COPY, on_click=self._copy_debug_console),
                            ft.Text(str(get_log_path()), color="#ffd6b2", selectable=True),
                        ],
                    ),
                    self.debug_console,
                ],
            ),
        )

    def _build_about_tab(self) -> ft.Control:
        logo_path = app_dir() / "logo.png"
        logo = ft.Image(src=str(logo_path.resolve()), width=164, height=164, fit=ft.BoxFit.CONTAIN) if logo_path.exists() else ft.Icon(ft.Icons.GESTURE, size=96, color=ACCENT)

        created_by_card = ft.Card(
            elevation=2,
            content=ft.Container(
                padding=30,
                content=ft.Column(
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Created by", size=18, weight=ft.FontWeight.W_700, color=TEXT, text_align=ft.TextAlign.CENTER),
                        ft.Text("Patryk Smolinski", size=24, weight=ft.FontWeight.W_700, color=ACCENT, text_align=ft.TextAlign.CENTER),
                        ft.ElevatedButton(
                            "Visit GitHub Profile",
                            icon=ft.Icons.OPEN_IN_NEW,
                            on_click=lambda _e: webbrowser.open("https://github.com/SmolinskiP"),
                        ),
                    ],
                ),
            ),
        )

        support_card = ft.Card(
            elevation=2,
            content=ft.Container(
                padding=30,
                content=ft.Column(
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Support the Project", size=18, weight=ft.FontWeight.W_700, color=TEXT, text_align=ft.TextAlign.CENTER),
                        ft.Text("Like my work? Buy me a coffee!", size=16, color=MUTED, text_align=ft.TextAlign.CENTER),
                        ft.ElevatedButton(
                            "Buy me a coffee",
                            icon=ft.Icons.FAVORITE,
                            style=ft.ButtonStyle(bgcolor=ACCENT, color=TEXT),
                            on_click=lambda _e: webbrowser.open("https://buymeacoffee.com/smolinskip"),
                        ),
                    ],
                ),
            ),
        )

        return ft.Container(
            expand=True,
            padding=24,
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=560,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=18,
                    controls=[
                        ft.Container(content=logo, padding=12),
                        ft.Text("HouSign", size=34, weight=ft.FontWeight.W_700, color=TEXT, text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            "Gesture control runtime for Home Assistant. MediaPipe for perception, Python for execution, Flet for configuration.",
                            color=MUTED,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        created_by_card,
                        support_card,
                    ],
                ),
            ),
        )

    def _build_binding_row(self, binding: GestureBinding, index: int) -> ft.Control:
        return ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.CLICK,
            on_tap=lambda _event, idx=index: self._load_binding(idx),
            content=ft.Container(
                padding=16,
                border_radius=16,
                border=ft.border.all(1, BORDER),
                bgcolor=CARD_BG_ALT,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Column(
                            spacing=6,
                            expand=True,
                            controls=[
                                ft.Text(binding.gesture_name, size=16, weight=ft.FontWeight.W_700, color=TEXT),
                                ft.Text(binding.trigger_id, size=12, color="#ffd6b2", selectable=True),
                                ft.Text(f"Mode: {binding.mode} | Action: {binding.action_name}", size=13, color=MUTED),
                                ft.Text("Tap to load this binding", size=11, color=ACCENT_ALT),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=DANGER,
                            tooltip="Remove binding",
                            on_click=lambda _event, idx=index: self._remove_binding(idx),
                        ),
                    ],
                ),
            ),
        )

    def _toggle_finger(self, owner: str, finger: str) -> None:
        hand = self.left_hand if owner == "left" else self.right_hand
        hand.toggle_finger(finger)  # type: ignore[arg-type]
        self._refresh_view()

    def _on_hand_tap(self, owner: str, event: ft.TapEvent) -> None:
        if event.local_position is None:
            return
        hand = self.left_hand if owner == "left" else self.right_hand
        finger = hit_test_finger(hand, event.local_position.x, event.local_position.y)
        if finger is None:
            return
        hand.toggle_finger(finger)
        self._refresh_view()

    def _set_palm(self, owner: str, palm: str) -> None:
        hand = self.left_hand if owner == "left" else self.right_hand
        hand.palm_side = palm  # type: ignore[assignment]
        self._refresh_view()

    def _set_rotation(self, owner: str, rotation: int) -> None:
        hand = self.left_hand if owner == "left" else self.right_hand
        hand.rotation_quadrant = rotation
        self._refresh_view()

    def _on_mode_change(self, event: ft.ControlEvent) -> None:
        self.mode = event.control.value
        _LOG.info("GUI gesture mode changed: %s", self.mode)
        self._refresh_view()

    def _on_selection_change(self, event: ft.ControlEvent) -> None:
        self.one_hand_selection = event.control.value
        _LOG.info("GUI active hand selected: %s", self.one_hand_selection)
        self._refresh_view()

    def _on_action_preset_change(self, event: ft.ControlEvent) -> None:
        preset_key = event.control.value or "placeholder"
        _LOG.info("GUI action preset selected: %s", preset_key)
        self._apply_action_preset(preset_key)

    def _on_action_type_change(self, _event: ft.ControlEvent) -> None:
        self._refresh_view()

    def _on_execution_mode_change(self, _event: ft.ControlEvent) -> None:
        self._refresh_view()

    def _on_listening_mode_change(self, _event: ft.ControlEvent) -> None:
        self._refresh_view()

    def _on_service_fields_changed(self, _event: ft.ControlEvent) -> None:
        self._refresh_view()

    def _use_current_pose_as_activation(self, _event: ft.ControlEvent) -> None:
        gesture_name, trigger_id, _frame = resolve_preview(
            self.left_hand,
            self.right_hand,
            self.mode,
            self.one_hand_selection,
            self.gestures_path,
        )
        self.activation_mode.value = self.mode
        self.activation_trigger_id.value = trigger_id
        self.activation_gesture_name.value = (self.binding_name.value or "").strip() or gesture_name
        self.status_message = "Current editor pose stored as activation gesture."
        _LOG.info("Activation gesture updated mode=%s trigger=%s", self.mode, trigger_id)
        self._refresh_view()

    def _clear_activation_gesture(self, _event: ft.ControlEvent) -> None:
        self.activation_trigger_id.value = ""
        self.activation_gesture_name.value = ""
        self.status_message = "Cleared activation gesture."
        _LOG.info("Activation gesture cleared.")
        self._refresh_view()

    def _open_sound_folder(self, _event: ft.ControlEvent) -> None:
        sound_dir = (Path(__file__).resolve().parent / "sound").resolve()
        try:
            os.startfile(str(sound_dir))
            self.status_message = f"Opened sound folder: {sound_dir}"
            _LOG.info("Opened sound folder: %s", sound_dir)
        except OSError as exc:
            self.status_message = f"Failed to open sound folder: {exc}"
            _LOG.error("Failed to open sound folder %s: %s", sound_dir, exc)
        self._refresh_view()

    def _apply_action_preset(self, preset_key: str, *, refresh: bool = True) -> None:
        preset = ACTION_PRESETS.get(preset_key, ACTION_PRESETS["placeholder"])
        existing_entity_id = (self.service_entity_id.value or "").strip()
        self.action_preset.value = preset_key
        self.action_type.value = str(preset.get("action_type", "placeholder"))
        self.execution_mode.value = str(preset.get("execution_mode", "instant"))
        self.cooldown_ms.value = str(preset.get("cooldown_ms", 800))
        self.repeat_every_ms.value = str(preset.get("repeat_every_ms", 150))
        self.service_domain.value = str(preset.get("domain", self.service_domain.value or ""))
        self.service_name.value = str(preset.get("service", self.service_name.value or ""))
        self.service_entity_id.value = existing_entity_id or str(preset.get("entity_id", ""))
        self.service_data.value = self._format_json_text(preset.get("service_data"))
        self.event_type.value = str(preset.get("event_type", self.event_type.value or ""))
        self.event_data.value = self._format_json_text(preset.get("event_data"))
        self.return_response.value = bool(preset.get("return_response", False))
        if refresh:
            self._refresh_view()

    @staticmethod
    def _format_json_text(value: object) -> str:
        if isinstance(value, dict) and value:
            import json

            return json.dumps(value, indent=2, ensure_ascii=False)
        return ""

    def _build_action_from_controls(self) -> GestureAction | None:
        action_type = (self.action_type.value or "placeholder").strip()
        if action_type == "placeholder":
            return GestureAction(type="placeholder", label=(self.binding_action.value or "").strip())

        if action_type == "service":
            domain = (self.service_domain.value or "").strip()
            service = (self.service_name.value or "").strip()
            if not domain or not service:
                self.status_message = "Service actions require both domain and service."
                return None
            service_data = self._parse_json_field(self.service_data, "Service data")
            if self.service_data.error_text is not None:
                return None
            entity_id = (self.service_entity_id.value or "").strip()
            target = {"entity_id": entity_id} if entity_id else None
            return GestureAction(
                type="service",
                label=(self.binding_action.value or "").strip(),
                domain=domain,
                service=service,
                target=target,
                data=service_data,
                return_response=bool(self.return_response.value),
            )

        if action_type == "event":
            event_type = (self.event_type.value or "").strip()
            if not event_type:
                self.status_message = "Event actions require event type."
                return None
            event_data = self._parse_json_field(self.event_data, "Event data")
            if self.event_data.error_text is not None:
                return None
            return GestureAction(
                type="event",
                label=(self.binding_action.value or "").strip(),
                event_type=event_type,
                event_data=event_data,
            )

        self.status_message = f"Unsupported action type: {action_type}"
        return None

    def _build_execution_from_controls(self) -> GestureExecution | None:
        try:
            cooldown_ms = int((self.cooldown_ms.value or "0").strip())
            repeat_every_ms = int((self.repeat_every_ms.value or "150").strip())
        except ValueError:
            self.status_message = "Execution values must be integers."
            return None

        return GestureExecution(
            mode=(self.execution_mode.value or "instant").strip(),
            cooldown_ms=cooldown_ms,
            repeat_every_ms=repeat_every_ms,
        )

    def _parse_json_field(self, field: ft.TextField, field_name: str) -> dict[str, object] | None:
        raw = (field.value or "").strip()
        if not raw:
            field.error_text = None
            return None

        import json

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            field.error_text = f"{field_name} must be valid JSON."
            self.status_message = f"{field_name} JSON error: {exc.msg}"
            self.page.update()
            return None

        if not isinstance(payload, dict):
            field.error_text = f"{field_name} must be a JSON object."
            self.status_message = f"{field_name} must be a JSON object."
            self.page.update()
            return None

        field.error_text = None
        return payload

    def _refresh_entity_dropdown(self) -> None:
        domain = (self.service_domain.value or "").strip()
        filtered = [entity for entity in self.ha_entities if not domain or entity["entity_id"].startswith(f"{domain}.")]
        self.entity_dropdown.options = [
            ft.dropdown.Option(entity["entity_id"], f'{entity["name"]} ({entity["entity_id"]})')
            for entity in filtered
        ]
        self.entity_dropdown.disabled = self.action_type.value != "service" or not bool(filtered)
        current = (self.service_entity_id.value or "").strip()
        if current and any(entity["entity_id"] == current for entity in filtered):
            self.entity_dropdown.value = current
        else:
            self.entity_dropdown.value = None

    def _on_entity_selected(self, event: ft.ControlEvent) -> None:
        selected = event.control.value or ""
        self.service_entity_id.value = selected
        self._refresh_view()

    def _load_entities_from_ha(self, url: str, token: str, *, announce_success: bool) -> bool:
        client = HomeAssistantWsClient(HomeAssistantConnectionSettings(url=url, token=token))
        try:
            client.connect()
            states = client.get_states()
            self.ha_entities = []
            for item in states:
                entity_id = str(item.get("entity_id", "")).strip()
                if not entity_id:
                    continue
                attributes = item.get("attributes")
                friendly_name = ""
                if isinstance(attributes, dict):
                    friendly_name = str(attributes.get("friendly_name", "")).strip()
                self.ha_entities.append(
                    {
                        "entity_id": entity_id,
                        "name": friendly_name or entity_id,
                    }
                )
            self.ha_entities.sort(key=lambda item: (item["entity_id"].split(".", 1)[0], item["name"].lower()))
            if announce_success:
                self.ha_connection_status.value = f"Connected successfully. Loaded {len(self.ha_entities)} entities."
                self.ha_connection_status.color = ACCENT_ALT
            _LOG.info("Home Assistant entity load succeeded. Entities: %s", len(self.ha_entities))
            return True
        except HomeAssistantWsError as exc:
            self.ha_connection_status.value = f"Home Assistant error: {exc}"
            self.ha_connection_status.color = DANGER
            _LOG.error("Home Assistant WebSocket error: %s", exc)
        except Exception as exc:
            self.ha_connection_status.value = f"Connection failed: {exc}"
            self.ha_connection_status.color = DANGER
            _LOG.exception("Unexpected Home Assistant connection failure.")
        finally:
            client.close()
        return False

    def _test_connection_and_load_entities(self, _event: ft.ControlEvent) -> None:
        url = (self.ha_url.value or "").strip()
        token = (self.ha_token.value or "").strip()
        if not url or not token:
            self.ha_connection_status.value = "Enter Home Assistant URL and token first."
            self.ha_connection_status.color = DANGER
            _LOG.warning("Home Assistant connection test aborted: missing URL or token.")
            self.page.update()
            return

        _LOG.info("Starting Home Assistant connection test for URL: %s", url)
        self._load_entities_from_ha(url, token, announce_success=True)
        self._load_debug_console()
        self._refresh_view()

    def post_mount(self) -> None:
        url = (self.ha_url.value or "").strip()
        token = (self.ha_token.value or "").strip()
        if not url or not token:
            return
        _LOG.info("Attempting automatic Home Assistant entity load on GUI startup.")
        if self._load_entities_from_ha(url, token, announce_success=False):
            self.ha_connection_status.value = f"Auto-loaded {len(self.ha_entities)} entities on startup."
            self.ha_connection_status.color = ACCENT_ALT
        self._load_debug_console()
        self._refresh_view()

    def _load_debug_console(self) -> None:
        log_path = get_log_path()
        if log_path.exists():
            self.debug_console.value = log_path.read_text(encoding="utf-8")
        else:
            self.debug_console.value = ""

    def _refresh_debug_console(self, _event: ft.ControlEvent | None = None) -> None:
        self._load_debug_console()
        self.status_message = f"Loaded debug log from {get_log_path()}"
        self._refresh_view()

    def _copy_debug_console(self, _event: ft.ControlEvent) -> None:
        pyperclip.copy(self.debug_console.value or "")
        self.status_message = "Copied debug console to clipboard."
        self._refresh_view()

    def _add_binding(self, _event: ft.ControlEvent) -> None:
        gesture_name, trigger_id, _frame = resolve_preview(
            self.left_hand,
            self.right_hand,
            self.mode,
            self.one_hand_selection,
            self.gestures_path,
        )
        action = self._build_action_from_controls()
        if action is None:
            self._refresh_view()
            return
        execution = self._build_execution_from_controls()
        if execution is None:
            self._refresh_view()
            return
        binding = GestureBinding(
            mode=self.mode,  # type: ignore[arg-type]
            trigger_id=trigger_id,
            gesture_name=(self.binding_name.value or "").strip() or gesture_name,
            action=action,
            execution=execution,
        )
        existing_index = next(
            (idx for idx, current in enumerate(self.bindings) if current.mode == binding.mode and current.trigger_id == binding.trigger_id),
            None,
        )
        if existing_index is None:
            self.bindings.append(binding)
            self.status_message = f"Saved new binding to {self.bindings_path}"
            _LOG.info("Saved new binding gesture=%s trigger=%s action=%s", binding.gesture_name, binding.trigger_id, binding.action_name)
        else:
            self.bindings[existing_index] = binding
            self.status_message = f"Updated binding in {self.bindings_path}"
            _LOG.info("Updated binding gesture=%s trigger=%s action=%s", binding.gesture_name, binding.trigger_id, binding.action_name)
        self._persist_bindings()
        self.binding_name.value = ""
        self.binding_action.value = ""
        self._refresh_view()

    def _remove_binding(self, index: int) -> None:
        _LOG.info("Removed binding gesture=%s trigger=%s", self.bindings[index].gesture_name, self.bindings[index].trigger_id)
        self.bindings.pop(index)
        self._persist_bindings()
        self.status_message = f"Removed binding and saved {self.bindings_path}"
        self._refresh_view()

    def _find_binding(self, trigger_id: str) -> GestureBinding | None:
        return find_binding(self.bindings, self.mode, trigger_id)

    def _load_bindings(self) -> None:
        try:
            self.bindings = load_bindings(self.bindings_path)
            if not self.bindings_path.exists():
                self.status_message = f"Bindings will be saved to {self.bindings_path}"
                return
            self.status_message = f"Loaded {len(self.bindings)} bindings from {self.bindings_path}"
        except Exception as exc:
            self.bindings = []
            self.status_message = f"Failed to load {self.bindings_path}: {exc}"

    def _persist_bindings(self) -> None:
        save_bindings(self.bindings_path, self.bindings)

    def _load_binding(self, index: int) -> None:
        binding = self.bindings[index]
        self.left_hand, self.right_hand, self.mode, self.one_hand_selection = editor_state_from_binding(binding)
        self.mode_selector.value = self.mode
        self.one_hand_dropdown.value = self.one_hand_selection
        self.binding_name.value = binding.gesture_name
        self.binding_action.value = binding.action.label
        self._load_action_controls_from_binding(binding)
        self.status_message = f"Loaded binding from {self.bindings_path}"
        _LOG.info("Loaded binding into editor gesture=%s trigger=%s", binding.gesture_name, binding.trigger_id)
        self._refresh_view()

    def _load_action_controls_from_binding(self, binding: GestureBinding) -> None:
        self.action_type.value = binding.action.type
        self.service_domain.value = binding.action.domain
        self.service_name.value = binding.action.service
        self.service_entity_id.value = str((binding.action.target or {}).get("entity_id", "")) if binding.action.target else ""
        self.service_data.value = self._format_json_text(binding.action.data)
        self.event_type.value = binding.action.event_type
        self.event_data.value = self._format_json_text(binding.action.event_data)
        self.return_response.value = binding.action.return_response
        self.execution_mode.value = binding.execution.mode
        self.cooldown_ms.value = str(binding.execution.cooldown_ms)
        self.repeat_every_ms.value = str(binding.execution.repeat_every_ms)
        self.action_preset.value = self._matching_preset_for_binding(binding)

    def _matching_preset_for_binding(self, binding: GestureBinding) -> str:
        for preset_key, preset in ACTION_PRESETS.items():
            if str(preset.get("action_type", "placeholder")) != binding.action.type:
                continue
            if binding.action.type == "service":
                if str(preset.get("domain", "")) != binding.action.domain:
                    continue
                if str(preset.get("service", "")) != binding.action.service:
                    continue
                preset_data = preset.get("service_data")
                if isinstance(preset_data, dict) and preset_data != (binding.action.data or {}):
                    continue
            elif binding.action.type == "event":
                if str(preset.get("event_type", "")) != binding.action.event_type:
                    continue
            if str(preset.get("execution_mode", "instant")) != binding.execution.mode:
                continue
            return preset_key
        return "custom_service" if binding.action.type == "service" else "custom_event" if binding.action.type == "event" else "placeholder"

    def _load_settings_into_controls(self) -> None:
        self.ha_url.value = self.settings.ha.url
        self.ha_token.value = self.settings.ha.token
        self.camera_index.value = str(self.settings.runtime.camera_index)
        self.model_path.value = self.settings.runtime.model_path
        self.gestures_config.value = self.settings.runtime.gestures_config
        self.bindings_config.value = self.settings.runtime.bindings_config
        self.print_every.value = str(self.settings.runtime.print_every)
        self.runtime_mirror.value = self.settings.runtime.mirror
        self.listening_mode.value = self.settings.recognition.listening_mode
        self.activation_mode.value = self.settings.recognition.activation_mode
        self.activation_trigger_id.value = self.settings.recognition.activation_trigger_id
        self.activation_gesture_name.value = self.settings.recognition.activation_gesture_name
        self.activation_hold_ms.value = str(self.settings.recognition.activation_hold_ms)
        self.session_timeout_ms.value = str(self.settings.recognition.session_timeout_ms)
        self.gesture_hold_ms.value = str(self.settings.recognition.gesture_hold_ms)
        self.gesture_gap_tolerance_ms.value = str(self.settings.recognition.gesture_gap_tolerance_ms)
        self.activation_sound_enabled.value = self.settings.recognition.activation_sound_enabled
        self.deactivation_sound_enabled.value = self.settings.recognition.deactivation_sound_enabled
        self.gesture_sound_enabled.value = self.settings.recognition.gesture_sound_enabled
        self.window_maximized.value = self.settings.gui.window_maximized

    def _reload_settings(self, _event: ft.ControlEvent) -> None:
        self.settings = load_settings(self.settings_path)
        self._load_settings_into_controls()
        self.gestures_path = str((app_dir() / self.settings.runtime.gestures_config).resolve())
        self.bindings_path = (app_dir() / self.settings.runtime.bindings_config).resolve()
        self._load_bindings()
        self.status_message = f"Reloaded settings from {self.settings_path}"
        self.post_mount()

    def _save_settings(self, _event: ft.ControlEvent) -> None:
        try:
            self.settings.ha.url = (self.ha_url.value or "").strip()
            self.settings.ha.token = (self.ha_token.value or "").strip()
            self.settings.runtime.camera_index = int((self.camera_index.value or "0").strip())
            self.settings.runtime.model_path = (self.model_path.value or "").strip() or "models/hand_landmarker.task"
            self.settings.runtime.gestures_config = (self.gestures_config.value or "").strip() or "gestures.yaml"
            self.settings.runtime.bindings_config = (self.bindings_config.value or "").strip() or "gesture_bindings.json"
            self.settings.runtime.print_every = int((self.print_every.value or "10").strip())
            self.settings.runtime.mirror = bool(self.runtime_mirror.value)
            self.settings.recognition.listening_mode = (self.listening_mode.value or "always_listening").strip()
            self.settings.recognition.activation_mode = (self.activation_mode.value or "one_hand").strip()
            self.settings.recognition.activation_trigger_id = (self.activation_trigger_id.value or "").strip()
            self.settings.recognition.activation_gesture_name = (self.activation_gesture_name.value or "").strip()
            self.settings.recognition.activation_hold_ms = int((self.activation_hold_ms.value or "600").strip())
            self.settings.recognition.session_timeout_ms = int((self.session_timeout_ms.value or "4000").strip())
            self.settings.recognition.gesture_hold_ms = int((self.gesture_hold_ms.value or "140").strip())
            self.settings.recognition.gesture_gap_tolerance_ms = int((self.gesture_gap_tolerance_ms.value or "100").strip())
            self.settings.recognition.activation_sound_enabled = bool(self.activation_sound_enabled.value)
            self.settings.recognition.deactivation_sound_enabled = bool(self.deactivation_sound_enabled.value)
            self.settings.recognition.gesture_sound_enabled = bool(self.gesture_sound_enabled.value)
            self.settings.gui.window_maximized = bool(self.window_maximized.value)
        except ValueError as exc:
            self.status_message = f"Invalid settings value: {exc}"
            self._refresh_view()
            return

        from .settings_store import save_settings

        save_settings(self.settings, self.settings_path)
        self.gestures_path = str((app_dir() / self.settings.runtime.gestures_config).resolve())
        self.bindings_path = (app_dir() / self.settings.runtime.bindings_config).resolve()
        self._load_bindings()
        self.status_message = f"Saved settings to {self.settings_path}"
        _LOG.info("Saved settings to %s", self.settings_path)
        if self.settings.ha.url and self.settings.ha.token:
            self.post_mount()
            return
        self._refresh_view()

    def _status_control(self) -> ft.Control:
        return ft.Text(self.storage_status_value, color=MUTED, size=12)


def main(page: ft.Page) -> None:
    studio = GestureStudio(page)
    root = studio.build()
    page.add(root)
    studio._refresh_view()
    studio.post_mount()


if __name__ == "__main__":
    from .log_capture import configure_process_logging

    configure_process_logging("gui")
    ft.app(target=main, view=ft.AppView.FLET_APP)
