from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from skillhub.views.request_models.common import IdentityRef, OpencodeAgentId, SkillSlug, SkillTagPayload, TagGroupId, TagValue


class AdminPublishTargetUpdatePayload(BaseModel):
    enabled: bool = True
    auto_publish_enabled: bool = False
    gate_expression: dict[str, Any] = Field(default_factory=dict)


class OpencodeAgentPermissionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bash: bool = False
    edit: bool = False
    glob: bool = False
    grep: bool = False
    list: bool = False
    read: bool = False
    write: bool = False


class AdminOpencodeAgentPayload(BaseModel):
    id: OpencodeAgentId | None = None
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=1000)] = ""
    prompt: Annotated[str, Field(min_length=1, max_length=20000)]
    enabled: bool = True
    permission: OpencodeAgentPermissionPayload = Field(default_factory=OpencodeAgentPermissionPayload)
    provider_id: Annotated[str, Field(max_length=120)] | None = None
    model_id: Annotated[str, Field(max_length=120)] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    steps: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(default_factory=list, max_length=20)


class AdminOpencodeAgentCreatePayload(AdminOpencodeAgentPayload):
    id: OpencodeAgentId


class SkillGroupPayload(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=1000)] = ""


class SkillGroupMemberPayload(BaseModel):
    subject_id: str
    subject_type: str = "user"


class AdminGroupPayload(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=1000)] = ""


class AdminGroupMemberPayload(BaseModel):
    subject_id: str
    subject_type: str = "user"


class AdminRoleAssignmentPayload(BaseModel):
    subject_type: str = "user"
    subject_id: str
    resource_type: str
    resource_id: str
    role: str


class AdminTagGroupPayload(BaseModel):
    id: TagGroupId
    display_name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=1000)] = ""
    sort_order: int = 0
    required: bool = False
    free_form: bool = False


class AdminTagGroupUpdatePayload(BaseModel):
    display_name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=1000)] = ""
    sort_order: int = 0
    required: bool = False
    free_form: bool = False


class AdminTagValuePayload(BaseModel):
    value: TagValue
    display_name: Annotated[str, Field(max_length=120)] | None = None
    description: Annotated[str, Field(max_length=1000)] = ""
    sort_order: int = 0


class AdminTagCascadePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_group_id: TagGroupId
    parent_value: TagValue
    child_group_id: TagGroupId


class AdminSkillUpdatePayload(BaseModel):
    slug: SkillSlug | None = None
    owner_ref: IdentityRef | None = None
    tags: list[SkillTagPayload] | None = None
