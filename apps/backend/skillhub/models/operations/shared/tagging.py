from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.rules.tag_resources import encode_skill_tag_resource_id
from skillhub.models.schema import tables


class TaggingHelperMixin:
    def _skill_tags(self, connection, skill_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(
                    tables.skill_tags.c.tag_group_id,
                    tables.tag_groups.c.display_name.label("group_display_name"),
                    tables.skill_tags.c.tag_value,
                    tables.tag_values.c.display_name.label("value_display_name"),
                    tables.tag_groups.c.sort_order.label("group_sort_order"),
                    tables.tag_values.c.sort_order.label("value_sort_order"),
                )
                .join(tables.tag_groups, tables.tag_groups.c.id == tables.skill_tags.c.tag_group_id)
                .join(
                    tables.tag_values,
                    (tables.tag_values.c.tag_group_id == tables.skill_tags.c.tag_group_id)
                    & (tables.tag_values.c.value == tables.skill_tags.c.tag_value),
                )
                .where(tables.skill_tags.c.skill_id == skill_id)
                .order_by(
                    tables.tag_groups.c.sort_order,
                    tables.skill_tags.c.tag_group_id,
                    tables.tag_values.c.sort_order,
                    tables.skill_tags.c.tag_value,
                )
            )
            .mappings()
            .all()
        )
        keys = {(str(row["tag_group_id"]), str(row["tag_value"])) for row in rows}
        validity = self._tag_path_validity(connection, keys)
        return [
            {
                "group_id": row["tag_group_id"],
                "group_display_name": row["group_display_name"],
                "value": row["tag_value"],
                "value_display_name": row["value_display_name"],
                "path_valid": validity[(str(row["tag_group_id"]), str(row["tag_value"]))],
            }
            for row in rows
        ]

    def _skill_tag_resource_ids(self, connection, skill_id: str) -> list[str]:
        return [
            encode_skill_tag_resource_id(tag["group_id"], tag["value"])
            for tag in self._skill_tags(connection, skill_id)
            if tag["path_valid"]
        ]

    def _clean_skill_tags(self, tags: list[dict[str, Any]] | None) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in tags or []:
            raw_group_id = item.get("group_id", "") if isinstance(item, dict) else getattr(item, "group_id", "")
            raw_value = item.get("value", "") if isinstance(item, dict) else getattr(item, "value", "")
            group_id = str(raw_group_id).strip()
            value = str(raw_value).strip()
            if not group_id or not value:
                raise FieldInvariantError(
                    "Skill tag requires tag group and value.",
                    [FieldError(field="tags", message="Tag 需要选择 Tag Group 和 Tag 值。", code="skill_tag.required")],
                )
            key = (group_id, value)
            if key not in seen:
                result.append({"group_id": group_id, "value": value})
                seen.add(key)
        return result

    def _require_tag_values_exist(self, connection, tags: list[dict[str, str]]) -> None:
        if not tags:
            return
        groups = self._tag_group_map(connection)
        unknown_groups = sorted({tag["group_id"] for tag in tags if tag["group_id"] not in groups})
        if unknown_groups:
            raise FieldInvariantError(
                "Skill tag group does not exist.",
                [FieldError(field="tags", message=f"Tag Group 不存在：{'、'.join(unknown_groups)}", code="skill_tag.group_undefined")],
            )
        keys = [(tag["group_id"], tag["value"]) for tag in tags]
        existing = set(
            connection.execute(
                select(tables.tag_values.c.tag_group_id, tables.tag_values.c.value).where(
                    tuple_(tables.tag_values.c.tag_group_id, tables.tag_values.c.value).in_(keys)
                )
            ).all()
        )
        missing = [
            tag
            for tag in tags
            if (tag["group_id"], tag["value"]) not in existing and not groups[tag["group_id"]]["free_form"]
        ]
        if missing:
            message = "、".join(f"{item['group_id']}:{item['value']}" for item in missing)
            raise FieldInvariantError(
                "Skill tag must exist in an enum tag group.",
                [FieldError(field="tags", message=f"枚举 Tag 必须先在后台定义：{message}", code="skill_tag.undefined")],
            )

    def _require_required_tag_groups_present(self, connection, tags: list[dict[str, str]]) -> None:
        groups = self._tag_group_map(connection)
        relations = self._tag_group_relations(connection)
        selected = {(tag["group_id"], tag["value"]) for tag in tags}
        active = self._active_tag_group_ids(all_group_ids=set(groups), relations=relations, selected_tags=selected)
        orphaned = sorted({group_id for group_id, _ in selected if group_id not in active})
        if orphaned:
            names = "、".join(str(groups.get(group_id, {}).get("display_name") or group_id) for group_id in orphaned)
            raise FieldInvariantError(
                "Skill tags contain inactive cascade groups.",
                [FieldError(field="tags", message=f"以下子 Tag Group 尚未被父 Tag 激活：{names}", code="skill_tag.orphaned")],
            )
        selected_group_ids = {group_id for group_id, _ in selected}
        missing = [
            groups[group_id]["display_name"]
            for group_id in active
            if groups[group_id]["required"] and group_id not in selected_group_ids
        ]
        if missing:
            raise FieldInvariantError(
                "Skill tags must include active required tag groups.",
                [FieldError(field="tags", message=f"请为必选 Tag Group 选择 Tag：{'、'.join(sorted(missing))}", code="skill_tag.required_group_missing")],
            )

    def _ensure_free_tag_values(
        self,
        connection,
        *,
        tags: list[dict[str, str]],
        actor: str,
        created_at: datetime,
    ) -> None:
        if not tags:
            return
        groups = self._tag_group_map(connection)
        free_values: dict[str, set[str]] = defaultdict(set)
        for tag in tags:
            group = groups.get(tag["group_id"])
            if group and group["free_form"]:
                free_values[tag["group_id"]].add(tag["value"])
        for group_id in sorted(free_values):
            connection.execute(select(tables.tag_groups.c.id).where(tables.tag_groups.c.id == group_id).with_for_update())
            existing = set(
                connection.execute(
                    select(tables.tag_values.c.value)
                    .where(tables.tag_values.c.tag_group_id == group_id)
                    .where(tables.tag_values.c.value.in_(sorted(free_values[group_id])))
                ).scalars()
            )
            missing = sorted(free_values[group_id] - existing)
            next_order = int(
                connection.execute(
                    select(func.coalesce(func.max(tables.tag_values.c.sort_order), -1) + 1)
                    .where(tables.tag_values.c.tag_group_id == group_id)
                ).scalar_one()
            )
            for offset, value in enumerate(missing):
                statement = pg_insert(tables.tag_values).values(
                    tag_group_id=group_id,
                    value=value,
                    display_name=None,
                    description="",
                    sort_order=next_order + offset,
                    created_at=created_at,
                    updated_at=created_at,
                    created_by=actor,
                )
                connection.execute(
                    statement.on_conflict_do_nothing(
                        index_elements=[tables.tag_values.c.tag_group_id, tables.tag_values.c.value]
                    )
                )

    def _protected_skill_tags(self, connection, tags: set[tuple[str, str]]) -> set[tuple[str, str]]:
        if not tags:
            return set()
        resource_ids = [encode_skill_tag_resource_id(group_id, value) for group_id, value in tags]
        protected_ids = set(
            connection.execute(
                select(tables.role_assignments.c.resource_id)
                .where(tables.role_assignments.c.resource_type == "skill_tag")
                .where(tables.role_assignments.c.resource_id.in_(resource_ids))
            ).scalars()
        )
        return {tag for tag in tags if encode_skill_tag_resource_id(tag[0], tag[1]) in protected_ids}

    def _set_skill_tags(
        self,
        connection,
        *,
        skill_id: str,
        tags: list[dict[str, Any]],
        actor: str,
        created_at: datetime,
        enforce_protected: bool = True,
    ) -> None:
        clean_tags = self._clean_skill_tags(tags)
        self._require_tag_values_exist(connection, clean_tags)
        self._require_required_tag_groups_present(connection, clean_tags)
        self._ensure_free_tag_values(connection, tags=clean_tags, actor=actor, created_at=created_at)
        current_tags = {(tag["group_id"], tag["value"]) for tag in self._skill_tags(connection, skill_id)}
        next_tags = {(tag["group_id"], tag["value"]) for tag in clean_tags}
        protected_changes = self._protected_skill_tags(connection, current_tags.symmetric_difference(next_tags))
        if enforce_protected and protected_changes:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="tag.protected.manage")
        connection.execute(delete(tables.skill_tags).where(tables.skill_tags.c.skill_id == skill_id))
        for tag in clean_tags:
            connection.execute(
                insert(tables.skill_tags).values(
                    skill_id=skill_id,
                    tag_group_id=tag["group_id"],
                    tag_value=tag["value"],
                    created_at=created_at,
                    created_by=actor,
                )
            )

    def _require_protected_tag_creation_permission(self, connection, *, tags: list[dict[str, Any]], actor: str) -> None:
        clean_tags = self._clean_skill_tags(tags)
        self._require_tag_values_exist(connection, clean_tags)
        self._require_required_tag_groups_present(connection, clean_tags)
        protected_tags = self._protected_skill_tags(connection, {(tag["group_id"], tag["value"]) for tag in clean_tags})
        if not protected_tags:
            return
        allowed_tags = {
            source["resource_id"]
            for source in self._actor_tag_role_sources(connection, actor=actor, tags=protected_tags)
            if source["role"] == "admin"
        }
        missing = {tag for tag in protected_tags if encode_skill_tag_resource_id(tag[0], tag[1]) not in allowed_tags}
        if missing:
            formatted = ", ".join(sorted(f"{group_id}:{value}" for group_id, value in missing))
            raise InvariantError(f"Adding protected Skill tags requires admin role: {formatted}")
