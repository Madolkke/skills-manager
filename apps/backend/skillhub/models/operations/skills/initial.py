from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import ContentRef, new_id, utc_now
from skillhub.models.rules.semver import normalize_semver
from skillhub.models.schema import tables
from skillhub.models.operations.shared.errors import skill_slug_conflict
from skillhub.models.operations.shared.results import CreateSkillResult


class SkillCreateCommandMixin:
    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        version: str | None = None,
        tags: list[dict[str, Any]] | None = None,
    ) -> CreateSkillResult:
        """Legacy store facade; SkillService owns normal create-skill orchestration."""
        return self.insert_skill_with_initial_version(
            slug=slug,
            owner_ref=owner_ref,
            content_ref=content_ref,
            change_summary=change_summary or "Initial version.",
            version=normalize_semver(version or "0.0.1"),
            tags=tags or [],
            actor=actor,
            creator_role_reason="skill.creator",
        )

    def insert_skill_with_initial_version(
        self,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str,
        version: str,
        tags: list[dict[str, Any]],
        actor: str,
        creator_role_reason: str,
        connection=None,
    ) -> CreateSkillResult:
        if connection is not None:
            return self._insert_skill_with_initial_version(
                connection,
                slug=slug,
                owner_ref=owner_ref,
                content_ref=content_ref,
                change_summary=change_summary,
                version=version,
                tags=tags,
                actor=actor,
                creator_role_reason=creator_role_reason,
            )
        try:
            with self.engine.begin() as opened_connection:
                return self._insert_skill_with_initial_version(
                    opened_connection,
                    slug=slug,
                    owner_ref=owner_ref,
                    content_ref=content_ref,
                    change_summary=change_summary,
                    version=version,
                    tags=tags,
                    actor=actor,
                    creator_role_reason=creator_role_reason,
                )
        except IntegrityError as exc:
            raise skill_slug_conflict(slug, owner_ref) from exc

    def _insert_skill_with_initial_version(
        self,
        connection,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str,
        version: str,
        tags: list[dict[str, Any]],
        actor: str,
        creator_role_reason: str,
    ) -> CreateSkillResult:
        created_at = utc_now()
        skill_id = new_id("skill")
        skill_version_id = new_id("skillver")
        eval_set_id = new_id("evalset")
        semver = normalize_semver(version)

        try:
            self._require_protected_tag_creation_permission(connection, tags=tags, actor=actor)
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
                    display_name=None,
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
            self._set_skill_tags(
                connection,
                skill_id=skill_id,
                tags=tags,
                actor=actor,
                created_at=created_at,
                enforce_protected=False,
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
                role="admin",
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
                    payload={"subject_type": "user", "subject_id": actor, "role": "admin", "reason": creator_role_reason},
                    created_at=created_at,
                )
            )
        except IntegrityError as exc:
            raise skill_slug_conflict(slug, owner_ref) from exc

        return CreateSkillResult(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            version_number=1,
            version=semver,
        )
