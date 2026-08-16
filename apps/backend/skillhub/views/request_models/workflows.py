from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from skillhub.models.rules.workflows.schema import JsonSchema
from skillhub.views.request_models.common import IdentityRef, SkillSlug, SkillTagPayload, SkillVersionSemVer, VersionChangeSummary, VersionDisplayName

WorkflowDescription = Annotated[str, Field(max_length=1024)]
WorkflowMetadataText = Annotated[str, Field(max_length=1000)]


class CreateWorkflowSkillPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: SkillSlug
    owner_ref: IdentityRef
    description: Annotated[str, Field(min_length=1, max_length=1024)]
    tags: list[SkillTagPayload] = Field(default_factory=list)


class WorkflowCollectionChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["create", "revise", "fork"]
    definition: dict[str, Any]


class SaveWorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: dict[str, Any]
    collection_changes: list[WorkflowCollectionChangePayload] = Field(default_factory=list)


class WorkflowMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(max_length=160)]
    code: WorkflowMetadataText = ""
    description: WorkflowDescription
    symptom: WorkflowDescription = ""
    industry: WorkflowMetadataText = ""
    device: WorkflowMetadataText = ""
    versions: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(default_factory=list)


class SyncWorkflowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: SkillVersionSemVer
    display_name: VersionDisplayName | None = None
    change_summary: VersionChangeSummary
    expected_workflow_revision: Annotated[int, Field(gt=0)]
    generator_id: Annotated[str, Field(min_length=1, max_length=120)]
    generator_version: Annotated[str, Field(min_length=1, max_length=120)]
    generator_options: dict[str, Any]
    preview_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class WorkflowSyncPreviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_workflow_revision: Annotated[int, Field(gt=0)]
    generator_id: Annotated[str, Field(min_length=1, max_length=120)]
    generator_options: dict[str, Any]


class WorkflowExpressionOutputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    sample_count: Annotated[int, Field(alias="sampleCount", gt=0)]
    fields: dict[str, JsonSchema] = Field(default_factory=dict)
    schema_: JsonSchema | None = Field(default=None, alias="schema")


class WorkflowExpressionEnvironmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, JsonSchema] = Field(default_factory=dict)
    outputs: dict[str, WorkflowExpressionOutputPayload | dict[str, JsonSchema]] = Field(default_factory=dict)
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)


class WorkflowExpressionValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[str, Field(max_length=20_000)]
    environment: WorkflowExpressionEnvironmentPayload = Field(default_factory=WorkflowExpressionEnvironmentPayload)


class WorkflowExpressionBatchItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(min_length=1, max_length=200)]
    source: Annotated[str, Field(max_length=20_000)]


class WorkflowExpressionBatchValidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expressions: Annotated[list[WorkflowExpressionBatchItemPayload], Field(max_length=1000)] = Field(default_factory=list)
    environment: WorkflowExpressionEnvironmentPayload = Field(default_factory=WorkflowExpressionEnvironmentPayload)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "WorkflowExpressionBatchValidationPayload":
        ids = [item.id for item in self.expressions]
        if len(ids) != len(set(ids)):
            raise ValueError("Workflow expression batch IDs must be unique")
        return self


class WorkflowLogSchemaColumnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    duckdb_type: Literal["TIMESTAMP", "VARCHAR"]
    nullable: bool
    title: str
    description: str


class WorkflowLogSchemaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_schema_version: int
    dialect: Literal["duckdb"]
    logs_table: Literal["logs"]
    params_table: Literal["params"]
    columns: list[WorkflowLogSchemaColumnResponse]
