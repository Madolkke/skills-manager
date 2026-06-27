from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, insert, select, update

from skillhub.models.schema import tables


class EvalSetCaseHelperMixin:
    def _update_eval_set_cases(
        self,
        connection,
        *,
        skill_id: str,
        eval_set_id: str,
        case_ids: list[str],
        updated_at: datetime,
    ) -> str:
        self._replace_eval_set_cases(
            connection,
            eval_set_id=eval_set_id,
            skill_id=skill_id,
            case_ids=case_ids,
        )
        connection.execute(
            update(tables.eval_sets)
            .where(tables.eval_sets.c.id == eval_set_id)
            .values(updated_at=updated_at)
        )
        return eval_set_id

    def _eval_set_case_ids(self, connection, eval_set_id: str) -> list[str]:
        return list(
            connection.execute(
                select(tables.eval_set_cases.c.case_id)
                .where(tables.eval_set_cases.c.eval_set_id == eval_set_id)
                .order_by(tables.eval_set_cases.c.position)
            ).scalars()
        )

    def _eval_set_case_version_ids(self, connection, eval_set_id: str) -> list[str]:
        case_ids = self._eval_set_case_ids(connection, eval_set_id)
        if not case_ids:
            return []
        rows = (
            connection.execute(
                select(tables.eval_cases.c.id, tables.eval_cases.c.current_version_id)
                .where(tables.eval_cases.c.id.in_(case_ids))
            )
            .mappings()
            .all()
        )
        current_by_case = {row["id"]: row["current_version_id"] for row in rows if row["current_version_id"]}
        return [current_by_case[case_id] for case_id in case_ids if case_id in current_by_case]

    def _require_eval_set_contains_case(self, connection, *, eval_set_id: str, case_id: str) -> None:
        membership = (
            connection.execute(
                select(tables.eval_set_cases.c.case_id)
                .where(tables.eval_set_cases.c.eval_set_id == eval_set_id)
                .where(tables.eval_set_cases.c.case_id == case_id)
            )
            .scalars()
            .one_or_none()
        )
        if membership is None:
            from skillhub.models.errors import NotFoundError

            raise NotFoundError(f"EvalCase not found in EvalSet: {case_id}")

    def _replace_eval_set_cases(
        self,
        connection,
        *,
        eval_set_id: str,
        skill_id: str,
        case_ids: list[str],
    ) -> None:
        connection.execute(
            delete(tables.eval_set_cases).where(tables.eval_set_cases.c.eval_set_id == eval_set_id)
        )
        if not case_ids:
            return
        connection.execute(
            insert(tables.eval_set_cases),
            [
                {
                    "eval_set_id": eval_set_id,
                    "skill_id": skill_id,
                    "case_id": case_id,
                    "position": position,
                }
                for position, case_id in enumerate(case_ids)
            ],
        )
