from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from skillhub.application.eval_runner import OPENCODE_RUNNER
from skillhub.domain.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.domain.models import new_id, normalize_tags, utc_now
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.results import RecordEvalCaseRunResult


class EvalRunCommandMixin:
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
        created_at = utc_now()
        tags = normalize_tags(list(environment_tags or []))
        context = self._canonical_json_object(run_context or {})
        context_hash = self._run_context_hash(tags, context)

        with self.engine.begin() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            case_version = self._eval_case_version_row(connection, case_version_id)
            self._require_same_skill_for_case_run(skill_version, eval_set, case_version)
            self._require_skill_permission(connection, skill_id=skill_version["skill_id"], actor=actor, permission="eval.run")
            self._require_current_eval_set_case_version(connection, eval_set_id=eval_set_id, case_version=case_version)
            result = self._insert_eval_case_run(
                connection,
                skill_id=skill_version["skill_id"],
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_id=case_version_id,
                actor=actor,
                tags=tags,
                context=context,
                context_hash=context_hash,
                created_at=created_at,
            )
        return result

    def finalize_eval_case_run(
        self,
        *,
        eval_case_run_id: str,
        passed: bool,
        actual_output: str = "",
        actor: str,
        runner_metadata: dict[str, Any] | None = None,
    ) -> RecordEvalCaseRunResult:
        finished_at = utc_now()
        with self.engine.begin() as connection:
            case_run = self._eval_case_run_row(connection, eval_case_run_id)
            if case_run["status"] not in {"queued", "running"}:
                raise InvariantError("EvalCaseRun is not pending.")
            if case_run["status"] == "queued":
                self._start_job(connection, job_id=case_run["job_id"], started_at=finished_at)
            result_artifact_id = self._actual_output_artifact(connection, eval_case_run_id, actual_output, actor, finished_at)
            connection.execute(
                update(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.id == eval_case_run_id)
                .values(
                    status="succeeded",
                    passed=passed,
                    score=1 if passed else 0,
                    result_artifact_id=result_artifact_id,
                    runner_metadata=self._canonical_json_object(runner_metadata or {}),
                    started_at=case_run["started_at"] or finished_at,
                    finished_at=finished_at,
                    error=None,
                )
            )
            self._finish_job(connection, job_id=case_run["job_id"], result_ref=eval_case_run_id, finished_at=finished_at)
            finished = self._eval_case_run_row(connection, eval_case_run_id)
        return self._case_run_result(finished)

    def fail_eval_case_run(self, *, eval_case_run_id: str, error: str) -> RecordEvalCaseRunResult:
        finished_at = utc_now()
        message = error.strip() or "Eval case run failed."
        with self.engine.begin() as connection:
            case_run = self._eval_case_run_row(connection, eval_case_run_id)
            if case_run["status"] not in {"queued", "running"}:
                raise InvariantError("EvalCaseRun is not pending.")
            connection.execute(
                update(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.id == eval_case_run_id)
                .values(status="failed", started_at=case_run["started_at"] or finished_at, finished_at=finished_at, error=message)
            )
            self._fail_job(connection, job_id=case_run["job_id"], error=message, finished_at=finished_at)
            failed = self._eval_case_run_row(connection, eval_case_run_id)
        return self._case_run_result(failed)

    def update_eval_case_run_metadata(self, *, eval_case_run_id: str, runner_metadata: dict[str, Any]) -> None:
        with self.engine.begin() as connection:
            self._eval_case_run_row(connection, eval_case_run_id)
            connection.execute(
                update(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.id == eval_case_run_id)
                .values(runner_metadata=self._canonical_json_object(runner_metadata or {}))
            )

    def claim_next_eval_case_run_job(self, *, worker_id: str, runner: str = OPENCODE_RUNNER) -> dict[str, Any] | None:
        now = utc_now()
        with self.engine.begin() as connection:
            job = (
                connection.execute(
                    select(tables.jobs)
                    .where(tables.jobs.c.type == "eval_case_run")
                    .where(tables.jobs.c.status == "queued")
                    .where(tables.jobs.c.payload["runner"].as_string() == runner)
                    .order_by(tables.jobs.c.created_at, tables.jobs.c.id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .one_or_none()
            )
            if job is None:
                return None
            payload = dict(job["payload"])
            eval_case_run_id = str(payload["eval_case_run_id"])
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job["id"])
                .values(
                    status="running",
                    attempts=job["attempts"] + 1,
                    locked_by=worker_id,
                    started_at=job["started_at"] or now,
                    last_heartbeat_at=now,
                    error=None,
                )
            )
            connection.execute(
                update(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.id == eval_case_run_id)
                .values(status="running", started_at=now, error=None)
            )
        return self.eval_case_run_detail(eval_case_run_id)

    def retry_eval_case_run_job(self, *, eval_case_run_id: str, error: str) -> RecordEvalCaseRunResult:
        now = utc_now()
        message = error.strip() or "Eval case run will be retried."
        with self.engine.begin() as connection:
            case_run = self._eval_case_run_row(connection, eval_case_run_id)
            if case_run["status"] != "running":
                raise InvariantError("EvalCaseRun is not running.")
            connection.execute(
                update(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.id == eval_case_run_id)
                .values(status="queued", started_at=None, error=message)
            )
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == case_run["job_id"])
                .values(status="queued", locked_by=None, last_heartbeat_at=now, error=message)
            )
            retried = self._eval_case_run_row(connection, eval_case_run_id)
        return self._case_run_result(retried)

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
            insert(tables.eval_case_runs).values(
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
