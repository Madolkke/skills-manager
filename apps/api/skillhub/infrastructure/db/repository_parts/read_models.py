from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from skillhub.infrastructure.db import tables


class ReadModelMixin:
    def list_skills(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(tables.skills)
                    .where(tables.skills.c.lifecycle_status == "active")
                    .order_by(tables.skills.c.slug)
                )
                .mappings()
                .all()
            )
            return [
                {
                    "skill": self._row_dict(row),
                    "summary": self._skill_summary(connection, row),
                }
                for row in rows
            ]

    def skill_detail(self, skill_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            version_rows = (
                connection.execute(
                    select(tables.skill_versions)
                    .where(tables.skill_versions.c.skill_id == skill_id)
                    .order_by(desc(tables.skill_versions.c.version_number))
                )
                .mappings()
                .all()
            )
            versions = [self._skill_version_detail(connection, row) for row in version_rows]
            eval_sets = [
                self._eval_set_summary(connection, row)
                for row in connection.execute(
                    select(tables.eval_sets).where(tables.eval_sets.c.skill_id == skill_id).order_by(tables.eval_sets.c.name)
                )
                .mappings()
                .all()
            ]
            latest_runs = [
                self._row_dict(row)
                for row in connection.execute(
                    select(tables.eval_runs)
                    .where(tables.eval_runs.c.skill_id == skill_id)
                    .order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id))
                    .limit(10)
                )
                .mappings()
                .all()
            ]
            summary = self._skill_summary(connection, skill)
            role_assignments = self._skill_role_assignments(connection, skill_id)
            audit_events = self._skill_audit_events(connection, skill_id, limit=10)
        return {
            "skill": self._row_dict(skill),
            "summary": summary,
            "versions": versions,
            "eval_sets": eval_sets,
            "latest_eval_runs": latest_runs,
            "role_assignments": role_assignments,
            "audit_events": audit_events,
        }

    def _skill_summary(self, connection, skill) -> dict[str, Any]:
        current_version = None
        if skill["current_version_id"]:
            current_version = self._skill_version_detail(connection, self._skill_version_row(connection, skill["current_version_id"]))
        primary_eval_set = None
        current_eval_set_version = None
        primary_row = (
            connection.execute(
                select(tables.eval_sets).where(tables.eval_sets.c.skill_id == skill["id"]).where(tables.eval_sets.c.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if primary_row is not None:
            primary_eval_set = self._eval_set_summary(connection, primary_row)
            current_eval_set_version = primary_eval_set["current_version"]
        latest_eval_run = None
        if current_version is not None and current_eval_set_version is not None:
            latest_row = (
                connection.execute(
                    select(tables.eval_runs)
                    .where(tables.eval_runs.c.skill_version_id == current_version["id"])
                    .where(tables.eval_runs.c.eval_set_version_id == current_eval_set_version["id"])
                    .where(tables.eval_runs.c.status == "finished")
                    .order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id))
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            latest_eval_run = self._row_dict(latest_row) if latest_row is not None else None
        return {
            "skill": self._row_dict(skill),
            "current_version": current_version,
            "primary_eval_set": primary_eval_set,
            "latest_accepted_eval_run": latest_eval_run,
        }

    def _skill_version_detail(self, connection, version) -> dict[str, Any]:
        detail = self._row_dict(version)
        content_ref = detail.get("content_ref") or {}
        locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
        if content_ref.get("kind") == "artifact" and isinstance(locator, str) and locator.startswith("artifact:"):
            artifact_id = locator.split(":", 1)[1]
            artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one_or_none()
            if artifact is not None:
                artifact_detail = self._row_dict(artifact)
                detail["bundle_artifact"] = artifact_detail
                detail["bundle_files"] = self._bundle_files_from_artifact(artifact_detail)
        return detail

    def _eval_set_summary(self, connection, eval_set) -> dict[str, Any]:
        versions = [
            self._row_dict(row)
            for row in connection.execute(
                select(tables.eval_set_versions)
                .where(tables.eval_set_versions.c.eval_set_id == eval_set["id"])
                .order_by(desc(tables.eval_set_versions.c.version_number))
            )
            .mappings()
            .all()
        ]
        current_version = next((version for version in versions if version["id"] == eval_set["current_version_id"]), None)
        return {**self._row_dict(eval_set), "current_version": current_version, "versions": versions}

    def _eval_set_cases(self, connection, eval_set_version_id: str) -> list[dict[str, Any]]:
        memberships = (
            connection.execute(
                select(tables.eval_set_case_versions)
                .where(tables.eval_set_case_versions.c.eval_set_version_id == eval_set_version_id)
                .order_by(tables.eval_set_case_versions.c.position)
            )
            .mappings()
            .all()
        )
        cases = []
        for membership in memberships:
            case_version = self._eval_case_version_row(connection, membership["case_version_id"])
            eval_case = self._eval_case_row(connection, case_version["case_id"])
            cases.append(
                {
                    "position": membership["position"],
                    "case": self._row_dict(eval_case),
                    "case_version": self._case_version_detail(connection, case_version),
                }
            )
        return cases

    def _case_version_detail(self, connection, case_version) -> dict[str, Any]:
        input_artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == case_version["input_artifact_id"])).mappings().one()
        expected_output_artifact = (
            connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == case_version["expected_output_artifact_id"]))
            .mappings()
            .one()
        )
        return {
            **self._row_dict(case_version),
            "input_artifact": self._row_dict(input_artifact),
            "expected_output_artifact": self._row_dict(expected_output_artifact),
        }
