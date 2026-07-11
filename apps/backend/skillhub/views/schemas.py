from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from skillhub.models.entities import ContentRef
from skillhub.models.rules.semver import SEMVER_PATTERN


SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
TAG_GROUP_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
ENV_TAG_PATTERN = r"^[A-Za-z0-9._-]+$"
IDENTITY_REF_PATTERN = r"^[A-Za-z0-9._@-]{1,120}$"
OPENCODE_AGENT_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
SkillSlug = Annotated[str, Field(min_length=1, max_length=64, pattern=SLUG_PATTERN)]
TagGroupId = Annotated[str, Field(min_length=1, max_length=80, pattern=TAG_GROUP_ID_PATTERN)]
OpencodeAgentId = Annotated[str, Field(min_length=1, max_length=80, pattern=OPENCODE_AGENT_ID_PATTERN)]
TagValue = Annotated[str, Field(min_length=1)]
EnvironmentTagValue = Annotated[str, Field(min_length=1, max_length=64, pattern=ENV_TAG_PATTERN)]
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
SKILL_BUILDER_MESSAGE_MAX_LENGTH = 20_000
SKILL_BUILDER_FILE_CONTENT_MAX_LENGTH = 200_000

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
SkillBuilderMessageText = Annotated[str, Field(min_length=1, max_length=SKILL_BUILDER_MESSAGE_MAX_LENGTH)]
SkillBuilderFileContent = Annotated[str, Field(max_length=SKILL_BUILDER_FILE_CONTENT_MAX_LENGTH)]


class ContentRefPayload(BaseModel):
    kind: str
    locator: str
    digest: str
    path: str | None = None


class SkillTagPayload(BaseModel):
    group_id: TagGroupId
    value: TagValue


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


class AssignSkillRolePayload(BaseModel):
    subject_id: str
    role: str
    subject_type: str = "user"


class ReviewPublishTargetPayload(BaseModel):
    publish_target_id: str
    auto_submit_on_pass: bool = True


class ReviewSubjectPayload(BaseModel):
    subject_type: Literal["user", "group"] = "user"
    subject_id: IdentityRef


class CreateReviewRequestPayload(BaseModel):
    skill_version_id: str
    publish_targets: list[ReviewPublishTargetPayload] = Field(default_factory=list)
    reviewer_sources: list[ReviewSubjectPayload] = Field(default_factory=list)


class SubmitReviewResponsePayload(BaseModel):
    score: int = Field(ge=-1, le=1)
    comment: Annotated[str, Field(max_length=4000)] = ""


class NotificationUpdatePayload(BaseModel):
    read: bool = True


class CreatePublishRecordPayload(BaseModel):
    skill_version_id: str
    review_request_id: str
    publish_target_id: str


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


class CreateSkillBuilderSessionPayload(BaseModel):
    title: Annotated[str, Field(max_length=160)] | None = None
    replace_running: bool = False


class SkillBuilderMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: SkillBuilderMessageText
    intent: str = "chat"
    provider_id: Annotated[str, Field(max_length=120)] | None = None
    model_id: Annotated[str, Field(max_length=120)] | None = None


class SkillBuilderDraftFilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Annotated[str, Field(min_length=1, max_length=240)]
    content_text: SkillBuilderFileContent


class UpdateSkillBuilderDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[SkillBuilderDraftFilePayload] = Field(min_length=1, max_length=100)


class UpdateSkillBuilderWorkspacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[SkillBuilderDraftFilePayload] = Field(default_factory=list, max_length=100)


class CreateSkillFromBuilderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: SkillVersionSemVer
    tags: list[SkillTagPayload] = Field(default_factory=list)
    files: list[SkillBuilderDraftFilePayload] | None = Field(default=None, max_length=100)


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
    model_config = ConfigDict(extra="ignore")

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
    environment_tags: list[EnvironmentTagValue] = Field(default_factory=list)
    run_context: dict[str, Any] = Field(default_factory=dict)


class ListEvalCaseRunsQuery(BaseModel):
    skill_version_id: str
    eval_set_id: str
    environment_tags: list[EnvironmentTagValue] | None = None
    run_context: dict[str, Any] | None = None


class AggregateEvalRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_version_id: str
    eval_set_id: str
    environment_tags: list[EnvironmentTagValue] = Field(default_factory=list)
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
