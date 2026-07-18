from __future__ import annotations

import re
from typing import Any

from skillhub.models.errors import InvariantError

AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
SUPPORTED_AGENT_TOOLS = ("bash", "edit", "glob", "grep", "list", "read", "write")


def normalize_agent_id(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise InvariantError("Agent id is required.")
    if len(clean) > 80:
        raise InvariantError("Agent id must be 80 characters or fewer.")
    if not AGENT_ID_PATTERN.fullmatch(clean):
        raise InvariantError("Agent id may only contain letters, numbers, '_' or '-'.")
    return clean


def normalize_agent_name(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise InvariantError("Agent name is required.")
    if len(clean) > 120:
        raise InvariantError("Agent name must be 120 characters or fewer.")
    return clean


def normalize_agent_description(value: str | None) -> str:
    clean = (value or "").strip()
    if len(clean) > 1000:
        raise InvariantError("Agent description must be 1000 characters or fewer.")
    return clean


def normalize_agent_prompt(value: str) -> str:
    clean = value.strip()
    if not clean:
        raise InvariantError("Agent prompt is required.")
    if len(clean) > 20000:
        raise InvariantError("Agent prompt must be 20000 characters or fewer.")
    return clean


def normalize_agent_permission(value: Any) -> dict[str, bool]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise InvariantError("Agent permission must be an object.")
    unsupported = sorted(str(key) for key in value if key not in SUPPORTED_AGENT_TOOLS)
    if unsupported:
        raise InvariantError(f"Unsupported Agent permission tools: {', '.join(unsupported)}")
    return {tool: bool(value.get(tool, False)) for tool in SUPPORTED_AGENT_TOOLS}


def normalize_agent_optional_text(value: str | None, *, label: str, max_length: int = 120) -> str | None:
    clean = (value or "").strip()
    if not clean:
        return None
    if len(clean) > max_length:
        raise InvariantError(f"{label} must be {max_length} characters or fewer.")
    return clean


def normalize_agent_temperature(value: str | int | float | None) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvariantError("Agent temperature must be a number.") from exc
    if number < 0 or number > 2:
        raise InvariantError("Agent temperature must be between 0 and 2.")
    return str(number).rstrip("0").rstrip(".")


def normalize_agent_steps(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise InvariantError("Agent steps must be an array.")
    steps: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            if len(text) > 500:
                raise InvariantError("Each Agent step must be 500 characters or fewer.")
            steps.append(text)
    if len(steps) > 20:
        raise InvariantError("Agent steps must contain 20 items or fewer.")
    return steps
