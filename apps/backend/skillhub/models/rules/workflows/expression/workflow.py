from __future__ import annotations

from typing import Any

from .checker import validate_expression
from .config_schema import command_expression_schema

_BLOCKING_CODES = {"CONFIG_STRING_SUBSCRIPT_FORBIDDEN", "CONFIG_ARRAY_INDEX_INVALID"}


def config_expression_issues(source: str, environment: dict[str, Any]) -> list[dict[str, Any]]:
    """Return config path diagnostics that must block Workflow synchronization."""
    if not source.strip():
        return []
    result = validate_expression(source, environment)
    return [item for item in result["diagnostics"] if item.get("code") in _BLOCKING_CODES]


__all__ = ["command_expression_schema", "config_expression_issues"]
