from collections.abc import Mapping
from typing import Any

from skillhub.models.errors import InvariantError

from .expression.environment import is_expression_identifier
from .source_references import _validate_source_expression_references


def _validate_source_compatibility(
    *,
    document: Mapping[str, Any],
    source_call: Mapping[str, Any],
    current: Mapping[str, Any] | None,
    desired: Mapping[str, Any],
) -> None:
    """Reject source updates that would leave existing bindings dangling."""
    desired_input_ids = {str(item.get("id")) for item in desired.get("inputs", []) if item.get("id")}
    bindings = source_call.get("inputBindings", {}) or {}
    invalid_inputs = sorted(set(bindings) - desired_input_ids)
    if invalid_inputs:
        raise InvariantError(f"系统命令同步会移除已绑定输入: {', '.join(invalid_inputs)}")
    missing_required = sorted(
        str(item["id"])
        for item in desired.get("inputs", [])
        if item.get("required", True) and item.get("id") not in bindings
    )
    if missing_required:
        raise InvariantError(f"系统命令同步新增了未绑定的必填输入: {', '.join(missing_required)}")

    workflow_inputs = {
        str(item.get("id")): item
        for item in (document.get("workflow", {}) or {}).get("inputs", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    snapshots = {
        (str(item.get("id")), int(item.get("revision", 0))): item
        for item in document.get("collectionSnapshots", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    calls_by_id = {
        str(call.get("id")): call
        for node in (document.get("workflow", {}) or {}).get("nodes", [])
        if isinstance(node, Mapping)
        for call in node.get("collectionCalls", [])
        if isinstance(call, Mapping) and call.get("id")
    }
    from skillhub.models.rules.workflows.device_bindings import resolve_device_role_field
    from skillhub.models.rules.workflows.expression import validate_binding_expression
    from skillhub.models.rules.workflows.expression.environment import binding_expression_environment
    from skillhub.models.rules.workflows.json_schema import schemas_assignable, value_matches_schema

    for input_definition in desired.get("inputs", []):
        input_id = str(input_definition.get("id", ""))
        binding = bindings.get(input_id)
        if not isinstance(binding, Mapping):
            continue
        if input_definition.get("required", True) and binding.get("kind") == "literal" and binding.get("value") in (None, ""):
            raise InvariantError(f"系统命令同步会使必填输入“{input_id}”失去绑定值")
        source_schema: Mapping[str, Any] | None = None
        kind = binding.get("kind")
        reference = binding.get("reference") if isinstance(binding.get("reference"), Mapping) else {}
        if kind == "workflow_input":
            source = workflow_inputs.get(str(reference.get("input_id")))
            if source is None:
                raise InvariantError(f"系统命令同步发现无效的全局输入绑定: {input_id}")
            source_schema = source.get("schema")
        elif kind == "collection_output":
            bound_call = calls_by_id.get(str(reference.get("call_id")))
            source_definition = None
            if bound_call:
                source_ref = bound_call.get("definition", {})
                source_definition = snapshots.get((str(source_ref.get("id")), int(source_ref.get("revision", 0))))
            output_id = str(reference.get("output_id", ""))
            source_output = next(
                (item for item in (source_definition or {}).get("outputs", []) if item.get("id") == output_id),
                None,
            )
            if source_output is None:
                raise InvariantError(f"系统命令同步发现无效的前序输出绑定: {input_id}")
            source_schema = source_output.get("schema")
        elif kind == "device_role_field":
            resolution = resolve_device_role_field(
                (document.get("workflow", {}) or {}).get("deviceRoles", []),
                str(reference.get("role_id", "")),
                str(reference.get("path", "")),
            )
            if resolution.status != "ok" or resolution.schema is None:
                raise InvariantError(f"系统命令同步发现无效的设备角色字段绑定: {input_id}")
            source_schema = resolution.schema
        elif kind == "expression":
            expression = binding.get("expression")
            if not isinstance(expression, str) or not expression.strip():
                raise InvariantError(f"系统命令同步发现空表达式绑定: {input_id}")
            source_step = next(
                (node for node in (document.get("workflow", {}) or {}).get("nodes", [])
                 if isinstance(node, Mapping) and any(call.get("id") == source_call.get("id") for call in node.get("collectionCalls", []))),
                None,
            )
            if source_step is None:
                raise InvariantError(f"系统命令同步无法定位表达式绑定调用: {input_id}")
            input_environment = {
                str(item.get("key", "")).strip(): item.get("schema", {})
                for item in (document.get("workflow", {}) or {}).get("inputs", [])
                if str(item.get("key", "")).strip()
            }
            definitions = snapshots
            environment = binding_expression_environment(
                (document.get("workflow", {}) or {}).get("nodes", []),
                str(source_step.get("id")),
                str(source_call.get("id")),
                definitions,
                input_environment,
                (document.get("workflow", {}) or {}).get("deviceRoles", []),
            )
            result = validate_binding_expression(expression, environment, input_definition.get("schema", {}))
            if result["diagnostics"]:
                raise InvariantError(f"系统命令同步发现无效表达式绑定: {input_id}")
            if not result["assignable"]:
                raise InvariantError(f"系统命令同步会使输入“{input_id}”的表达式结果与新 Schema 不兼容")
            continue
        elif kind == "literal":
            if binding.get("value") in (None, "") and not input_definition.get("required", True):
                continue
            if not value_matches_schema(binding.get("value"), input_definition.get("schema", {})):
                raise InvariantError(f"系统命令同步会使输入“{input_id}”的固定值与新 Schema 不兼容")
            continue
        else:
            raise InvariantError(f"系统命令同步发现未知输入绑定类型: {kind}")
        if not schemas_assignable(dict(source_schema or {}), dict(input_definition.get("schema", {}))):
            raise InvariantError(f"系统命令同步会使输入“{input_id}”的绑定 Schema 不兼容")

    desired_outputs = {
        str(item.get("id")): item
        for item in desired.get("outputs", [])
        if item.get("id")
    }
    all_calls = [
        call
        for node in (document.get("workflow", {}) or {}).get("nodes", [])
        if isinstance(node, Mapping)
        for call in node.get("collectionCalls", [])
        if isinstance(call, Mapping)
    ]
    source_call_id = source_call.get("id")
    for consumer in all_calls:
        for input_id, binding in (consumer.get("inputBindings", {}) or {}).items():
            reference = (binding or {}).get("reference", {})
            if (binding or {}).get("kind") != "collection_output" or reference.get("call_id") != source_call_id:
                continue
            output_id = str(reference.get("output_id", ""))
            output = desired_outputs.get(output_id)
            if output is None:
                raise InvariantError(f"系统命令同步会移除已绑定输出: {output_id}")
            consumer_ref = consumer.get("definition", {})
            consumer_definition = snapshots.get(
                (str(consumer_ref.get("id")), int(consumer_ref.get("revision", 0)))
            )
            target = next(
                (item for item in (consumer_definition or {}).get("inputs", []) if item.get("id") == input_id),
                None,
            )
            if target is None:
                continue
            from skillhub.models.rules.workflows.json_schema import schemas_assignable

            if not schemas_assignable(output.get("schema", {}), target.get("schema", {})):
                raise InvariantError(f"系统命令同步会使输出“{output_id}”与绑定输入不兼容。")

    _validate_source_output_scope(document=document, source_call=source_call, desired=desired, snapshots=snapshots)
    if current is not None:
        _validate_source_expression_references(
            document=document,
            source_call=source_call,
            current=current,
            desired=desired,
        )


def _validate_source_output_scope(
    *,
    document: Mapping[str, Any],
    source_call: Mapping[str, Any],
    desired: Mapping[str, Any],
    snapshots: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    """Keep direct output names unambiguous while a source is refreshed."""
    workflow = document.get("workflow") if isinstance(document.get("workflow"), Mapping) else {}
    reserved = {
        str(item.get("key", "")).strip()
        for item in workflow.get("inputs", [])
        if isinstance(item, Mapping) and str(item.get("key", "")).strip()
    }
    source_id = str(source_call.get("id", ""))
    source_step = next(
        (
            node
            for node in workflow.get("nodes", [])
            if isinstance(node, Mapping)
            and any(
                isinstance(call, Mapping) and str(call.get("id", "")) == source_id
                for call in node.get("collectionCalls", [])
            )
        ),
        None,
    )
    if source_step is None:
        return
    names: dict[str, str] = {}
    for call in source_step.get("collectionCalls", []):
        if not isinstance(call, Mapping):
            continue
        call_id = str(call.get("id", ""))
        if call_id == source_id:
            definition = desired
        else:
            reference = call.get("definition") if isinstance(call.get("definition"), Mapping) else {}
            definition = snapshots.get((str(reference.get("id", "")), int(reference.get("revision", 0))))
        if not isinstance(definition, Mapping) or str(call.get("key", "")).strip():
            continue
        for output in definition.get("outputs", []):
            if not isinstance(output, Mapping):
                continue
            key = str(output.get("key", "")).strip()
            if not is_expression_identifier(key):
                continue
            if key in reserved:
                raise InvariantError(f"系统命令同步会使直接输出“{key}”与 Workflow 全局输入冲突。")
            previous = names.get(key)
            if previous is not None and previous != call_id:
                raise InvariantError(f"系统命令同步会使直接输出“{key}”与同一步骤的其他采集冲突。")
            names[key] = call_id


