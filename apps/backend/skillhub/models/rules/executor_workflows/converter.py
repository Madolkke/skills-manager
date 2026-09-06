from __future__ import annotations

from typing import Literal, TypeVar, cast

from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.rules.executor_workflows.bindings import binding_value
from skillhub.models.rules.executor_workflows.references import (
    allocate_ids,
    group_definitions,
    group_nodes,
    output_path,
    projected_call_indexes,
)
from skillhub.models.rules.executor_workflows.schema import (
    ExecutorCollection,
    ExecutorConclusion,
    ExecutorStep,
    ExecutorTransition,
    ExecutorValue,
    ExecutorValueType,
    ExecutorWorkflow,
)
from skillhub.models.rules.workflows.schema import (
    BaseStep,
    CollectionCall,
    CollectionDefinition,
    Conclusion,
    ConfigCollectionSpec,
    ExpressionStep,
    FunctionCollectionSpec,
    JsonSchema,
    LogCollectionSpec,
    ScriptStep,
    WorkflowBundle,
)

SCALAR_TYPES = {"string", "integer", "number", "boolean"}
ERROR_DETAIL = "Workflow 无法转换为执行器定义。"
ReferenceT = TypeVar("ReferenceT")

class _Converter:
    def __init__(self, bundle: WorkflowBundle) -> None:
        self.workflow = bundle.workflow
        self.errors: list[FieldError] = []
        self.error_keys: set[tuple[str, str]] = set()
        self.all_steps = [(index, node) for index, node in enumerate(self.workflow.nodes) if isinstance(node, BaseStep)]
        self.steps = [(index, node) for index, node in enumerate(self.workflow.nodes) if isinstance(node, ExpressionStep)]
        self.conclusions = [(index, node) for index, node in enumerate(self.workflow.nodes) if isinstance(node, Conclusion)]
        self.node_groups = group_nodes(self.workflow.nodes)
        self.definition_groups = group_definitions(bundle.collection_snapshots)
        self.definition_indexes = {id(definition): index for index, definition in enumerate(bundle.collection_snapshots)}
        included_calls = projected_call_indexes(self.all_steps, self.definition_groups)
        self.step_ids, self.call_ids, self.transition_ids, self.conclusion_ids = allocate_ids(
            self.all_steps,
            self.conclusions,
            included_calls,
        )

    def convert(self) -> ExecutorWorkflow:
        inputs = self._workflow_inputs()
        steps: list[ExecutorStep] = []
        for node_index, node in enumerate(self.workflow.nodes):
            if isinstance(node, ExpressionStep):
                steps.append(self._step(node_index, node))
            elif isinstance(node, ScriptStep):
                self._error(
                    f"workflow.nodes[{node_index}].stepType",
                    "executor_workflow.unsupported_step_type",
                    "执行器 Workflow 暂不支持 script Step。",
                )
                for call_index, call in enumerate(node.collection_calls):
                    self._collection(node_index, node, call_index, call)
                for transition_index, transition in enumerate(node.topology):
                    self._transition(node_index, transition_index, transition)
        conclusions = [
            ExecutorConclusion(
                id=self.conclusion_ids[node_index],
                conclusion=conclusion.name,
                severity=conclusion.severity,
            )
            for node_index, conclusion in self.conclusions
        ]
        if self.errors:
            raise FieldInvariantError(ERROR_DETAIL, self.errors)
        return ExecutorWorkflow(
            id=1,
            name=self.workflow.metadata.name,
            start_step_ids=[self.step_ids[index] for index, step in self.steps if step.is_start],
            inputs=inputs,
            steps=steps,
            conclusions=conclusions,
        )

    def _workflow_inputs(self) -> list[ExecutorValue]:
        values: list[ExecutorValue] = []
        for input_index, parameter in enumerate(self.workflow.inputs):
            value_type = self._schema_type(parameter.schema_, f"workflow.inputs[{input_index}].schema")
            if value_type is not None:
                values.append(
                    ExecutorValue(
                        name=parameter.key,
                        description=parameter.schema_.description,
                        value=f"inputs.{parameter.key}",
                        type=value_type,
                    )
                )
        return values

    def _step(self, node_index: int, step: ExpressionStep) -> ExecutorStep:
        collections = [self._collection(node_index, step, call_index, call) for call_index, call in enumerate(step.collection_calls)]
        transitions = [
            transition
            for transition_index, item in enumerate(step.topology)
            if (transition := self._transition(node_index, transition_index, item)) is not None
        ]
        return ExecutorStep(
            id=self.step_ids[node_index],
            name=step.name,
            condition=step.description,
            collections=[item for item in collections if item is not None],
            transitions=transitions,
        )

    def _collection(
        self,
        node_index: int,
        step: BaseStep,
        call_index: int,
        call: CollectionCall,
    ) -> ExecutorCollection | None:
        base = f"workflow.nodes[{node_index}].collectionCalls[{call_index}]"
        definition = self._definition(call, f"{base}.definition")
        if definition is None:
            for parameter_id in call.input_bindings:
                binding_value(self, step, call, parameter_id, base)
            return None
        if isinstance(definition.spec, (LogCollectionSpec, ConfigCollectionSpec, FunctionCollectionSpec)):
            return None
        if call.device_role_id not in (None, ""):
            self._error(
                f"{base}.deviceRoleId",
                "executor_workflow.unsupported_device_role",
                "执行器 Workflow 暂不支持设备角色。",
            )
        if call.sample_count != 1:
            self._error(
                f"{base}.sampleCount",
                "executor_workflow.unsupported_sample_count",
                "执行器 Workflow 暂只支持 sampleCount 为 1。",
            )
        definition_index = self.definition_indexes[id(definition)]
        unknown_bindings = self._unknown_bindings(call, definition, base)
        for parameter_id in unknown_bindings:
            binding_value(self, step, call, parameter_id, base)
        inputs: list[ExecutorValue] = []
        for input_index, parameter in enumerate(definition.inputs):
            schema_path = f"collectionSnapshots[{definition_index}].inputs[{input_index}].schema"
            value_type = self._schema_type(parameter.schema_, schema_path)
            value = binding_value(self, step, call, parameter.id, base)
            if value_type is not None:
                inputs.append(
                    ExecutorValue(
                        name=parameter.key,
                        description=parameter.schema_.description,
                        value=value,
                        type=value_type,
                    )
                )
        outputs: list[ExecutorValue] = []
        for output_index, output in enumerate(definition.outputs):
            schema_path = f"collectionSnapshots[{definition_index}].outputs[{output_index}].schema"
            value_type = self._schema_type(output.schema_, schema_path)
            if value_type is not None:
                outputs.append(
                    ExecutorValue(
                        name=output.key,
                        description=output.schema_.description,
                        value=output_path(call, output.key),
                        type=value_type,
                    )
                )
        return ExecutorCollection(
            id=self.call_ids[(node_index, call_index)],
            kind="command",
            command=definition.spec.command_template,
            example_outputs=[],
            inputs=inputs,
            outputs=outputs,
        )

    def _unknown_bindings(self, call: CollectionCall, definition: CollectionDefinition, base: str) -> list[str]:
        parameter_ids = {parameter.id for parameter in definition.inputs}
        unknown: list[str] = []
        for parameter_id in call.input_bindings:
            if parameter_id not in parameter_ids:
                unknown.append(parameter_id)
                self._error(
                    f"{base}.inputBindings[{parameter_id}]",
                    "executor_workflow.unresolvable_reference",
                    "输入绑定无法匹配 Collection 输入。",
                )
        return unknown

    def _transition(self, node_index: int, transition_index: int, transition) -> ExecutorTransition | None:
        path = f"workflow.nodes[{node_index}].topology[{transition_index}].target.id"
        matches = self.node_groups.get(transition.target.id, [])
        target = self._single_reference(matches, path, "Workflow node")
        if target is None:
            return None
        target_index, target_node = target
        target_type: Literal["step", "conclusion"]
        if isinstance(target_node, Conclusion):
            target_type = "conclusion"
            target_id = self.conclusion_ids[target_index]
        elif isinstance(target_node, ExpressionStep):
            target_type = "step"
            target_id = self.step_ids[target_index]
        else:
            self._error(
                path,
                "executor_workflow.unsupported_step_type",
                "Transition 不能指向不受支持的 script Step。",
            )
            return None
        return ExecutorTransition(
            id=self.transition_ids[(node_index, transition_index)],
            target_type=target_type,
            target_id=target_id,
            condition=transition.condition_expression,
            description=transition.condition_text,
        )

    def _definition(self, call: CollectionCall, field: str) -> CollectionDefinition | None:
        matches = self.definition_groups.get((call.definition.id, call.definition.revision), [])
        return self._single_reference(matches, field, "Collection definition")

    def _schema_type(self, schema: JsonSchema, field: str) -> ExecutorValueType | None:
        if schema.type in SCALAR_TYPES:
            return cast(ExecutorValueType, schema.type)
        self._error(
            field,
            "executor_workflow.unsupported_schema",
            "执行器 Workflow 暂只支持 string、integer、number 和 boolean schema。",
        )
        return None

    def _single_reference(self, matches: list[ReferenceT], field: str, label: str) -> ReferenceT | None:
        if not matches:
            self._error(field, "executor_workflow.unresolvable_reference", f"{label} 引用不存在。")
            return None
        if len(matches) > 1:
            self._error(field, "executor_workflow.ambiguous_reference", f"{label} 引用不唯一。")
            return None
        return matches[0]

    def _error(self, field: str, code: str, message: str) -> None:
        key = (field, code)
        if key in self.error_keys:
            return
        self.error_keys.add(key)
        self.errors.append(FieldError(field=field, code=code, message=message))
