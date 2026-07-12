from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from skillhub.views.request_models.common import EnvironmentTagValue


EVAL_CASE_TITLE_MAX_LENGTH = 160
EVAL_CASE_INPUT_MAX_LENGTH = 20_000
EVAL_CASE_NOTES_MAX_LENGTH = 2_000
EVAL_CASE_ACTUAL_OUTPUT_MAX_LENGTH = 20_000
EVAL_CASE_WORKSPACE_MAX_BASE64_LENGTH = 7_000_000
EVAL_SET_NAME_MAX_LENGTH = 120
EVAL_SET_DESCRIPTION_MAX_LENGTH = 1_000
ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH = 1_000

EvalCaseTitle = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_TITLE_MAX_LENGTH)]
EvalCaseInput = Annotated[str, Field(min_length=1, max_length=EVAL_CASE_INPUT_MAX_LENGTH)]
EvalCaseNotes = Annotated[str, Field(max_length=EVAL_CASE_NOTES_MAX_LENGTH)]
EvalCaseWorkspaceBase64 = Annotated[str, Field(max_length=EVAL_CASE_WORKSPACE_MAX_BASE64_LENGTH)]
EvalSetName = Annotated[str, Field(min_length=1, max_length=EVAL_SET_NAME_MAX_LENGTH)]
EvalSetDescription = Annotated[str, Field(max_length=EVAL_SET_DESCRIPTION_MAX_LENGTH)]
AcceptedVerificationNote = Annotated[str, Field(max_length=ACCEPTED_VERIFICATION_NOTE_MAX_LENGTH)]


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


class UpdateEvalSetPayload(CreateEvalSetPayload):
    pass


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
