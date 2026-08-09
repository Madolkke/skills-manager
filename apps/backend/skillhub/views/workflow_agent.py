from __future__ import annotations

import json
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, Query
from fastapi.responses import StreamingResponse

from skillhub.services import WorkflowAgentService
from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import workflow_agent_service_dependency
from skillhub.views.schemas import (
    ApplyWorkflowAgentProposalPayload,
    CreateWorkflowAgentSessionPayload,
    DeletedResponse,
    StartWorkflowAgentRunPayload,
    WorkflowAgentApplyResponse,
    WorkflowAgentCatalogResponse,
    WorkflowAgentRunResponse,
    WorkflowAgentSessionResponse,
)


def register_workflow_agent_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/workflow/agents", response_model=WorkflowAgentCatalogResponse)
    def workflow_agent_catalog(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.catalog(skill_id=skill_id, actor=actor.id)

    @app.get("/api/skills/{skill_id}/workflow/agent-sessions", response_model=list[WorkflowAgentSessionResponse])
    def list_workflow_agent_sessions(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.list_sessions(skill_id=skill_id, actor=actor.id)

    @app.post("/api/skills/{skill_id}/workflow/agent-sessions", response_model=WorkflowAgentSessionResponse)
    def create_workflow_agent_session(
        skill_id: str,
        payload: CreateWorkflowAgentSessionPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.create_session(skill_id=skill_id, actor=actor.id, title=payload.title)

    @app.get("/api/workflow-agent-sessions/{session_id}/runs", response_model=list[WorkflowAgentRunResponse])
    def list_workflow_agent_runs(
        session_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.list_runs(session_id=session_id, actor=actor.id)

    @app.post("/api/workflow-agent-sessions/{session_id}/runs", response_model=WorkflowAgentRunResponse)
    def start_workflow_agent_run(
        session_id: str,
        payload: StartWorkflowAgentRunPayload,
        background_tasks: BackgroundTasks,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        run = service.create_run(
            session_id=session_id,
            agent_id=payload.agent_id,
            content=payload.content,
            base_revision=payload.base_revision,
            draft=payload.draft,
            selection=payload.selection.model_dump(mode="json", by_alias=True, exclude_none=True),
            actor=actor.id,
        )
        background_tasks.add_task(service.schedule_run, run["id"])
        return run

    @app.get("/api/workflow-agent-runs/{run_id}", response_model=WorkflowAgentRunResponse)
    def workflow_agent_run(
        run_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.get_run(run_id=run_id, actor=actor.id)

    @app.get("/api/workflow-agent-runs/{run_id}/events")
    async def workflow_agent_events(
        run_id: str,
        after: Annotated[int, Query(ge=0)] = 0,
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        run = service.get_run(run_id=run_id, actor=actor.id)
        cursor = _event_cursor(after, last_event_id)

        async def stream():
            async for event in service.event_stream(run_id=run_id, actor=actor.id, after=cursor):
                if event is None:
                    yield ": keep-alive\n\n"
                    continue
                envelope = {
                    "event_id": event["sequence"],
                    "session_id": run["session_id"],
                    "run_id": run_id,
                    "event": event["payload"],
                }
                yield f"id: {event['sequence']}\nevent: agentscope\ndata: {json.dumps(envelope, ensure_ascii=False, separators=(',', ':'))}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/workflow-agent-runs/{run_id}/cancel", response_model=WorkflowAgentRunResponse)
    def cancel_workflow_agent_run(
        run_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.cancel_run(run_id=run_id, actor=actor.id)

    @app.post("/api/workflow-agent-sessions/{session_id}/archive", response_model=WorkflowAgentSessionResponse)
    def archive_workflow_agent_session(
        session_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.archive_session(session_id=session_id, actor=actor.id)

    @app.delete("/api/workflow-agent-sessions/{session_id}", response_model=DeletedResponse)
    async def delete_workflow_agent_session(
        session_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return await service.delete_session(session_id=session_id, actor=actor.id)

    @app.post("/api/workflow-agent-proposals/{proposal_id}/apply", response_model=WorkflowAgentApplyResponse)
    def apply_workflow_agent_proposal(
        proposal_id: str,
        payload: ApplyWorkflowAgentProposalPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowAgentService = Depends(workflow_agent_service_dependency),
    ):
        return service.apply_proposal(
            proposal_id=proposal_id,
            candidates=[item.model_dump(mode="json") for item in payload.candidates],
            actor=actor.id,
        )


def _event_cursor(after: int, last_event_id: str | None) -> int:
    if not last_event_id:
        return after
    try:
        return max(after, int(last_event_id))
    except ValueError:
        return after


__all__ = ["register_workflow_agent_routes"]
