from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert, select, update

from skillhub.domain.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.domain.models import new_id, normalize_tags, utc_now
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.results import RecordEvalCaseRunResult, RecordEvalRunResult


class EvalRunCommandMixin:
    def enqueue_eval_case_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        strategy: str,
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
            result = self._insert_eval_case_run(
                connection,
                skill_id=skill_version["skill_id"],
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_id=case_version_id,
                strategy=strategy,
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

    def aggregate_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        strategy: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> RecordEvalRunResult:
        created_at = utc_now()
        eval_run_id = new_id("evalrun")
        tags = normalize_tags(list(environment_tags or []))
        context = self._canonical_json_object(run_context or {})
        context_hash = self._run_context_hash(tags, context)

        with self.engine.begin() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            if skill_version["skill_id"] != eval_set["skill_id"]:
                raise InvariantError("EvalRun must bind a skill version and eval set from the same skill.")
            skill_id = skill_version["skill_id"]
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_id)
            latest_case_runs = self._latest_succeeded_case_runs(
                connection,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_ids=case_version_ids,
                strategy=strategy,
                context_hash=context_hash,
            )
            self._require_complete_case_runs(case_version_ids, latest_case_runs)
            passed_count = sum(1 for case_version_id in case_version_ids if latest_case_runs[case_version_id]["passed"])
            failed_count = len(case_version_ids) - passed_count
            summary = {"passed": passed_count, "failed": failed_count, "total": len(case_version_ids)}
            connection.execute(
                insert(tables.eval_runs).values(
                    id=eval_run_id,
                    skill_id=skill_id,
                    skill_version_id=skill_version_id,
                    eval_set_id=eval_set_id,
                    strategy=strategy,
                    status="finished",
                    environment_tags=list(tags),
                    run_context=context,
                    run_context_hash=context_hash,
                    summary=summary,
                    result_artifact_id=None,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                insert(tables.case_results),
                [
                    {
                        "run_id": eval_run_id,
                        "skill_id": skill_id,
                        "case_version_id": case_version_id,
                        "passed": latest_case_runs[case_version_id]["passed"],
                        "score": latest_case_runs[case_version_id]["score"],
                        "result_artifact_id": latest_case_runs[case_version_id]["result_artifact_id"],
                        "created_at": created_at,
                    }
                    for case_version_id in case_version_ids
                ],
            )
        return RecordEvalRunResult(eval_run_id, skill_id, skill_version_id, eval_set_id, passed_count, failed_count, len(case_version_ids), tags, context, context_hash)

    def record_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        strategy: str,
        results: dict[str, Any],
        actor: str,
        environment_tags: list[str] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> RecordEvalRunResult:
        tags = normalize_tags(environment_tags or [])
        context = self._canonical_json_object(run_context or {})
        with self.engine.begin() as connection:
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_id)
            normalized_results = self._normalize_eval_run_results(case_version_ids, results)

        for case_version_id in case_version_ids:
            queued = self.enqueue_eval_case_run(
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_id=case_version_id,
                strategy=strategy,
                actor=actor,
                environment_tags=tags,
                run_context=context,
            )
            self.finalize_eval_case_run(
                eval_case_run_id=queued.eval_case_run_id,
                passed=normalized_results[case_version_id]["passed"],
                actual_output=normalized_results[case_version_id]["actual_output"],
                actor=actor,
            )
        return self.aggregate_eval_run(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            strategy=strategy,
            actor=actor,
            environment_tags=tags,
            run_context=context,
        )

    def _insert_eval_case_run(
        self,
        connection,
        *,
        skill_id: str,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        strategy: str,
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
                "strategy": strategy,
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
                strategy=strategy,
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

    def _latest_succeeded_case_runs(
        self,
        connection,
        *,
        skill_version_id: str,
        eval_set_id: str,
        case_version_ids: list[str],
        strategy: str,
        context_hash: str,
    ) -> dict[str, Any]:
        rows = (
            connection.execute(
                select(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.skill_version_id == skill_version_id)
                .where(tables.eval_case_runs.c.eval_set_id == eval_set_id)
                .where(tables.eval_case_runs.c.case_version_id.in_(case_version_ids))
                .where(tables.eval_case_runs.c.strategy == strategy)
                .where(tables.eval_case_runs.c.run_context_hash == context_hash)
                .where(tables.eval_case_runs.c.status == "succeeded")
                .order_by(desc(tables.eval_case_runs.c.finished_at), desc(tables.eval_case_runs.c.id))
            )
            .mappings()
            .all()
        )
        latest: dict[str, Any] = {}
        for row in rows:
            latest.setdefault(row["case_version_id"], row)
        return latest

    def _require_complete_case_runs(self, case_version_ids: list[str], latest_case_runs: dict[str, Any]) -> None:
        missing = [case_version_id for case_version_id in case_version_ids if case_version_id not in latest_case_runs]
        if missing:
            raise FieldInvariantError(
                "EvalRun aggregation requires finished case runs.",
                [
                    FieldError(field=f"case_runs.{case_version_id}", message="该 case 尚未完成测评。", code="eval_run.case_run_missing")
                    for case_version_id in missing
                ],
            )

    def _require_same_skill_for_case_run(self, skill_version, eval_set, case_version) -> None:
        if skill_version["skill_id"] != eval_set["skill_id"] or skill_version["skill_id"] != case_version["skill_id"]:
            raise InvariantError("EvalCaseRun must bind a skill version, eval set, and case version from the same skill.")

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
