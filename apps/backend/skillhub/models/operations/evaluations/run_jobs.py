from __future__ import annotations

from typing import Any

from sqlalchemy import update

from skillhub.models.entities import utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.shared.results import RecordEvalCaseRunResult
from skillhub.models.rules.eval_runner import OPENCODE_RUNNER
from skillhub.models.schema import orm


class EvalCaseRunJobMixin:
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
        with self._write_session() as connection:
            case_run = self._eval_case_run_row(connection, eval_case_run_id)
            if case_run["status"] not in {"queued", "running"}:
                raise InvariantError("EvalCaseRun is not pending.")
            if case_run["status"] == "queued":
                self._start_job(connection, job_id=case_run["job_id"], started_at=finished_at)
            result_artifact_id = self._actual_output_artifact(connection, eval_case_run_id, actual_output, actor, finished_at)
            connection.execute(
                update(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.id == eval_case_run_id)
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
        with self._write_session() as connection:
            case_run = self._eval_case_run_row(connection, eval_case_run_id)
            if case_run["status"] not in {"queued", "running"}:
                raise InvariantError("EvalCaseRun is not pending.")
            connection.execute(
                update(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.id == eval_case_run_id)
                .values(status="failed", started_at=case_run["started_at"] or finished_at, finished_at=finished_at, error=message)
            )
            self._fail_job(connection, job_id=case_run["job_id"], error=message, finished_at=finished_at)
            failed = self._eval_case_run_row(connection, eval_case_run_id)
        return self._case_run_result(failed)

    def update_eval_case_run_metadata(self, *, eval_case_run_id: str, runner_metadata: dict[str, Any]) -> None:
        with self._write_session() as connection:
            self._eval_case_run_row(connection, eval_case_run_id)
            connection.execute(
                update(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.id == eval_case_run_id)
                .values(runner_metadata=self._canonical_json_object(runner_metadata or {}))
            )

    def claim_next_eval_case_run_job(self, *, worker_id: str, runner: str = OPENCODE_RUNNER) -> dict[str, Any] | None:
        now = utc_now()
        with self._write_session() as connection:
            job = (
                connection.execute(
                    orm.select_entity(orm.Job)
                    .where(orm.Job.type == "eval_case_run")
                    .where(orm.Job.status == "queued")
                    .where(orm.Job.payload["runner"].as_string() == runner)
                    .order_by(orm.Job.created_at, orm.Job.id)
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
                update(orm.Job)
                .where(orm.Job.id == job["id"])
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
                update(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.id == eval_case_run_id)
                .values(status="running", started_at=now, error=None)
            )
        return self.eval_case_run_detail(eval_case_run_id)

    def retry_eval_case_run_job(self, *, eval_case_run_id: str, error: str) -> RecordEvalCaseRunResult:
        now = utc_now()
        message = error.strip() or "Eval case run will be retried."
        with self._write_session() as connection:
            case_run = self._eval_case_run_row(connection, eval_case_run_id)
            if case_run["status"] != "running":
                raise InvariantError("EvalCaseRun is not running.")
            connection.execute(
                update(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.id == eval_case_run_id)
                .values(status="queued", started_at=None, error=message)
            )
            connection.execute(
                update(orm.Job)
                .where(orm.Job.id == case_run["job_id"])
                .values(status="queued", locked_by=None, last_heartbeat_at=now, error=message)
            )
            retried = self._eval_case_run_row(connection, eval_case_run_id)
        return self._case_run_result(retried)
