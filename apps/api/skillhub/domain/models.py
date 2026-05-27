from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4


ContentKind = Literal["inline_bundle", "skill_bundle", "artifact", "git", "external_repo"]
EvalRunStatus = Literal["queued", "running", "finished", "failed"]
LifecycleStatus = Literal["active", "archived"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_tags(tags: list[str]) -> tuple[str, ...]:
    return tuple(sorted({tag.strip() for tag in tags if tag.strip()}))


def digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContentRef:
    kind: ContentKind
    locator: str
    digest: str
    path: str | None = None


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    kind: str
    locator: str
    digest: str
    media_type: str


@dataclass(frozen=True)
class Skill:
    id: str
    slug: str
    owner_ref: str
    current_version_id: str | None
    created_at: datetime
    lifecycle_status: LifecycleStatus = "active"


@dataclass(frozen=True)
class SkillVersion:
    id: str
    skill_id: str
    version_number: int
    content_ref: ContentRef
    change_summary: str
    created_at: datetime
    created_by: str
    display_name: str | None = None


@dataclass(frozen=True)
class EvalSet:
    id: str
    skill_id: str
    name: str
    description: str
    current_version_id: str | None
    created_at: datetime
    lifecycle_status: LifecycleStatus = "active"


@dataclass(frozen=True)
class EvalSetVersion:
    id: str
    eval_set_id: str
    version_number: int
    case_version_ids: tuple[str, ...]
    created_at: datetime
    display_name: str | None = None


@dataclass(frozen=True)
class EvalCase:
    id: str
    skill_id: str
    title: str
    current_version_id: str
    created_at: datetime
    lifecycle_status: LifecycleStatus = "active"


@dataclass(frozen=True)
class EvalCaseVersion:
    id: str
    case_id: str
    version_number: int
    input_ref: ArtifactRef
    expected_output_ref: ArtifactRef
    notes: str | None
    created_at: datetime


@dataclass(frozen=True)
class EvalRun:
    id: str
    skill_version_id: str
    eval_set_version_id: str
    strategy: str
    status: EvalRunStatus
    created_at: datetime
    created_by: str
    environment_tags: tuple[str, ...] = ()
    run_context: dict[str, Any] | None = None
    run_context_hash: str = ""


@dataclass(frozen=True)
class CaseResult:
    run_id: str
    case_version_id: str
    passed: bool
    score: int
