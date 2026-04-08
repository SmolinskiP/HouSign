from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GestureRule:
    key: str
    kind: str = "hand"
    priority: int = 0
    name: str | None = None
    alias_template: str | None = None
    match: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GestureConfig:
    gestures: list[GestureRule] = field(default_factory=list)


def load_gesture_config(path: str | Path | None) -> GestureConfig:
    if path is None:
        return GestureConfig()

    config_path = Path(path)
    if not config_path.exists():
        return GestureConfig()

    data = _parse_yaml_subset(config_path.read_text(encoding="utf-8"))
    gestures = [
        GestureRule(
            key=str(item["key"]),
            kind=str(item.get("kind", "hand")),
            priority=int(item.get("priority", 0)),
            name=item.get("name"),
            alias_template=item.get("alias_template"),
            match=dict(item.get("match", {})),
        )
        for item in data.get("gestures", [])
    ]
    return GestureConfig(gestures=gestures)


def _parse_yaml_subset(text: str) -> dict[str, Any]:
    lines = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line.strip()))

    index = 0

    def parse_block(expected_indent: int):
        nonlocal index
        if index >= len(lines) or lines[index][0] < expected_indent:
            return None
        if lines[index][1].startswith("- "):
            return parse_list(expected_indent)
        return parse_mapping(expected_indent)

    def parse_list(expected_indent: int):
        nonlocal index
        items: list[Any] = []
        while index < len(lines):
            indent, content = lines[index]
            if indent < expected_indent or not content.startswith("- "):
                break

            item_content = content[2:].strip()
            index += 1

            if not item_content:
                items.append(parse_block(expected_indent + 2))
                continue

            if ":" not in item_content:
                items.append(_parse_scalar(item_content))
                continue

            key, value = _split_key_value(item_content)
            item: dict[str, Any] = {}
            if value is None:
                item[key] = parse_block(expected_indent + 2)
            else:
                item[key] = _parse_scalar(value)

            while index < len(lines):
                next_indent, next_content = lines[index]
                if next_indent < expected_indent + 2:
                    break
                if next_indent == expected_indent and next_content.startswith("- "):
                    break
                if next_indent == expected_indent + 2:
                    child_key, child_value = _split_key_value(next_content)
                    index += 1
                    if child_value is None:
                        item[child_key] = parse_block(expected_indent + 4)
                    else:
                        item[child_key] = _parse_scalar(child_value)
                    continue
                break

            items.append(item)
        return items

    def parse_mapping(expected_indent: int):
        nonlocal index
        mapping: dict[str, Any] = {}
        while index < len(lines):
            indent, content = lines[index]
            if indent < expected_indent or content.startswith("- "):
                break
            if indent != expected_indent:
                break

            key, value = _split_key_value(content)
            index += 1
            if value is None:
                mapping[key] = parse_block(expected_indent + 2)
            else:
                mapping[key] = _parse_scalar(value)
        return mapping

    parsed = parse_block(0)
    return parsed if isinstance(parsed, dict) else {}


def _split_key_value(content: str) -> tuple[str, str | None]:
    key, _, value = content.partition(":")
    key = key.strip()
    value = value.strip()
    return key, value or None


def _parse_scalar(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]

    if value.startswith(('"', "'")) and value.endswith(('"', "'")):
        return value[1:-1]

    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    try:
        return float(value)
    except ValueError:
        pass

    lowered = value.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    return value
