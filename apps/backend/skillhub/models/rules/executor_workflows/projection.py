from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from pydantic import ValidationError

from skillhub.models.errors import InvariantError
from skillhub.models.rules.executor_workflows.converter import _Converter
from skillhub.models.rules.executor_workflows.schema import ExecutorWorkflow
from skillhub.models.rules.workflows.schema import WorkflowBundle

CallSource: TypeAlias = tuple[str, str]
CallOutputSource: TypeAlias = tuple[str, str, str]
TransitionSource: TypeAlias = tuple[str, str]


@dataclass(frozen=True)
class ExecutorWorkflowIdMap:
    """Authoring identities and keys needed to interpret executor results."""

    step_ids: Mapping[str, int]
    conclusion_ids: Mapping[str, int]
    call_ids: Mapping[CallSource, int]
    transition_ids: Mapping[TransitionSource, int]
    workflow_input_keys: Mapping[str, str]
    call_output_keys: Mapping[CallOutputSource, str]


@dataclass(frozen=True)
class ExecutorWorkflowProjection:
    workflow: ExecutorWorkflow
    id_map: ExecutorWorkflowIdMap


def project_workflow_document(document: dict[str, Any]) -> ExecutorWorkflowProjection:
    """Project an authoring Workflow and retain its executor identity mapping."""
    bundle = _parse_bundle(document)
    converter = _Converter(bundle)
    workflow = converter.convert()
    return ExecutorWorkflowProjection(workflow=workflow, id_map=_build_id_map(bundle, converter))


def convert_workflow_document(document: dict[str, Any]) -> ExecutorWorkflow:
    return project_workflow_document(document).workflow


def _parse_bundle(document: dict[str, Any]) -> WorkflowBundle:
    try:
        return WorkflowBundle.model_validate(document)
    except ValidationError as exc:
        raise InvariantError("Workflow 文档格式不正确。") from exc


def _build_id_map(bundle: WorkflowBundle, converter: _Converter) -> ExecutorWorkflowIdMap:
    workflow = bundle.workflow

    mapped_steps = {step.id: converter.step_ids[node_index] for node_index, step in converter.all_steps}
    mapped_conclusions = {
        conclusion.id: converter.conclusion_ids[node_index]
        for node_index, conclusion in converter.conclusions
    }
    mapped_calls: dict[CallSource, int] = {}
    mapped_transitions: dict[TransitionSource, int] = {}
    mapped_outputs: dict[CallOutputSource, str] = {}
    for node_index, step in converter.all_steps:
        for transition_index, transition in enumerate(step.topology):
            mapped_transitions[(step.id, transition.id)] = converter.transition_ids[(node_index, transition_index)]
        for call_index, call in enumerate(step.collection_calls):
            executor_call_id = converter.call_ids.get((node_index, call_index))
            if executor_call_id is None:
                continue
            call_source = (step.id, call.id)
            mapped_calls[call_source] = executor_call_id
            matching_definitions = converter.definition_groups.get((call.definition.id, call.definition.revision), [])
            if len(matching_definitions) != 1:
                continue
            for output in matching_definitions[0].outputs:
                mapped_outputs[(*call_source, output.id)] = output.key

    return ExecutorWorkflowIdMap(
        step_ids=MappingProxyType(mapped_steps),
        conclusion_ids=MappingProxyType(mapped_conclusions),
        call_ids=MappingProxyType(mapped_calls),
        transition_ids=MappingProxyType(mapped_transitions),
        workflow_input_keys=MappingProxyType({parameter.id: parameter.key for parameter in workflow.inputs}),
        call_output_keys=MappingProxyType(mapped_outputs),
    )


__all__ = [
    "CallOutputSource",
    "CallSource",
    "TransitionSource",
    "ExecutorWorkflowIdMap",
    "ExecutorWorkflowProjection",
    "convert_workflow_document",
    "project_workflow_document",
]
