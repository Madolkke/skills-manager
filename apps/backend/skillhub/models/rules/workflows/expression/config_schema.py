from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def command_expression_schema(command: Mapping[str, Any]) -> dict[str, Any]:
    """Project one Config command into the expression JSON Schema subset."""
    properties = {
        str(name): schema
        for name, schema in (command.get("captures") or {}).items()
    }
    properties.update(
        {
            str(child["name"]): command_expression_schema(child)
            for child in command.get("children", [])
        }
    )
    title = str(command.get("name", ""))
    object_schema: dict[str, Any] = {
        "type": "object",
        "title": title,
        "description": "",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }
    if command.get("unique") is False:
        return {
            "type": "array",
            "title": title,
            "description": "",
            "items": object_schema,
        }
    return {
        **object_schema,
        "type": ["object", "null"],
    }


__all__ = ["command_expression_schema"]
