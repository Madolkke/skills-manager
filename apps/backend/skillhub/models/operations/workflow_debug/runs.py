from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, insert, or_, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError
from skillhub.models.operations.workflow_debug.helpers import ACTIVE_DEBUG_RUN_STATUSES, WorkflowDebugHelperMixin
from skillhub.models.rules.workflows import migrate_workflow_document
from skillhub.models.schema import orm


class WorkflowDebugRunMixin(WorkflowDebugHelperMixin):
    def workflow_debug_start_source(self, *, case_id: str, actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            case = self._workflow_debug_case_row(session, case_id, for_update=True)
            self._require_skill_permission(session, skill_id=case["skill_id"], actor=actor, permission="skill.edit")
            active = (
                session.execute(
                    orm.select_entity(orm.WorkflowDebugRun)
                    .where(orm.WorkflowDebugRun.case_id == case_id)
                    .where(orm.WorkflowDebugRun.status.in_(ACTIVE_DEBUG_RUN_STATUSES))
                    .order_by(orm.WorkflowDebugRun.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            workflow = self._workflow_row(session, skill_id=case["skill_id"])
            return {
                "case": self._debug_case_payload(case),
                "active_run": self._debug_run_payload(active) if active is not None else None,
                "workflow_revision": int(workflow["revision"]),
                "workflow_digest": str(workflow["document_digest"]),
                "document": migrate_workflow_document(int(workflow["document_schema_version"]), dict(workflow["document"])),
            }

    def insert_workflow_debug_run(self, *, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {"id": new_id("workflow_debug_run"), **values, "created_at": now, "updated_at": now}
        try:
            with self._write_session() as session:
                session.execute(insert(orm.WorkflowDebugRun).values(**row))
        except IntegrityError as exc:
            raise ConflictError("A Workflow debug run is already active for this case.") from exc
        return row

    def workflow_debug_run(self, *, run_id: str, actor: str, for_update: bool = False) -> dict[str, Any]:
        context = self._write_session() if for_update else self._read_session()
        with context as session:
            row = self._workflow_debug_run_row(session, run_id, for_update=for_update)
            self._require_skill_permission(session, skill_id=row["skill_id"], actor=actor, permission="skill.edit")
            return self._debug_run_payload(row)

    def update_workflow_debug_run(self, *, run_id: str, values: dict[str, Any], actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_debug_run_row(session, run_id, for_update=True)
            self._require_skill_permission(session, skill_id=current["skill_id"], actor=actor, permission="skill.edit")
            changes = {**values, "updated_at": utc_now()}
            session.execute(update(orm.WorkflowDebugRun).where(orm.WorkflowDebugRun.id == run_id).values(**changes))
            return {**self._debug_run_payload(current), **changes}

    def list_workflow_debug_runs(
        self,
        *,
        case_id: str,
        actor: str,
        limit: int,
        before: tuple[datetime, str] | None,
    ) -> list[dict[str, Any]]:
        with self._read_session() as session:
            case = self._workflow_debug_case_row(session, case_id)
            self._require_skill_permission(session, skill_id=case["skill_id"], actor=actor, permission="skill.edit")
            statement = orm.select_entity(orm.WorkflowDebugRun).where(orm.WorkflowDebugRun.case_id == case_id)
            if before is not None:
                created_at, run_id = before
                statement = statement.where(
                    or_(
                        orm.WorkflowDebugRun.created_at < created_at,
                        and_(orm.WorkflowDebugRun.created_at == created_at, orm.WorkflowDebugRun.id < run_id),
                    )
                )
            rows = (
                session.execute(statement.order_by(orm.WorkflowDebugRun.created_at.desc(), orm.WorkflowDebugRun.id.desc()).limit(limit))
                .mappings()
                .all()
            )
            return [self._debug_run_payload(row) for row in rows]


__all__ = ["WorkflowDebugRunMixin"]
