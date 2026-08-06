from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

WorkflowDebugScalar = str | int | float | bool | None
DebugName = Annotated[str, Field(min_length=1)]
DebugDescription = str
DebugId = Annotated[str, Field(min_length=1)]


class WorkflowDebugCollectionFixturePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_output: list[str] = Field(default_factory=list)
    outputs: dict[str, WorkflowDebugScalar] = Field(default_factory=dict)


class CreateWorkflowDebugCasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    step_id: DebugId
    name: DebugName
    description: DebugDescription = ""
    expected_target_id: DebugId
    workflow_inputs: dict[str, WorkflowDebugScalar] = Field(default_factory=dict)
    collection_fixtures: dict[str, WorkflowDebugCollectionFixturePayload] = Field(default_factory=dict)


class UpdateWorkflowDebugCasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: DebugName | None = None
    description: DebugDescription | None = None
    expected_target_id: DebugId | None = None
    workflow_inputs: dict[str, WorkflowDebugScalar] | None = None
    collection_fixtures: dict[str, WorkflowDebugCollectionFixturePayload] | None = None


__all__ = ["CreateWorkflowDebugCasePayload", "UpdateWorkflowDebugCasePayload", "WorkflowDebugCollectionFixturePayload"]
