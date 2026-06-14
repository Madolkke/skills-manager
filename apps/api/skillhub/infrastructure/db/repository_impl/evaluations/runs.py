from __future__ import annotations

from typing import Any

from sqlalchemy import insert

from skillhub.domain.errors import InvariantError
from skillhub.domain.models import new_id, normalize_tags, utc_now
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.results import RecordEvalRunResult


class EvalRunCommandMixin:
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
        created_at = utc_now()
        eval_run_id = new_id("evalrun")
        tags = normalize_tags(environment_tags or [])
        context = self._canonical_json_object(run_context or {})
        context_hash = self._run_context_hash(tags, context)

        with self.engine.begin() as connection:
            skill_version = self._skill_version_row(connection, skill_version_id)
            eval_set = self._eval_set_row(connection, eval_set_id)
            if skill_version["skill_id"] != eval_set["skill_id"]:
                raise InvariantError("EvalRun must bind a skill version and eval set from the same skill.")
            skill_id = skill_version["skill_id"]
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_id)
            normalized_results = self._normalize_eval_run_results(case_version_ids, results)
            passed_count = sum(1 for case_version_id in case_version_ids if normalized_results[case_version_id]["passed"])
            failed_count = len(case_version_ids) - passed_count
            summary = {"passed": passed_count, "failed": failed_count, "total": len(case_version_ids)}
            result_artifact_ids = {
                case_version_id: self._insert_text_artifact(
                    connection,
                    kind="actual_output",
                    namespace=f"eval_run:{eval_run_id}",
                    content=result["actual_output"],
                    actor=actor,
                    created_at=created_at,
                )
                for case_version_id, result in normalized_results.items()
                if result["actual_output"].strip()
            }
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
                        "passed": normalized_results[case_version_id]["passed"],
                        "score": 1 if normalized_results[case_version_id]["passed"] else 0,
                        "result_artifact_id": result_artifact_ids.get(case_version_id),
                        "created_at": created_at,
                    }
                    for case_version_id in case_version_ids
                ],
            )
        return RecordEvalRunResult(
            eval_run_id,
            skill_id,
            skill_version_id,
            eval_set_id,
            passed_count,
            failed_count,
            len(case_version_ids),
            tags,
            context,
            context_hash,
        )
