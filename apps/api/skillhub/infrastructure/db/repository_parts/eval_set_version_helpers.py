from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, insert, select, update

from skillhub.domain.models import new_id
from skillhub.infrastructure.db import tables
from .core_helpers import clean_display_name


class EvalSetVersionHelperMixin:
    def _create_eval_set_version(
        self,
        connection,
        *,
        skill_id: str,
        eval_set_id: str,
        case_version_ids: list[str],
        created_at: datetime,
        actor: str,
        display_name: str | None = None,
    ) -> str:
        eval_set_version_id = new_id("evalsetver")
        connection.execute(
            insert(tables.eval_set_versions).values(
                id=eval_set_version_id,
                skill_id=skill_id,
                eval_set_id=eval_set_id,
                version_number=self._next_eval_set_version_number(connection, eval_set_id),
                display_name=clean_display_name(display_name),
                created_at=created_at,
                created_by=actor,
            )
        )
        self._replace_eval_set_version_cases(
            connection,
            eval_set_version_id=eval_set_version_id,
            skill_id=skill_id,
            case_version_ids=case_version_ids,
        )
        connection.execute(
            update(tables.eval_sets)
            .where(tables.eval_sets.c.id == eval_set_id)
            .values(current_version_id=eval_set_version_id, updated_at=created_at)
        )
        return eval_set_version_id

    def _update_current_eval_set_cases(
        self,
        connection,
        *,
        skill_id: str,
        eval_set_id: str,
        current_eval_set_version_id: str,
        case_version_ids: list[str],
        updated_at: datetime,
        actor: str,
        display_name: str | None = None,
    ) -> str:
        if self._eval_set_version_has_runs(connection, current_eval_set_version_id):
            return self._create_eval_set_version(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set_id,
                case_version_ids=case_version_ids,
                created_at=updated_at,
                actor=actor,
                display_name=display_name,
            )

        self._replace_eval_set_version_cases(
            connection,
            eval_set_version_id=current_eval_set_version_id,
            skill_id=skill_id,
            case_version_ids=case_version_ids,
        )
        connection.execute(
            update(tables.eval_sets)
            .where(tables.eval_sets.c.id == eval_set_id)
            .values(current_version_id=current_eval_set_version_id, updated_at=updated_at)
        )
        if display_name is not None:
            connection.execute(
                update(tables.eval_set_versions)
                .where(tables.eval_set_versions.c.id == current_eval_set_version_id)
                .values(display_name=clean_display_name(display_name))
            )
        return current_eval_set_version_id

    def _eval_set_case_version_ids(self, connection, eval_set_version_id: str) -> list[str]:
        return list(
            connection.execute(
                select(tables.eval_set_case_versions.c.case_version_id)
                .where(tables.eval_set_case_versions.c.eval_set_version_id == eval_set_version_id)
                .order_by(tables.eval_set_case_versions.c.position)
            ).scalars()
        )

    def _replace_eval_set_version_cases(
        self,
        connection,
        *,
        eval_set_version_id: str,
        skill_id: str,
        case_version_ids: list[str],
    ) -> None:
        connection.execute(
            delete(tables.eval_set_case_versions).where(
                tables.eval_set_case_versions.c.eval_set_version_id == eval_set_version_id
            )
        )
        if not case_version_ids:
            return
        connection.execute(
            insert(tables.eval_set_case_versions),
            [
                {
                    "eval_set_version_id": eval_set_version_id,
                    "skill_id": skill_id,
                    "case_version_id": case_version_id,
                    "position": position,
                }
                for position, case_version_id in enumerate(case_version_ids)
            ],
        )

    def _eval_set_version_has_runs(self, connection, eval_set_version_id: str) -> bool:
        return (
            connection.execute(
                select(tables.eval_runs.c.id)
                .where(tables.eval_runs.c.eval_set_version_id == eval_set_version_id)
                .limit(1)
            )
            .scalars()
            .one_or_none()
            is not None
        )
