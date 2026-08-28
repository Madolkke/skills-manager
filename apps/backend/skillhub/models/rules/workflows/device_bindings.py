from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, NamedTuple

from .expression.environment import is_device_expression_identifier, is_projectable_device_schema

DeviceBindingStatus = Literal["ok", "role_missing", "path_invalid"]


class DeviceBindingResolution(NamedTuple):
    status: DeviceBindingStatus
    role: Mapping[str, Any] | None = None
    schema: Mapping[str, Any] | None = None


def resolve_device_role_field(
    roles: Sequence[Mapping[str, Any]],
    role_id: str,
    path: str,
) -> DeviceBindingResolution:
    """Resolve a dot path without traversing or selecting array schemas."""
    role = next((item for item in roles if str(item.get("id", "")) == role_id), None)
    if role is None:
        return DeviceBindingResolution("role_missing")
    schema = role.get("schema")
    parts = path.split(".") if path else []
    if (
        not is_device_expression_identifier(str(role.get("key", "")).strip())
        or not is_projectable_device_schema(schema)
        or not parts
        or any(not is_device_expression_identifier(part) for part in parts)
    ):
        return DeviceBindingResolution("path_invalid", role)
    current = schema
    for part in parts:
        if not isinstance(current, Mapping) or current.get("type") != "object":
            return DeviceBindingResolution("path_invalid", role)
        properties = current.get("properties")
        if not isinstance(properties, Mapping) or part not in properties:
            return DeviceBindingResolution("path_invalid", role)
        current = properties[part]
    if not isinstance(current, Mapping) or current.get("type") == "array":
        return DeviceBindingResolution("path_invalid", role)
    return DeviceBindingResolution("ok", role, current)
