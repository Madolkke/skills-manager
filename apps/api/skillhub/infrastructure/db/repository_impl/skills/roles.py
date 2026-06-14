from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, desc, insert, or_, select

from skillhub.domain.errors import InvariantError, NotFoundError, PermissionDeniedError
from skillhub.domain.models import new_id, utc_now
from skillhub.domain.permissions import ROLE_PERMISSIONS, VALID_ROLES, permission_label, role_allows
from skillhub.infrastructure.db import tables


class RoleMixin:
    def list_skill_role_assignments(self, *, skill_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_role_assignments(connection, skill_id)

    def skill_capabilities(self, *, skill_id: str, actor: str, subject_type: str = "user") -> dict[str, Any]:
        permissions = sorted({permission for role_permissions in ROLE_PERMISSIONS.values() for permission in role_permissions})
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            roles = sorted(self._actor_skill_roles(connection, skill_id=skill_id, actor=actor))
        return {
            "actor": actor,
            "subject_type": subject_type,
            "roles": roles,
            "permissions": {permission: any(role_allows(role, permission) for role in roles) for permission in permissions},
        }

    def assign_skill_role(
        self,
        *,
        skill_id: str,
        subject_id: str,
        role: str,
        actor: str,
        subject_type: str = "user",
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            assignment = self._grant_skill_role(connection, skill_id, subject_id, role, actor, created_at, subject_type)
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="role.assigned",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={key: assignment[key] for key in ["id", "subject_type", "subject_id", "role"]},
                    created_at=created_at,
                )
            )
        return assignment

    def revoke_role_assignment(self, *, role_assignment_id: str, actor: str) -> dict[str, bool]:
        revoked_at = utc_now()
        with self.engine.begin() as connection:
            assignment = self._role_assignment_row(connection, role_assignment_id)
            if assignment["resource_type"] != "skill":
                raise InvariantError("Only skill role assignments can be revoked.")
            skill_id = assignment["resource_id"]
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            if assignment["role"] == "owner" and self._skill_owner_count(connection, skill_id) <= 1:
                raise InvariantError("Cannot revoke the last owner for a skill.")
            connection.execute(delete(tables.role_assignments).where(tables.role_assignments.c.id == role_assignment_id))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="role.revoked",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={
                        "role_assignment_id": role_assignment_id,
                        "subject_type": assignment["subject_type"],
                        "subject_id": assignment["subject_id"],
                        "role": assignment["role"],
                    },
                    created_at=revoked_at,
                )
            )
        return {"ok": True}

    def list_skill_audit_events(
        self,
        *,
        skill_id: str,
        limit: int = 50,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            return self._skill_audit_events(connection, skill_id, limit=limit, actor=actor, action=action, resource_type=resource_type)

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
                .order_by(tables.role_assignments.c.role, tables.role_assignments.c.subject_id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _skill_audit_events(
        self,
        connection,
        skill_id: str,
        *,
        limit: int,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
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
        rows = (
            connection.execute(
                select(tables.audit_events)
                .where(*conditions)
                .order_by(desc(tables.audit_events.c.created_at), desc(tables.audit_events.c.id))
                .limit(max(1, min(limit, 200)))
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _grant_skill_role(
        self,
        connection,
        skill_id: str,
        subject_id: str,
        role: str,
        actor: str,
        created_at: datetime,
        subject_type: str = "user",
    ) -> dict[str, Any]:
        clean_subject_id = subject_id.strip()
        clean_subject_type = subject_type.strip() or "user"
        if not clean_subject_id:
            raise InvariantError("Role subject_id is required.")
        if role not in VALID_ROLES:
            raise InvariantError(f"Unsupported role: {role}")
        existing = (
            connection.execute(
                select(tables.role_assignments)
                .where(tables.role_assignments.c.subject_type == clean_subject_type)
                .where(tables.role_assignments.c.subject_id == clean_subject_id)
                .where(tables.role_assignments.c.resource_type == "skill")
                .where(tables.role_assignments.c.resource_id == skill_id)
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
            "resource_type": "skill",
            "resource_id": skill_id,
            "role": role,
            "created_at": created_at,
            "created_by": actor,
        }
        connection.execute(insert(tables.role_assignments).values(**row))
        return row

    def _actor_skill_roles(self, connection, *, skill_id: str, actor: str) -> set[str]:
        return set(
            connection.execute(
                select(tables.role_assignments.c.role)
                .where(tables.role_assignments.c.subject_type == "user")
                .where(tables.role_assignments.c.subject_id == actor)
                .where(tables.role_assignments.c.resource_type == "skill")
                .where(tables.role_assignments.c.resource_id == skill_id)
            ).scalars()
        )

    def _require_skill_permission(self, connection, *, skill_id: str, actor: str, permission: str) -> None:
        roles = self._actor_skill_roles(connection, skill_id=skill_id, actor=actor)
        if any(role_allows(role, permission) for role in roles):
            return
        raise PermissionDeniedError(f"{permission} requires {permission_label(permission)} for this skill.")

    def _skill_owner_count(self, connection, skill_id: str) -> int:
        return len(
            list(
                connection.execute(
                    select(tables.role_assignments.c.id)
                    .where(tables.role_assignments.c.resource_type == "skill")
                    .where(tables.role_assignments.c.resource_id == skill_id)
                    .where(tables.role_assignments.c.role == "owner")
                ).scalars()
            )
        )
