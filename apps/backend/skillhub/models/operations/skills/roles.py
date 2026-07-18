from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, desc, insert, or_, select

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError, NotFoundError, PermissionDeniedError
from skillhub.models.rules.permissions import ROLE_PERMISSIONS, VALID_ROLES, permission_label, role_allows
from skillhub.models.rules.tag_resources import encode_skill_tag_resource_id
from skillhub.models.schema import orm


class RoleMixin:
    def list_skill_role_assignments(self, *, skill_id: str) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_role_assignments(connection, skill_id)

    def list_all_role_assignments(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = connection.execute(orm.select_entity(orm.RoleAssignment).order_by(orm.RoleAssignment.resource_type, orm.RoleAssignment.resource_id)).mappings().all()
            return [self._row_dict(row) for row in rows]

    def skill_capabilities(self, *, skill_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_capabilities(connection, skill_id=skill_id, actor=actor, subject_type=subject_type)

    def assign_skill_role(self, *, skill_id: str, subject_id: str, role: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        with self._write_session() as connection:
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
        with self._write_session() as connection:
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
        with self._write_session() as connection:
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
        with self._write_session() as connection:
            assignment = self._role_assignment_row(connection, role_assignment_id)
            connection.execute(delete(orm.RoleAssignment).where(orm.RoleAssignment.id == role_assignment_id))
            connection.execute(
                insert(orm.AuditEvent).values(
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
        with self._read_session() as connection:
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
            insert(orm.AuditEvent).values(
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
        connection.execute(delete(orm.RoleAssignment).where(orm.RoleAssignment.id == assignment["id"]))
        connection.execute(
            insert(orm.AuditEvent).values(
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
        row = connection.execute(orm.select_entity(orm.RoleAssignment).where(orm.RoleAssignment.id == role_assignment_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"RoleAssignment not found: {role_assignment_id}")
        return row

    def _skill_role_assignments(self, connection, skill_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                orm.select_entity(orm.RoleAssignment)
                .where(orm.RoleAssignment.resource_type == "skill")
                .where(orm.RoleAssignment.resource_id == skill_id)
                .order_by(orm.RoleAssignment.role, orm.RoleAssignment.subject_type, orm.RoleAssignment.subject_id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _skill_audit_events(self, connection, skill_id: str, *, limit: int, actor: str | None = None, action: str | None = None, resource_type: str | None = None) -> list[dict[str, Any]]:
        skill_version_ids = select(orm.SkillVersion.id).where(orm.SkillVersion.skill_id == skill_id)
        eval_run_ids = select(orm.EvalRun.id).where(orm.EvalRun.skill_id == skill_id)
        conditions = [
            or_(
                and_(orm.AuditEvent.resource_type == "skill", orm.AuditEvent.resource_id == skill_id),
                and_(orm.AuditEvent.resource_type == "skill_version", orm.AuditEvent.resource_id.in_(skill_version_ids)),
                and_(orm.AuditEvent.resource_type == "eval_run", orm.AuditEvent.resource_id.in_(eval_run_ids)),
            )
        ]
        if actor:
            conditions.append(orm.AuditEvent.actor_ref == actor)
        if action:
            conditions.append(orm.AuditEvent.action == action)
        if resource_type:
            conditions.append(orm.AuditEvent.resource_type == resource_type)
        rows = connection.execute(orm.select_entity(orm.AuditEvent).where(*conditions).order_by(desc(orm.AuditEvent.created_at), desc(orm.AuditEvent.id)).limit(max(1, min(limit, 200)))).mappings().all()
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
                orm.select_entity(orm.RoleAssignment)
                .where(orm.RoleAssignment.subject_type == clean_subject_type)
                .where(orm.RoleAssignment.subject_id == clean_subject_id)
                .where(orm.RoleAssignment.resource_type == clean_resource_type)
                .where(orm.RoleAssignment.resource_id == clean_resource_id)
                .where(orm.RoleAssignment.role == role)
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
        connection.execute(insert(orm.RoleAssignment).values(**row))
        return row

    def _actor_skill_roles(self, connection, *, skill_id: str, actor: str) -> set[str]:
        return {item["role"] for item in self._actor_role_sources(connection, skill_id=skill_id, actor=actor)}

    def _actor_role_sources(self, connection, *, skill_id: str, actor: str) -> list[dict[str, Any]]:
        subjects = [("user", actor), *[("group", group_id) for group_id in self._actor_group_ids(connection, actor)]]
        subject_filters = [and_(orm.RoleAssignment.subject_type == subject_type, orm.RoleAssignment.subject_id == subject_id) for subject_type, subject_id in subjects]
        resource_filters = [and_(orm.RoleAssignment.resource_type == "skill", orm.RoleAssignment.resource_id == skill_id)]
        tag_resource_ids = self._skill_tag_resource_ids(connection, skill_id)
        if tag_resource_ids:
            resource_filters.append(and_(orm.RoleAssignment.resource_type == "skill_tag", orm.RoleAssignment.resource_id.in_(tag_resource_ids)))
        rows = connection.execute(orm.select_entity(orm.RoleAssignment).where(or_(*subject_filters)).where(or_(*resource_filters))).mappings().all()
        return [self._row_dict(row) for row in rows]

    def _actor_tag_role_sources(self, connection, *, actor: str, tags: set[tuple[str, str]]) -> list[dict[str, Any]]:
        if not tags:
            return []
        resource_ids = [encode_skill_tag_resource_id(group_id, value) for group_id, value in tags]
        subjects = [("user", actor), *[("group", group_id) for group_id in self._actor_group_ids(connection, actor)]]
        subject_filters = [and_(orm.RoleAssignment.subject_type == subject_type, orm.RoleAssignment.subject_id == subject_id) for subject_type, subject_id in subjects]
        rows = (
            connection.execute(
                orm.select_entity(orm.RoleAssignment)
                .where(or_(*subject_filters))
                .where(orm.RoleAssignment.resource_type == "skill_tag")
                .where(orm.RoleAssignment.resource_id.in_(resource_ids))
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

    def _clean_resource_type(self, value: str) -> str:
        clean = value.strip()
        if clean not in {"skill", "skill_tag"}:
            raise InvariantError(f"Unsupported role resource_type: {clean}")
        return clean

    def _skill_admin_owner_count(self, connection, skill_id: str) -> int:
        return len(
            list(
                connection.execute(
                    select(orm.RoleAssignment.id)
                    .where(orm.RoleAssignment.resource_type == "skill")
                    .where(orm.RoleAssignment.resource_id == skill_id)
                    .where(orm.RoleAssignment.role.in_(["admin", "owner"]))
                ).scalars()
            )
        )
