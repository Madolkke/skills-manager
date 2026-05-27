from __future__ import annotations

from sqlalchemy import select

from skillhub.infrastructure.db import tables
from .results import EvalRunDetail, EvalSetVersionDetail


class DetailQueryMixin:
    def eval_set_version_detail(self, eval_set_version_id: str) -> EvalSetVersionDetail:
        with self.engine.connect() as connection:
            eval_set_version = self._eval_set_version_row(connection, eval_set_version_id)
            eval_set = (
                connection.execute(select(tables.eval_sets).where(tables.eval_sets.c.id == eval_set_version["eval_set_id"]))
                .mappings()
                .one()
            )
            cases = self._eval_set_cases(connection, eval_set_version_id)
        return EvalSetVersionDetail(self._row_dict(eval_set_version), self._row_dict(eval_set), cases)

    def eval_run_detail(self, eval_run_id: str) -> EvalRunDetail:
        with self.engine.connect() as connection:
            eval_run = self._eval_run_row(connection, eval_run_id)
            skill = self._skill_row(connection, eval_run["skill_id"])
            skill_version = self._skill_version_row(connection, eval_run["skill_version_id"])
            eval_set_version = self._eval_set_version_row(connection, eval_run["eval_set_version_id"])
            case_results = []
            for result in (
                connection.execute(
                    select(tables.case_results)
                    .where(tables.case_results.c.run_id == eval_run_id)
                    .order_by(tables.case_results.c.case_version_id)
                )
                .mappings()
                .all()
            ):
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
                    }
                )
            skill_version_detail = self._skill_version_detail(connection, skill_version)
        return EvalRunDetail(self._row_dict(eval_run), self._row_dict(skill), skill_version_detail, self._row_dict(eval_set_version), case_results)
