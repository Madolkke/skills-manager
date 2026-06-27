from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError


def positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InvariantError(f"{field} must be a positive integer.") from exc
    if parsed < 1:
        raise InvariantError(f"{field} must be a positive integer.")
    return parsed


def non_negative_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InvariantError(f"{field} must be a non-negative integer.") from exc
    if parsed < 0:
        raise InvariantError(f"{field} must be a non-negative integer.")
    return parsed


def number(value: Any, field: str) -> int | float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise InvariantError(f"{field} must be a number.") from exc
    return int(parsed) if parsed.is_integer() else parsed


def percent_ratio(value: Any, field: str) -> float:
    parsed = float(number(value, field))
    if parsed < 0 or parsed > 100:
        raise InvariantError(f"{field} must be between 0 and 100.")
    return parsed / 100
