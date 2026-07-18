from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from skillhub.models.schema import orm


class CaseHistoryQueryMixin:
    def eval_case_history(self, case_id: str) -> dict[str, Any]:
        with self._read_session() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            rows = (
                connection.execute(
                    orm.select_entity(orm.EvalCaseVersion)
                    .where(orm.EvalCaseVersion.case_id == case_id)
                    .order_by(desc(orm.EvalCaseVersion.version_number))
                )
                .mappings()
                .all()
            )
            versions = []
            for case_version in rows:
                memberships = (
                    connection.execute(
                        select(
                            orm.EvalSetCase.eval_set_id,
                            orm.EvalSetCase.position,
                            orm.EvalSet.name,
                            orm.EvalSet.created_at,
                        )
                        .join(orm.EvalSet, orm.EvalSetCase.eval_set_id == orm.EvalSet.id)
                        .where(orm.EvalSetCase.case_id == case_id)
                        .order_by(orm.EvalSet.name)
                    )
                    .mappings()
                    .all()
                )
                versions.append(
                    {
                        "case_version": self._case_version_detail(connection, case_version),
                        "included_in_eval_sets": [
                            {
                                "eval_set_id": membership["eval_set_id"],
                                "name": membership["name"],
                                "position": membership["position"],
                                "created_at": membership["created_at"],
                            }
                            for membership in memberships
                        ],
                    }
                )
        return {"case": self._row_dict(eval_case), "versions": versions}
