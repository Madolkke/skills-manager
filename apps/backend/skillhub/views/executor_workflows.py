from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.models.rules.executor_workflows import ExecutorWorkflow
from skillhub.services import ExecutorWorkflowService
from skillhub.views.dependencies import executor_workflow_service_dependency


def register_executor_workflow_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/workflow/executor", response_model=ExecutorWorkflow)
    def executor_workflow(
        skill_id: str,
        service: ExecutorWorkflowService = Depends(executor_workflow_service_dependency),
    ) -> ExecutorWorkflow:
        return service.current(skill_id=skill_id)


__all__ = ["register_executor_workflow_routes"]
