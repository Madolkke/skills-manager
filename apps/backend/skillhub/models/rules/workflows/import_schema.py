from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import Field

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.schema import (
    Binding,
    CliCollectionSpec,
    CollectionMetadata,
    CollectionOutput,
    Conclusion,
    DeviceRole,
    Parameter,
    ScriptDraft,
    Transition,
    WorkflowMetadata,
    WorkflowModel,
    _normalize,
)


class ImportCollectionDefinition(WorkflowModel):
    local_id: str
    key: str
    metadata: CollectionMetadata
    spec: CliCollectionSpec
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[CollectionOutput] = Field(default_factory=list)


class ImportCollectionCall(WorkflowModel):
    id: str
    key: str
    name: str
    definition_local_id: str
    device_role_id: str | None = None
    sample_count: int = 1
    input_bindings: dict[str, Binding] = Field(default_factory=dict)


class ImportBaseStep(WorkflowModel):
    id: str
    name: str
    description: str = ""
    is_start: bool = False
    collection_calls: list[ImportCollectionCall] = Field(default_factory=list)
    topology: list[Transition] = Field(default_factory=list)


class ImportExpressionStep(ImportBaseStep):
    step_type: Literal["expression"]


class ImportScriptStep(ImportBaseStep):
    step_type: Literal["script"]
    script: ScriptDraft | None = None


class ImportWorkflow(WorkflowModel):
    metadata: WorkflowMetadata
    inputs: list[Parameter] = Field(default_factory=list)
    device_roles: list[DeviceRole] = Field(default_factory=list)
    nodes: list[ImportExpressionStep | ImportScriptStep | Conclusion] = Field(default_factory=list)


class WorkflowImportBundle(WorkflowModel):
    document_type: Literal["workflow_import_bundle"]
    workflow: ImportWorkflow
    collections: list[ImportCollectionDefinition] = Field(default_factory=list)


def normalize_workflow_import_bundle(value: dict[str, Any]) -> dict[str, Any]:
    return _normalize(WorkflowImportBundle, value, "Workflow 导入文档格式不正确。")


def validate_workflow_import_references(bundle: dict[str, Any]) -> None:
    definitions = _definition_map(bundle["collections"])
    workflow = bundle["workflow"]
    nodes = workflow["nodes"]
    node_ids = {item["id"] for item in nodes}
    workflow_input_ids = {item["id"] for item in workflow["inputs"]}

    for node in nodes:
        if "stepType" not in node:
            continue
        calls = {item["id"]: item for item in node["collectionCalls"]}
        for item in node["topology"]:
            if item["target"]["id"] not in node_ids:
                raise InvariantError(f"Workflow import transition target does not exist: {item['target']['id']}")
        for call in node["collectionCalls"]:
            local_id = call["definitionLocalId"]
            definition = definitions.get(local_id)
            if definition is None:
                raise InvariantError(f"Workflow import Collection does not exist: {local_id}")
            definition_input_ids = {item["id"] for item in definition["inputs"]}
            for input_id, binding in call["inputBindings"].items():
                if input_id not in definition_input_ids:
                    raise InvariantError(f"Workflow import Collection input does not exist: {input_id}")
                _validate_binding(binding, workflow_input_ids, calls, definitions)


def materialize_workflow_import(
    bundle: dict[str, Any],
    *,
    workflow_id: str,
    revision: int,
    collection_mappings: dict[str, tuple[str, int]],
) -> dict[str, Any]:
    workflow = deepcopy(bundle["workflow"])
    workflow["id"] = workflow_id
    workflow["revision"] = revision
    for node in workflow["nodes"]:
        if "stepType" not in node:
            continue
        for call in node["collectionCalls"]:
            local_id = call.pop("definitionLocalId")
            definition_id, definition_revision = collection_mappings[local_id]
            call["definition"] = {"id": definition_id, "revision": definition_revision}
    return {"documentType": "workflow_bundle", "workflow": workflow, "collectionSnapshots": []}


def _definition_map(definitions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        local_id = definition["localId"].strip()
        if not local_id or local_id in result:
            raise InvariantError("Workflow import Collection localId values must be non-empty and unique.")
        result[local_id] = definition
    return result


def _validate_binding(binding, workflow_inputs, calls, definitions) -> None:
    kind = binding["kind"]
    reference = binding["reference"]
    valid = kind == "literal"
    if kind == "workflow_input":
        valid = reference.get("input_id") in workflow_inputs
    elif kind == "collection_output":
        call = calls.get(reference.get("call_id"))
        definition = definitions.get(call["definitionLocalId"]) if call else None
        valid = bool(definition and any(item["id"] == reference.get("output_id") for item in definition["outputs"]))
    if not valid:
        raise InvariantError(f"Workflow import Binding reference is invalid: {kind}")
