from __future__ import annotations

from typing import Any

from sqlalchemy import func, insert, select

from skillhub.models.entities import new_id
from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.rules.tag_resources import decode_skill_tag_resource_id, encode_skill_tag_resource_id
from skillhub.models.schema import tables


class TagCatalogHelperMixin:
    def _tag_group_payload(self, connection, row) -> dict[str, Any]:
        return {
            **self._row_dict(row),
            "parent": self._tag_group_parent(connection, group_id=str(row["id"])),
            "values": self._tag_values(connection, str(row["id"])),
        }

    def _tag_group_row(self, connection, group_id: str):
        row = connection.execute(select(tables.tag_groups).where(tables.tag_groups.c.id == group_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"TagGroup not found: {group_id}")
        return row

    def _tag_value_row(self, connection, group_id: str, value: str):
        row = (
            connection.execute(
                select(tables.tag_values)
                .where(tables.tag_values.c.tag_group_id == group_id)
                .where(tables.tag_values.c.value == value)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"TagValue not found: {group_id}:{value}")
        return row

    def _skill_tag_resource_row(self, connection, resource_id: str):
        try:
            group_id, value = decode_skill_tag_resource_id(resource_id)
        except Exception as exc:
            raise InvariantError("Skill tag resource_id must use group_id:base64url(value).") from exc
        return self._tag_value_row(connection, group_id, value)

    def _tag_values(self, connection, group_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(tables.tag_values)
                .where(tables.tag_values.c.tag_group_id == group_id)
                .order_by(tables.tag_values.c.sort_order, tables.tag_values.c.value)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _tag_group_has_values(self, connection, *, group_id: str) -> bool:
        return self._tag_value_count(connection, group_id=group_id) > 0

    def _tag_value_count(self, connection, *, group_id: str) -> int:
        return int(connection.execute(
            select(func.count()).select_from(tables.tag_values).where(tables.tag_values.c.tag_group_id == group_id)
        ).scalar_one())

    def _tag_value_exists(self, connection, *, group_id: str, value: str) -> bool:
        return connection.execute(
            select(tables.tag_values.c.value)
            .where(tables.tag_values.c.tag_group_id == group_id)
            .where(tables.tag_values.c.value == value)
        ).scalar_one_or_none() is not None

    def _tag_group_reference_counts(self, connection, *, group_id: str) -> dict[str, int]:
        escaped_group_id = group_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return {
            "skill_tags": int(connection.execute(select(func.count()).select_from(tables.skill_tags).where(tables.skill_tags.c.tag_group_id == group_id)).scalar_one()),
            "roles": int(connection.execute(select(func.count()).select_from(tables.role_assignments).where(tables.role_assignments.c.resource_type == "skill_tag").where(tables.role_assignments.c.resource_id.like(f"{escaped_group_id}:%", escape="\\"))).scalar_one()),
            "parent_relation": int(connection.execute(select(func.count()).select_from(tables.tag_group_cascades).where(tables.tag_group_cascades.c.child_tag_group_id == group_id)).scalar_one()),
            "child_relations": int(connection.execute(select(func.count()).select_from(tables.tag_group_cascades).where(tables.tag_group_cascades.c.parent_tag_group_id == group_id)).scalar_one()),
        }

    def _tag_value_reference_counts(self, connection, *, group_id: str, value: str) -> dict[str, int]:
        resource_id = encode_skill_tag_resource_id(group_id, value)
        return {
            "skill_tags": int(connection.execute(select(func.count()).select_from(tables.skill_tags).where(tables.skill_tags.c.tag_group_id == group_id).where(tables.skill_tags.c.tag_value == value)).scalar_one()),
            "roles": int(connection.execute(select(func.count()).select_from(tables.role_assignments).where(tables.role_assignments.c.resource_type == "skill_tag").where(tables.role_assignments.c.resource_id == resource_id)).scalar_one()),
            "child_relations": int(connection.execute(select(func.count()).select_from(tables.tag_group_cascades).where(tables.tag_group_cascades.c.parent_tag_group_id == group_id).where(tables.tag_group_cascades.c.parent_tag_value == value)).scalar_one()),
        }

    def _clean_tag_group_id(self, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise InvariantError("Tag Group id is required.")
        if len(clean) > 80:
            raise InvariantError("Tag Group id must be 80 characters or fewer.")
        if not all(item.isalnum() or item in {"_", "-"} for item in clean):
            raise InvariantError("Tag Group id may only contain letters, numbers, '_' or '-'.")
        return clean

    def _clean_tag_value(self, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise InvariantError("Tag value is required.")
        return clean

    def _clean_display_text(self, value: str, label: str) -> str:
        clean = value.strip()
        if not clean:
            raise InvariantError(f"{label} is required.")
        if len(clean) > 120:
            raise InvariantError(f"{label} must be 120 characters or fewer.")
        return clean

    def _optional_display_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            return None
        if len(clean) > 120:
            raise InvariantError("Tag value display_name must be 120 characters or fewer.")
        return clean

    def _insert_tag_audit(
        self,
        connection,
        *,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any],
        created_at,
    ) -> None:
        connection.execute(
            insert(tables.audit_events).values(
                id=new_id("audit"),
                actor_ref=actor,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                payload=payload,
                created_at=created_at,
            )
        )

    def _tag_group_delete_error(self, counts: dict[str, int]) -> str:
        return "Tag Group 仍被引用，不能删除：" + "，".join(f"{key}={value}" for key, value in counts.items() if value)

    def _tag_value_delete_error(self, counts: dict[str, int]) -> str:
        return "Tag 值仍被引用，不能删除：" + "，".join(f"{key}={value}" for key, value in counts.items() if value)
