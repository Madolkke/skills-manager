from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert, select

from skillhub.domain.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.domain.models import new_id, normalize_tags, utc_now
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.results import RecordEvalRunResult


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
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.run")
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_id)
            self._require_non_empty_eval_set(case_version_ids)
            latest_case_runs = self._latest_succeeded_case_runs(
                connection,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_ids=case_version_ids,
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
                select(tables.eval_case_runs)
                .where(tables.eval_case_runs.c.skill_version_id == skill_version_id)
                .where(tables.eval_case_runs.c.eval_set_id == eval_set_id)
                .where(tables.eval_case_runs.c.case_version_id.in_(case_version_ids))
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

    def _require_non_empty_eval_set(self, case_version_ids: list[str]) -> None:
        if not case_version_ids:
            raise FieldInvariantError(
                "EvalRun aggregation requires at least one case.",
                [
                    FieldError(
                        field="eval_set_id",
                        message="当前测评集没有测试例，无法生成测评记录。",
                        code="eval_run.eval_set_empty",
                    )
                ],
            )

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
