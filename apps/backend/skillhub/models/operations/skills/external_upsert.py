from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.entities import ContentRef, new_id, utc_now
from skillhub.models.rules.semver import normalize_semver
from skillhub.models.schema import tables
from skillhub.models.operations.shared.errors import skill_slug_conflict


class ExternalSkillUpsertCommandMixin:
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
        """Legacy store facade; ExternalSkillService owns normal upsert orchestration."""
        snapshot = self.external_skill_upsert_snapshot(owner_ref=owner_ref, slug=slug, actor=actor, tags=tags)
        return self.apply_external_skill_upsert(
            owner_ref=owner_ref,
            slug=slug,
            actor=actor,
            operation=snapshot["operation"],
            skill_id=snapshot["skill_id"],
            eval_set_id=snapshot.get("eval_set_id"),
            current_version_id=snapshot.get("current_version_id"),
            bundle_digest=bundle_digest,
            bundle_manifest_text=bundle_manifest_text,
            file_count=file_count,
            entry_path=entry_path,
            tags=tags,
            change_summary=change_summary or f"Uploaded skill bundle with {file_count} files.",
            display_name=display_name,
            version=normalize_semver(version or snapshot["next_version"]),
            version_number=snapshot["next_version_number"],
            make_current=make_current,
            explicit_version=version is not None,
        )

    def external_skill_upsert_snapshot(self, *, owner_ref: str, slug: str, actor: str, tags: list[dict[str, Any]]) -> dict[str, Any]:
        clean_tags = self._clean_skill_tags(tags)
        with self.engine.connect() as connection:
            self._require_tag_values_exist(connection, clean_tags)
            self._require_required_tag_groups_present(connection, clean_tags)
            skill = (
                connection.execute(
                    select(tables.skills)
                    .where(tables.skills.c.slug == slug)
                    .where(tables.skills.c.lifecycle_status == "active")
                )
                .mappings()
                .one_or_none()
            )
            if skill is None:
                self._require_protected_tag_creation_permission(connection, tags=clean_tags, actor=actor)
                return {
                    "operation": "created",
                    "skill_id": new_id("skill"),
                    "eval_set_id": new_id("evalset"),
                    "current_version_id": None,
                    "next_version_number": 1,
                    "next_version": "0.0.1",
                }
            if skill["owner_ref"] != owner_ref:
                raise skill_slug_conflict(slug, owner_ref)
            skill_id = skill["id"]
            return {
                "operation": "updated",
                "skill_id": skill_id,
                "eval_set_id": self._primary_eval_set_row(connection, skill_id)["id"],
                "current_version_id": skill["current_version_id"],
                "next_version_number": self._next_skill_version_number(connection, skill_id),
                "next_version": self._next_skill_semver(connection, skill_id),
            }

    def apply_external_skill_upsert(
        self,
        *,
        owner_ref: str,
        slug: str,
        actor: str,
        operation: str,
        skill_id: str,
        eval_set_id: str | None,
        current_version_id: str | None,
        bundle_digest: str,
        bundle_manifest_text: str,
        file_count: int,
        entry_path: str,
        tags: list[dict[str, Any]],
        change_summary: str,
        display_name: str | None,
        version: str,
        version_number: int,
        make_current: bool,
        explicit_version: bool,
    ) -> dict[str, Any]:
        created_at = utc_now()
        clean_tags = self._clean_skill_tags(tags)
        skill_version_id = new_id("skillver")
        semver = normalize_semver(version)
        try:
            with self.engine.begin() as connection:
                self._require_tag_values_exist(connection, clean_tags)
                is_created = operation == "created"
                if is_created:
                    self._require_protected_tag_creation_permission(connection, tags=clean_tags, actor=actor)
                else:
                    skill = self._skill_row(connection, skill_id)
                    if skill["owner_ref"] != owner_ref or skill["slug"] != slug or skill["lifecycle_status"] != "active":
                        raise FieldInvariantError(
                            "External skill upsert target changed.",
                            [FieldError(field="slug", message="Skill ID 状态已变化，请重试。", code="skill.upsert_target_changed")],
                        )
                bundle_artifact_id = self._insert_text_artifact(
                    connection,
                    kind="skill_bundle",
                    namespace=f"external-skill-upsert:{owner_ref}:{slug}",
                    content=bundle_manifest_text,
                    actor=actor,
                    created_at=created_at,
                )
                content_ref = ContentRef(kind="artifact", locator=f"artifact:{bundle_artifact_id}", digest=bundle_digest, path=entry_path)

                if is_created:
                    if eval_set_id is None:
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
                elif eval_set_id is None:
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
                        change_summary=change_summary,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                if is_created or make_current:
                    connection.execute(
                        update(tables.skills)
                        .where(tables.skills.c.id == skill_id)
                        .values(current_version_id=skill_version_id, updated_at=created_at)
                    )
                    current_version_id = skill_version_id
                self._set_skill_tags(connection, skill_id=skill_id, tags=clean_tags, actor=actor, created_at=created_at)
        except IntegrityError as exc:
            if explicit_version:
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
