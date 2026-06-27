from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.entities import new_id, utc_now
from skillhub.models.schema import tables
from skillhub.models.operations.shared.results import CreateEvalCaseResult


class EvalCaseVersionCommandMixin:
    def create_eval_case_version(
        self,
        *,
        case_id: str,
        eval_set_id: str | None = None,
        title: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        actor: str,
        workspace_name: str | None = None,
        workspace_base64: str | None = None,
        preserve_workspace: bool = True,
        runner_config: dict[str, Any] | None = None,
        notes: str | None = None,
        make_current: bool = True,
        input_text: str | None = None,
        expected_output: str | None = None,
        attachment_name: str | None = None,
        attachment_base64: str | None = None,
    ) -> CreateEvalCaseResult:
        """Legacy store facade; EvaluationService owns normal eval-case version orchestration."""
        snapshot = self.eval_case_version_create_snapshot(case_id=case_id, eval_set_id=eval_set_id, actor=actor)
        return self.insert_eval_case_version(
            case_id=case_id,
            skill_id=snapshot["skill_id"],
            eval_set_id=snapshot["eval_set_id"],
            title=title,
            version_number=snapshot["next_version_number"],
            steps=self._case_steps(steps or self._legacy_step(input_text, expected_output)),
            workspace_name=workspace_name or attachment_name,
            workspace_base64=workspace_base64 or attachment_base64,
            preserve_workspace=preserve_workspace,
            runner_config=self._case_runner_config(runner_config),
            actor=actor,
            notes=notes,
            make_current=make_current,
        )

    def eval_case_version_create_snapshot(self, *, case_id: str, eval_set_id: str | None, actor: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            skill_id = eval_case["skill_id"]
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.manage")
            self._require_eval_set_contains_case(connection, eval_set_id=eval_set["id"], case_id=case_id)
            return {
                "case_id": case_id,
                "skill_id": skill_id,
                "eval_set_id": eval_set["id"],
                "next_version_number": self._next_eval_case_version_number(connection, case_id),
            }

    def insert_eval_case_version(
        self,
        *,
        case_id: str,
        skill_id: str,
        eval_set_id: str,
        title: str | None,
        version_number: int,
        steps: list[dict[str, Any]],
        workspace_name: str | None,
        workspace_base64: str | None,
        preserve_workspace: bool,
        runner_config: dict[str, Any],
        actor: str,
        notes: str | None,
        make_current: bool,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_version_id = new_id("casever")
        with self.engine.begin() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            if eval_case["skill_id"] != skill_id:
                raise InvariantError("Eval case does not match the requested skill.")
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.manage")
            self._require_eval_set_contains_case(connection, eval_set_id=eval_set["id"], case_id=case_id)
            workspace_artifact_id = self._create_case_workspace(
                connection,
                skill_id=skill_id,
                actor=actor,
                workspace_name=workspace_name,
                workspace_base64=workspace_base64,
                created_at=created_at,
            )
            if workspace_artifact_id is None and preserve_workspace and eval_case["current_version_id"]:
                workspace_artifact_id = self._eval_case_version_row(connection, eval_case["current_version_id"])["workspace_artifact_id"]
            connection.execute(
                insert(tables.eval_case_versions).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=case_id,
                    version_number=version_number,
                    workspace_artifact_id=workspace_artifact_id,
                    steps=steps,
                    runner_config=runner_config,
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            if make_current:
                values: dict[str, Any] = {"current_version_id": eval_case_version_id, "updated_at": created_at}
                if title is not None:
                    values["title"] = title
                connection.execute(update(tables.eval_cases).where(tables.eval_cases.c.id == case_id).values(**values))
            elif title is not None:
                connection.execute(
                    update(tables.eval_cases)
                    .where(tables.eval_cases.c.id == case_id)
                    .values(title=title, updated_at=created_at)
                )
        return CreateEvalCaseResult(skill_id, eval_set["id"], case_id, eval_case_version_id, workspace_artifact_id)

    def restore_eval_case_version(
        self,
        *,
        case_id: str,
        eval_set_id: str | None = None,
        source_case_version_id: str,
        actor: str,
        notes: str | None = None,
    ) -> CreateEvalCaseResult:
        with self.engine.connect() as connection:
            self._eval_case_row(connection, case_id)
            source_case_version = self._eval_case_version_row(connection, source_case_version_id)
            if source_case_version["case_id"] != case_id:
                raise NotFoundError(f"EvalCaseVersion not found for case: {source_case_version_id}")
        return self.create_eval_case_version(
            case_id=case_id,
            eval_set_id=eval_set_id,
            steps=list(source_case_version["steps"]),
            workspace_name=None,
            workspace_base64=None,
            preserve_workspace=True,
            runner_config=dict(source_case_version["runner_config"] or {}),
            actor=actor,
            notes=notes if notes is not None else f"Restored from case v{source_case_version['version_number']}.",
            make_current=True,
        )
