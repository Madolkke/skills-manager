from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
