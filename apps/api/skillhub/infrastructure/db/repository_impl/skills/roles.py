from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, desc, insert, or_, select, update

from skillhub.domain.errors import InvariantError, NotFoundError, PermissionDeniedError
from skillhub.domain.models import new_id, utc_now
from skillhub.domain.permissions import ROLE_PERMISSIONS, VALID_ROLES, permission_label, role_allows
from skillhub.domain.tag_resources import decode_skill_tag_resource_id, encode_skill_tag_resource_id
from skillhub.infrastructure.db import tables


class RoleMixin:
    def list_skill_role_assignments(self, *, skill_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_role_assignments(connection, skill_id)

    def list_all_role_assignments(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(tables.role_assignments).order_by(tables.role_assignments.c.resource_type, tables.role_assignments.c.resource_id)).mappings().all()
            return [self._row_dict(row) for row in rows]

    def list_tag_groups(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(tables.tag_groups).order_by(tables.tag_groups.c.sort_order, tables.tag_groups.c.id)).mappings().all()
            return [{**self._row_dict(row), "values": self._tag_values(connection, row["id"])} for row in rows]

    def create_tag_group(self, *, group_id: str, display_name: str, description: str, sort_order: int, actor: str) -> dict[str, Any]:
        created_at = utc_now()
        clean_id = self._clean_tag_group_id(group_id)
        with self.engine.begin() as connection:
            if connection.execute(select(tables.tag_groups.c.id).where(tables.tag_groups.c.id == clean_id)).scalar_one_or_none() is not None:
                raise InvariantError(f"Tag Group already exists: {clean_id}")
            connection.execute(
                insert(tables.tag_groups).values(
                    id=clean_id,
                    display_name=self._clean_display_text(display_name, "Tag Group display_name"),
                    description=description.strip(),
                    sort_order=sort_order,
                    created_at=created_at,
                    updated_at=created_at,
                    created_by=actor,
                )
            )
        return self.tag_group_detail(clean_id)

    def update_tag_group(self, *, group_id: str, display_name: str, description: str, sort_order: int, actor: str) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            self._tag_group_row(connection, group_id)
            connection.execute(
                update(tables.tag_groups)
                .where(tables.tag_groups.c.id == group_id)
                .values(
                    display_name=self._clean_display_text(display_name, "Tag Group display_name"),
                    description=description.strip(),
                    sort_order=sort_order,
                    updated_at=updated_at,
                )
            )
        return self.tag_group_detail(group_id)

    def delete_tag_group_admin(self, *, group_id: str) -> dict[str, bool]:
        deleted_at = utc_now()
        with self.engine.begin() as connection:
            group = self._tag_group_row(connection, group_id)
            values = list(connection.execute(select(tables.tag_values.c.value).where(tables.tag_values.c.tag_group_id == group_id)).scalars())
            resource_ids = [encode_skill_tag_resource_id(group_id, value) for value in values]
            connection.execute(delete(tables.skill_tags).where(tables.skill_tags.c.tag_group_id == group_id))
            if resource_ids:
                connection.execute(
                    delete(tables.role_assignments)
                    .where(tables.role_assignments.c.resource_type == "skill_tag")
                    .where(tables.role_assignments.c.resource_id.in_(resource_ids))
                )
            connection.execute(delete(tables.tag_values).where(tables.tag_values.c.tag_group_id == group_id))
            connection.execute(delete(tables.tag_groups).where(tables.tag_groups.c.id == group_id))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref="admin-console",
                    action="tag_group.deleted",
                    resource_type="tag_group",
                    resource_id=group_id,
                    payload={"display_name": group["display_name"], "value_count": len(values)},
                    created_at=deleted_at,
                )
            )
        return {"ok": True}

    def tag_group_detail(self, group_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            group = self._tag_group_row(connection, group_id)
            return {**self._row_dict(group), "values": self._tag_values(connection, group_id)}

    def create_tag_value(self, *, group_id: str, value: str, display_name: str | None, description: str, sort_order: int, actor: str) -> dict[str, Any]:
        created_at = utc_now()
        clean_value = self._clean_tag_value(value)
        with self.engine.begin() as connection:
            self._tag_group_row(connection, group_id)
            if (
                connection.execute(
                    select(tables.tag_values.c.value)
                    .where(tables.tag_values.c.tag_group_id == group_id)
                    .where(tables.tag_values.c.value == clean_value)
                ).scalar_one_or_none()
                is not None
            ):
                raise InvariantError(f"Tag value already exists: {group_id}:{clean_value}")
            connection.execute(
                insert(tables.tag_values).values(
                    tag_group_id=group_id,
                    value=clean_value,
                    display_name=self._optional_display_text(display_name),
                    description=description.strip(),
                    sort_order=sort_order,
                    created_at=created_at,
                    updated_at=created_at,
                    created_by=actor,
                )
            )
        return self.tag_group_detail(group_id)

    def update_tag_value(self, *, group_id: str, value: str, display_name: str | None, description: str, sort_order: int, actor: str) -> dict[str, Any]:
        updated_at = utc_now()
        clean_value = self._clean_tag_value(value)
        with self.engine.begin() as connection:
            self._tag_value_row(connection, group_id, clean_value)
            connection.execute(
                update(tables.tag_values)
                .where(tables.tag_values.c.tag_group_id == group_id)
                .where(tables.tag_values.c.value == clean_value)
                .values(
                    display_name=self._optional_display_text(display_name),
                    description=description.strip(),
                    sort_order=sort_order,
                    updated_at=updated_at,
                )
            )
        return self.tag_group_detail(group_id)

    def delete_tag_value_admin(self, *, group_id: str, value: str) -> dict[str, bool]:
        deleted_at = utc_now()
        clean_value = self._clean_tag_value(value)
        with self.engine.begin() as connection:
            row = self._tag_value_row(connection, group_id, clean_value)
            resource_id = encode_skill_tag_resource_id(group_id, clean_value)
            connection.execute(
                delete(tables.skill_tags)
                .where(tables.skill_tags.c.tag_group_id == group_id)
                .where(tables.skill_tags.c.tag_value == clean_value)
            )
            connection.execute(
                delete(tables.role_assignments)
                .where(tables.role_assignments.c.resource_type == "skill_tag")
                .where(tables.role_assignments.c.resource_id == resource_id)
            )
            connection.execute(
                delete(tables.tag_values)
                .where(tables.tag_values.c.tag_group_id == group_id)
                .where(tables.tag_values.c.value == clean_value)
            )
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref="admin-console",
                    action="tag_value.deleted",
                    resource_type="tag_value",
                    resource_id=resource_id,
                    payload={"tag_group_id": group_id, "value": clean_value, "display_name": row["display_name"]},
                    created_at=deleted_at,
                )
            )
        return {"ok": True}

    def skill_capabilities(self, *, skill_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_capabilities(connection, skill_id=skill_id, actor=actor, subject_type=subject_type)

    def list_groups(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(tables.groups).order_by(tables.groups.c.scope_type, tables.groups.c.scope_id, tables.groups.c.name)).mappings().all()
            return [{**self._row_dict(row), "members": self._group_members(connection, row["id"])} for row in rows]

    def list_skill_groups(self, *, skill_id: str, actor: str | None = None) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            rows = (
                connection.execute(
                    select(tables.groups)
                    .where(tables.groups.c.scope_type == "skill")
                    .where(tables.groups.c.scope_id == skill_id)
                    .order_by(tables.groups.c.name)
                )
                .mappings()
                .all()
            )
            return [{**self._row_dict(row), "members": self._group_members(connection, row["id"])} for row in rows]

    def create_group(self, *, name: str, description: str, actor: str, scope_type: str = "global", scope_id: str = "default") -> dict[str, Any]:
        group_id = new_id("group")
        created_at = utc_now()
        clean_name = self._clean_group_name(name)
        clean_scope_type, clean_scope_id = self._clean_group_scope(scope_type, scope_id)
        with self.engine.begin() as connection:
            if (
                connection.execute(
                    select(tables.groups.c.id)
                    .where(tables.groups.c.scope_type == clean_scope_type)
                    .where(tables.groups.c.scope_id == clean_scope_id)
                    .where(tables.groups.c.name == clean_name)
                ).scalar_one_or_none()
                is not None
            ):
                raise InvariantError(f"Group already exists: {clean_name}")
            connection.execute(
                insert(tables.groups).values(
                    id=group_id,
                    scope_type=clean_scope_type,
                    scope_id=clean_scope_id,
                    name=clean_name,
                    description=description.strip(),
                    created_at=created_at,
                    updated_at=created_at,
                    created_by=actor,
                )
            )
        return self.group_detail(group_id)

    def create_skill_group(self, *, skill_id: str, name: str, description: str, actor: str) -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
        return self.create_group(name=name, description=description, actor=actor, scope_type="skill", scope_id=skill_id)

    def update_group(self, *, group_id: str, name: str, description: str, actor: str) -> dict[str, Any]:
        updated_at = utc_now()
        clean_name = self._clean_group_name(name)
        with self.engine.begin() as connection:
            group = self._group_row(connection, group_id)
            duplicate = (
                connection.execute(
                    select(tables.groups.c.id)
                    .where(tables.groups.c.scope_type == group["scope_type"])
                    .where(tables.groups.c.scope_id == group["scope_id"])
                    .where(tables.groups.c.name == clean_name)
                    .where(tables.groups.c.id != group_id)
                )
                .scalars()
                .first()
            )
            if duplicate is not None:
                raise InvariantError(f"Group already exists: {clean_name}")
            connection.execute(update(tables.groups).where(tables.groups.c.id == group_id).values(name=clean_name, description=description.strip(), updated_at=updated_at))
        return self.group_detail(group_id)

    def update_skill_group(self, *, skill_id: str, group_id: str, name: str, description: str, actor: str) -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            group = self._group_row(connection, group_id)
            self._require_group_scope(group, scope_type="skill", scope_id=skill_id)
        return self.update_group(group_id=group_id, name=name, description=description, actor=actor)

    def group_detail(self, group_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            group = self._group_row(connection, group_id)
            return {**self._row_dict(group), "members": self._group_members(connection, group_id)}

    def add_group_member(self, *, group_id: str, subject_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        created_at = utc_now()
        clean_subject_type = self._clean_subject_type(subject_type)
        if clean_subject_type != "user":
            raise InvariantError("Group members only support user subjects.")
        clean_subject_id = self._clean_subject_id(subject_id)
        with self.engine.begin() as connection:
            self._group_row(connection, group_id)
            existing = self._group_member_row(connection, group_id, clean_subject_type, clean_subject_id)
            if existing is None:
                connection.execute(
                    insert(tables.group_memberships).values(
                        group_id=group_id,
                        subject_type=clean_subject_type,
                        subject_id=clean_subject_id,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
        return self.group_detail(group_id)

    def add_skill_group_member(self, *, skill_id: str, group_id: str, subject_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            group = self._group_row(connection, group_id)
            self._require_group_scope(group, scope_type="skill", scope_id=skill_id)
        return self.add_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type, actor=actor)

    def remove_group_member(self, *, group_id: str, subject_id: str, subject_type: str = "user") -> dict[str, Any]:
        clean_subject_type = self._clean_subject_type(subject_type)
        clean_subject_id = self._clean_subject_id(subject_id)
        with self.engine.begin() as connection:
            self._group_row(connection, group_id)
            connection.execute(
                delete(tables.group_memberships)
                .where(tables.group_memberships.c.group_id == group_id)
                .where(tables.group_memberships.c.subject_type == clean_subject_type)
                .where(tables.group_memberships.c.subject_id == clean_subject_id)
            )
        return self.group_detail(group_id)

    def remove_skill_group_member(self, *, skill_id: str, group_id: str, subject_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            group = self._group_row(connection, group_id)
            self._require_group_scope(group, scope_type="skill", scope_id=skill_id)
        return self.remove_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type)

    def delete_skill_group(self, *, skill_id: str, group_id: str, actor: str) -> dict[str, bool]:
        with self.engine.begin() as connection:
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            group = self._group_row(connection, group_id)
            self._require_group_scope(group, scope_type="skill", scope_id=skill_id)
        return self.delete_group_admin(group_id=group_id, actor=actor)

    def delete_group_admin(self, *, group_id: str, actor: str = "admin-console") -> dict[str, bool]:
        deleted_at = utc_now()
        with self.engine.begin() as connection:
            group = self._group_row(connection, group_id)
            member_count = len(self._group_members(connection, group_id))
            role_count = len(
                list(
                    connection.execute(
                        select(tables.role_assignments.c.id)
                        .where(tables.role_assignments.c.subject_type == "group")
                        .where(tables.role_assignments.c.subject_id == group_id)
                    ).scalars()
                )
            )
            connection.execute(delete(tables.group_memberships).where(tables.group_memberships.c.group_id == group_id))
            connection.execute(
                delete(tables.role_assignments)
                .where(tables.role_assignments.c.subject_type == "group")
                .where(tables.role_assignments.c.subject_id == group_id)
            )
            connection.execute(delete(tables.groups).where(tables.groups.c.id == group_id))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="group.deleted",
                    resource_type="group",
                    resource_id=group_id,
                    payload={"name": group["name"], "member_count": member_count, "role_count": role_count},
                    created_at=deleted_at,
                )
            )
        return {"ok": True}

    def assign_skill_role(self, *, skill_id: str, subject_id: str, role: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            if subject_type == "group":
                group = self._group_row(connection, subject_id)
                self._require_group_scope(group, scope_type="skill", scope_id=skill_id)
            return self._assign_role_in_tx(connection, resource_type="skill", resource_id=skill_id, subject_id=subject_id, role=role, actor=actor, subject_type=subject_type)

    def assign_role(
        self,
        *,
        resource_type: str,
        resource_id: str,
        subject_id: str,
        role: str,
        actor: str,
        subject_type: str = "user",
        require_permission: bool = True,
    ) -> dict[str, Any]:
        with self.engine.begin() as connection:
            clean_resource_type = self._clean_resource_type(resource_type)
            if clean_resource_type == "skill":
                self._skill_row(connection, resource_id)
                if require_permission:
                    self._require_skill_permission(connection, skill_id=resource_id, actor=actor, permission="role.manage")
            if clean_resource_type == "skill_tag":
                self._skill_tag_resource_row(connection, resource_id)
            return self._assign_role_in_tx(connection, resource_type=clean_resource_type, resource_id=resource_id, subject_id=subject_id, role=role, actor=actor, subject_type=subject_type)

    def revoke_role_assignment(self, *, role_assignment_id: str, actor: str) -> dict[str, bool]:
        revoked_at = utc_now()
        with self.engine.begin() as connection:
            assignment = self._role_assignment_row(connection, role_assignment_id)
            if assignment["resource_type"] == "skill":
                self._skill_row(connection, assignment["resource_id"])
                self._require_skill_permission(connection, skill_id=assignment["resource_id"], actor=actor, permission="role.manage")
                if assignment["role"] in {"admin", "owner"} and self._skill_admin_owner_count(connection, assignment["resource_id"]) <= 1:
                    raise InvariantError("Cannot revoke the last admin or owner for a skill.")
            else:
                raise InvariantError("Only skill role assignments can be revoked from the skill page.")
            self._delete_role_assignment(connection, assignment, actor=actor, created_at=revoked_at)
        return {"ok": True}

    def revoke_role_assignment_admin(self, *, role_assignment_id: str) -> dict[str, bool]:
        with self.engine.begin() as connection:
            assignment = self._role_assignment_row(connection, role_assignment_id)
            connection.execute(delete(tables.role_assignments).where(tables.role_assignments.c.id == role_assignment_id))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref="admin-console",
                    action="role.revoked",
                    resource_type=assignment["resource_type"],
                    resource_id=assignment["resource_id"],
                    payload={key: assignment[key] for key in ["id", "subject_type", "subject_id", "role"]},
                    created_at=utc_now(),
                )
            )
        return {"ok": True}

    def list_skill_audit_events(self, *, skill_id: str, limit: int = 50, actor: str | None = None, action: str | None = None, resource_type: str | None = None) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_audit_events(connection, skill_id, limit=limit, actor=actor, action=action, resource_type=resource_type)

    def _assign_role_in_tx(self, connection, *, resource_type: str, resource_id: str, subject_id: str, role: str, actor: str, subject_type: str) -> dict[str, Any]:
        created_at = utc_now()
        assignment = self._grant_role(
            connection,
            resource_type=resource_type,
            resource_id=resource_id,
            subject_id=subject_id,
            role=role,
            actor=actor,
            created_at=created_at,
            subject_type=subject_type,
        )
        connection.execute(
            insert(tables.audit_events).values(
                id=new_id("audit"),
                actor_ref=actor,
                action="role.assigned",
                resource_type=resource_type,
                resource_id=resource_id,
                payload={key: assignment[key] for key in ["id", "subject_type", "subject_id", "role"]},
                created_at=created_at,
            )
        )
        return assignment

    def _delete_role_assignment(self, connection, assignment, *, actor: str, created_at: datetime) -> None:
        connection.execute(delete(tables.role_assignments).where(tables.role_assignments.c.id == assignment["id"]))
        connection.execute(
            insert(tables.audit_events).values(
                id=new_id("audit"),
                actor_ref=actor,
                action="role.revoked",
                resource_type=assignment["resource_type"],
                resource_id=assignment["resource_id"],
                payload={key: assignment[key] for key in ["id", "subject_type", "subject_id", "role"]},
                created_at=created_at,
            )
        )

    def _role_assignment_row(self, connection, role_assignment_id: str):
        row = connection.execute(select(tables.role_assignments).where(tables.role_assignments.c.id == role_assignment_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"RoleAssignment not found: {role_assignment_id}")
        return row

    def _skill_role_assignments(self, connection, skill_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(tables.role_assignments)
                .where(tables.role_assignments.c.resource_type == "skill")
                .where(tables.role_assignments.c.resource_id == skill_id)
                .order_by(tables.role_assignments.c.role, tables.role_assignments.c.subject_type, tables.role_assignments.c.subject_id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _skill_audit_events(self, connection, skill_id: str, *, limit: int, actor: str | None = None, action: str | None = None, resource_type: str | None = None) -> list[dict[str, Any]]:
        skill_version_ids = select(tables.skill_versions.c.id).where(tables.skill_versions.c.skill_id == skill_id)
        eval_run_ids = select(tables.eval_runs.c.id).where(tables.eval_runs.c.skill_id == skill_id)
        conditions = [
            or_(
                and_(tables.audit_events.c.resource_type == "skill", tables.audit_events.c.resource_id == skill_id),
                and_(tables.audit_events.c.resource_type == "skill_version", tables.audit_events.c.resource_id.in_(skill_version_ids)),
                and_(tables.audit_events.c.resource_type == "eval_run", tables.audit_events.c.resource_id.in_(eval_run_ids)),
            )
        ]
        if actor:
            conditions.append(tables.audit_events.c.actor_ref == actor)
        if action:
            conditions.append(tables.audit_events.c.action == action)
        if resource_type:
            conditions.append(tables.audit_events.c.resource_type == resource_type)
        rows = connection.execute(select(tables.audit_events).where(*conditions).order_by(desc(tables.audit_events.c.created_at), desc(tables.audit_events.c.id)).limit(max(1, min(limit, 200)))).mappings().all()
        return [self._row_dict(row) for row in rows]

    def _grant_skill_role(self, connection, skill_id: str, subject_id: str, role: str, actor: str, created_at: datetime, subject_type: str = "user") -> dict[str, Any]:
        return self._grant_role(connection, resource_type="skill", resource_id=skill_id, subject_id=subject_id, role=role, actor=actor, created_at=created_at, subject_type=subject_type)

    def _grant_role(self, connection, *, resource_type: str, resource_id: str, subject_id: str, role: str, actor: str, created_at: datetime, subject_type: str = "user") -> dict[str, Any]:
        clean_subject_type = self._clean_subject_type(subject_type)
        clean_subject_id = self._clean_subject_id(subject_id)
        clean_resource_type = self._clean_resource_type(resource_type)
        clean_resource_id = resource_id.strip()
        if not clean_resource_id:
            raise InvariantError("Role resource_id is required.")
        if role not in VALID_ROLES:
            raise InvariantError(f"Unsupported role: {role}")
        if clean_subject_type == "group":
            group = self._group_row(connection, clean_subject_id)
            if group["scope_type"] == "skill" and (clean_resource_type != "skill" or clean_resource_id != group["scope_id"]):
                raise InvariantError("Skill-scoped groups can only be assigned to their own skill.")
        existing = (
            connection.execute(
                select(tables.role_assignments)
                .where(tables.role_assignments.c.subject_type == clean_subject_type)
                .where(tables.role_assignments.c.subject_id == clean_subject_id)
                .where(tables.role_assignments.c.resource_type == clean_resource_type)
                .where(tables.role_assignments.c.resource_id == clean_resource_id)
                .where(tables.role_assignments.c.role == role)
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            return self._row_dict(existing)
        row = {
            "id": new_id("role"),
            "subject_type": clean_subject_type,
            "subject_id": clean_subject_id,
            "resource_type": clean_resource_type,
            "resource_id": clean_resource_id,
            "role": role,
            "created_at": created_at,
            "created_by": actor,
        }
        connection.execute(insert(tables.role_assignments).values(**row))
        return row

    def _actor_skill_roles(self, connection, *, skill_id: str, actor: str) -> set[str]:
        return {item["role"] for item in self._actor_role_sources(connection, skill_id=skill_id, actor=actor)}

    def _actor_role_sources(self, connection, *, skill_id: str, actor: str) -> list[dict[str, Any]]:
        subjects = [("user", actor), *[("group", group_id) for group_id in self._actor_group_ids(connection, actor)]]
        subject_filters = [and_(tables.role_assignments.c.subject_type == subject_type, tables.role_assignments.c.subject_id == subject_id) for subject_type, subject_id in subjects]
        resource_filters = [and_(tables.role_assignments.c.resource_type == "skill", tables.role_assignments.c.resource_id == skill_id)]
        tag_resource_ids = self._skill_tag_resource_ids(connection, skill_id)
        if tag_resource_ids:
            resource_filters.append(and_(tables.role_assignments.c.resource_type == "skill_tag", tables.role_assignments.c.resource_id.in_(tag_resource_ids)))
        rows = connection.execute(select(tables.role_assignments).where(or_(*subject_filters)).where(or_(*resource_filters))).mappings().all()
        return [self._row_dict(row) for row in rows]

    def _actor_tag_role_sources(self, connection, *, actor: str, tags: set[tuple[str, str]]) -> list[dict[str, Any]]:
        if not tags:
            return []
        resource_ids = [encode_skill_tag_resource_id(group_id, value) for group_id, value in tags]
        subjects = [("user", actor), *[("group", group_id) for group_id in self._actor_group_ids(connection, actor)]]
        subject_filters = [and_(tables.role_assignments.c.subject_type == subject_type, tables.role_assignments.c.subject_id == subject_id) for subject_type, subject_id in subjects]
        rows = (
            connection.execute(
                select(tables.role_assignments)
                .where(or_(*subject_filters))
                .where(tables.role_assignments.c.resource_type == "skill_tag")
                .where(tables.role_assignments.c.resource_id.in_(resource_ids))
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _require_skill_permission(self, connection, *, skill_id: str, actor: str, permission: str) -> None:
        roles = self._actor_skill_roles(connection, skill_id=skill_id, actor=actor)
        if any(role_allows(role, permission) for role in roles):
            return
        raise PermissionDeniedError(f"{permission} requires {permission_label(permission)} for this skill.")

    def _skill_capabilities(self, connection, *, skill_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        permissions = sorted({permission for role_permissions in ROLE_PERMISSIONS.values() for permission in role_permissions})
        sources = self._actor_role_sources(connection, skill_id=skill_id, actor=actor)
        roles = sorted({source["role"] for source in sources})
        return {
            "actor": actor,
            "subject_type": subject_type,
            "groups": self._actor_group_ids(connection, actor),
            "roles": roles,
            "effective_roles": roles,
            "permissions": {permission: any(role_allows(role, permission) for role in roles) for permission in permissions},
            "permission_sources": sources,
        }

    def _actor_group_ids(self, connection, actor: str) -> list[str]:
        return list(
            connection.execute(
                select(tables.group_memberships.c.group_id)
                .where(tables.group_memberships.c.subject_type == "user")
                .where(tables.group_memberships.c.subject_id == actor)
                .order_by(tables.group_memberships.c.group_id)
            ).scalars()
        )

    def _group_row(self, connection, group_id: str):
        row = connection.execute(select(tables.groups).where(tables.groups.c.id == group_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Group not found: {group_id}")
        return row

    def _group_member_row(self, connection, group_id: str, subject_type: str, subject_id: str):
        return (
            connection.execute(
                select(tables.group_memberships)
                .where(tables.group_memberships.c.group_id == group_id)
                .where(tables.group_memberships.c.subject_type == subject_type)
                .where(tables.group_memberships.c.subject_id == subject_id)
            )
            .mappings()
            .one_or_none()
        )

    def _group_members(self, connection, group_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(select(tables.group_memberships).where(tables.group_memberships.c.group_id == group_id).order_by(tables.group_memberships.c.subject_type, tables.group_memberships.c.subject_id)).mappings().all()
        return [self._row_dict(row) for row in rows]

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

    def _clean_resource_type(self, value: str) -> str:
        clean = value.strip()
        if clean not in {"skill", "skill_tag"}:
            raise InvariantError(f"Unsupported role resource_type: {clean}")
        return clean

    def _skill_admin_owner_count(self, connection, skill_id: str) -> int:
        return len(
            list(
                connection.execute(
                    select(tables.role_assignments.c.id)
                    .where(tables.role_assignments.c.resource_type == "skill")
                    .where(tables.role_assignments.c.resource_id == skill_id)
                    .where(tables.role_assignments.c.role.in_(["admin", "owner"]))
                ).scalars()
            )
        )
