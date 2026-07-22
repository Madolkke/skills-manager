from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import new_id, utc_now
from skillhub.models.operations.shared.errors import skill_slug_conflict
from skillhub.models.schema import orm


class SkillUpdateCommandMixin:
    def update_skill(self, *, skill_id: str, slug: str, owner_ref: str, actor: str | None = None, tags: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Legacy store facade; SkillService owns normal update-skill orchestration."""
        snapshot = self.skill_update_snapshot(skill_id=skill_id, actor=actor)
        return self.apply_skill_update(
            skill_id=skill_id,
            slug=slug or snapshot["slug"],
            owner_ref=owner_ref or snapshot["owner_ref"],
            tags=tags,
            actor=actor or "system",
            require_permission=actor is not None,
        )

    def skill_update_snapshot(self, *, skill_id: str, actor: str | None) -> dict[str, Any]:
        with self._read_session() as connection:
            skill = self._skill_row(connection, skill_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.edit")
            return {**self._row_dict(skill), "tags": self._skill_tags(connection, skill_id)}

    def apply_skill_update(
        self,
        *,
        skill_id: str,
        slug: str,
        owner_ref: str,
        actor: str,
        tags: list[dict[str, Any]] | None = None,
        require_permission: bool = True,
    ) -> dict[str, Any]:
        updated_at = utc_now()
        try:
            with self._write_session() as connection:
                self._skill_row(connection, skill_id)
                if require_permission:
                    self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.edit")
                connection.execute(
                    update(orm.Skill)
                    .where(orm.Skill.id == skill_id)
                    .values(slug=slug, owner_ref=owner_ref, updated_at=updated_at)
                )
                if tags is not None:
                    self._set_skill_tags(connection, skill_id=skill_id, tags=tags, actor=actor, created_at=updated_at)
                return {**self._row_dict(self._skill_row(connection, skill_id)), "tags": self._skill_tags(connection, skill_id)}
        except IntegrityError as exc:
            raise skill_slug_conflict(slug, owner_ref) from exc

    def update_skill_admin(
        self,
        *,
        skill_id: str,
        slug: str | None = None,
        owner_ref: str | None = None,
        tags: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        updated_at = utc_now()
        try:
            with self._write_session() as connection:
                skill = self._skill_row(connection, skill_id)
                target_slug = slug or skill["slug"]
                target_owner_ref = owner_ref or skill["owner_ref"]
                values: dict[str, Any] = {"updated_at": updated_at}
                if slug is not None:
                    values["slug"] = slug
                if owner_ref is not None:
                    values["owner_ref"] = owner_ref
                connection.execute(update(orm.Skill).where(orm.Skill.id == skill_id).values(**values))
                if tags is not None:
                    self._set_skill_tags(connection, skill_id=skill_id, tags=tags, actor="admin-console", created_at=updated_at, enforce_protected=False)
                connection.execute(
                    insert(orm.AuditEvent).values(
                        id=new_id("audit"),
                        actor_ref="admin-console",
                        action="skill.admin_updated",
                        resource_type="skill",
                        resource_id=skill_id,
                        payload={"previous_slug": skill["slug"]},
                        created_at=updated_at,
                    )
                )
                return {**self._row_dict(self._skill_row(connection, skill_id)), "tags": self._skill_tags(connection, skill_id)}
        except IntegrityError as exc:
            raise skill_slug_conflict(target_slug, target_owner_ref) from exc
