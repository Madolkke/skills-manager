from __future__ import annotations

from typing import Any


def schema_title(field: dict[str, Any]) -> str:
    return str(field.get("schema", {}).get("title") or field.get("key") or "未命名字段")


def schemas_assignable(source: dict[str, Any], target: dict[str, Any]) -> bool:
    source_type, target_type = source.get("type"), target.get("type")
    if source_type is None or target_type is None:
        return True
    if source_type != target_type and not (source_type == "integer" and target_type == "number"):
        return False
    if source_type == "array":
        return schemas_assignable(source.get("items", {}), target.get("items", {}))
    if source_type != "object":
        return True
    source_properties = source.get("properties", {})
    target_properties = target.get("properties", {})
    for key in target.get("required", []):
        if key not in source_properties or key not in target_properties:
            return False
        if not schemas_assignable(source_properties[key], target_properties[key]):
            return False
    return all(key not in source_properties or schemas_assignable(source_properties[key], child) for key, child in target_properties.items())


def value_matches_schema(value: Any, schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if schema_type is None:
        return True
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "array":
        return isinstance(value, list) and all(value_matches_schema(item, schema.get("items", {})) for item in value)
    if schema_type != "object" or not isinstance(value, dict):
        return False
    properties = schema.get("properties", {})
    if any(key not in value for key in schema.get("required", [])):
        return False
    if schema.get("additionalProperties") is False and any(key not in properties for key in value):
        return False
    return all(key not in value or value_matches_schema(value[key], child) for key, child in properties.items())


def has_legacy_schema(schema: dict[str, Any]) -> bool:
    if schema.get("x-skillhub-legacy-loose"):
        return True
    if schema.get("type") == "object":
        return any(has_legacy_schema(child) for child in schema.get("properties", {}).values())
    if schema.get("type") == "array":
        return has_legacy_schema(schema.get("items", {}))
    return False
