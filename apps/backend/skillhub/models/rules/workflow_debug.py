from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Literal

from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.rules.executor_workflows import ExecutorWorkflowProjection
from skillhub.models.rules.workflows.schema import BaseStep, ConfigCollectionSpec, LogCollectionSpec, WorkflowBundle

TARGET_ERROR_DETAIL = "Workflow 调试例引用与当前 Workflow 不一致。"
UNSUPPORTED_COLLECTION_DETAIL = "当前 Step 包含暂不支持单步调试的采集类型。"


@dataclass(frozen=True)
class DebugTarget:
    type: Literal["step", "conclusion"]
    id: int


def validate_debug_case_target(document: dict[str, Any], *, step_id: str, expected_target_id: str) -> None:
    bundle = WorkflowBundle.model_validate(document)
    steps = [node for node in bundle.workflow.nodes if isinstance(node, BaseStep) and node.id == step_id]
    if len(steps) != 1:
        raise _reference_error("step_id", "调试 Step 不存在或不唯一。")
    if expected_target_id not in {transition.target.id for transition in steps[0].topology}:
        raise _reference_error("expected_target_id", "预期节点必须是当前 Step 的直接拓扑目标。")


def validate_debug_step_collections(document: dict[str, Any], *, step_id: str) -> None:
    bundle = WorkflowBundle.model_validate(document)
    step = next((node for node in bundle.workflow.nodes if isinstance(node, BaseStep) and node.id == step_id), None)
    if step is None:
        return
    for call in step.collection_calls:
        definitions = [
            definition
            for definition in bundle.collection_snapshots
            if definition.id == call.definition.id and definition.revision == call.definition.revision
        ]
        if len(definitions) == 1 and isinstance(definitions[0].spec, (LogCollectionSpec, ConfigCollectionSpec)):
            raise FieldInvariantError(
                UNSUPPORTED_COLLECTION_DETAIL,
                [
                    FieldError(
                        field="step_id",
                        message="日志和配置采集暂不支持单步调试。",
                        code="workflow_debug.unsupported_collection_type",
                    )
                ],
            )


def build_executor_identity(
    projection: ExecutorWorkflowProjection,
    *,
    document: dict[str, Any],
    case: dict[str, Any],
) -> dict[str, Any]:
    step_id = str(case["step_id"])
    target_id = str(case["expected_target_id"])
    validate_debug_case_target(document, step_id=step_id, expected_target_id=target_id)
    validate_debug_step_collections(document, step_id=step_id)
    step_executor_id = projection.id_map.step_ids.get(step_id)
    target = _target(projection, target_id)
    expected_transition_ids = _expected_transition_ids(projection, document, step_id=step_id, target_id=target_id)
    errors: list[FieldError] = []
    if step_executor_id is None:
        errors.append(_field_error("step_id", "调试 Step 无法映射到执行器。"))
    if target is None:
        errors.append(_field_error("expected_target_id", "预期节点无法映射到执行器。"))
    if not expected_transition_ids:
        errors.append(_field_error("expected_target_id", "指向预期节点的跳转无法映射到执行器。"))

    input_keys = dict(projection.id_map.workflow_input_keys)
    for input_id in case["workflow_inputs"]:
        if input_id not in input_keys:
            errors.append(_field_error(f"workflow_inputs.{input_id}", "Workflow input 已不存在。"))

    collections: dict[str, dict[str, Any]] = {}
    for (source_step_id, call_id), executor_id in projection.id_map.call_ids.items():
        if source_step_id != step_id:
            continue
        output_keys = {
            output_id: output_key
            for (output_step_id, output_call_id, output_id), output_key in projection.id_map.call_output_keys.items()
            if output_step_id == step_id and output_call_id == call_id
        }
        collections[call_id] = {"executor_id": executor_id, "output_keys": output_keys}
    for call_id, fixture in case["collection_fixtures"].items():
        if call_id not in collections:
            errors.append(_field_error(f"collection_fixtures.{call_id}", "CollectionCall 已不存在或不属于当前 Step。"))
            continue
        for output_id in fixture["outputs"]:
            if output_id not in collections[call_id]["output_keys"]:
                errors.append(_field_error(f"collection_fixtures.{call_id}.outputs.{output_id}", "Collection output 已不存在。"))
    if errors:
        raise FieldInvariantError(TARGET_ERROR_DETAIL, errors)
    assert step_executor_id is not None and target is not None
    return {
        "step_id": step_executor_id,
        "expected_target": {"type": target.type, "id": target.id, "transition_ids": expected_transition_ids},
        "workflow_input_keys": input_keys,
        "collections": collections,
    }


