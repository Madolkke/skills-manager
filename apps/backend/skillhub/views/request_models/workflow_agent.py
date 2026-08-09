from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from skillhub.models.rules.workflow_agent import WorkflowAgentDebugCaseCandidate


class CreateWorkflowAgentSessionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: Annotated[str, Field(max_length=160)] = ""


class WorkflowAgentSelectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)

    type: Annotated[str, Field(min_length=1, max_length=40)]
    id: Annotated[str, Field(max_length=200)] | None = None
    revision: Annotated[int, Field(gt=0)] | None = None
    section: Annotated[str, Field(max_length=80)] | None = None
    item_id: Annotated[str | None, Field(alias="itemId", max_length=200)] = None
    field: Annotated[str, Field(max_length=300)] | None = None


class StartWorkflowAgentRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    agent_id: Annotated[str, Field(min_length=1, max_length=80)]
    content: Annotated[str, Field(min_length=1, max_length=20_000)]
    base_revision: Annotated[int, Field(gt=0)]
    draft: dict[str, Any]
    selection: WorkflowAgentSelectionPayload


class ApplyWorkflowAgentProposalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidates: Annotated[list[WorkflowAgentDebugCaseCandidate], Field(min_length=1, max_length=10)]


class WorkflowAgentDescriptorResponse(BaseModel):
    id: str
    name: str
    description: str
    prompt_version: str
    tools: list[str]
    proposal_kind: str | None


class WorkflowAgentCatalogResponse(BaseModel):
    agents: list[WorkflowAgentDescriptorResponse]
    available: bool
    unavailable_reason: str
    agentscope_version: Literal["2.0.6"]


class WorkflowAgentSessionResponse(BaseModel):
    id: str
    skill_id: str
    actor_ref: str
    title: str
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime


class WorkflowAgentProposalResponse(BaseModel):
    id: str
    run_id: str
    skill_id: str
    kind: Literal["debug_case_draft"]
    status: Literal["proposed", "applied", "stale"]
    payload: dict[str, Any]
    base_revision: int
    base_workflow_digest: str
    draft_digest: str
    applied_result: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime


class WorkflowAgentRunResponse(BaseModel):
    id: str
    session_id: str
    skill_id: str
    agent_id: str
    status: Literal["starting", "running", "completed", "failed", "canceled", "interrupted"]
    user_input: str
    response_text: str
    selection: dict[str, Any]
    base_revision: int
    base_workflow_digest: str
    draft_digest: str
    cancel_requested: bool
    usage: dict[str, Any]
    error: dict[str, Any] | None
    created_by: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    proposal: WorkflowAgentProposalResponse | None


class WorkflowAgentApplyResponse(BaseModel):
    proposal: WorkflowAgentProposalResponse
    created_cases: list[dict[str, Any]]
    stale: bool


class DeletedResponse(BaseModel):
    deleted: bool


__all__ = [
    "ApplyWorkflowAgentProposalPayload",
    "CreateWorkflowAgentSessionPayload",
    "DeletedResponse",
    "StartWorkflowAgentRunPayload",
    "WorkflowAgentApplyResponse",
    "WorkflowAgentCatalogResponse",
    "WorkflowAgentRunResponse",
    "WorkflowAgentSessionResponse",
]
