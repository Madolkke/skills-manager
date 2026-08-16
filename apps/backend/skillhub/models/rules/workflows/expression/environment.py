from __future__ import annotations

import keyword
from typing import Any

from .types import TypeSpec, array, from_json_schema, object_type


def is_expression_identifier(value: str) -> bool:
    """Return whether a key can be addressed through Python attribute syntax."""
    return value.isidentifier() and not keyword.iskeyword(value)


def normalize_expression_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy output field maps and the v2 explicit call structure."""
    outputs: dict[str, dict[str, Any]] = {}
    for key, value in environment.get("outputs", {}).items():
        if isinstance(value, dict) and "sampleCount" in value and ("fields" in value or "schema" in value):
            sample_count = int(value["sampleCount"])
            fields = dict(value.get("fields", {}))
            schema = value.get("schema")
        else:
            sample_count = 1
            fields = dict(value)
            schema = None
        normalized = {"sampleCount": sample_count, "fields": fields}
        if schema is not None:
            normalized["schema"] = schema
        outputs[str(key)] = normalized
    return {
        "inputs": dict(environment.get("inputs", {})),
        "outputs": outputs,
        "config": dict(environment.get("config", {})),
    }


def expression_root_types(environment: dict[str, Any]) -> dict[str, TypeSpec]:
    """Build checker root types while retaining fixed collection sample counts."""
    normalized = normalize_expression_environment(environment)
    output_types: dict[str, TypeSpec] = {}
    for call_key, value in normalized["outputs"].items():
        sample_count = int(value["sampleCount"])
        if value.get("schema") is not None:
            output_type = from_json_schema(value["schema"])
            output_types[call_key] = output_type if sample_count == 1 else array(output_type, sample_count=sample_count)
            continue
        fields = object_type({key: from_json_schema(schema) for key, schema in value["fields"].items()})
        output_types[call_key] = object_type(fields.properties, sample_count=1) if sample_count == 1 else array(fields, sample_count=sample_count)
    return {
        "inputs": object_type({key: from_json_schema(value) for key, value in normalized["inputs"].items()}),
        "outputs": object_type(output_types),
        "config": object_type({key: from_json_schema(value) for key, value in normalized["config"].items()}),
    }


def workflow_expression_environment(document: dict[str, Any]) -> dict[str, Any]:
    """Project a document into a compatibility environment for public tooling."""
    workflow = document["workflow"]
    definitions = {(item["id"], item["revision"]): item for item in document.get("collectionSnapshots", [])}
    outputs: dict[str, dict[str, Any]] = {}
    input_keys = {item["key"].strip() for item in workflow["inputs"] if item["key"].strip()}
    direct_candidates: dict[str, dict[str, Any] | None] = {}
    for step in workflow["nodes"]:
        if "stepType" not in step:
            continue
        for call in step["collectionCalls"]:
            call_key = call["key"].strip()
            definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
            if definition is None:
                continue
            sample_count = max(int(call["sampleCount"]), 1)
            if not call_key:
                for item in definition["outputs"]:
                    output_key = item["key"].strip()
                    if not is_expression_identifier(output_key) or output_key in input_keys:
                        continue
                    if output_key in direct_candidates:
                        direct_candidates[output_key] = None
                    else:
                        direct_candidates[output_key] = {"sampleCount": sample_count, "fields": {}, "schema": item["schema"]}
                continue
            fields = {item["key"].strip(): item["schema"] for item in definition["outputs"] if item["key"].strip()}
            outputs.setdefault(call_key, {"sampleCount": sample_count, "fields": fields})
    for output_key, value in direct_candidates.items():
        if value is not None and output_key not in outputs:
            outputs[output_key] = value
    return {
        "inputs": {item["key"].strip(): item["schema"] for item in workflow["inputs"] if item["key"].strip()},
        "outputs": outputs,
        "config": {},
    }
