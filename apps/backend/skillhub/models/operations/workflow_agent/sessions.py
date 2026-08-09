from __future__ import annotations

from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError
from skillhub.models.operations.workflow_agent.helpers import ACTIVE_AGENT_RUN_STATUSES, WorkflowAgentHelperMixin
from skillhub.models.schema import orm


class WorkflowAgentSessionMixin(WorkflowAgentHelperMixin):
    def require_workflow_agent_access(self, *, skill_id: str, actor: str) -> None:
        with self._read_session() as session:
            self._skill_row(session, skill_id)
            self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")

    def list_workflow_agent_sessions(self, *, skill_id: str, actor: str) -> list[dict[str, Any]]:
        with self._read_session() as session:
            self._skill_row(session, skill_id)
            self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")
            rows = (
                session.execute(
                    orm.select_entity(orm.WorkflowAgentSession)
                    .where(orm.WorkflowAgentSession.skill_id == skill_id)
                    .where(orm.WorkflowAgentSession.actor_ref == actor)
                    .order_by(orm.WorkflowAgentSession.updated_at.desc(), orm.WorkflowAgentSession.id.desc())
                )
                .mappings()
                .all()
            )
            return [self._agent_session_payload(row) for row in rows]

    def create_workflow_agent_session(self, *, skill_id: str, actor: str, title: str) -> dict[str, Any]:
        now = utc_now()
        with self._write_session() as session:
            self._skill_row(session, skill_id)
            self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")
            existing = (
                session.execute(
                    orm.select_entity(orm.WorkflowAgentSession)
                    .where(orm.WorkflowAgentSession.skill_id == skill_id)
                    .where(orm.WorkflowAgentSession.actor_ref == actor)
                    .where(orm.WorkflowAgentSession.status == "active")
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                return self._agent_session_payload(existing)
            row = {
                "id": new_id("workflow_agent_session"),
                "skill_id": skill_id,
                "actor_ref": actor,
                "title": title,
                "status": "active",
                "agentscope_sessions": {},
                "created_at": now,
                "updated_at": now,
            }
            try:
                session.execute(insert(orm.WorkflowAgentSession).values(**row))
            except IntegrityError as exc:
                raise ConflictError("A Workflow Agent session is already active.") from exc
            return row

    def archive_workflow_agent_session(self, *, session_id: str, actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_agent_session_row(session, session_id, actor=actor, for_update=True)
            self._require_skill_permission(session, skill_id=current["skill_id"], actor=actor, permission="skill.edit")
            active = session.execute(
                select(orm.WorkflowAgentRun.id)
                .where(orm.WorkflowAgentRun.session_id == session_id)
                .where(orm.WorkflowAgentRun.status.in_(ACTIVE_AGENT_RUN_STATUSES))
                .limit(1)
            ).scalar_one_or_none()
            if active is not None:
                raise ConflictError("Cannot archive a Workflow Agent session while a run is active.")
            changes = {"status": "archived", "updated_at": utc_now()}
            session.execute(update(orm.WorkflowAgentSession).where(orm.WorkflowAgentSession.id == session_id).values(**changes))
            return {**self._agent_session_payload(current), **changes}

    def delete_workflow_agent_session(self, *, session_id: str, actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_agent_session_row(session, session_id, actor=actor, for_update=True)
            self._require_skill_permission(session, skill_id=current["skill_id"], actor=actor, permission="skill.edit")
            if current["status"] != "archived":
                raise ConflictError("Archive the Workflow Agent session before deleting it.")
            session.execute(delete(orm.WorkflowAgentSession).where(orm.WorkflowAgentSession.id == session_id))
            return {"deleted": True, "agentscope_sessions": dict(current["agentscope_sessions"]), "actor_ref": current["actor_ref"]}

    def update_workflow_agent_scope_session(self, *, session_id: str, agent_id: str, agentscope_session_id: str) -> None:
        with self._write_session() as session:
            current = self._workflow_agent_session_row(session, session_id, for_update=True)
            mapping = dict(current["agentscope_sessions"])
            mapping[agent_id] = agentscope_session_id
            session.execute(
                update(orm.WorkflowAgentSession)
                .where(orm.WorkflowAgentSession.id == session_id)
                .values(agentscope_sessions=mapping, updated_at=utc_now())
            )

    def _workflow_agent_session_for_runtime(self, *, session_id: str) -> dict[str, Any]:
        with self._read_session() as session:
            return self._agent_session_payload(self._workflow_agent_session_row(session, session_id))


__all__ = ["WorkflowAgentSessionMixin"]
