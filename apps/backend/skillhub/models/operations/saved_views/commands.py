from __future__ import annotations

from typing import Any

from sqlalchemy import delete, desc, insert
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import FieldError, FieldInvariantError, NotFoundError
from skillhub.models.rules.saved_views import normalize_saved_view_config, validate_saved_view_type
from skillhub.models.schema import orm


class SavedViewCommandMixin:
    def list_saved_views(self, *, skill_id: str, view_type: str = "run_history") -> list[dict[str, Any]]:
        validate_saved_view_type(view_type)
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            rows = (
                connection.execute(
                    orm.select_entity(orm.SavedView)
                    .where(orm.SavedView.skill_id == skill_id)
                    .where(orm.SavedView.view_type == view_type)
                    .order_by(orm.SavedView.name, desc(orm.SavedView.created_at))
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
        """Legacy store facade; SavedViewService owns normal validation."""
        validate_saved_view_type(view_type)
        clean_name = name.strip()
        if not clean_name:
            raise FieldInvariantError("Saved view name is required.", [FieldError("name", "填写保存视图名称。", "saved_view.name_required")])
        return self.insert_saved_view(
            skill_id=skill_id,
            name=clean_name,
            view_type=view_type,
            config=normalize_saved_view_config(config),
            actor=actor,
        )

    def insert_saved_view(
        self,
        *,
        skill_id: str,
        name: str,
        view_type: str,
        config: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        values = {
            "id": new_id("view"),
            "skill_id": skill_id,
            "name": name,
            "view_type": view_type,
            "config": config,
            "created_at": utc_now(),
            "created_by": actor,
        }
        try:
            with self._write_session() as connection:
                self._skill_row(connection, skill_id)
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="saved_view.manage")
                connection.execute(insert(orm.SavedView).values(**values))
                row = connection.execute(orm.select_entity(orm.SavedView).where(orm.SavedView.id == values["id"])).mappings().one()
        except IntegrityError as exc:
            raise FieldInvariantError(
                f"Saved view name already exists: {name}",
                [FieldError("name", "保存视图名称已存在。", "saved_view.name_conflict")],
            ) from exc
        return self._row_dict(row)

    def delete_saved_view(self, saved_view_id: str, actor: str | None = None) -> dict[str, bool]:
        """Legacy store facade; SavedViewService owns normal delete orchestration."""
        return self.delete_saved_view_record(saved_view_id=saved_view_id, actor=actor)

    def delete_saved_view_record(self, *, saved_view_id: str, actor: str | None = None) -> dict[str, bool]:
        with self._write_session() as connection:
            row = connection.execute(orm.select_entity(orm.SavedView).where(orm.SavedView.id == saved_view_id)).mappings().one_or_none()
            if row is None:
                raise NotFoundError(f"SavedView not found: {saved_view_id}")
            if actor is not None:
                self._require_skill_permission(connection, skill_id=row["skill_id"], actor=actor, permission="saved_view.manage")
            result = connection.execute(delete(orm.SavedView).where(orm.SavedView.id == saved_view_id))
            if result.rowcount == 0:
                raise NotFoundError(f"SavedView not found: {saved_view_id}")
        return {"ok": True}
