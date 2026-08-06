from __future__ import annotations

from typing import Any

from sqlalchemy import delete, insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError
from skillhub.models.operations.workflow_debug.helpers import ACTIVE_DEBUG_RUN_STATUSES, WorkflowDebugHelperMixin
from skillhub.models.rules.workflows import migrate_workflow_document
from skillhub.models.schema import orm


class WorkflowDebugCaseMixin(WorkflowDebugHelperMixin):
    def workflow_debug_document(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as session:
            self._skill_row(session, skill_id)
            self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")
            workflow = self._workflow_row(session, skill_id=skill_id)
            return migrate_workflow_document(int(workflow["document_schema_version"]), dict(workflow["document"]))

    def list_workflow_debug_cases(self, *, skill_id: str, actor: str, step_id: str | None = None) -> list[dict[str, Any]]:
        with self._read_session() as session:
            self._skill_row(session, skill_id)
            self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")
            statement = orm.select_entity(orm.WorkflowDebugCase).where(orm.WorkflowDebugCase.skill_id == skill_id)
            if step_id is not None:
                statement = statement.where(orm.WorkflowDebugCase.step_id == step_id)
            rows = (
                session.execute(
                    statement.order_by(orm.WorkflowDebugCase.created_at, orm.WorkflowDebugCase.id)
                )
                .mappings()
                .all()
            )
            return [self._debug_case_payload(row) for row in rows]

    def workflow_debug_case(self, *, case_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as session:
            row = self._workflow_debug_case_row(session, case_id)
            self._require_skill_permission(session, skill_id=row["skill_id"], actor=actor, permission="skill.edit")
            return self._debug_case_payload(row)

    def insert_workflow_debug_case(self, *, skill_id: str, values: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utc_now()
        row = {
            "id": new_id("workflow_debug_case"),
            "skill_id": skill_id,
            **values,
            "created_by": actor,
            "updated_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        with self._write_session() as session:
            self._skill_row(session, skill_id)
            self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")
            session.execute(insert(orm.WorkflowDebugCase).values(**row))
        return row

    def update_workflow_debug_case(self, *, case_id: str, values: dict[str, Any], actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            current = self._workflow_debug_case_row(session, case_id, for_update=True)
            self._require_skill_permission(session, skill_id=current["skill_id"], actor=actor, permission="skill.edit")
            changes = {**values, "updated_by": actor, "updated_at": utc_now()}
            session.execute(update(orm.WorkflowDebugCase).where(orm.WorkflowDebugCase.id == case_id).values(**changes))
            return {**self._debug_case_payload(current), **changes}

    def delete_workflow_debug_case(self, *, case_id: str, actor: str) -> dict[str, bool]:
        with self._write_session() as session:
            current = self._workflow_debug_case_row(session, case_id, for_update=True)
            self._require_skill_permission(session, skill_id=current["skill_id"], actor=actor, permission="skill.edit")
            active = session.execute(
                select(orm.WorkflowDebugRun.id)
                .where(orm.WorkflowDebugRun.case_id == case_id)
                .where(orm.WorkflowDebugRun.status.in_(ACTIVE_DEBUG_RUN_STATUSES))
                .limit(1)
            ).scalar_one_or_none()
            if active is not None:
                raise ConflictError("Cannot delete a Workflow debug case while a run is active.")
            session.execute(delete(orm.WorkflowDebugRun).where(orm.WorkflowDebugRun.case_id == case_id))
            session.execute(delete(orm.WorkflowDebugCase).where(orm.WorkflowDebugCase.id == case_id))
        return {"deleted": True}

    def delete_removed_step_debug_cases(self, session, *, skill_id: str, step_ids: set[str]) -> None:
        case_ids = select(orm.WorkflowDebugCase.id).where(orm.WorkflowDebugCase.skill_id == skill_id)
        if step_ids:
            case_ids = case_ids.where(orm.WorkflowDebugCase.step_id.not_in(step_ids))
        session.execute(delete(orm.WorkflowDebugRun).where(orm.WorkflowDebugRun.case_id.in_(case_ids)))
        statement = delete(orm.WorkflowDebugCase).where(orm.WorkflowDebugCase.skill_id == skill_id)
        if step_ids:
            statement = statement.where(orm.WorkflowDebugCase.step_id.not_in(step_ids))
        session.execute(statement)


__all__ = ["WorkflowDebugCaseMixin"]
