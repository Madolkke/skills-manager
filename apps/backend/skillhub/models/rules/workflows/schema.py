from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from skillhub.models.errors import InvariantError

DOCUMENT_SCHEMA_VERSION = 3


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True, alias_generator=_camel)


class VersionedRef(WorkflowModel):
    id: str
    revision: int


class Parameter(WorkflowModel):
    id: str
    key: str
    name: str
    description: str = ""
    data_type: str = "string"
    required: bool = True


class Binding(WorkflowModel):
    kind: Literal["workflow_input", "collection_output", "literal"]
    reference: dict[str, str] = Field(default_factory=dict)
    value: Any = None


class WorkflowMetadata(WorkflowModel):
    name: str
    code: str = ""
    description: str = ""
    symptom: str = ""
    industry: str = ""
    device: str = ""
    versions: list[str] = Field(default_factory=list)


class DeviceRole(WorkflowModel):
    id: str
    key: str
    name: str
    description: str = ""
    required: bool = True


class CollectionMetadata(WorkflowModel):
    name: str
    description: str = ""
    industry: str = ""
    device: str = ""
    versions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CollectionOutput(WorkflowModel):
    id: str
    key: str
    description: str = ""
    data_type: str = "string"


class CliOutputSample(WorkflowModel):
    id: str
    name: str
    stdout: str = ""
    input_values: dict[str, Any] = Field(default_factory=dict)


class CliCollectionSpec(WorkflowModel):
    command_template: str = ""
    output_samples: list[CliOutputSample] = Field(default_factory=list)
    collection_type: Literal["cli"] = "cli"


class CollectionDefinition(WorkflowModel):
    id: str
    revision: int
    key: str
    metadata: CollectionMetadata
    spec: CliCollectionSpec
    inputs: list[Parameter] = Field(default_factory=list)
    outputs: list[CollectionOutput] = Field(default_factory=list)
    forked_from: VersionedRef | None = None


class CollectionCall(WorkflowModel):
    id: str
    key: str
    name: str
    definition: VersionedRef
    device_role_id: str | None = None
    sample_count: int = 1
    input_bindings: dict[str, Binding] = Field(default_factory=dict)


class NodeRef(WorkflowModel):
    id: str


class Transition(WorkflowModel):
    id: str
    target: NodeRef
    condition_text: str = ""
    condition_expression: str = ""


class ScriptDraft(WorkflowModel):
    language: str = "python"
    source: str = ""
    options: dict[str, Any] = Field(default_factory=dict)


class BaseStep(WorkflowModel):
    id: str
    name: str
    description: str = ""
    is_start: bool = False
    collection_calls: list[CollectionCall] = Field(default_factory=list)
    topology: list[Transition] = Field(default_factory=list)


class ExpressionStep(BaseStep):
    step_type: Literal["expression"]


class ScriptStep(BaseStep):
    step_type: Literal["script"]
    script: ScriptDraft | None = None


class Conclusion(WorkflowModel):
    id: str
    name: str
    root_cause: str = ""
    repair_recommendation: str = ""
    node_type: Literal["conclusion"]


class Workflow(WorkflowModel):
    id: str
    revision: int
    metadata: WorkflowMetadata
    inputs: list[Parameter] = Field(default_factory=list)
    device_roles: list[DeviceRole] = Field(default_factory=list)
    nodes: list[ExpressionStep | ScriptStep | Conclusion] = Field(default_factory=list)


class WorkflowBundle(WorkflowModel):
    workflow: Workflow
    collection_snapshots: list[CollectionDefinition] = Field(default_factory=list)
    document_type: Literal["workflow_bundle"]


def normalize_workflow_document(value: dict[str, Any]) -> dict[str, Any]:
    return _normalize(WorkflowBundle, value, "Workflow 文档格式不正确。")


def normalize_collection_definition(value: dict[str, Any]) -> dict[str, Any]:
    return _normalize(CollectionDefinition, value, "Collection 定义格式不正确。")


def migrate_workflow_document(document_schema_version: int, value: dict[str, Any]) -> dict[str, Any]:
    if document_schema_version != DOCUMENT_SCHEMA_VERSION:
        raise InvariantError(f"Unsupported Workflow document schema version: {document_schema_version}")
    return normalize_workflow_document(value)


def _normalize(model, value: dict[str, Any], message: str) -> dict[str, Any]:
    try:
        parsed = model.model_validate(value)
    except ValidationError as exc:
        detail = exc.errors(include_url=False)[0]
        path = ".".join(str(item) for item in detail.get("loc", ()))
        raise InvariantError(f"{message} {path}: {detail.get('msg', 'invalid value')}") from exc
    return parsed.model_dump(mode="json", by_alias=True, exclude_none=True)
