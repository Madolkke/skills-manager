from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from skillhub.views.request_models.common import (
    ContentRefPayload,
    IdentityRef,
    SkillSlug,
    SkillTagPayload,
    SkillVersionSemVer,
    VersionChangeSummary,
    VersionDisplayName,
)


class ExternalSkillUpsertTagsPayload(BaseModel):
    tags: list[SkillTagPayload] = Field(min_length=1)


class CreateSkillPayload(BaseModel):
    slug: SkillSlug
    owner_ref: IdentityRef
    content_ref: ContentRefPayload
    change_summary: VersionChangeSummary
    version: SkillVersionSemVer | None = None
    tags: list[SkillTagPayload] = Field(default_factory=list)


class ImportSkillPayload(BaseModel):
    owner_ref: IdentityRef
    source: dict[str, Any]
    version: SkillVersionSemVer | None = None
    tags: list[SkillTagPayload] = Field(default_factory=list)


class CreateSkillVersionPayload(BaseModel):
    skill_id: str
    content_ref: ContentRefPayload | None = None
    source: dict[str, Any] | None = None
    change_summary: VersionChangeSummary | None = None
    display_name: VersionDisplayName | None = None
    version: SkillVersionSemVer | None = None
    make_current: bool = False


class UpdateVersionDisplayNamePayload(BaseModel):
    display_name: VersionDisplayName | None = None


class UpdateSkillPayload(BaseModel):
    slug: SkillSlug
    owner_ref: IdentityRef
    tags: list[SkillTagPayload] | None = None


class DeleteSkillPayload(BaseModel):
    confirmation_slug: str


class AssignSkillRolePayload(BaseModel):
    subject_id: str
    role: str
    subject_type: str = "user"
