from __future__ import annotations

from typing import Any

from skillhub.models.errors import NotFoundError
from skillhub.models.schema import orm

ACTIVE_DEBUG_RUN_STATUSES = ("starting", "running", "paused", "external_state_unknown")


class WorkflowDebugHelperMixin:
    def _workflow_debug_case_row(self, session, case_id: str, *, for_update: bool = False):
        statement = orm.select_entity(orm.WorkflowDebugCase).where(orm.WorkflowDebugCase.id == case_id)
        if for_update:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"WorkflowDebugCase not found: {case_id}")
        return row

    def _workflow_debug_run_row(self, session, run_id: str, *, for_update: bool = False):
        statement = orm.select_entity(orm.WorkflowDebugRun).where(orm.WorkflowDebugRun.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"WorkflowDebugRun not found: {run_id}")
        return row

    def _debug_case_payload(self, row) -> dict[str, Any]:
        return self._row_dict(row)

    def _debug_run_payload(self, row) -> dict[str, Any]:
        return self._row_dict(row)


__all__ = ["ACTIVE_DEBUG_RUN_STATUSES", "WorkflowDebugHelperMixin"]
