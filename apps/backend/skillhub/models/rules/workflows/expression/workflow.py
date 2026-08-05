from __future__ import annotations

from typing import Any

from .checker import validate_expression

_BLOCKING_CODES = {"CONFIG_STRING_SUBSCRIPT_FORBIDDEN", "CONFIG_ARRAY_INDEX_INVALID"}


def config_expression_issues(source: str, environment: dict[str, Any]) -> list[dict[str, Any]]:
    """Return config path diagnostics that must block Workflow synchronization."""
    if not source.strip():
        return []
    result = validate_expression(source, environment)
    return [item for item in result["diagnostics"] if item.get("code") in _BLOCKING_CODES]


def command_expression_schema(command: dict[str, Any]) -> dict[str, Any]:
    """Project one Config command into the expression JSON Schema subset."""
    properties = {name: schema for name, schema in (command.get("captures") or {}).items()}
    properties.update({child["name"]: command_expression_schema(child) for child in command.get("children", [])})
    object_schema = {
        "type": "object",
        "title": command.get("name", ""),
        "description": "",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    if command.get("unique") is False:
        return {"type": "array", "title": command.get("name", ""), "description": "", "items": object_schema}
    return {
        "type": ["object", "null"],
        "title": command.get("name", ""),
        "description": "",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


__all__ = ["command_expression_schema", "config_expression_issues"]
