from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..workflows.schema import BaseStep, CollectionCall
from .references import output_path, visible_output_calls
from .schema import ExecutorScalar

if TYPE_CHECKING:
    from .converter import _Converter


def binding_value(
    converter: _Converter,
    step: BaseStep,
    call: CollectionCall,
    parameter_id: str,
    base: str,
) -> ExecutorScalar:
    """Resolve one binding against the converter's visible workflow sources."""
    binding = call.input_bindings.get(parameter_id)
    if binding is None:
        return None
    path = f"{base}.inputBindings[{parameter_id}]"
    if binding.kind == "literal":
        if isinstance(binding.value, (dict, list)):
            converter._error(
                f"{path}.value",
                "executor_workflow.unsupported_literal",
                "执行器 Workflow 暂不支持 object 或 array literal。",
            )
            return None
        return cast(ExecutorScalar, binding.value)
    if binding.kind == "workflow_input":
        input_id = binding.reference.get("input_id")
        matches = [item for item in converter.workflow.inputs if item.id == input_id]
        resolved = converter._single_reference(matches, f"{path}.reference.input_id", "Workflow input")
        return f"inputs.{resolved.key}" if resolved is not None else None
    if binding.kind == "device_role_field":
        converter._error(
            f"{path}.kind",
            "executor_workflow.unsupported_device_role_binding",
            "执行器 Workflow 当前不支持设备角色参数绑定；该绑定只能用于作者侧 Workflow。",
        )
        return None
    if binding.kind == "expression":
        converter._error(
            f"{path}.kind",
            "executor_workflow.unsupported_expression_binding",
            "执行器 Workflow 当前不支持表达式参数绑定；该绑定只能用于作者侧 Workflow。",
        )
        return None
    call_id = binding.reference.get("call_id")
    source = converter._single_reference(
        visible_output_calls(converter.all_steps, step, call, call_id), f"{path}.reference.call_id", "CollectionCall",
    )
    if source is None:
        return None
    source_node_index, source_call_index, source_call = source
    source_definition = converter._definition(
        source_call,
        f"workflow.nodes[{source_node_index}].collectionCalls[{source_call_index}].definition",
    )
    if source_definition is None:
        return None
    output_id = binding.reference.get("output_id")
    output_matches = [item for item in source_definition.outputs if item.id == output_id]
    output = converter._single_reference(output_matches, f"{path}.reference.output_id", "Collection output")
    return output_path(source_call, output.key) if output is not None else None

