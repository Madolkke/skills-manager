from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from skillhub.infrastructure.db import tables


class CaseHistoryQueryMixin:
    def eval_case_history(self, case_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            rows = (
                connection.execute(
                    select(tables.eval_case_versions)
                    .where(tables.eval_case_versions.c.case_id == case_id)
                    .order_by(desc(tables.eval_case_versions.c.version_number))
                )
                .mappings()
                .all()
            )
            versions = []
            for case_version in rows:
                memberships = (
                    connection.execute(
                        select(
                            tables.eval_set_cases.c.eval_set_id,
                            tables.eval_set_cases.c.position,
                            tables.eval_sets.c.name,
                            tables.eval_sets.c.created_at,
                        )
                        .join(tables.eval_sets, tables.eval_set_cases.c.eval_set_id == tables.eval_sets.c.id)
                        .where(tables.eval_set_cases.c.case_version_id == case_version["id"])
                        .order_by(tables.eval_sets.c.name)
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
