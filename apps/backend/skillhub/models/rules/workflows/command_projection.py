"""系统命令来源到采集快照的纯投影。"""
from collections.abc import Mapping
from typing import Any

from skillhub.models.errors import InvariantError


def _source_to_collection(source: Any, *, definition_id: str, revision: int, source_id: str) -> dict[str, Any]:
    from skillhub.models.rules.workflows import normalize_collection_definition

    document = dict(source.document or {})
    metadata = dict(document.get("metadata") or source.metadata_json or {})
    metadata.setdefault("name", source.name)
    metadata.setdefault("description", source.description)
    metadata.setdefault("industry", "")
    metadata.setdefault("device", "")
    metadata.setdefault("versions", [])
    metadata.setdefault("tags", [])
    captures = source.captures or {}
    inputs = []
    for name, value in sorted(captures.items()):
        repeated = isinstance(value, Mapping) and bool(value.get("repeated"))
        input_schema: dict[str, Any] = {
            "type": "array",
            "title": f"{name} 列表",
            "description": "",
            "items": {"type": "string", "title": str(name), "description": ""},
        } if repeated else {"type": "string", "title": str(name), "description": ""}
        inputs.append(
            {
                "id": f"input_{name}",
                "key": name,
                "required": not bool(value.get("optional", False)) if isinstance(value, Mapping) else True,
                "schema": input_schema,
            }
        )
    output_schema = document.get("outputSchema") or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    if not isinstance(output_schema, Mapping) or output_schema.get("type") != "object":
        raise InvariantError("System command root output schema must be an object.")
    properties = output_schema.get("properties")
    if not isinstance(properties, Mapping):
        raise InvariantError("System command root output schema requires properties.")
    raw_required = output_schema.get("required", [])
    if not isinstance(raw_required, list) or any(not isinstance(name, str) for name in raw_required):
        raise InvariantError("System command root output schema requires a string required list.")
    required = set(raw_required)
    outputs = [
        {"id": f"output_{name}", "key": name, "required": name in required, "schema": _workflow_schema(schema, fallback_title=str(name))}
        for name, schema in sorted(properties.items())
    ]
    return normalize_collection_definition(
        {
            "id": definition_id,
            "revision": revision,
            "key": source.key,
            "metadata": metadata,
            "spec": {
                "collectionType": "cli",
                "commandTemplate": source.expression,
                "outputSamples": [
                    {
                        "id": item.get("id") or f"sample_{source.id}_{index}",
                        "name": item.get("name", "示例"),
                        "stdout": item.get("stdout", ""),
                        "inputValues": {},
                    }
                    for index, item in enumerate(document.get("samples", []), start=1)
                ],
            },
            "inputs": inputs,
            "outputs": outputs,
            "sourceSystemCommandId": source_id,
        }
    )


def _workflow_schema(value: Any, *, fallback_title: str = "") -> dict[str, Any]:
    """Adapt standard JSON Schema fragments to the strict Workflow schema shape."""
    source = dict(value) if isinstance(value, Mapping) else {"x-skillhub-legacy-loose": True}
    result = {
        "title": str(source.get("title") or fallback_title),
        "description": str(source.get("description", "")),
    }
    schema_type = source.get("type")
    if schema_type == "object":
        properties = source.get("properties")
        if not isinstance(properties, Mapping):
            raise InvariantError("Object output schema requires properties.")
        additional_properties = bool(source.get("additionalProperties", False))
        result.update(
            {
                "type": "object",
                "properties": {
                    str(name): _workflow_schema(child, fallback_title=str(name))
                    for name, child in properties.items()
                },
                "required": [str(name) for name in source.get("required", [])],
                "additionalProperties": additional_properties,
            }
        )
        if additional_properties:
            result["x-skillhub-legacy-loose"] = True
        return result
    if schema_type == "array":
        if "items" not in source:
            raise InvariantError("Array output schema requires items.")
        result.update({"type": "array", "items": _workflow_schema(source["items"], fallback_title=fallback_title)})
        return result
    if schema_type in {"string", "integer", "number", "boolean"}:
        result["type"] = schema_type
        return result
    result["x-skillhub-legacy-loose"] = True
    return result
