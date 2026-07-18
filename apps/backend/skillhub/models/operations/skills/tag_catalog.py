from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, insert, select, update

from skillhub.models.entities import utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.skills.tag_catalog_helpers import TagCatalogHelperMixin
from skillhub.models.rules.tag_resources import encode_skill_tag_resource_id
from skillhub.models.schema import orm

logger = logging.getLogger(__name__)


class TagCatalogMixin(TagCatalogHelperMixin):
    def list_tag_groups(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = connection.execute(orm.select_entity(orm.TagGroup).order_by(orm.TagGroup.sort_order, orm.TagGroup.id)).mappings().all()
            return [self._tag_group_payload(connection, row) for row in rows]

    def create_tag_group(
        self,
        *,
        group_id: str,
        display_name: str,
        description: str,
        sort_order: int,
        required: bool = False,
        free_form: bool = False,
        actor: str,
    ) -> dict[str, Any]:
        now = utc_now()
        clean_id = self._clean_tag_group_id(group_id)
        if required and not free_form:
            logger.warning("tag group create rejected reason=required_enum_without_values group_id=%s", clean_id)
            raise InvariantError("必选 Tag Group（枚举组）至少需要先添加一个 Tag 值。")
        with self._write_session() as connection:
            if connection.execute(select(orm.TagGroup.id).where(orm.TagGroup.id == clean_id)).scalar_one_or_none() is not None:
                raise InvariantError(f"Tag Group already exists: {clean_id}")
            connection.execute(
                insert(orm.TagGroup).values(
                    id=clean_id,
                    display_name=self._clean_display_text(display_name, "Tag Group display_name"),
                    description=description.strip(),
                    sort_order=sort_order,
                    required=required,
                    free_form=free_form,
                    created_at=now,
                    updated_at=now,
                    created_by=actor,
                )
            )
        return self.tag_group_detail(clean_id)

    def update_tag_group(
        self,
        *,
        group_id: str,
        display_name: str,
        description: str,
        sort_order: int,
        required: bool = False,
        free_form: bool = False,
        actor: str,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._write_session() as connection:
            group = self._tag_group_row(connection, group_id)
            if free_form and self._tag_group_has_children(connection, group_id=group_id):
                logger.warning("tag group update rejected reason=free_parent_has_children group_id=%s", group_id)
                raise InvariantError("有子 Tag Group 的枚举组不能切换为自由 Tag Group，请先解除级联。")
            if required and not free_form and not self._tag_group_has_values(connection, group_id=group_id):
                logger.warning("tag group update rejected reason=required_enum_without_values group_id=%s", group_id)
                raise InvariantError("必选 Tag Group（枚举组）至少需要先添加一个 Tag 值。")
            connection.execute(
                update(orm.TagGroup)
                .where(orm.TagGroup.id == group_id)
                .values(
                    display_name=self._clean_display_text(display_name, "Tag Group display_name"),
                    description=description.strip(),
                    sort_order=sort_order,
                    required=required,
                    free_form=free_form,
                    updated_at=now,
                )
            )
            if bool(group["free_form"]) != free_form:
                self._insert_tag_audit(
                    connection,
                    actor=actor,
                    action="tag_group.type_changed",
                    resource_type="tag_group",
                    resource_id=group_id,
                    payload={"from_free_form": bool(group["free_form"]), "to_free_form": free_form},
                    created_at=now,
                )
        if bool(group["free_form"]) != free_form:
            logger.info("tag group type changed group_id=%s free_form=%s", group_id, free_form)
        return self.tag_group_detail(group_id)

    def delete_tag_group_admin(self, *, group_id: str) -> dict[str, bool]:
        now = utc_now()
        with self._write_session() as connection:
            group = self._tag_group_row(connection, group_id)
            counts = self._tag_group_reference_counts(connection, group_id=group_id)
            if any(counts.values()):
                logger.warning("tag group delete rejected group_id=%s references=%s", group_id, counts)
                raise InvariantError(self._tag_group_delete_error(counts))
            values = list(connection.execute(select(orm.TagValue.value).where(orm.TagValue.tag_group_id == group_id)).scalars())
            connection.execute(delete(orm.TagValue).where(orm.TagValue.tag_group_id == group_id))
            connection.execute(delete(orm.TagGroup).where(orm.TagGroup.id == group_id))
            self._insert_tag_audit(
                connection,
                actor="admin-console",
                action="tag_group.deleted",
                resource_type="tag_group",
                resource_id=group_id,
                payload={"display_name": group["display_name"], "value_count": len(values)},
                created_at=now,
            )
        return {"ok": True}

    def tag_group_detail(self, group_id: str) -> dict[str, Any]:
        with self._read_session() as connection:
            return self._tag_group_payload(connection, self._tag_group_row(connection, group_id))

    def create_tag_value(
        self,
        *,
        group_id: str,
        value: str,
        display_name: str | None,
        description: str,
        sort_order: int,
        actor: str,
    ) -> dict[str, Any]:
        now = utc_now()
        clean_value = self._clean_tag_value(value)
        with self._write_session() as connection:
            self._tag_group_row(connection, group_id)
            if self._tag_value_exists(connection, group_id=group_id, value=clean_value):
                raise InvariantError(f"Tag value already exists: {group_id}:{clean_value}")
            connection.execute(
                insert(orm.TagValue).values(
                    tag_group_id=group_id,
                    value=clean_value,
                    display_name=self._optional_display_text(display_name),
                    description=description.strip(),
                    sort_order=sort_order,
                    created_at=now,
                    updated_at=now,
                    created_by=actor,
                )
            )
        return self.tag_group_detail(group_id)

    def update_tag_value(
        self,
        *,
        group_id: str,
        value: str,
        display_name: str | None,
        description: str,
        sort_order: int,
        actor: str,
    ) -> dict[str, Any]:
        now = utc_now()
        clean_value = self._clean_tag_value(value)
        with self._write_session() as connection:
            self._tag_value_row(connection, group_id, clean_value)
            connection.execute(
                update(orm.TagValue)
                .where(orm.TagValue.tag_group_id == group_id)
                .where(orm.TagValue.value == clean_value)
                .values(
                    display_name=self._optional_display_text(display_name),
                    description=description.strip(),
                    sort_order=sort_order,
                    updated_at=now,
                )
            )
        return self.tag_group_detail(group_id)

    def delete_tag_value_admin(self, *, group_id: str, value: str) -> dict[str, bool]:
        now = utc_now()
        clean_value = self._clean_tag_value(value)
        with self._write_session() as connection:
            row = self._tag_value_row(connection, group_id, clean_value)
            group = self._tag_group_row(connection, group_id)
            counts = self._tag_value_reference_counts(connection, group_id=group_id, value=clean_value)
            if any(counts.values()):
                logger.warning("tag value delete rejected group_id=%s value=%s references=%s", group_id, clean_value, counts)
                raise InvariantError(self._tag_value_delete_error(counts))
            if group["required"] and not group["free_form"] and self._tag_value_count(connection, group_id=group_id) <= 1:
                logger.warning("tag value delete rejected reason=required_last_value group_id=%s value=%s", group_id, clean_value)
                raise InvariantError("必选 Tag Group（枚举组）至少需要保留一个 Tag 值。")
            connection.execute(
                delete(orm.TagValue)
                .where(orm.TagValue.tag_group_id == group_id)
                .where(orm.TagValue.value == clean_value)
            )
            self._insert_tag_audit(
                connection,
                actor="admin-console",
                action="tag_value.deleted",
                resource_type="tag_value",
                resource_id=encode_skill_tag_resource_id(group_id, clean_value),
                payload={"tag_group_id": group_id, "value": clean_value, "display_name": row["display_name"]},
                created_at=now,
            )
        return {"ok": True}
