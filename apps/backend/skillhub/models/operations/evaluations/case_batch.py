from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.shared.results import CreatedEvalCaseResult, CreateEvalCasesBatchResult
from skillhub.models.rules.eval_cases import normalize_eval_case_title
from skillhub.models.schema import orm


class EvalCaseBatchCommandMixin:
    def create_eval_cases_batch(self, *, skill_id: str, cases: list[dict[str, Any]], actor: str, eval_set_id: str | None = None) -> CreateEvalCasesBatchResult:
        """Legacy store facade; EvaluationService owns normal batch-case orchestration."""
        if not cases:
            raise InvariantError("At least one eval case is required.")
        clean_cases = [
            {
                **item,
                "title": normalize_eval_case_title(item.get("title")),
                "steps": self._case_steps(item.get("steps") or []),
                "runner_config": self._case_runner_config(item.get("runner_config")),
            }
            for item in cases
        ]
        snapshot = self.eval_case_create_snapshot(skill_id=skill_id, eval_set_id=eval_set_id, actor=actor)
        return self.insert_eval_cases_batch(skill_id=skill_id, eval_set_id=snapshot["eval_set_id"], cases=clean_cases, actor=actor)

    def insert_eval_cases_batch(self, *, skill_id: str, cases: list[dict[str, Any]], actor: str, eval_set_id: str) -> CreateEvalCasesBatchResult:
        created_at = utc_now()
        created_cases: list[CreatedEvalCaseResult] = []
        with self._write_session() as connection:
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.manage")
            for item in cases:
                eval_case_id = new_id("case")
                eval_case_version_id = new_id("casever")
                workspace_artifact_id = self._create_case_workspace(
                    connection,
                    skill_id=skill_id,
                    actor=actor,
                    workspace_name=item.get("workspace_name"),
                    workspace_base64=item.get("workspace_base64"),
                    created_at=created_at,
                )
                connection.execute(
                    insert(orm.EvalCase).values(
                        id=eval_case_id,
                        skill_id=skill_id,
                        title=item["title"],
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
                        steps=item["steps"],
                        runner_config=item["runner_config"],
                        notes=item.get("notes"),
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(orm.EvalCase)
                    .where(orm.EvalCase.id == eval_case_id)
                    .values(current_version_id=eval_case_version_id, updated_at=created_at)
                )
                created_cases.append(CreatedEvalCaseResult(eval_case_id, eval_case_version_id, workspace_artifact_id))
            eval_set_id = self._update_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_ids=[*self._eval_set_case_ids(connection, eval_set["id"]), *[item.eval_case_id for item in created_cases]],
                updated_at=created_at,
            )
        return CreateEvalCasesBatchResult(skill_id, eval_set_id, tuple(created_cases))
