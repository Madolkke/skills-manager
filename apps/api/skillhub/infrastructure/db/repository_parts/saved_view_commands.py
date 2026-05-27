from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert, select
from sqlalchemy.exc import IntegrityError

from skillhub.application.saved_views import normalize_saved_view_config, validate_saved_view_type
from skillhub.domain.errors import FieldError, FieldInvariantError, NotFoundError
from skillhub.domain.models import new_id, utc_now
from skillhub.infrastructure.db import tables


class SavedViewCommandMixin:
    def list_saved_views(self, *, skill_id: str, view_type: str = "run_history") -> list[dict[str, Any]]:
        validate_saved_view_type(view_type)
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            rows = (
                connection.execute(
                    select(tables.saved_views)
                    .where(tables.saved_views.c.skill_id == skill_id)
                    .where(tables.saved_views.c.view_type == view_type)
                    .order_by(tables.saved_views.c.name, desc(tables.saved_views.c.created_at))
                )
                .mappings()
                .all()
            )
        return [self._row_dict(row) for row in rows]

    def create_saved_view(
        self,
        *,
        skill_id: str,
        name: str,
        view_type: str,
        config: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        validate_saved_view_type(view_type)
        clean_name = name.strip()
        if not clean_name:
            raise FieldInvariantError("Saved view name is required.", [FieldError("name", "填写保存视图名称。", "saved_view.name_required")])
        values = {
            "id": new_id("view"),
            "skill_id": skill_id,
            "name": clean_name,
            "view_type": view_type,
            "config": normalize_saved_view_config(config),
            "created_at": utc_now(),
            "created_by": actor,
        }
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                connection.execute(insert(tables.saved_views).values(**values))
                row = connection.execute(select(tables.saved_views).where(tables.saved_views.c.id == values["id"])).mappings().one()
        except IntegrityError as exc:
            raise FieldInvariantError(
                f"Saved view name already exists: {clean_name}",
                [FieldError("name", "保存视图名称已存在。", "saved_view.name_conflict")],
            ) from exc
        return self._row_dict(row)

    def delete_saved_view(self, saved_view_id: str) -> dict[str, bool]:
        with self.engine.begin() as connection:
            result = connection.execute(tables.saved_views.delete().where(tables.saved_views.c.id == saved_view_id))
            if result.rowcount == 0:
                raise NotFoundError(f"SavedView not found: {saved_view_id}")
        return {"ok": True}
