from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.shared.results import RecordEvalRunResult
from skillhub.models.rules.eval_runs import decide_eval_run_aggregation, normalize_run_environment
from skillhub.models.schema import orm


class EvalRunAggregationMixin:
    def aggregate_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> RecordEvalRunResult:
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        snapshot = self.eval_run_aggregation_snapshot(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
        )
        decision = decide_eval_run_aggregation(case_version_ids=snapshot["case_version_ids"], latest_case_runs=snapshot["latest_case_runs"])
        return self.insert_aggregated_eval_run(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
            run_context_hash=context_hash,
            summary=decision["summary"],
            case_results=decision["case_results"],
        )

    def eval_run_aggregation_snapshot(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...],
        run_context: dict[str, Any],
    ) -> dict[str, Any]:
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        with self._read_session() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            if skill_version["skill_id"] != eval_set["skill_id"]:
                raise InvariantError("EvalRun must bind a skill version and eval set from the same skill.")
            skill_id = skill_version["skill_id"]
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.run")
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_id)
            latest_case_runs = self._latest_succeeded_case_runs(
                connection,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_ids=case_version_ids,
                context_hash=context_hash,
            )
        return {
            "skill_id": skill_version["skill_id"],
            "case_version_ids": case_version_ids,
            "latest_case_runs": {key: self._row_dict(value) for key, value in latest_case_runs.items()},
            "environment_tags": list(tags),
            "run_context": context,
            "run_context_hash": context_hash,
        }

    def insert_aggregated_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        actor: str,
        environment_tags: list[str] | tuple[str, ...],
        run_context: dict[str, Any],
        run_context_hash: str,
        summary: dict[str, Any],
        case_results: list[dict[str, Any]],
    ) -> RecordEvalRunResult:
        created_at = utc_now()
        eval_run_id = new_id("evalrun")
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        if context_hash != run_context_hash:
            raise InvariantError("EvalRun aggregation context hash does not match normalized run context.")
        passed_count = int(summary.get("passed", 0))
        failed_count = int(summary.get("failed", 0))
        total_count = int(summary.get("total", len(case_results)))
        with self._write_session() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            if skill_version["skill_id"] != eval_set["skill_id"]:
                raise InvariantError("EvalRun must bind a skill version and eval set from the same skill.")
            skill_id = skill_version["skill_id"]
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.run")
            connection.execute(
                insert(orm.EvalRun).values(
                    id=eval_run_id,
                    skill_id=skill_id,
                    skill_version_id=skill_version_id,
                    eval_set_id=eval_set_id,
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
                insert(orm.CaseResult),
                [
                    {
                        "run_id": eval_run_id,
                        "skill_id": skill_id,
                        "case_version_id": result["case_version_id"],
                        "passed": result["passed"],
                        "score": result["score"],
                        "result_artifact_id": result["result_artifact_id"],
                        "created_at": created_at,
                    }
                    for result in case_results
                ],
            )
        return RecordEvalRunResult(eval_run_id, skill_id, skill_version_id, eval_set_id, passed_count, failed_count, total_count, tags, context, context_hash)

    def _latest_succeeded_case_runs(
        self,
        connection,
        *,
        skill_version_id: str,
        eval_set_id: str,
        case_version_ids: list[str],
        context_hash: str,
    ) -> dict[str, Any]:
        rows = (
            connection.execute(
                orm.select_entity(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.skill_version_id == skill_version_id)
                .where(orm.EvalCaseRun.eval_set_id == eval_set_id)
                .where(orm.EvalCaseRun.case_version_id.in_(case_version_ids))
                .where(orm.EvalCaseRun.run_context_hash == context_hash)
                .where(orm.EvalCaseRun.status == "succeeded")
                .order_by(desc(orm.EvalCaseRun.finished_at), desc(orm.EvalCaseRun.id))
            )
            .mappings()
            .all()
        )
        latest: dict[str, Any] = {}
        for row in rows:
            latest.setdefault(row["case_version_id"], row)
        return latest
