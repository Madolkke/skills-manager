from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.document_migration import migrate_collection_v3, migrate_workflow_v3, workflow_uses_v3_fields

DOCUMENT_SCHEMA_VERSION = 5


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True, alias_generator=_camel)


class VersionedRef(WorkflowModel):
    id: str
    revision: int


class JsonSchema(WorkflowModel):
    type: Literal["string", "integer", "number", "boolean", "object", "array"] | None = None
    title: str = ""
    description: str = ""
    properties: dict[str, JsonSchema] | None = None
    required: list[str] | None = None
    additional_properties: bool | None = None
    items: JsonSchema | None = None
    legacy_loose: bool = Field(default=False, alias="x-skillhub-legacy-loose")

    @model_validator(mode="after")
    def validate_shape(self) -> "JsonSchema":
        if self.type is None:
            if not self.legacy_loose or any(value is not None for value in (self.properties, self.required, self.additional_properties, self.items)):
                raise ValueError("Only migrated legacy schemas may omit type")
            return self
        if self.type == "object":
            if self.properties is None or self.required is None or self.additional_properties is None or self.items is not None:
                raise ValueError("Object schema requires properties, required and additionalProperties")
            if self.additional_properties and not self.legacy_loose:
                raise ValueError("New object schemas must set additionalProperties to false")
            if any(not key.strip() for key in self.properties):
                raise ValueError("Object property keys must be non-empty")
            if len(self.required) != len(set(self.required)) or not set(self.required).issubset(self.properties):
                raise ValueError("Object required entries must be unique property keys")
            self.properties = dict(sorted(self.properties.items()))
            self.required = sorted(self.required)
            return self
        if self.type == "array":
            if self.items is None or any(value is not None for value in (self.properties, self.required, self.additional_properties)):
                raise ValueError("Array schema requires items")
            return self
        if any(value is not None for value in (self.properties, self.required, self.additional_properties, self.items)):
            raise ValueError("Scalar schemas cannot define structural keywords")
        return self


class Parameter(WorkflowModel):
    id: str
    key: str
    required: bool = True
    schema_: JsonSchema = Field(alias="schema")


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
    required: bool = True
    schema_: JsonSchema = Field(alias="schema")


class CliOutputSample(WorkflowModel):
    id: str
    name: str
    stdout: str = ""
    input_values: dict[str, Any] = Field(default_factory=dict)


class CliCollectionSpec(WorkflowModel):
    command_template: str = ""
    output_samples: list[CliOutputSample] = Field(default_factory=list)
    collection_type: Literal["cli"] = "cli"


class LogAggregationQuery(WorkflowModel):
    id: str
    name: str
    sql: str = ""
    output_ids: list[str] = Field(default_factory=list)


class LogOutputSample(WorkflowModel):
    id: str
    name: str
    text: str = ""


class LogCollectionSpec(WorkflowModel):
    collection_type: Literal["log"] = "log"
    sql_dialect: Literal["duckdb"]
    queries: list[LogAggregationQuery] = Field(default_factory=list)
    output_samples: list[LogOutputSample] = Field(default_factory=list)


class ConfigCommand(WorkflowModel):
    name: str
    unique: bool = True
    pattern: str
    captures: dict[str, JsonSchema] = Field(default_factory=dict)
    children: list["ConfigCommand"] = Field(default_factory=list)


class ConfigRoot(WorkflowModel):
    commands: list[ConfigCommand] = Field(default_factory=list)


class ConfigCollectionSpec(WorkflowModel):
    collection_type: Literal["config"] = "config"
    config: ConfigRoot


CollectionSpec = Annotated[CliCollectionSpec | LogCollectionSpec | ConfigCollectionSpec, Field(discriminator="collection_type")]


class CollectionDefinition(WorkflowModel):
    id: str
    revision: int
    key: str
    metadata: CollectionMetadata
    spec: CollectionSpec
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
    if workflow_uses_v3_fields(value):
        value = migrate_workflow_v3(value)
    value = _normalize_legacy_cli_specs(value)
    return _normalize(WorkflowBundle, value, "Workflow 文档格式不正确。")


def normalize_collection_definition(value: dict[str, Any]) -> dict[str, Any]:
    if any("schema" not in item for item in [*value.get("inputs", []), *value.get("outputs", [])]):
        value = migrate_collection_v3(value)
    value = _normalize_legacy_cli_specs(value)
    return _normalize(CollectionDefinition, value, "Collection 定义格式不正确。")


def migrate_workflow_document(document_schema_version: int, value: dict[str, Any]) -> dict[str, Any]:
    if document_schema_version == 3:
        value = migrate_workflow_v3(value)
    elif document_schema_version not in {4, DOCUMENT_SCHEMA_VERSION}:
        raise InvariantError(f"Unsupported Workflow document schema version: {document_schema_version}")
    if document_schema_version < DOCUMENT_SCHEMA_VERSION:
        value = _normalize_legacy_log_specs(value, fill_dialect=True)
    return normalize_workflow_document(value)


def migrate_collection_definition(document_schema_version: int, value: dict[str, Any]) -> dict[str, Any]:
    if document_schema_version == 3:
        value = migrate_collection_v3(value)
    elif document_schema_version not in {4, DOCUMENT_SCHEMA_VERSION}:
        raise InvariantError(f"Unsupported Collection document schema version: {document_schema_version}")
    if document_schema_version < DOCUMENT_SCHEMA_VERSION:
        value = _normalize_legacy_log_specs(value, fill_dialect=True)
    return normalize_collection_definition(value)


def _normalize(model, value: dict[str, Any], message: str) -> dict[str, Any]:
    try:
        parsed = model.model_validate(value)
    except ValidationError as exc:
        detail = exc.errors(include_url=False)[0]
        path = ".".join(str(item) for item in detail.get("loc", ()))
        raise InvariantError(f"{message} {path}: {detail.get('msg', 'invalid value')}") from exc
    return parsed.model_dump(mode="json", by_alias=True, exclude_none=True)


def _normalize_legacy_cli_specs(value: dict[str, Any]) -> dict[str, Any]:
    """Add the discriminator to v4 CLI documents that predate the union field."""
    result = deepcopy(value)
    definitions = [result] if "metadata" in result and "spec" in result else result.get("collectionSnapshots", [])
    for definition in definitions:
        spec = definition.get("spec")
        if isinstance(spec, dict) and "collectionType" not in spec and "queries" not in spec and "sqlDialect" not in spec:
            spec["collectionType"] = "cli"
    return result


def _normalize_legacy_log_specs(value: dict[str, Any], *, fill_dialect: bool) -> dict[str, Any]:
    """Materialize the v4 log discriminator and dialect before strict v5 parsing."""
    result = deepcopy(value)
    definitions = [result] if "metadata" in result and "spec" in result else result.get("collectionSnapshots", [])
    for definition in definitions:
        spec = definition.get("spec")
        if not isinstance(spec, dict):
            continue
        if "collectionType" not in spec and ("queries" in spec or "sqlDialect" in spec):
            spec["collectionType"] = "log"
        if fill_dialect and spec.get("collectionType") == "log":
            spec.setdefault("sqlDialect", "duckdb")
    return result
