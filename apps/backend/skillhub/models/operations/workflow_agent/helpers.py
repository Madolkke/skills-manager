from __future__ import annotations

from typing import Any

from skillhub.models.errors import NotFoundError
from skillhub.models.schema import orm

ACTIVE_AGENT_RUN_STATUSES = ("starting", "running")


class WorkflowAgentHelperMixin:
    def _workflow_agent_session_row(self, session, session_id: str, *, actor: str | None = None, for_update: bool = False):
        statement = orm.select_entity(orm.WorkflowAgentSession).where(orm.WorkflowAgentSession.id == session_id)
        if actor is not None:
            statement = statement.where(orm.WorkflowAgentSession.actor_ref == actor)
        if for_update:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"WorkflowAgentSession not found: {session_id}")
        return row

    def _workflow_agent_run_row(self, session, run_id: str, *, for_update: bool = False):
        statement = orm.select_entity(orm.WorkflowAgentRun).where(orm.WorkflowAgentRun.id == run_id)
        if for_update:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"WorkflowAgentRun not found: {run_id}")
        return row

    def _workflow_agent_proposal_row(self, session, proposal_id: str, *, for_update: bool = False):
        statement = orm.select_entity(orm.WorkflowAgentProposal).where(orm.WorkflowAgentProposal.id == proposal_id)
        if for_update:
            statement = statement.with_for_update()
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"WorkflowAgentProposal not found: {proposal_id}")
        return row

    def _agent_session_payload(self, row) -> dict[str, Any]:
        return self._row_dict(row)

    def _agent_run_payload(self, row) -> dict[str, Any]:
        return self._row_dict(row)

    def _agent_proposal_payload(self, row) -> dict[str, Any]:
        return self._row_dict(row)


__all__ = ["ACTIVE_AGENT_RUN_STATUSES", "WorkflowAgentHelperMixin"]
