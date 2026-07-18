from __future__ import annotations

from typing import Any

from sqlalchemy import insert

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.operations.evaluations.run_jobs import EvalCaseRunJobMixin
from skillhub.models.operations.shared.results import RecordEvalCaseRunResult
from skillhub.models.rules.eval_runner import OPENCODE_RUNNER
from skillhub.models.rules.eval_runs import normalize_run_environment
from skillhub.models.schema import orm


class EvalRunCommandMixin(EvalCaseRunJobMixin):
    def enqueue_eval_case_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> RecordEvalCaseRunResult:
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        snapshot = self.eval_case_run_enqueue_snapshot(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            case_version_id=case_version_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
        )
        return self.insert_eval_case_run(
            skill_id=snapshot["skill_id"],
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            case_version_id=case_version_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
            run_context_hash=context_hash,
        )

    def eval_case_run_enqueue_snapshot(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...],
        run_context: dict[str, Any],
    ) -> dict[str, Any]:
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        with self._read_session() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            case_version = self._eval_case_version_row(connection, case_version_id)
            self._require_same_skill_for_case_run(skill_version, eval_set, case_version)
            self._require_skill_permission(connection, skill_id=skill_version["skill_id"], actor=actor, permission="eval.run")
            self._require_current_eval_set_case_version(connection, eval_set_id=eval_set_id, case_version=case_version)
        return {
            "skill_id": skill_version["skill_id"],
            "environment_tags": list(tags),
            "run_context": context,
            "run_context_hash": context_hash,
        }

    def insert_eval_case_run(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...],
        run_context: dict[str, Any],
        run_context_hash: str,
    ) -> RecordEvalCaseRunResult:
        created_at = utc_now()
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        if context_hash != run_context_hash:
            raise InvariantError("EvalCaseRun context hash does not match normalized run context.")
        with self._write_session() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            case_version = self._eval_case_version_row(connection, case_version_id)
            self._require_same_skill_for_case_run(skill_version, eval_set, case_version)
            if skill_version["skill_id"] != skill_id:
                raise InvariantError("EvalCaseRun skill_id does not match skill version.")
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.run")
            self._require_current_eval_set_case_version(connection, eval_set_id=eval_set_id, case_version=case_version)
            return self._insert_eval_case_run(
                connection,
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_id=case_version_id,
                actor=actor,
                tags=tags,
                context=context,
                context_hash=context_hash,
                created_at=created_at,
            )

    def _insert_eval_case_run(
        self,
        connection,
        *,
        skill_id: str,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        actor: str,
        tags: tuple[str, ...],
        context: dict[str, Any],
        context_hash: str,
        created_at,
    ) -> RecordEvalCaseRunResult:
        eval_case_run_id = new_id("evalcase")
        job_id = self._insert_job(
            connection,
            job_type="eval_case_run",
            payload={
                "eval_case_run_id": eval_case_run_id,
                "skill_version_id": skill_version_id,
                "eval_set_id": eval_set_id,
                "case_version_id": case_version_id,
                "runner": OPENCODE_RUNNER,
                "environment_tags": list(tags),
                "run_context": context,
            },
            actor=actor,
            created_at=created_at,
        )
        connection.execute(
            insert(orm.EvalCaseRun).values(
                id=eval_case_run_id,
                job_id=job_id,
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_id=case_version_id,
                status="queued",
                environment_tags=list(tags),
                run_context=context,
                run_context_hash=context_hash,
                created_at=created_at,
                created_by=actor,
            )
        )
        return RecordEvalCaseRunResult(eval_case_run_id, job_id, skill_id, skill_version_id, eval_set_id, case_version_id, "queued", context_hash)

    def _actual_output_artifact(self, connection, eval_case_run_id: str, actual_output: str, actor: str, created_at) -> str | None:
        if not actual_output.strip():
            return None
        return self._insert_text_artifact(
            connection,
            kind="actual_output",
            namespace=f"eval_case_run:{eval_case_run_id}",
            content=actual_output,
            actor=actor,
            created_at=created_at,
        )

    def _require_same_skill_for_case_run(self, skill_version, eval_set, case_version) -> None:
        if skill_version["skill_id"] != eval_set["skill_id"] or skill_version["skill_id"] != case_version["skill_id"]:
            raise InvariantError("EvalCaseRun must bind a skill version, eval set, and case version from the same skill.")

    def _require_current_eval_set_case_version(self, connection, *, eval_set_id: str, case_version) -> None:
        case_id = case_version["case_id"]
        self._require_eval_set_contains_case(connection, eval_set_id=eval_set_id, case_id=case_id)
        eval_case = self._eval_case_row(connection, case_id)
        if eval_case["current_version_id"] != case_version["id"]:
            raise FieldInvariantError(
                "EvalCaseRun must use current eval case version.",
                [
                    FieldError(
                        field="case_version_id",
                        message="只能运行当前测评集中测试例的最新版本。",
                        code="eval_case_run.case_version_not_current",
                    )
                ],
            )

    def _case_run_result(self, row) -> RecordEvalCaseRunResult:
        return RecordEvalCaseRunResult(
            eval_case_run_id=row["id"],
            job_id=row["job_id"],
            skill_id=row["skill_id"],
            skill_version_id=row["skill_version_id"],
            eval_set_id=row["eval_set_id"],
            case_version_id=row["case_version_id"],
            status=row["status"],
            run_context_hash=row["run_context_hash"],
            passed=row["passed"],
            score=row["score"],
        )