def target_reached(status: dict[str, Any], target: dict[str, Any]) -> bool:
    expected_transitions = set(target.get("transition_ids", []))
    if expected_transitions and any(_selected_transition(step) in expected_transitions for step in status["steps"]):
        return True
    if target["type"] == "conclusion":
        return target["id"] in status["conclusion_ids"]
    return any(
        step["step_id"] == target["id"] and step["status"] in {"success", "failure"}
        for step in status["steps"]
    )


def _selected_transition(step: dict[str, Any]) -> int | None:
    if step.get("status") not in {"success", "failure"}:
        return None
    result = step.get("result")
    if not isinstance(result, dict):
        return None
    selected = result.get("selected_transition_id")
    return selected if isinstance(selected, int) and not isinstance(selected, bool) else None


def paused_run_input(schema: dict[str, Any], *, snapshot: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("paused schema properties must be an object")
    if "value" in properties:
        return _collection_run_input(properties["value"], snapshot=snapshot, identity=identity)
    return _parameter_run_input(schema, properties, snapshot=snapshot, identity=identity)


def _parameter_run_input(schema, properties, *, snapshot, identity) -> dict[str, Any]:
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ValueError("paused schema required must be an array of strings")
    by_key: dict[str, list[str]] = {}
    for input_id, key in identity["workflow_input_keys"].items():
        by_key.setdefault(key, []).append(input_id)
    values: dict[str, Any] = {}
    for key, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            raise ValueError(f"paused schema property {key} must be an object")
        source_ids = by_key.get(key, [])
        provided = [source_id for source_id in source_ids if source_id in snapshot["workflow_inputs"]]
        if len(provided) == 1:
            values[key] = snapshot["workflow_inputs"][provided[0]]
        elif len(provided) > 1:
            raise ValueError(f"paused parameter {key} is ambiguous")
        elif "default" in property_schema:
            values[key] = copy.deepcopy(property_schema["default"])
        elif key in required:
            raise ValueError(f"paused parameter {key} is required")
    return values


def _collection_run_input(value_schema, *, snapshot, identity) -> dict[str, Any]:
    if not isinstance(value_schema, dict) or not isinstance(value_schema.get("default"), list):
        raise ValueError("paused collection schema requires value.default array")
    fixtures = snapshot["collection_fixtures"]
    by_executor_id = {value["executor_id"]: call_id for call_id, value in identity["collections"].items()}
    result = []
    for index, template in enumerate(value_schema["default"]):
        if not isinstance(template, dict) or not isinstance(template.get("collection_id"), int):
            raise ValueError(f"paused collection template {index} is invalid")
        call_id = by_executor_id.get(template["collection_id"])
        if call_id is None or call_id not in fixtures:
            raise ValueError(f"collection fixture {template['collection_id']} is required")
        fixture = fixtures[call_id]
        output_keys = identity["collections"][call_id]["output_keys"]
        outputs = {output_keys[output_id]: value for output_id, value in fixture["outputs"].items()}
        result.append({**copy.deepcopy(template), "raw_output": list(fixture["raw_output"]), "outputs": outputs})
    return {"value": result}


def _target(projection: ExecutorWorkflowProjection, target_id: str) -> DebugTarget | None:
    if target_id in projection.id_map.step_ids:
        return DebugTarget(type="step", id=projection.id_map.step_ids[target_id])
    if target_id in projection.id_map.conclusion_ids:
        return DebugTarget(type="conclusion", id=projection.id_map.conclusion_ids[target_id])
    return None


def _expected_transition_ids(
    projection: ExecutorWorkflowProjection,
    document: dict[str, Any],
    *,
    step_id: str,
    target_id: str,
) -> list[int]:
    bundle = WorkflowBundle.model_validate(document)
    step = next((node for node in bundle.workflow.nodes if isinstance(node, BaseStep) and node.id == step_id), None)
    if step is None:
        return []
    return [
        executor_id
        for transition in step.topology
        if transition.target.id == target_id
        and (executor_id := projection.id_map.transition_ids.get((step_id, transition.id))) is not None
    ]


def _reference_error(field: str, message: str) -> FieldInvariantError:
    return FieldInvariantError(TARGET_ERROR_DETAIL, [_field_error(field, message)])


def _field_error(field: str, message: str) -> FieldError:
    return FieldError(field=field, message=message, code="workflow_debug.unresolvable_reference")


__all__ = [
    "build_executor_identity",
    "paused_run_input",
    "target_reached",
    "validate_debug_case_target",
    "validate_debug_step_collections",
]
