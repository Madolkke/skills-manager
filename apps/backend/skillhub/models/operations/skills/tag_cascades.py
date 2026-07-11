from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import delete, insert, select

from skillhub.models.entities import utc_now
from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.schema import tables


logger = logging.getLogger(__name__)


class TagCascadeMixin:
    def tag_cascade_overview(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            relations = self._tag_group_relations(connection)
            diagnostics = self._tag_cascade_diagnostics(connection, relations=relations)
        return {"relations": relations, "diagnostics": diagnostics}

    def create_tag_cascade(
        self,
        *,
        parent_group_id: str,
        parent_value: str,
        child_group_id: str,
        actor: str,
    ) -> dict[str, Any]:
        now = utc_now()
        clean_parent_value = self._clean_tag_value(parent_value)
        with self.engine.begin() as connection:
            parent_group = self._tag_group_row(connection, parent_group_id)
            self._tag_value_row(connection, parent_group_id, clean_parent_value)
            self._tag_group_row(connection, child_group_id)
            if parent_group["free_form"]:
                logger.warning("tag cascade create rejected reason=free_form_parent parent_group_id=%s child_group_id=%s", parent_group_id, child_group_id)
                raise InvariantError("自由 Tag Group 不能作为级联父组。")
            if parent_group_id == child_group_id:
                logger.warning("tag cascade create rejected reason=self_reference group_id=%s", child_group_id)
                raise InvariantError("Tag Group 不能挂到自身的 Tag 值下。")
            if self._tag_group_parent(connection, group_id=child_group_id) is not None:
                logger.warning("tag cascade create rejected reason=child_already_attached child_group_id=%s", child_group_id)
                raise InvariantError("子 Tag Group 已有父级，请先解除现有级联。")
            if self._tag_cascade_would_cycle(connection, parent_group_id=parent_group_id, child_group_id=child_group_id):
                logger.warning("tag cascade create rejected reason=cycle parent_group_id=%s child_group_id=%s", parent_group_id, child_group_id)
                raise InvariantError("Tag 级联不能形成循环。")
            connection.execute(
                insert(tables.tag_group_cascades).values(
                    child_tag_group_id=child_group_id,
                    parent_tag_group_id=parent_group_id,
                    parent_tag_value=clean_parent_value,
                    created_at=now,
                    created_by=actor,
                )
            )
            self._insert_tag_audit(
                connection,
                actor=actor,
                action="tag_cascade.created",
                resource_type="tag_group",
                resource_id=child_group_id,
                payload={"parent_group_id": parent_group_id, "parent_value": clean_parent_value},
                created_at=now,
            )
        logger.info(
            "tag cascade created parent_group_id=%s parent_value=%s child_group_id=%s",
            parent_group_id,
            clean_parent_value,
            child_group_id,
        )
        return self.tag_cascade_overview()

    def delete_tag_cascade(self, *, child_group_id: str, actor: str) -> dict[str, Any]:
        now = utc_now()
        with self.engine.begin() as connection:
            relation = self._tag_group_parent_row(connection, group_id=child_group_id)
            if relation is None:
                raise NotFoundError(f"Tag cascade not found for child group: {child_group_id}")
            child_group = self._tag_group_row(connection, child_group_id)
            if child_group["required"]:
                logger.warning("tag cascade delete rejected reason=required_child child_group_id=%s", child_group_id)
                raise InvariantError("required 子 Tag Group 必须先改为可选，才能解除级联。")
            connection.execute(delete(tables.tag_group_cascades).where(tables.tag_group_cascades.c.child_tag_group_id == child_group_id))
            self._insert_tag_audit(
                connection,
                actor=actor,
                action="tag_cascade.deleted",
                resource_type="tag_group",
                resource_id=child_group_id,
                payload={
                    "parent_group_id": relation["parent_tag_group_id"],
                    "parent_value": relation["parent_tag_value"],
                },
                created_at=now,
            )
        logger.info("tag cascade deleted child_group_id=%s", child_group_id)
        return self.tag_cascade_overview()

    def _tag_group_relations(self, connection) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(tables.tag_group_cascades).order_by(
                    tables.tag_group_cascades.c.parent_tag_group_id,
                    tables.tag_group_cascades.c.parent_tag_value,
                    tables.tag_group_cascades.c.child_tag_group_id,
                )
            )
            .mappings()
            .all()
        )
        return [self._tag_cascade_payload(row) for row in rows]

    def _tag_group_parent(self, connection, *, group_id: str) -> dict[str, str] | None:
        row = self._tag_group_parent_row(connection, group_id=group_id)
        if row is None:
            return None
        return {"group_id": str(row["parent_tag_group_id"]), "value": str(row["parent_tag_value"])}

    def _tag_group_parent_row(self, connection, *, group_id: str):
        return (
            connection.execute(
                select(tables.tag_group_cascades).where(tables.tag_group_cascades.c.child_tag_group_id == group_id)
            )
            .mappings()
            .one_or_none()
        )

    def _tag_group_has_children(self, connection, *, group_id: str) -> bool:
        return connection.execute(
            select(tables.tag_group_cascades.c.child_tag_group_id)
            .where(tables.tag_group_cascades.c.parent_tag_group_id == group_id)
            .limit(1)
        ).scalar_one_or_none() is not None

    def _tag_cascade_would_cycle(self, connection, *, parent_group_id: str, child_group_id: str) -> bool:
        current = parent_group_id
        seen: set[str] = set()
        while current not in seen:
            if current == child_group_id:
                return True
            seen.add(current)
            parent = self._tag_group_parent(connection, group_id=current)
            if parent is None:
                return False
            current = parent["group_id"]
        return True

    def _active_tag_group_ids(
        self,
        *,
        all_group_ids: set[str],
        relations: list[dict[str, Any]],
        selected_tags: set[tuple[str, str]],
    ) -> set[str]:
        child_ids = {str(item["child_group_id"]) for item in relations}
        active = set(all_group_ids - child_ids)
        pending = list(relations)
        changed = True
        while changed:
            changed = False
            remaining: list[dict[str, Any]] = []
            for relation in pending:
                parent_key = (str(relation["parent_group_id"]), str(relation["parent_value"]))
                child_id = str(relation["child_group_id"])
                if parent_key in selected_tags and parent_key[0] in active:
                    if child_id not in active:
                        active.add(child_id)
                        changed = True
                else:
                    remaining.append(relation)
            pending = remaining
        return active

    def _tag_path_validity(
        self,
        connection,
        tags: set[tuple[str, str]],
        *,
        groups: dict[str, dict[str, Any]] | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> dict[tuple[str, str], bool]:
        group_rows = groups or self._tag_group_map(connection)
        relation_rows = relations or self._tag_group_relations(connection)
        active = self._active_tag_group_ids(all_group_ids=set(group_rows), relations=relation_rows, selected_tags=tags)
        return {tag: tag[0] in active for tag in tags}

    def _tag_cascade_diagnostics(self, connection, *, relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups = self._tag_group_map(connection)
        skill_rows = connection.execute(
            select(tables.skill_tags.c.skill_id, tables.skill_tags.c.tag_group_id, tables.skill_tags.c.tag_value)
            .join(tables.skills, tables.skills.c.id == tables.skill_tags.c.skill_id)
            .where(tables.skills.c.lifecycle_status == "active")
        ).all()
        tags_by_skill: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for skill_id, group_id, value in skill_rows:
            tags_by_skill[str(skill_id)].add((str(group_id), str(value)))
        active_skill_ids = set(
            str(item)
            for item in connection.execute(select(tables.skills.c.id).where(tables.skills.c.lifecycle_status == "active")).scalars()
        )
        orphaned: dict[str, set[str]] = defaultdict(set)
        missing_required: dict[str, set[str]] = defaultdict(set)
        for skill_id in active_skill_ids:
            selected = tags_by_skill.get(skill_id, set())
            active_groups = self._active_tag_group_ids(all_group_ids=set(groups), relations=relations, selected_tags=selected)
            for group_id, _ in selected:
                if group_id not in active_groups:
                    orphaned[group_id].add(skill_id)
            selected_groups = {group_id for group_id, _ in selected}
            for group_id in active_groups:
                if groups[group_id]["required"] and group_id not in selected_groups:
                    missing_required[group_id].add(skill_id)
        return [
            {
                "group_id": group_id,
                "orphaned_skill_ids": sorted(orphaned[group_id]),
                "missing_required_skill_ids": sorted(missing_required[group_id]),
            }
            for group_id in sorted(groups)
        ]

    def _tag_group_map(self, connection) -> dict[str, dict[str, Any]]:
        rows = connection.execute(select(tables.tag_groups)).mappings().all()
        return {str(row["id"]): self._row_dict(row) for row in rows}

    def _tag_cascade_payload(self, row) -> dict[str, Any]:
        return {
            "child_group_id": str(row["child_tag_group_id"]),
            "parent_group_id": str(row["parent_tag_group_id"]),
            "parent_value": str(row["parent_tag_value"]),
            "created_at": row["created_at"],
            "created_by": str(row["created_by"]),
        }
