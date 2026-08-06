from __future__ import annotations

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase
from skillhub.services.workflow_debug_cases import WorkflowDebugCaseServiceMixin
from skillhub.services.workflow_debug_runs import WorkflowDebugRunServiceMixin
from skillhub.services.workflow_debug_runtime import ExecutorClientFactory, WorkflowDebugSettings, create_executor_client


class WorkflowDebugService(WorkflowDebugCaseServiceMixin, WorkflowDebugRunServiceMixin, ServiceBase[SkillHubStore]):
    def __init__(
        self,
        store: SkillHubStore,
        settings: WorkflowDebugSettings,
        client_factory: ExecutorClientFactory = create_executor_client,
    ) -> None:
        super().__init__(store)
        self.settings = settings
        self.client_factory = client_factory


__all__ = ["WorkflowDebugService"]
