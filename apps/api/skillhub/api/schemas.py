from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from skillhub.domain.models import ContentRef
from skillhub.domain.semver import SEMVER_PATTERN


SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
TAG_PATTERN = r"^[A-Za-z0-9._-]+$"
IDENTITY_REF_PATTERN = r"^[A-Za-z0-9._@-]{1,120}$"
SkillSlug = Annotated[str, Field(min_length=1, max_length=64, pattern=SLUG_PATTERN)]
TagValue = Annotated[str, Field(min_length=1, max_length=64, pattern=TAG_PATTERN)]
IdentityRef = Annotated[str, Field(min_length=1, max_length=120, pattern=IDENTITY_REF_PATTERN)]

EVAL_CASE_TITLE_MAX_LENGTH = 160
EVAL_CASE_INPUT_MAX_LENGTH = 20_000
EVAL_CASE_NOTES_MAX_LENGTH = 2_000
EVAL_CASE_ACTUAL_OUTPUT_MAX_LENGTH = 20_000
EVAL_CASE_WORKSPACE_MAX_BASE64_LENGTH = 7_000_000
EVAL_SET_NAME_MAX_LENGTH = 120
EVAL_SET_DESCRIPTION_MAX_LENGTH = 1_000
SAVED_VIEW_NAME_MAX_LENGTH = 80
ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH = 1_000
VERSION_CHANGE_SUMMARY_MAX_LENGTH = 1_000
VERSION_DISPLAY_NAME_MAX_LENGTH = 80

EvalCaseTitle = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_TITLE_MAX_LENGTH)]
EvalCaseInput = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_INPUT_MAX_LENGTH)]
EvalCaseNotes = Annotated[str, Field(max_length=EVAL_CASE_NOTES_MAX_LENGTH)]
EvalCaseWorkspaceBase64 = Annotated[str, Field(max_length=EVAL_CASE_WORKSPACE_MAX_BASE64_LENGTH)]
EvalSetName = Annotated[str, Field(min_length=1, max_length=EVAL_SET_NAME_MAX_LENGTH)]
EvalSetDescription = Annotated[str, Field(max_length=EVAL_SET_DESCRIPTION_MAX_LENGTH)]
SavedViewName = Annotated[str, Field(min_length=1, max_length=SAVED_VIEW_NAME_MAX_LENGTH)]
AcceptedVerificationNote = Annotated[str, Field(max_length=ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH)]
VersionChangeSummary = Annotated[str, Field(min_length=1, max_length=VERSION_CHANGE_SUMMARY_MAX_LENGTH)]
VersionDisplayName = Annotated[str, Field(min_length=1, max_length=VERSION_DISPLAY_NAME_MAX_LENGTH)]
SkillVersionSemVer = Annotated[str, Field(min_length=5, max_length=80, pattern=SEMVER_PATTERN)]


class ContentRefPayload(BaseModel):
    kind: str
    locator: str
    digest: str
    path: str | None = None


class CreateSkillPayload(BaseModel):
    slug: SkillSlug
    owner_ref: IdentityRef
    content_ref: ContentRefPayload
    change_summary: VersionChangeSummary
    display_name: VersionDisplayName | None = None
    version: SkillVersionSemVer | None = None


class ImportSkillPayload(BaseModel):
    owner_ref: IdentityRef
    source: dict[str, Any]
    display_name: VersionDisplayName | None = None
    version: SkillVersionSemVer | None = None


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


class AssignSkillRolePayload(BaseModel):
    subject_id: IdentityRef
    role: str
    subject_type: str = "user"


class EvalStepAssertionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    assertion_template_id: str = "agent_output_semantic"
    assertion_params: dict[str, Any] = Field(default_factory=dict)


class EvalCaseStepPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    title: str | None = None
    input: EvalCaseInput
    assertions: list[EvalStepAssertionPayload] = Field(min_length=1)


class EvalCaseRunnerConfigPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_provider_id: str | None = None
    model_id: str | None = None
    timeout_seconds: int | None = None


class CreateEvalCasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    eval_set_id: str
    title: EvalCaseTitle
    steps: list[EvalCaseStepPayload] = Field(min_length=1)
    workspace_name: str | None = None
    workspace_base64: EvalCaseWorkspaceBase64 | None = None
    runner_config: EvalCaseRunnerConfigPayload = Field(default_factory=EvalCaseRunnerConfigPayload)
    notes: EvalCaseNotes | None = None


class CreateEvalCaseItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: EvalCaseTitle
    steps: list[EvalCaseStepPayload] = Field(min_length=1)
    workspace_name: str | None = None
    workspace_base64: EvalCaseWorkspaceBase64 | None = None
    runner_config: EvalCaseRunnerConfigPayload = Field(default_factory=EvalCaseRunnerConfigPayload)
    notes: EvalCaseNotes | None = None


class CreateEvalCasesBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    eval_set_id: str
    cases: list[CreateEvalCaseItemPayload] = Field(min_length=1)


class CreateEvalCaseVersionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    eval_set_id: str
    title: EvalCaseTitle | None = None
    steps: list[EvalCaseStepPayload] = Field(min_length=1)
    workspace_name: str | None = None
    workspace_base64: EvalCaseWorkspaceBase64 | None = None
    preserve_workspace: bool = True
    runner_config: EvalCaseRunnerConfigPayload = Field(default_factory=EvalCaseRunnerConfigPayload)
    notes: EvalCaseNotes | None = None
    make_current: bool = True


class RestoreEvalCaseVersionPayload(BaseModel):
    source_case_version_id: str
    eval_set_id: str | None = None
    notes: EvalCaseNotes | None = None


class CreateEvalSetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: EvalSetName
    description: EvalSetDescription = ""


class UpdateEvalSetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: EvalSetName
    description: EvalSetDescription = ""


class AddEvalSetCasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    position: int | None = None


class ReorderEvalSetCasesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_ids: list[str]


class EnqueueEvalCaseRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_version_id: str
    eval_set_id: str
    case_version_id: str
    environment_tags: list[TagValue] = Field(default_factory=list)
    run_context: dict[str, Any] = Field(default_factory=dict)


class ListEvalCaseRunsQuery(BaseModel):
    skill_version_id: str
    eval_set_id: str
    environment_tags: list[TagValue] | None = None
    run_context: dict[str, Any] | None = None


class AggregateEvalRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_version_id: str
    eval_set_id: str
    environment_tags: list[TagValue] = Field(default_factory=list)
    run_context: dict[str, Any] = Field(default_factory=dict)


class AcceptEvalRunVerificationPayload(BaseModel):
    eval_run_id: str
    note: AcceptedVerificationNote = ""


class CreateSavedViewPayload(BaseModel):
    skill_id: str
    name: SavedViewName
    view_type: str = "run_history"
    config: dict[str, str] = Field(default_factory=dict)


class SetSessionPayload(BaseModel):
    actor: str
    access_code: str


def content_ref(payload: ContentRefPayload) -> ContentRef:
    return ContentRef(kind=payload.kind, locator=payload.locator, digest=payload.digest, path=payload.path)  # type: ignore[arg-type]
