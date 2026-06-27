from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from skillhub.models.entities import ContentRef
from skillhub.models.rules.skills import initial_skill_version, skill_change_summary
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class SkillService(ServiceBase[SkillHubStore]):
    def list_skills(self) -> Any:
        return self.store.list_skills()

    def list_tag_groups(self) -> Any:
        return self.store.list_tag_groups()

    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str | None,
        display_name: str | None,
        version: str | None,
        tags: list[Any],
        actor: str,
    ) -> Any:
        return self.store.insert_skill_with_initial_version(
            slug=slug,
            owner_ref=owner_ref,
            content_ref=content_ref,
            change_summary=skill_change_summary(change_summary),
            display_name=display_name,
            version=initial_skill_version(version),
            tags=tags,
            actor=actor,
            creator_role_reason="skill.creator",
        )

    def import_skill(
        self,
        *,
        source: dict[str, Any] | None = None,
        bundle: Any | None = None,
        owner_ref: str,
        display_name: str | None,
        version: str | None,
        tags: list[Any],
        actor: str,
    ) -> dict[str, Any]:
        if bundle is None:
            bundle = parse_skill_import_source(source or {})
        artifact = self.store.create_text_artifact(
            kind="skill_bundle",
            namespace=f"skill-import:{bundle.slug}",
            content=bundle.manifest_text,
            actor=actor,
        )
        result = self.store.insert_skill_with_initial_version(
            slug=bundle.slug,
            owner_ref=owner_ref,
            content_ref=ContentRef(kind="artifact", locator=f"artifact:{artifact['id']}", digest=artifact["digest"], path=bundle.entry_path),
            change_summary=f"Imported standard skill bundle with {bundle.file_count} files.",
            display_name=display_name,
            version=initial_skill_version(version),
            tags=tags,
            actor=actor,
            creator_role_reason="skill.creator",
        )
        return {
            **(asdict(result) if is_dataclass(result) else result),
            "slug": bundle.slug,
            "description": bundle.description,
            "file_count": bundle.file_count,
            "entry_path": bundle.entry_path,
            "bundle_artifact_id": artifact["id"],
            "bundle_digest": bundle.digest,
        }

    def skill_detail(self, *, skill_id: str, actor: str) -> Any:
        return self.store.skill_detail(skill_id, actor=actor)

    def update_skill(self, *, skill_id: str, slug: str | None, owner_ref: str | None, tags: list[Any] | None, actor: str) -> Any:
        snapshot = self.store.skill_update_snapshot(skill_id=skill_id, actor=actor)
        return self.store.apply_skill_update(
            skill_id=skill_id,
            slug=slug or snapshot["slug"],
            owner_ref=owner_ref or snapshot["owner_ref"],
            tags=tags,
            actor=actor,
            require_permission=True,
        )

    def archive_skill(self, *, skill_id: str, actor: str) -> None:
        self.store.archive_skill(skill_id=skill_id, actor=actor)

    def list_skill_role_assignments(self, *, skill_id: str) -> Any:
        return self.store.list_skill_role_assignments(skill_id=skill_id)

    def list_skill_groups(self, *, skill_id: str, actor: str) -> Any:
        return self.store.list_skill_groups(skill_id=skill_id, actor=actor)

    def create_skill_group(self, *, skill_id: str, name: str, description: str | None, actor: str) -> Any:
        return self.store.create_skill_group(skill_id=skill_id, name=name, description=description, actor=actor)

    def update_skill_group(self, *, skill_id: str, group_id: str, name: str, description: str | None, actor: str) -> Any:
        return self.store.update_skill_group(skill_id=skill_id, group_id=group_id, name=name, description=description, actor=actor)

    def delete_skill_group(self, *, skill_id: str, group_id: str, actor: str) -> Any:
        return self.store.delete_skill_group(skill_id=skill_id, group_id=group_id, actor=actor)

    def add_skill_group_member(self, *, skill_id: str, group_id: str, subject_id: str, subject_type: str, actor: str) -> Any:
        return self.store.add_skill_group_member(
            skill_id=skill_id,
            group_id=group_id,
            subject_id=subject_id,
            subject_type=subject_type,
            actor=actor,
        )

    def remove_skill_group_member(self, *, skill_id: str, group_id: str, subject_id: str, subject_type: str, actor: str) -> Any:
        return self.store.remove_skill_group_member(
            skill_id=skill_id,
            group_id=group_id,
            subject_id=subject_id,
            subject_type=subject_type,
            actor=actor,
        )

    def skill_capabilities(self, *, skill_id: str, actor: str, subject_type: str) -> Any:
        return self.store.skill_capabilities(skill_id=skill_id, actor=actor, subject_type=subject_type)

    def list_skill_audit_events(
        self,
        *,
        skill_id: str,
        limit: int,
        actor: str | None,
        action: str | None,
        resource_type: str | None,
    ) -> Any:
        return self.store.list_skill_audit_events(skill_id=skill_id, limit=max(1, min(limit, 200)), actor=actor, action=action, resource_type=resource_type)

    def assign_skill_role(self, *, skill_id: str, subject_id: str, role: str, subject_type: str, actor: str) -> Any:
        return self.store.assign_skill_role(skill_id=skill_id, subject_id=subject_id, role=role, subject_type=subject_type, actor=actor)

    def revoke_role_assignment(self, *, role_assignment_id: str, actor: str) -> Any:
        return self.store.revoke_role_assignment(role_assignment_id=role_assignment_id, actor=actor)
