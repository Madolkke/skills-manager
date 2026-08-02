from __future__ import annotations

from skillhub.models.rules.executor_workflows import ExecutorWorkflow, convert_workflow_document
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class ExecutorWorkflowService(ServiceBase[SkillHubStore]):
    def current(self, *, skill_id: str) -> ExecutorWorkflow:
        """Convert the current saved authoring document for an executor."""
        document = self.store.executor_workflow_source(skill_id=skill_id)
        return convert_workflow_document(document)


__all__ = ["ExecutorWorkflowService"]
