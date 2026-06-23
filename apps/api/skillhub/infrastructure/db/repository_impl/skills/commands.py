from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update
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
        tags: list[dict[str, Any]] | None = None,
    ) -> CreateSkillResult:
        created_at = utc_now()
        skill_id = new_id("skill")
        skill_version_id = new_id("skillver")
        eval_set_id = new_id("evalset")
        semver = normalize_semver(version or "0.0.1")

        try:
            with self.engine.begin() as connection:
                self._require_protected_tag_creation_permission(connection, tags=tags or [], actor=actor)
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
                self._set_skill_tags(
                    connection,
                    skill_id=skill_id,
                    tags=tags or [],
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
                        payload={"subject_type": "user", "subject_id": actor, "role": "admin", "reason": "skill.creator"},
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
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.version.create")
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

    def update_skill_version_name(self, *, skill_version_id: str, display_name: str | None, actor: str | None = None) -> dict[str, Any]:
        with self.engine.begin() as connection:
            version = self._skill_version_row(connection, skill_version_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=version["skill_id"], actor=actor, permission="skill.version.create")
            connection.execute(
                update(tables.skill_versions)
                .where(tables.skill_versions.c.id == skill_version_id)
                .values(display_name=clean_display_name(display_name))
            )
            return self._row_dict(self._skill_version_row(connection, skill_version_id))

    def update_skill(self, *, skill_id: str, slug: str, owner_ref: str, actor: str | None = None, tags: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        updated_at = utc_now()
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                if actor is not None:
                    self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.edit")
                connection.execute(
                    update(tables.skills)
                    .where(tables.skills.c.id == skill_id)
                    .values(slug=slug, owner_ref=owner_ref, updated_at=updated_at)
                )
                if tags is not None:
                    self._set_skill_tags(connection, skill_id=skill_id, tags=tags, actor=actor or "system", created_at=updated_at)
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
            with self.engine.begin() as connection:
                skill = self._skill_row(connection, skill_id)
                target_slug = slug or skill["slug"]
                target_owner_ref = owner_ref or skill["owner_ref"]
                values: dict[str, Any] = {"updated_at": updated_at}
                if slug is not None:
                    values["slug"] = slug
                if owner_ref is not None:
                    values["owner_ref"] = owner_ref
                connection.execute(update(tables.skills).where(tables.skills.c.id == skill_id).values(**values))
                if tags is not None:
                    self._set_skill_tags(connection, skill_id=skill_id, tags=tags, actor="admin-console", created_at=updated_at, enforce_protected=False)
                connection.execute(
                    insert(tables.audit_events).values(
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

    def upsert_skill_bundle_for_owner(
        self,
        *,
        owner_ref: str,
        slug: str,
        actor: str,
        bundle_digest: str,
        bundle_manifest_text: str,
        file_count: int,
        entry_path: str,
        tags: list[dict[str, Any]],
        change_summary: str | None = None,
        display_name: str | None = None,
        version: str | None = None,
        make_current: bool = True,
    ) -> dict[str, Any]:
        created_at = utc_now()
        clean_tags = self._clean_skill_tags(tags)
        try:
            with self.engine.begin() as connection:
                self._require_tag_values_exist(connection, clean_tags)
                skill = (
                    connection.execute(
                        select(tables.skills)
                        .where(tables.skills.c.owner_ref == owner_ref)
                        .where(tables.skills.c.slug == slug)
                        .where(tables.skills.c.lifecycle_status == "active")
                    )
                    .mappings()
                    .one_or_none()
                )
                operation = "updated" if skill is not None else "created"
                if skill is None:
                    self._require_protected_tag_creation_permission(connection, tags=clean_tags, actor=actor)
                bundle_artifact_id = self._insert_text_artifact(
                    connection,
                    kind="skill_bundle",
                    namespace=f"external-skill-upsert:{owner_ref}:{slug}",
                    content=bundle_manifest_text,
                    actor=actor,
                    created_at=created_at,
                )
                content_ref = ContentRef(kind="artifact", locator=f"artifact:{bundle_artifact_id}", digest=bundle_digest, path=entry_path)
                skill_id = skill["id"] if skill is not None else new_id("skill")
                skill_version_id = new_id("skillver")
                semver = normalize_semver(version or ("0.0.1" if skill is None else self._next_skill_semver(connection, skill_id)))
                version_number = 1 if skill is None else self._next_skill_version_number(connection, skill_id)

                if skill is None:
                    eval_set_id = new_id("evalset")
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
                        insert(tables.eval_sets).values(
                            id=eval_set_id,
                            skill_id=skill_id,
                            name="Primary",
                            description="Primary regression suite",
                            created_at=created_at,
                            updated_at=created_at,
                        )
                    )
                    self._grant_skill_role(connection, skill_id=skill_id, subject_id=actor, role="admin", actor=actor, created_at=created_at)
                    connection.execute(
                        insert(tables.audit_events).values(
                            id=new_id("audit"),
                            actor_ref=actor,
                            action="role.assigned",
                            resource_type="skill",
                            resource_id=skill_id,
                            payload={"subject_type": "user", "subject_id": actor, "role": "admin", "reason": "skill.external_upsert_creator"},
                            created_at=created_at,
                        )
                    )
                else:
                    eval_set_id = self._primary_eval_set_row(connection, skill_id)["id"]

                connection.execute(
                    insert(tables.skill_versions).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=version_number,
                        version=semver,
                        display_name=display_name,
                        content_ref=self._content_ref_payload(content_ref),
                        content_digest=content_ref.digest,
                        change_summary=change_summary or f"Uploaded skill bundle with {file_count} files.",
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                if skill is None or make_current:
                    connection.execute(
                        update(tables.skills)
                        .where(tables.skills.c.id == skill_id)
                        .values(current_version_id=skill_version_id, updated_at=created_at)
                    )
                    current_version_id = skill_version_id
                else:
                    current_version_id = skill["current_version_id"]
                self._set_skill_tags(connection, skill_id=skill_id, tags=clean_tags, actor=actor, created_at=created_at)
        except IntegrityError as exc:
            if version is not None:
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
            raise skill_slug_conflict(slug, owner_ref) from exc
        return {
            "operation": operation,
            "skill_id": skill_id,
            "slug": slug,
            "owner_ref": owner_ref,
            "skill_version_id": skill_version_id,
            "version_number": version_number,
            "version": semver,
            "current_version_id": current_version_id,
            "eval_set_id": eval_set_id,
            "bundle_artifact_id": bundle_artifact_id,
            "bundle_digest": bundle_digest,
            "file_count": file_count,
            "entry_path": entry_path,
        }

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
