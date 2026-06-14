from __future__ import annotations

from sqlalchemy import delete, insert, select, update

from skillhub.infrastructure.db import tables


class EvalSetCaseHelperMixin:
    def _update_eval_set_cases(
        self,
        connection,
        *,
        skill_id: str,
        eval_set_id: str,
        case_version_ids: list[str],
        updated_at: datetime,
    ) -> str:
        self._replace_eval_set_cases(
            connection,
            eval_set_id=eval_set_id,
            skill_id=skill_id,
            case_version_ids=case_version_ids,
        )
        connection.execute(
            update(tables.eval_sets)
            .where(tables.eval_sets.c.id == eval_set_id)
            .values(updated_at=updated_at)
        )
        return eval_set_id

    def _eval_set_case_version_ids(self, connection, eval_set_id: str) -> list[str]:
        return list(
            connection.execute(
                select(tables.eval_set_cases.c.case_version_id)
                .where(tables.eval_set_cases.c.eval_set_id == eval_set_id)
                .order_by(tables.eval_set_cases.c.position)
            ).scalars()
        )

    def _replace_eval_set_cases(
        self,
        connection,
        *,
        eval_set_id: str,
        skill_id: str,
        case_version_ids: list[str],
    ) -> None:
        connection.execute(
            delete(tables.eval_set_cases).where(tables.eval_set_cases.c.eval_set_id == eval_set_id)
        )
        if not case_version_ids:
            return
        connection.execute(
            insert(tables.eval_set_cases),
            [
                {
                    "eval_set_id": eval_set_id,
                    "skill_id": skill_id,
                    "case_version_id": case_version_id,
                    "position": position,
                }
                for position, case_version_id in enumerate(case_version_ids)
            ],
        )
