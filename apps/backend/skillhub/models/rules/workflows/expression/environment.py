from __future__ import annotations

import keyword
import re
from typing import Any

from .types import TypeSpec, array, from_json_schema, object_type

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_expression_identifier(value: str) -> bool:
    """Return whether a key can be addressed through Python attribute syntax."""
    return bool(_IDENTIFIER.fullmatch(value)) and not keyword.iskeyword(value)


def normalize_expression_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy output field maps and the v2 explicit call structure."""
    outputs: dict[str, dict[str, Any]] = {}
    for key, value in environment.get("outputs", {}).items():
        if isinstance(value, dict) and "sampleCount" in value and "fields" in value:
            sample_count = int(value["sampleCount"])
            fields = dict(value["fields"])
        else:
            sample_count = 1
            fields = dict(value)
        outputs[str(key)] = {"sampleCount": sample_count, "fields": fields}
    return {"inputs": dict(environment.get("inputs", {})), "outputs": outputs}


def expression_root_types(environment: dict[str, Any]) -> dict[str, TypeSpec]:
    """Build checker root types while retaining fixed collection sample counts."""
    normalized = normalize_expression_environment(environment)
    output_types: dict[str, TypeSpec] = {}
    for call_key, value in normalized["outputs"].items():
        fields = object_type({key: from_json_schema(schema) for key, schema in value["fields"].items()})
        sample_count = int(value["sampleCount"])
        output_types[call_key] = (
            object_type(fields.properties, sample_count=1)
            if sample_count == 1
            else array(fields, sample_count=sample_count)
        )
    return {
        "inputs": object_type({key: from_json_schema(value) for key, value in normalized["inputs"].items()}),
        "outputs": object_type(output_types),
    }


def workflow_expression_environment(document: dict[str, Any]) -> dict[str, Any]:
    """Project a normalized Workflow document into the public expression environment."""
    workflow = document["workflow"]
    definitions = {
        (item["id"], item["revision"]): item
        for item in document.get("collectionSnapshots", [])
    }
    outputs: dict[str, dict[str, Any]] = {}
    for step in workflow["nodes"]:
        if "stepType" not in step:
            continue
        for call in step["collectionCalls"]:
            call_key = call["key"].strip()
            definition = definitions.get((call["definition"]["id"], call["definition"]["revision"]))
            if not call_key or definition is None or call_key in outputs:
                continue
            fields = {
                item["key"].strip(): item["schema"]
                for item in definition["outputs"]
                if item["key"].strip()
            }
            outputs[call_key] = {
                "sampleCount": max(int(call["sampleCount"]), 1),
                "fields": fields,
            }
    return {
        "inputs": {
            item["key"].strip(): item["schema"]
            for item in workflow["inputs"]
            if item["key"].strip()
        },
        "outputs": outputs,
    }
