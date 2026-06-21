from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.domain.errors import FieldError, FieldInvariantError
from skillhub.domain.models import ContentRef, new_id, utc_now
from skillhub.domain.semver import normalize_semver
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.errors import skill_slug_conflict
from skillhub.infrastructure.db.repository_impl.shared.results import CreateSkillResult, CreateSkillVersionResult


class SkillCommandMixin:
    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        display_name: str | None = None,
        version: str | None = None,
    ) -> CreateSkillResult:
        created_at = utc_now()
        skill_id = new_id("skill")
        skill_version_id = new_id("skillver")
        eval_set_id = new_id("evalset")
        semver = normalize_semver(version or "0.0.1")

        try:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(tables.skills).values(
                        id=skill_id,
                        slug=slug,
                        owner_ref=owner_ref,
                        current_version_id=None,
                        lifecycle_status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                connection.execute(
                    insert(tables.skill_versions).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=1,
                        version=semver,
                        display_name=display_name,
                        content_ref=self._content_ref_payload(content_ref),
                        content_digest=content_ref.digest,
                        change_summary=change_summary,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(tables.skills)
                    .where(tables.skills.c.id == skill_id)
                    .values(current_version_id=skill_version_id, updated_at=created_at)
                )
                connection.execute(
                    insert(tables.eval_sets).values(
                        id=eval_set_id,
                        skill_id=skill_id,
                        name="Primary",
                        description="Primary regression suite",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                self._grant_skill_role(
                    connection,
                    skill_id=skill_id,
                    subject_id=actor,
                    role="owner",
                    actor=actor,
                    created_at=created_at,
                )
                connection.execute(
                    insert(tables.audit_events).values(
                        id=new_id("audit"),
                        actor_ref=actor,
                        action="role.assigned",
                        resource_type="skill",
                        resource_id=skill_id,
                        payload={"subject_type": "user", "subject_id": actor, "role": "owner", "reason": "skill.creator"},
                        created_at=created_at,
                    )
                )
        except IntegrityError as exc:
            raise skill_slug_conflict(slug) from exc

        return CreateSkillResult(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            version_number=1,
            version=semver,
        )

    def create_skill_version(
        self,
        *,
        skill_id: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        make_current: bool,
        display_name: str | None = None,
        version: str | None = None,
    ) -> CreateSkillVersionResult:
        created_at = utc_now()
        skill_version_id = new_id("skillver")
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                version_number = self._next_skill_version_number(connection, skill_id)
                semver = normalize_semver(version or self._next_skill_semver(connection, skill_id))
                connection.execute(
                    insert(tables.skill_versions).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=version_number,
                        version=semver,
                        display_name=display_name,
                        content_ref=self._content_ref_payload(content_ref),
                        content_digest=content_ref.digest,
                        change_summary=change_summary,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                if make_current:
                    connection.execute(
                        update(tables.skills)
                        .where(tables.skills.c.id == skill_id)
                        .values(current_version_id=skill_version_id, updated_at=created_at)
                    )
        except IntegrityError as exc:
            raise FieldInvariantError(
                "SkillVersion version already exists for this skill.",
                [
                    FieldError(
                        field="version",
                        message="这个 Skill 已经存在相同版本号。",
                        code="skill_version.version_conflict",
                    )
                ],
            ) from exc
        return CreateSkillVersionResult(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            version_number=version_number,
            version=semver,
        )

    def update_skill_version_name(self, *, skill_version_id: str, display_name: str | None) -> dict[str, Any]:
        with self.engine.begin() as connection:
            self._skill_version_row(connection, skill_version_id)
            connection.execute(
                update(tables.skill_versions)
                .where(tables.skill_versions.c.id == skill_version_id)
                .values(display_name=clean_display_name(display_name))
            )
            return self._row_dict(self._skill_version_row(connection, skill_version_id))

    def update_skill(self, *, skill_id: str, slug: str, owner_ref: str) -> dict[str, Any]:
        updated_at = utc_now()
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                connection.execute(
                    update(tables.skills)
                    .where(tables.skills.c.id == skill_id)
                    .values(slug=slug, owner_ref=owner_ref, updated_at=updated_at)
                )
                return self._row_dict(self._skill_row(connection, skill_id))
        except IntegrityError as exc:
            raise skill_slug_conflict(slug) from exc

    def archive_skill(self, *, skill_id: str, actor: str) -> None:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="role.manage")
            connection.execute(
                update(tables.skills)
                .where(tables.skills.c.id == skill_id)
                .values(lifecycle_status="archived", updated_at=updated_at)
            )
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="skill.archived",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={"skill_id": skill_id},
                    created_at=updated_at,
                )
            )


def clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
