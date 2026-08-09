from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError
from skillhub.models.operations.workflow_agent.helpers import ACTIVE_AGENT_RUN_STATUSES, WorkflowAgentHelperMixin
from skillhub.models.schema import orm


class WorkflowAgentRunMixin(WorkflowAgentHelperMixin):
    def workflow_agent_run_source(self, *, session_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as session:
            agent_session = self._workflow_agent_session_row(session, session_id, actor=actor)
            self._require_skill_permission(session, skill_id=agent_session["skill_id"], actor=actor, permission="skill.edit")
            workflow = self._workflow_row(session, skill_id=agent_session["skill_id"])
            recent = (
                session.execute(
                    orm.select_entity(orm.WorkflowAgentRun)
                    .where(orm.WorkflowAgentRun.session_id == session_id)
                    .where(orm.WorkflowAgentRun.status == "completed")
                    .order_by(orm.WorkflowAgentRun.created_at.desc())
                    .limit(6)
                )
                .mappings()
                .all()
            )
            return {
                "session": self._agent_session_payload(agent_session),
                "workflow_revision": int(workflow["revision"]),
                "workflow_digest": str(workflow["document_digest"]),
                "workflow_id": str(workflow["id"]),
                "recent_history": [
                    {"agent_id": row["agent_id"], "user_input": row["user_input"], "response_text": row["response_text"]}
                    for row in reversed(recent)
                ],
            }

    def insert_workflow_agent_run(self, *, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {"id": new_id("workflow_agent_run"), **values, "created_at": now, "updated_at": now}
        try:
            with self._write_session() as session:
                session.execute(insert(orm.WorkflowAgentRun).values(**row))
        except IntegrityError as exc:
            raise ConflictError("A Workflow Agent run is already active for this session.") from exc
        return row

    def workflow_agent_run(self, *, run_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as session:
            row = self._workflow_agent_run_row(session, run_id)
            self._require_skill_permission(session, skill_id=row["skill_id"], actor=actor, permission="skill.edit")
            return self._agent_run_payload(row)

    def list_workflow_agent_runs(self, *, session_id: str, actor: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._read_session() as session:
            agent_session = self._workflow_agent_session_row(session, session_id, actor=actor)
            self._require_skill_permission(session, skill_id=agent_session["skill_id"], actor=actor, permission="skill.edit")
            rows = (
                session.execute(
                    orm.select_entity(orm.WorkflowAgentRun)
                    .where(orm.WorkflowAgentRun.session_id == session_id)
                    .order_by(orm.WorkflowAgentRun.created_at.desc())
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            return [self._agent_run_payload(row) for row in reversed(rows)]

    def workflow_agent_run_internal(self, *, run_id: str) -> dict[str, Any]:
        with self._read_session() as session:
            return self._agent_run_payload(self._workflow_agent_run_row(session, run_id))

    def start_workflow_agent_run(self, *, run_id: str) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_agent_run_row(session, run_id, for_update=True)
            if current["status"] != "starting":
                return self._agent_run_payload(current)
            changes = {"status": "running", "started_at": utc_now(), "updated_at": utc_now()}
            session.execute(update(orm.WorkflowAgentRun).where(orm.WorkflowAgentRun.id == run_id).values(**changes))
            return {**self._agent_run_payload(current), **changes}

    def finish_workflow_agent_run(
        self,
        *,
        run_id: str,
        status: str,
        response_text: str = "",
        usage: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_agent_run_row(session, run_id, for_update=True)
            if current["status"] not in ACTIVE_AGENT_RUN_STATUSES:
                return self._agent_run_payload(current)
            changes = {
                "status": status,
                "response_text": response_text,
                "usage": usage or dict(current["usage"]),
                "error": error,
                "finished_at": utc_now(),
                "updated_at": utc_now(),
            }
            session.execute(update(orm.WorkflowAgentRun).where(orm.WorkflowAgentRun.id == run_id).values(**changes))
            return {**self._agent_run_payload(current), **changes}

    def request_workflow_agent_cancel(self, *, run_id: str, actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_agent_run_row(session, run_id, for_update=True)
            self._require_skill_permission(session, skill_id=current["skill_id"], actor=actor, permission="skill.edit")
            if current["status"] not in ACTIVE_AGENT_RUN_STATUSES:
                return self._agent_run_payload(current)
            changes = {"cancel_requested": True, "updated_at": utc_now()}
            session.execute(update(orm.WorkflowAgentRun).where(orm.WorkflowAgentRun.id == run_id).values(**changes))
            return {**self._agent_run_payload(current), **changes}

    def workflow_agent_cancel_requested(self, *, run_id: str) -> bool:
        with self._read_session() as session:
            value = session.execute(select(orm.WorkflowAgentRun.cancel_requested).where(orm.WorkflowAgentRun.id == run_id)).scalar_one_or_none()
            return bool(value)

    def append_workflow_agent_events(self, *, run_id: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payloads:
            return []
        with self._write_session() as session:
            self._workflow_agent_run_row(session, run_id, for_update=True)
            sequence = int(session.execute(select(func.coalesce(func.max(orm.WorkflowAgentEvent.sequence), 0)).where(orm.WorkflowAgentEvent.run_id == run_id)).scalar_one()) + 1
            now = utc_now()
            rows = [
                {
                    "id": new_id("workflow_agent_event"),
                    "run_id": run_id,
                    "sequence": sequence + index,
                    "native_event_id": str(payload.get("id") or ""),
                    "payload": payload,
                    "created_at": now,
                }
                for index, payload in enumerate(payloads)
            ]
            session.execute(insert(orm.WorkflowAgentEvent), rows)
            return rows

    def list_workflow_agent_events(self, *, run_id: str, actor: str, after: int, limit: int = 200) -> list[dict[str, Any]]:
        with self._read_session() as session:
            run = self._workflow_agent_run_row(session, run_id)
            self._require_skill_permission(session, skill_id=run["skill_id"], actor=actor, permission="skill.edit")
            rows = (
                session.execute(
                    orm.select_entity(orm.WorkflowAgentEvent)
                    .where(orm.WorkflowAgentEvent.run_id == run_id)
                    .where(orm.WorkflowAgentEvent.sequence > after)
                    .order_by(orm.WorkflowAgentEvent.sequence)
                    .limit(limit)
                )
                .mappings()
                .all()
            )
            return [self._row_dict(row) for row in rows]

    def interrupt_orphaned_workflow_agent_runs(self) -> int:
        with self._write_session() as session:
            now = utc_now()
            result = session.execute(
                update(orm.WorkflowAgentRun)
                .where(orm.WorkflowAgentRun.status.in_(ACTIVE_AGENT_RUN_STATUSES))
                .values(status="interrupted", error={"code": "workflow_agent.api_restarted", "message": "SkillHub API restarted."}, finished_at=now, updated_at=now)
            )
            return int(result.rowcount or 0)


__all__ = ["WorkflowAgentRunMixin"]
