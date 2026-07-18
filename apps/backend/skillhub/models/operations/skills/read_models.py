from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from skillhub.models.operations.skills.list_read_models import ListReadModelMixin
from skillhub.models.rules.eval_assertion_templates import normalize_assertion_step
from skillhub.models.schema import orm


class ReadModelMixin(ListReadModelMixin):
    def skill_detail(self, skill_id: str, actor: str | None = None) -> dict[str, Any]:
        with self._read_session() as connection:
            skill = self._skill_row(connection, skill_id)
            version_rows = (
                connection.execute(
                    orm.select_entity(orm.SkillVersion)
                    .where(orm.SkillVersion.skill_id == skill_id)
                    .order_by(desc(orm.SkillVersion.version_number))
                )
                .mappings()
                .all()
            )
            versions = [self._skill_version_detail(connection, row) for row in version_rows]
            eval_sets = [
                self._eval_set_summary(connection, row)
                for row in connection.execute(
                    orm.select_entity(orm.EvalSet).where(orm.EvalSet.skill_id == skill_id).order_by(orm.EvalSet.name)
                )
                .mappings()
                .all()
            ]
            latest_runs = [
                self._row_dict(row)
                for row in connection.execute(
                    orm.select_entity(orm.EvalRun)
                    .where(orm.EvalRun.skill_id == skill_id)
                    .order_by(desc(orm.EvalRun.created_at), desc(orm.EvalRun.id))
                    .limit(10)
                )
                .mappings()
                .all()
            ]
            summary = self._skill_summary(connection, skill)
            role_assignments = self._skill_role_assignments(connection, skill_id)
            audit_events = self._skill_audit_events(connection, skill_id, limit=10)
            capabilities = self._skill_capabilities(connection, skill_id=skill_id, actor=actor or "", subject_type="user") if actor else None
            return {
                "skill": self._skill_record(connection, skill),
                "summary": summary,
                "versions": versions,
                "eval_sets": eval_sets,
                "latest_eval_runs": latest_runs,
                "role_assignments": role_assignments,
                "audit_events": audit_events,
                "capabilities": capabilities,
                "workflow": self._workflow_summary(connection, skill),
            }

    def _skill_summary(self, connection, skill) -> dict[str, Any]:
        current_version = None
        if skill["current_version_id"]:
            current_version = self._skill_version_detail(connection, self._skill_version_row(connection, skill["current_version_id"]))
        primary_eval_set = None
        current_eval_set = None
        primary_row = (
            connection.execute(
                orm.select_entity(orm.EvalSet).where(orm.EvalSet.skill_id == skill["id"]).where(orm.EvalSet.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if primary_row is not None:
            primary_eval_set = self._eval_set_summary(connection, primary_row)
            current_eval_set = primary_eval_set
        latest_eval_run = None
        if current_version is not None and current_eval_set is not None:
            latest_row = (
                connection.execute(
                    orm.select_entity(orm.EvalRun)
                    .where(orm.EvalRun.skill_version_id == current_version["id"])
                    .where(orm.EvalRun.eval_set_id == current_eval_set["id"])
                    .where(orm.EvalRun.status == "finished")
                    .order_by(desc(orm.EvalRun.created_at), desc(orm.EvalRun.id))
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            latest_eval_run = self._row_dict(latest_row) if latest_row is not None else None
        return {
            "skill": self._skill_record(connection, skill),
            "current_version": current_version,
            "primary_eval_set": primary_eval_set,
            "latest_accepted_eval_run": latest_eval_run,
        }

    def _skill_record(self, connection, skill) -> dict[str, Any]:
        return {**self._row_dict(skill), "tags": self._skill_tags(connection, skill["id"])}

    def _skill_version_detail(self, connection, version) -> dict[str, Any]:
        detail = self._row_dict(version)
        workflow_sync = connection.execute(
            select(
                orm.WorkflowSync.workflow_id,
                orm.WorkflowSync.workflow_revision,
                orm.WorkflowSync.generator_version,
                orm.WorkflowSync.created_at,
            ).where(orm.WorkflowSync.skill_version_id == version["id"])
        ).mappings().one_or_none()
        detail["workflow_sync"] = self._row_dict(workflow_sync) if workflow_sync is not None else None
        content_ref = detail.get("content_ref") or {}
        if not isinstance(content_ref, dict):
            return detail
        locator = content_ref.get("locator")
        if content_ref.get("kind") == "artifact" and isinstance(locator, str) and locator.startswith("artifact:"):
            artifact_id = locator.split(":", 1)[1]
            artifact = connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == artifact_id)).mappings().one_or_none()
            if artifact is not None:
                artifact_detail = self._row_dict(artifact)
                detail["bundle_artifact"] = artifact_detail
                detail["bundle_files"] = self._bundle_files_from_artifact(artifact_detail)
        return detail

    def _eval_set_summary(self, connection, eval_set) -> dict[str, Any]:
        return self._row_dict(eval_set)

    def _eval_set_cases(self, connection, eval_set_id: str) -> list[dict[str, Any]]:
        memberships = (
            connection.execute(
                orm.select_entity(orm.EvalSetCase)
                .where(orm.EvalSetCase.eval_set_id == eval_set_id)
                .order_by(orm.EvalSetCase.position)
            )
            .mappings()
            .all()
        )
        cases = []
        for membership in memberships:
            eval_case = self._eval_case_row(connection, membership["case_id"])
            if not eval_case["current_version_id"]:
                continue
            case_version = self._eval_case_version_row(connection, eval_case["current_version_id"])
            cases.append(
                {
                    "position": membership["position"],
                    "case": self._row_dict(eval_case),
                    "case_version": self._case_version_detail(connection, case_version),
                }
            )
        return cases

    def _case_version_detail(self, connection, case_version) -> dict[str, Any]:
        workspace_artifact = None
        if case_version.get("workspace_artifact_id"):
            workspace_artifact = (
                connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == case_version["workspace_artifact_id"]))
                .mappings()
                .one()
            )
        detail = self._row_dict(case_version)
        detail["steps"] = [normalize_assertion_step(step, index) for index, step in enumerate(detail.get("steps") or [])]
        return {
            **detail,
            "workspace_artifact": self._row_dict(workspace_artifact) if workspace_artifact is not None else None,
        }
