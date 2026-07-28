from __future__ import annotations

import copy
from typing import Any


def workflow_uses_v3_fields(value: dict[str, Any]) -> bool:
    workflow = value.get("workflow", {})
    fields = list(workflow.get("inputs", []))
    for definition in value.get("collectionSnapshots", []):
        fields.extend(definition.get("inputs", []))
        fields.extend(definition.get("outputs", []))
    return any("schema" not in item for item in fields)


def migrate_workflow_v3(value: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(value)
    workflow = migrated.get("workflow", {})
    workflow["inputs"] = [migrate_parameter_v3(item) if "schema" not in item else item for item in workflow.get("inputs", [])]
    migrated["collectionSnapshots"] = [migrate_collection_v3(item) for item in migrated.get("collectionSnapshots", [])]
    return migrated


def migrate_collection_v3(value: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(value)
    migrated["inputs"] = [migrate_parameter_v3(item) if "schema" not in item else item for item in migrated.get("inputs", [])]
    migrated["outputs"] = [migrate_output_v3(item) if "schema" not in item else item for item in migrated.get("outputs", [])]
    return migrated


def migrate_parameter_v3(value: dict[str, Any]) -> dict[str, Any]:
    migrated = {
        "id": value.get("id", ""),
        "key": value.get("key", ""),
        "required": bool(value.get("required", True)),
        "schema": legacy_schema(value.get("dataType", "string"), value.get("name", ""), value.get("description", "")),
    }
    migrated.update({key: item for key, item in value.items() if key not in {"id", "key", "required", "name", "description", "dataType"}})
    return migrated


def migrate_output_v3(value: dict[str, Any]) -> dict[str, Any]:
    migrated = {
        "id": value.get("id", ""),
        "key": value.get("key", ""),
        "required": False,
        "schema": legacy_schema(value.get("dataType", "string"), value.get("key", ""), value.get("description", "")),
    }
    migrated.update({key: item for key, item in value.items() if key not in {"id", "key", "description", "dataType"}})
    return migrated


def legacy_schema(data_type: Any, title: Any, description: Any) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": data_type if data_type in {"string", "integer", "number", "boolean", "array", "object"} else "string",
        "title": str(title),
        "description": str(description),
    }
    if schema["type"] == "array":
        schema.update({"items": {"x-skillhub-legacy-loose": True}, "x-skillhub-legacy-loose": True})
    elif schema["type"] == "object":
        schema.update({"properties": {}, "required": [], "additionalProperties": True, "x-skillhub-legacy-loose": True})
    return schema
