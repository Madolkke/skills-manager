from __future__ import annotations

from sqlalchemy import select

from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.results import EvalRunDetail, EvalSetDetail


class DetailQueryMixin:
    def eval_set_detail(self, eval_set_id: str) -> EvalSetDetail:
        with self.engine.connect() as connection:
            eval_set = self._eval_set_row(connection, eval_set_id)
            cases = self._eval_set_cases(connection, eval_set_id)
        return EvalSetDetail(self._row_dict(eval_set), cases)

    def eval_run_detail(self, eval_run_id: str) -> EvalRunDetail:
        with self.engine.connect() as connection:
            eval_run = self._eval_run_row(connection, eval_run_id)
            skill = self._skill_row(connection, eval_run["skill_id"])
            skill_version = self._skill_version_row(connection, eval_run["skill_version_id"])
            eval_set = self._eval_set_row(connection, eval_run["eval_set_id"])
            result_rows = {
                result["case_version_id"]: result
                for result in connection.execute(
                    select(tables.case_results).where(tables.case_results.c.run_id == eval_run_id)
                )
                .mappings()
                .all()
            }
            eval_set_cases = (
                connection.execute(
                    select(tables.eval_set_cases.c.case_version_id, tables.eval_set_cases.c.position)
                    .where(tables.eval_set_cases.c.eval_set_id == eval_run["eval_set_id"])
                    .order_by(tables.eval_set_cases.c.position)
                )
                .mappings()
                .all()
            )
            case_results = []
            for membership in eval_set_cases:
                result = result_rows.get(membership["case_version_id"])
                if result is None:
                    continue
                case_version = self._eval_case_version_row(connection, result["case_version_id"])
                eval_case = self._eval_case_row(connection, case_version["case_id"])
                result_artifact = None
                if result["result_artifact_id"] is not None:
                    result_artifact = (
                        connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == result["result_artifact_id"]))
                        .mappings()
                        .one_or_none()
                    )
                case_results.append(
                    {
                        "result": self._row_dict(result),
                        "result_artifact": self._row_dict(result_artifact) if result_artifact is not None else None,
                        "case": self._row_dict(eval_case),
                        "case_version": self._case_version_detail(connection, case_version),
                        "position": membership["position"],
                    }
                )
            skill_version_detail = self._skill_version_detail(connection, skill_version)
        return EvalRunDetail(self._row_dict(eval_run), self._row_dict(skill), skill_version_detail, self._row_dict(eval_set), case_results)
