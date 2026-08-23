from __future__ import annotations

import keyword
from collections import deque
from collections.abc import Mapping, Sequence
from typing import Any

from .config_schema import command_expression_schema
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
        "topo": {
            "devices": dict(environment.get("topo", {}).get("devices", {}))
            if isinstance(environment.get("topo", {}), Mapping)
            else {}
        },
    }


def expression_scope_steps(
    steps: Sequence[Mapping[str, Any]],
    source_step_id: str | None = None,
) -> list[Mapping[str, Any]]:
    """Return the current step and its transitive graph predecessors.

    Collection output availability follows the workflow graph rather than the
    order in which nodes happen to be stored in the document.  A reverse BFS
    keeps the helper cycle-safe and the final document-order sort makes
    first-wins projections deterministic.
    """
    step_list = [step for step in steps if "stepType" in step and step.get("id")]
    if source_step_id is None:
        return step_list
    by_id = {str(step["id"]): step for step in step_list}
    source_id = str(source_step_id)
    if source_id not in by_id:
        return []
    predecessors: dict[str, set[str]] = {step_id: set() for step_id in by_id}
    for step in step_list:
        step_id = str(step["id"])
        for transition in step.get("topology", []):
            target = transition.get("target", {})
            target_id = target.get("id") if isinstance(target, Mapping) else None
            if target_id in by_id:
                predecessors[str(target_id)].add(step_id)
    visible = {source_id}
    queue = deque([source_id])
    while queue:
        current = queue.popleft()
        for predecessor in predecessors.get(current, set()):
            if predecessor in visible:
                continue
            visible.add(predecessor)
            queue.append(predecessor)
    return [step for step in step_list if str(step["id"]) in visible]


def conclusion_scope_steps(
    nodes: Sequence[Mapping[str, Any]],
    conclusion_id: str,
) -> list[Mapping[str, Any]]:
    """Return steps that can reach a conclusion through workflow topology."""
    steps = [node for node in nodes if "stepType" in node and node.get("id")]
    node_ids = {str(node.get("id")) for node in nodes}
    target_id = str(conclusion_id)
    if target_id not in node_ids:
        return []
    visible: set[str] = set()
    queue = deque([target_id])
    while queue:
        current = queue.popleft()
        for step in steps:
            step_id = str(step["id"])
            if step_id in visible:
                continue
            if any(
                isinstance(transition.get("target"), Mapping)
                and str(transition["target"].get("id")) == current
                for transition in step.get("topology", [])
            ):
                visible.add(step_id)
                queue.append(step_id)
    return [step for step in steps if str(step["id"]) in visible]


def binding_scope_calls(
    steps: Sequence[Mapping[str, Any]],
    source_step_id: str,
    current_call_id: str,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    """Return visible binding calls and all calls indexed by call ID."""
    visible_step_ids = {str(step.get("id")) for step in expression_scope_steps(steps, source_step_id)}
    visible: dict[str, Mapping[str, Any]] = {}
    all_calls: dict[str, Mapping[str, Any]] = {}
    for step in steps:
        step_id = str(step.get("id", ""))
        for call in step.get("collectionCalls", []):
            call_id = str(call.get("id", ""))
            if not call_id:
                continue
            entry = {"call": call, "stepId": step_id}
            all_calls[call_id] = entry
            if step_id not in visible_step_ids:
                continue
            if step_id == source_step_id:
                if call_id == current_call_id:
                    break
            visible[call_id] = entry
    return visible, all_calls


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
        "topo": object_type({
            "devices": object_type({key: from_json_schema(value) for key, value in normalized["topo"]["devices"].items()}),
        }),
    }


def project_workflow_expression_environment(
    steps: Sequence[Mapping[str, Any]],
    definitions: Mapping[tuple[str, int], Mapping[str, Any]],
    workflow_inputs: Mapping[str, Any],
    workflow_roles: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Project one graph-scoped step set into the expression environment."""
    outputs: dict[str, dict[str, Any]] = {}
    input_keys = {str(key).strip() for key in workflow_inputs if str(key).strip()}
    direct_candidates: dict[str, dict[str, Any] | None] = {}
    config_candidates: dict[str, dict[str, Any] | None] = {}
    for step in steps:
        for call in step.get("collectionCalls", []):
            definition_ref = call.get("definition", {})
            definition = definitions.get((definition_ref.get("id"), definition_ref.get("revision")))
            if definition is None:
                continue
            call_key = str(call.get("key", "")).strip()
            sample_count = max(int(call.get("sampleCount", 1)), 1)
            if not call_key:
                if sample_count == 1:
                    for item in definition.get("outputs", []):
                        output_key = str(item.get("key", "")).strip()
                        if not is_expression_identifier(output_key):
                            continue
                        if output_key in input_keys or output_key in direct_candidates:
                            direct_candidates[output_key] = None
                        else:
                            direct_candidates[output_key] = {"sampleCount": sample_count, "fields": {}, "schema": item["schema"]}
            else:
                fields = {
                    str(item.get("key", "")).strip(): item["schema"]
                    for item in definition.get("outputs", [])
                    if str(item.get("key", "")).strip()
                }
                outputs.setdefault(call_key, {"sampleCount": sample_count, "fields": fields})
            if definition.get("spec", {}).get("collectionType") != "config":
                continue
            for command in definition.get("spec", {}).get("config", {}).get("commands", []):
                name = str(command.get("name", ""))
                schema = command_expression_schema(command)
                if name not in config_candidates:
                    config_candidates[name] = schema
                else:
                    config_candidates[name] = None
    for output_key, value in direct_candidates.items():
        if value is not None and output_key not in outputs:
            outputs[output_key] = value
    config = {name: schema for name, schema in config_candidates.items() if schema is not None}
    devices = {
        str(role.get("key", "")).strip(): role["schema"]
        for role in workflow_roles
        if str(role.get("key", "")).strip() and isinstance(role.get("schema"), Mapping) and role.get("schema", {}).get("type") == "object"
    }
    return {
        "inputs": dict(workflow_inputs),
        "outputs": outputs,
        "config": config,
        "topo": {"devices": devices},
    }


def workflow_expression_environment(
    document: dict[str, Any],
    source_step_id: str | None = None,
) -> dict[str, Any]:
    """Project a document into a graph-scoped compatibility environment."""
    workflow = document["workflow"]
    steps = expression_scope_steps(workflow.get("nodes", []), source_step_id)
    definitions = {
        (item["id"], item["revision"]): item
        for item in document.get("collectionSnapshots", [])
    }
    workflow_inputs = {
        item["key"].strip(): item["schema"]
        for item in workflow.get("inputs", [])
        if item.get("key", "").strip()
    }
    return project_workflow_expression_environment(steps, definitions, workflow_inputs, workflow.get("deviceRoles", []))
