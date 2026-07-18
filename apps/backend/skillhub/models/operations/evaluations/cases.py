from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.evaluations.case_batch import EvalCaseBatchCommandMixin
from skillhub.models.operations.evaluations.case_versions import EvalCaseVersionCommandMixin
from skillhub.models.operations.shared.results import CreateEvalCaseResult
from skillhub.models.rules.eval_cases import (
    legacy_eval_case_steps,
    normalize_eval_case_runner_config,
    normalize_eval_case_steps,
)
from skillhub.models.schema import orm


class EvalCaseCommandMixin(EvalCaseBatchCommandMixin, EvalCaseVersionCommandMixin):
    def update_eval_case_title(self, *, case_id: str, title: str) -> dict[str, Any]:
        updated_at = utc_now()
        with self._write_session() as connection:
            self._eval_case_row(connection, case_id)
            connection.execute(
                update(orm.EvalCase)
                .where(orm.EvalCase.id == case_id)
                .values(title=title, updated_at=updated_at)
            )
            return self._row_dict(self._eval_case_row(connection, case_id))

    def create_eval_case(
        self,
        *,
        skill_id: str,
        eval_set_id: str | None = None,
        title: str,
        steps: list[dict[str, Any]] | None = None,
        actor: str,
        workspace_name: str | None = None,
        workspace_base64: str | None = None,
        runner_config: dict[str, Any] | None = None,
        notes: str | None = None,
        input_text: str | None = None,
        expected_output: str | None = None,
        attachment_name: str | None = None,
        attachment_base64: str | None = None,
    ) -> CreateEvalCaseResult:
        """Legacy store facade; EvaluationService owns normal eval-case orchestration."""
        snapshot = self.eval_case_create_snapshot(skill_id=skill_id, eval_set_id=eval_set_id, actor=actor)
        return self.insert_eval_case(
            skill_id=skill_id,
            eval_set_id=snapshot["eval_set_id"],
            title=title,
            steps=self._case_steps(steps or self._legacy_step(input_text, expected_output)),
            workspace_name=workspace_name or attachment_name,
            workspace_base64=workspace_base64 or attachment_base64,
            runner_config=self._case_runner_config(runner_config),
            actor=actor,
            notes=notes,
        )

    def eval_case_create_snapshot(self, *, skill_id: str, eval_set_id: str | None, actor: str) -> dict[str, Any]:
        with self._read_session() as connection:
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.manage")
            return {"skill_id": skill_id, "eval_set_id": eval_set["id"]}

    def insert_eval_case(
        self,
        *,
        skill_id: str,
        eval_set_id: str,
        title: str,
        steps: list[dict[str, Any]],
        workspace_name: str | None,
        workspace_base64: str | None,
        runner_config: dict[str, Any],
        actor: str,
        notes: str | None,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_id = new_id("case")
        eval_case_version_id = new_id("casever")
        with self._write_session() as connection:
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.manage")
            workspace_artifact_id = self._create_case_workspace(
                connection,
                skill_id=skill_id,
                actor=actor,
                workspace_name=workspace_name,
                workspace_base64=workspace_base64,
                created_at=created_at,
            )
            connection.execute(
                insert(orm.EvalCase).values(
                    id=eval_case_id,
                    skill_id=skill_id,
                    title=title,
                    current_version_id=None,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            connection.execute(
                insert(orm.EvalCaseVersion).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=eval_case_id,
                    version_number=1,
                    workspace_artifact_id=workspace_artifact_id,
                    steps=steps,
                    runner_config=runner_config,
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                update(orm.EvalCase)
                .where(orm.EvalCase.id == eval_case_id)
                .values(current_version_id=eval_case_version_id, updated_at=created_at)
            )
            eval_set_id = self._update_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_ids=[*self._eval_set_case_ids(connection, eval_set["id"]), eval_case_id],
                updated_at=created_at,
            )
        return CreateEvalCaseResult(skill_id, eval_set_id, eval_case_id, eval_case_version_id, workspace_artifact_id)

    def _case_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return normalize_eval_case_steps(steps)

    def _legacy_step(self, input_text: str | None, expected_output: str | None) -> list[dict[str, Any]]:
        return legacy_eval_case_steps(input_text, expected_output)

    def _case_runner_config(self, value: dict[str, Any] | None) -> dict[str, Any]:
        return normalize_eval_case_runner_config(value)

    def _eval_set_for_case_write(self, connection, *, skill_id: str, eval_set_id: str | None):
        eval_set = self._eval_set_row(connection, eval_set_id) if eval_set_id else self._primary_eval_set_row(connection, skill_id)
        if eval_set["skill_id"] != skill_id:
            raise InvariantError("Eval case and eval set must belong to the same skill.")
        return eval_set
