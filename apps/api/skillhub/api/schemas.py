from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

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
EVAL_CASE_EXPECTED_OUTPUT_MAX_LENGTH = 10_000
EVAL_CASE_NOTES_MAX_LENGTH = 2_000
EVAL_CASE_ACTUAL_OUTPUT_MAX_LENGTH = 20_000
EVAL_CASE_ATTACHMENT_MAX_BASE64_LENGTH = 7_000_000
SAVED_VIEW_NAME_MAX_LENGTH = 80
ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH = 1_000
VERSION_CHANGE_SUMMARY_MAX_LENGTH = 1_000
VERSION_DISPLAY_NAME_MAX_LENGTH = 80

EvalCaseTitle = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_TITLE_MAX_LENGTH)]
EvalCaseInput = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_INPUT_MAX_LENGTH)]
EvalCaseExpectedOutput = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_EXPECTED_OUTPUT_MAX_LENGTH)]
EvalCaseNotes = Annotated[str, Field(max_length=EVAL_CASE_NOTES_MAX_LENGTH)]
EvalCaseActualOutput = Annotated[str, Field(max_length=EVAL_CASE_ACTUAL_OUTPUT_MAX_LENGTH)]
EvalCaseAttachmentBase64 = Annotated[str, Field(max_length=EVAL_CASE_ATTACHMENT_MAX_BASE64_LENGTH)]
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


class CreateEvalCasePayload(BaseModel):
    skill_id: str
    title: EvalCaseTitle
    input_text: EvalCaseInput
    expected_output: EvalCaseExpectedOutput
    attachment_name: str | None = None
    attachment_base64: EvalCaseAttachmentBase64 | None = None
    notes: EvalCaseNotes | None = None


class CreateEvalCaseItemPayload(BaseModel):
    title: EvalCaseTitle
    input_text: EvalCaseInput
    expected_output: EvalCaseExpectedOutput
    attachment_name: str | None = None
    attachment_base64: EvalCaseAttachmentBase64 | None = None
    notes: EvalCaseNotes | None = None


class CreateEvalCasesBatchPayload(BaseModel):
    skill_id: str
    cases: list[CreateEvalCaseItemPayload] = Field(min_length=1)


class CreateEvalCaseVersionPayload(BaseModel):
    case_id: str
    title: EvalCaseTitle | None = None
    input_text: EvalCaseInput
    expected_output: EvalCaseExpectedOutput
    attachment_name: str | None = None
    attachment_base64: EvalCaseAttachmentBase64 | None = None
    notes: EvalCaseNotes | None = None
    make_current: bool = True


class RestoreEvalCaseVersionPayload(BaseModel):
    source_case_version_id: str
    notes: EvalCaseNotes | None = None


class ManualEvalResultPayload(BaseModel):
    passed: bool
    actual_output: EvalCaseActualOutput = ""


class RecordEvalRunPayload(BaseModel):
    skill_version_id: str
    eval_set_id: str
    strategy: str = "manual_pass_fail"
    environment_tags: list[TagValue] = Field(default_factory=list)
    run_context: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, bool | ManualEvalResultPayload]


class EnqueueEvalCaseRunPayload(BaseModel):
    skill_version_id: str
    eval_set_id: str
    case_version_id: str
    strategy: str = "single_case"
    environment_tags: list[TagValue] = Field(default_factory=list)
    run_context: dict[str, Any] = Field(default_factory=dict)


class FinalizeEvalCaseRunPayload(BaseModel):
    passed: bool
    actual_output: EvalCaseActualOutput = ""


class AggregateEvalRunPayload(BaseModel):
    skill_version_id: str
    eval_set_id: str
    strategy: str = "manual_pass_fail"
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
