from __future__ import annotations

from typing import Any

from .config_pattern import ConfigPatternError, parse_config_pattern, validate_config_name
from .validation_helpers import issue

_SCALAR_TYPES = {"string", "integer", "number", "boolean"}


def validate_config_spec(spec: dict[str, Any], selection: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    """Validate the authoring shape without matching device configuration text."""
    root = spec.get("config") or {}
    _validate_commands(root.get("commands", []), "spec.config.commands", selection, issues)


def config_root_names(spec: dict[str, Any]) -> set[str]:
    return {str(command.get("name", "")) for command in (spec.get("config") or {}).get("commands", []) if command.get("name")}


def _validate_commands(commands: list[dict[str, Any]], path: str, selection: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for index, command in enumerate(commands):
        name = str(command.get("name", ""))
        command_path = f"{path}[{index}]"
        command_selection = {**selection, "itemId": name, "field": f"{command_path}.name"}
        try:
            validate_config_name(name)
        except ConfigPatternError as exc:
            issues.append(issue(exc.code, "error", exc.message, command_selection))
        if name in seen:
            issues.append(issue("CONFIG_COMMAND_NAME_DUPLICATE", "error", f"同一层级的配置命令名称“{name}”重复。", command_selection))
        seen.add(name)

        pattern = str(command.get("pattern", ""))
        try:
            parsed = parse_config_pattern(pattern)
        except ConfigPatternError as exc:
            issues.append(issue(exc.code, "error", exc.message, {**command_selection, "field": f"{command_path}.pattern"}))
            parsed = None

        captures = command.get("captures") or {}
        for capture_name in captures:
            try:
                validate_config_name(capture_name, label="捕获名称")
            except ConfigPatternError as exc:
                issues.append(issue(exc.code, "error", exc.message, {**command_selection, "field": f"{command_path}.captures.{capture_name}"}))
            schema = captures[capture_name]
            if schema.get("type") not in _SCALAR_TYPES:
                issues.append(
                    issue(
                        "CONFIG_CAPTURE_SCHEMA_NOT_SCALAR",
                        "error",
                        "配置捕获字段只支持 string、integer、number、boolean。",
                        {**command_selection, "field": f"{command_path}.captures.{capture_name}"},
                    )
                )
        if parsed is not None:
            expected = set(parsed.names)
            actual = set(captures)
            if expected != actual:
                issues.append(
                    issue(
                        "CONFIG_CAPTURE_SCHEMA_MISMATCH",
                        "error",
                        "配置命令模板中的捕获名称必须与 captures map 完全一致。",
                        {**command_selection, "field": f"{command_path}.captures"},
                    )
                )

        children = command.get("children", [])
        child_names = [str(item.get("name", "")) for item in children]
        capture_names = set(captures)
        for child_name in child_names:
            if child_name in capture_names:
                issues.append(
                    issue(
                        "CONFIG_COMMAND_PROPERTY_CONFLICT",
                        "error",
                        f"配置命令“{name}”的捕获字段与子命令“{child_name}”重名。",
                        {**command_selection, "field": f"{command_path}.children"},
                    )
                )
        _validate_commands(children, f"{command_path}.children", selection, issues)


__all__ = ["config_root_names", "validate_config_spec"]
