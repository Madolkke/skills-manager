from __future__ import annotations

from typing import Any

from sqlalchemy import delete, insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError, NotFoundError, PermissionDeniedError
from skillhub.models.schema import orm


class GroupMixin:
    def list_groups(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = connection.execute(
                orm.select_entity(orm.Group).order_by(orm.Group.scope_type, orm.Group.scope_id, orm.Group.name)
            ).mappings().all()
            return [{**self._row_dict(row), "members": self._group_members(connection, row["id"])} for row in rows]

    def list_skill_groups(self, *, skill_id: str, actor: str | None = None) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            rows = (
                connection.execute(
                    orm.select_entity(orm.Group)
                    .where(orm.Group.scope_type == "skill")
                    .where(orm.Group.scope_id == skill_id)
                    .order_by(orm.Group.name)
                )
                .mappings()
                .all()
            )
            return [{**self._row_dict(row), "members": self._group_members(connection, row["id"])} for row in rows]

    def create_group(
        self,
        *,
        name: str,
        description: str | None,
        actor: str,
        scope_type: str = "global",
        scope_id: str = "default",
    ) -> dict[str, Any]:
        group_id = new_id("group")
        now = utc_now()
        clean_name = self._clean_group_name(name)
        clean_scope_type, clean_scope_id = self._clean_group_scope(scope_type, scope_id)
        with self._write_session() as connection:
            duplicate = connection.execute(
                select(orm.Group.id)
                .where(orm.Group.scope_type == clean_scope_type)
                .where(orm.Group.scope_id == clean_scope_id)
                .where(orm.Group.name == clean_name)
            ).scalar_one_or_none()
            if duplicate is not None:
                raise InvariantError(f"Group already exists: {clean_name}")
            connection.execute(
                insert(orm.Group).values(
                    id=group_id,
                    scope_type=clean_scope_type,
                    scope_id=clean_scope_id,
                    name=clean_name,
                    description=(description or "").strip(),
                    created_at=now,
                    updated_at=now,
                    created_by=actor,
                )
            )
        return self.group_detail(group_id)

    def create_skill_group(self, *, skill_id: str, name: str, description: str | None, actor: str) -> dict[str, Any]:
        with self._write_session() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
        return self.create_group(name=name, description=description, actor=actor, scope_type="skill", scope_id=skill_id)

    def update_group(self, *, group_id: str, name: str, description: str | None, actor: str) -> dict[str, Any]:
        now = utc_now()
        clean_name = self._clean_group_name(name)
        with self._write_session() as connection:
            group = self._group_row(connection, group_id)
            duplicate = (
                connection.execute(
                    select(orm.Group.id)
                    .where(orm.Group.scope_type == group["scope_type"])
                    .where(orm.Group.scope_id == group["scope_id"])
                    .where(orm.Group.name == clean_name)
                    .where(orm.Group.id != group_id)
                )
                .scalars()
                .first()
            )
            if duplicate is not None:
                raise InvariantError(f"Group already exists: {clean_name}")
            connection.execute(
                update(orm.Group)
                .where(orm.Group.id == group_id)
                .values(name=clean_name, description=(description or "").strip(), updated_at=now)
            )
        return self.group_detail(group_id)

    def update_skill_group(self, *, skill_id: str, group_id: str, name: str, description: str | None, actor: str) -> dict[str, Any]:
        with self._write_session() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            self._require_group_scope(self._group_row(connection, group_id), scope_type="skill", scope_id=skill_id)
        return self.update_group(group_id=group_id, name=name, description=description, actor=actor)

    def group_detail(self, group_id: str) -> dict[str, Any]:
        with self._read_session() as connection:
            group = self._group_row(connection, group_id)
            return {**self._row_dict(group), "members": self._group_members(connection, group_id)}

    def add_group_member(self, *, group_id: str, subject_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        now = utc_now()
        clean_subject_type = self._clean_subject_type(subject_type)
        if clean_subject_type != "user":
            raise InvariantError("Group members only support user subjects.")
        clean_subject_id = self._clean_subject_id(subject_id)
        with self._write_session() as connection:
            self._group_row(connection, group_id)
            if self._group_member_row(connection, group_id, clean_subject_type, clean_subject_id) is None:
                connection.execute(
                    insert(orm.GroupMembership).values(
                        group_id=group_id,
                        subject_type=clean_subject_type,
                        subject_id=clean_subject_id,
                        created_at=now,
                        created_by=actor,
                    )
                )
        return self.group_detail(group_id)

    def add_skill_group_member(self, *, skill_id: str, group_id: str, subject_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self._write_session() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            self._require_group_scope(self._group_row(connection, group_id), scope_type="skill", scope_id=skill_id)
        return self.add_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type, actor=actor)

    def remove_group_member(self, *, group_id: str, subject_id: str, subject_type: str = "user") -> dict[str, Any]:
        clean_subject_type = self._clean_subject_type(subject_type)
        clean_subject_id = self._clean_subject_id(subject_id)
        with self._write_session() as connection:
            self._group_row(connection, group_id)
            connection.execute(
                delete(orm.GroupMembership)
                .where(orm.GroupMembership.group_id == group_id)
                .where(orm.GroupMembership.subject_type == clean_subject_type)
                .where(orm.GroupMembership.subject_id == clean_subject_id)
            )
        return self.group_detail(group_id)

    def remove_skill_group_member(self, *, skill_id: str, group_id: str, subject_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self._write_session() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            self._require_group_scope(self._group_row(connection, group_id), scope_type="skill", scope_id=skill_id)
        return self.remove_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type)

    def delete_skill_group(self, *, skill_id: str, group_id: str, actor: str) -> dict[str, bool]:
        with self._write_session() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            self._require_group_scope(self._group_row(connection, group_id), scope_type="skill", scope_id=skill_id)
        return self.delete_group_admin(group_id=group_id, actor=actor)

    def delete_group_admin(self, *, group_id: str, actor: str = "admin-console") -> dict[str, bool]:
        now = utc_now()
        with self._write_session() as connection:
            group = self._group_row(connection, group_id)
            member_count = len(self._group_members(connection, group_id))
            role_count = len(connection.execute(
                select(orm.RoleAssignment.id)
                .where(orm.RoleAssignment.subject_type == "group")
                .where(orm.RoleAssignment.subject_id == group_id)
            ).scalars().all())
            connection.execute(delete(orm.GroupMembership).where(orm.GroupMembership.group_id == group_id))
            connection.execute(
                delete(orm.RoleAssignment)
                .where(orm.RoleAssignment.subject_type == "group")
                .where(orm.RoleAssignment.subject_id == group_id)
            )
            connection.execute(delete(orm.Group).where(orm.Group.id == group_id))
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="group.deleted",
                    resource_type="group",
                    resource_id=group_id,
                    payload={"name": group["name"], "member_count": member_count, "role_count": role_count},
                    created_at=now,
                )
            )
        return {"ok": True}

    def _actor_group_ids(self, connection, actor: str) -> list[str]:
        return list(
            connection.execute(
                select(orm.GroupMembership.group_id)
                .where(orm.GroupMembership.subject_type == "user")
                .where(orm.GroupMembership.subject_id == actor)
                .order_by(orm.GroupMembership.group_id)
            ).scalars()
        )

    def _group_row(self, connection, group_id: str):
        row = connection.execute(orm.select_entity(orm.Group).where(orm.Group.id == group_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Group not found: {group_id}")
        return row

    def _group_member_row(self, connection, group_id: str, subject_type: str, subject_id: str):
        return connection.execute(
            orm.select_entity(orm.GroupMembership)
            .where(orm.GroupMembership.group_id == group_id)
            .where(orm.GroupMembership.subject_type == subject_type)
            .where(orm.GroupMembership.subject_id == subject_id)
        ).mappings().one_or_none()

    def _group_members(self, connection, group_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            orm.select_entity(orm.GroupMembership)
            .where(orm.GroupMembership.group_id == group_id)
            .order_by(orm.GroupMembership.subject_type, orm.GroupMembership.subject_id)
        ).mappings().all()
        return [self._row_dict(row) for row in rows]

    def _clean_group_name(self, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise InvariantError("Group name is required.")
        if len(clean) > 120:
            raise InvariantError("Group name must be 120 characters or fewer.")
        return clean

    def _clean_group_scope(self, scope_type: str, scope_id: str) -> tuple[str, str]:
        clean_scope_type = scope_type.strip() or "global"
        clean_scope_id = scope_id.strip() or "default"
        if clean_scope_type not in {"global", "skill"}:
            raise InvariantError(f"Unsupported group scope_type: {clean_scope_type}")
        if clean_scope_type == "global":
            clean_scope_id = "default"
        if clean_scope_type == "skill":
            self._clean_subject_id(clean_scope_id)
        return clean_scope_type, clean_scope_id

    def _require_group_scope(self, group, *, scope_type: str, scope_id: str) -> None:
        clean_scope_type, clean_scope_id = self._clean_group_scope(scope_type, scope_id)
        if group["scope_type"] != clean_scope_type or group["scope_id"] != clean_scope_id:
            raise PermissionDeniedError("This group does not belong to the current skill.")

    def _clean_subject_id(self, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise InvariantError("Role subject_id is required.")
        return clean

    def _clean_subject_type(self, value: str) -> str:
        clean = value.strip() or "user"
        if clean not in {"user", "group"}:
            raise InvariantError(f"Unsupported role subject_type: {clean}")
        return clean
