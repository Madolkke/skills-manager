"""分页读模型：业务元信息具有明确字段，扩展 JSON 保留原值。"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VersionSummary(ReadModel):
    id: str
    skill_id: str
    version_number: int
    version: str
    display_name: str | None
    content_ref: dict[str, Any]
    content_digest: str
    change_summary: str
    created_at: datetime
    created_by: str
    description: str | None = None
    workflow_sync: dict[str, Any] | None = None


class VersionDetail(VersionSummary):
    bundle_artifact: dict[str, Any] | None = None
    bundle_files: list[dict[str, Any]] = Field(default_factory=list)


class VersionDetailResponse(ReadModel):
    version: VersionDetail
    previous: VersionSummary | None


class SkillRecord(ReadModel):
    id: str
    slug: str
    display_name: str | None
    owner_ref: str
    current_version_id: str | None
    lifecycle_status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime
    tags: list[dict[str, Any]]


class RunSummary(ReadModel):
    id: str
    skill_id: str
    skill_version_id: str
    eval_set_id: str
    status: Literal["queued", "running", "finished", "failed"]
    environment_tags: list[str]
    run_context: dict[str, Any]
    run_context_hash: str
    summary: dict[str, Any]
    result_artifact_id: str | None
    created_at: datetime
    created_by: str


class SkillStatus(ReadModel):
    skill: SkillRecord
    current_version: VersionSummary | None
    primary_eval_set: dict[str, Any] | None
    latest_accepted_eval_run: RunSummary | None
    review_status: str
    publish_status: str


class SkillListItem(ReadModel):
    skill: SkillRecord
    summary: SkillStatus
    workflow: dict[str, Any] | None


class SkillCoreResponse(SkillListItem):
    version_count: int
    highest_version: VersionSummary | None
    eval_sets: list[dict[str, Any]]
    latest_eval_runs: list[RunSummary]
    role_assignments: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]
    capabilities: dict[str, Any] | None


class ReviewSummary(ReadModel):
    id: str
    skill_id: str
    skill_version_id: str
    status: Literal["open", "closed", "cancelled"]
    summary: dict[str, Any]
    closed_at: datetime | None
    closed_by: str | None
    created_at: datetime
    created_by: str
    skill_version: VersionSummary


class RunListItem(ReadModel):
    eval_run: RunSummary
    skill_version: VersionSummary
    eval_set: dict[str, Any]


class RoleSummary(ReadModel):
    id: str
    subject_type: Literal["user", "group"]
    subject_id: str
    resource_type: Literal["skill", "skill_tag", "global"]
    resource_id: str
    role: Literal["admin", "owner", "maintainer", "evaluator", "reviewer", "viewer"]
    created_at: datetime
    created_by: str
    resource_label: str
    resource_missing: bool


class AdminOverviewResponse(ReadModel):
    counts: dict[str, int]
    recent_tag_groups: list[dict[str, Any]]
    recent_roles: list[RoleSummary]


class GuidanceResponse(ReadModel):
    versions: list[VersionSummary]
    reviews: list[dict[str, Any]]
    publish_records: list[dict[str, Any]]
    eval_runs: list[RunSummary]
