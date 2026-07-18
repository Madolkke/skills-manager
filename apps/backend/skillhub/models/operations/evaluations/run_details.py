from __future__ import annotations

from typing import Any

from sqlalchemy import desc

from skillhub.models.rules.eval_runs import normalize_run_environment
from skillhub.models.schema import orm


class EvalCaseRunDetailMixin:
    def eval_case_run_detail(self, eval_case_run_id: str) -> dict[str, Any]:
        with self._read_session() as connection:
            return self._eval_case_run_detail_from_row(connection, self._eval_case_run_row(connection, eval_case_run_id))

    def latest_eval_case_run_details(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        environment_tags: list[str] | tuple[str, ...] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        context_hash = None
        if environment_tags is not None or run_context is not None:
            _tags, _context, context_hash = normalize_run_environment(environment_tags, run_context)
        with self._read_session() as connection:
            case_version_ids = self._eval_set_case_version_ids(connection, eval_set_id)
            statement = (
                orm.select_entity(orm.EvalCaseRun)
                .where(orm.EvalCaseRun.skill_version_id == skill_version_id)
                .where(orm.EvalCaseRun.eval_set_id == eval_set_id)
                .where(orm.EvalCaseRun.case_version_id.in_(case_version_ids))
                .order_by(desc(orm.EvalCaseRun.created_at), desc(orm.EvalCaseRun.id))
            )
            if context_hash is not None:
                statement = statement.where(orm.EvalCaseRun.run_context_hash == context_hash)
            rows = connection.execute(statement).mappings().all()
            latest: dict[str, Any] = {}
            for row in rows:
                latest.setdefault(row["case_version_id"], row)
            return [self._eval_case_run_detail_from_row(connection, latest[case_version_id]) for case_version_id in case_version_ids if case_version_id in latest]

    def _eval_case_run_detail_from_row(self, connection, case_run) -> dict[str, Any]:
        skill = self._skill_row(connection, case_run["skill_id"])
        skill_version = self._skill_version_detail(connection, self._skill_version_row(connection, case_run["skill_version_id"]))
        eval_set = self._eval_set_row(connection, case_run["eval_set_id"])
        case_version = self._eval_case_version_row(connection, case_run["case_version_id"])
        case_version_detail = self._case_version_detail(connection, case_version)
        eval_case = self._eval_case_row(connection, case_version["case_id"])
        result_artifact = None
        if case_run["result_artifact_id"] is not None:
            result_artifact = (
                connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == case_run["result_artifact_id"]))
                .mappings()
                .one_or_none()
            )
        job = None
        if case_run["job_id"] is not None:
            job = connection.execute(orm.select_entity(orm.Job).where(orm.Job.id == case_run["job_id"])).mappings().one_or_none()
        return {
            "eval_case_run": self._row_dict(case_run),
            "job": self._row_dict(job) if job is not None else None,
            "skill": self._row_dict(skill),
            "skill_version": skill_version,
            "eval_set": self._row_dict(eval_set),
            "case": self._row_dict(eval_case),
            "case_version": case_version_detail,
            "result_artifact": self._row_dict(result_artifact) if result_artifact is not None else None,
        }
