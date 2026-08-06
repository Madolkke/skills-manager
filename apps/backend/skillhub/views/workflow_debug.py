from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Query

from skillhub.services import WorkflowDebugService
from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import workflow_debug_service_dependency
from skillhub.views.schemas import CreateWorkflowDebugCasePayload, UpdateWorkflowDebugCasePayload


def register_workflow_debug_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/workflow/debug-cases")
    def list_workflow_debug_cases(
        skill_id: str,
        step_id: str | None = None,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.list_cases(skill_id=skill_id, actor=actor.id, step_id=step_id)

    @app.post("/api/skills/{skill_id}/workflow/debug-cases")
    def create_workflow_debug_case(
        skill_id: str,
        payload: CreateWorkflowDebugCasePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.create_case(skill_id=skill_id, values=payload.model_dump(mode="json"), actor=actor.id)

    @app.get("/api/workflow-debug-cases/{case_id}")
    def workflow_debug_case(
        case_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.get_case(case_id=case_id, actor=actor.id)

    @app.patch("/api/workflow-debug-cases/{case_id}")
    def update_workflow_debug_case(
        case_id: str,
        payload: UpdateWorkflowDebugCasePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        values = payload.model_dump(mode="json", exclude_unset=True)
        return service.update_case(case_id=case_id, values=values, actor=actor.id)

    @app.delete("/api/workflow-debug-cases/{case_id}")
    def delete_workflow_debug_case(
        case_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.delete_case(case_id=case_id, actor=actor.id)

    @app.post("/api/workflow-debug-cases/{case_id}/runs")
    def start_workflow_debug_run(
        case_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.start_run(case_id=case_id, actor=actor.id)

    @app.get("/api/workflow-debug-cases/{case_id}/runs")
    def list_workflow_debug_runs(
        case_id: str,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.list_runs(case_id=case_id, actor=actor.id, cursor=cursor, limit=limit)

    @app.get("/api/workflow-debug-runs/{run_id}")
    def workflow_debug_run(
        run_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.get_run(run_id=run_id, actor=actor.id)

    @app.post("/api/workflow-debug-runs/{run_id}/advance")
    def advance_workflow_debug_run(
        run_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowDebugService = Depends(workflow_debug_service_dependency),
    ):
        return service.advance_run(run_id=run_id, actor=actor.id)


__all__ = ["register_workflow_debug_routes"]
