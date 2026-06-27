from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.entities import ContentRef
from skillhub.models.rules.semver import normalize_semver
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class VersionService(ServiceBase[SkillHubStore]):
    def create_skill_version(
        self,
        *,
        skill_id: str,
        source: dict[str, Any] | None,
        content_ref: ContentRef | None,
        change_summary: str | None,
        display_name: str | None,
        version: str | None,
        make_current: bool,
        actor: str,
    ) -> Any:
        bundle = None
        if source is not None:
            bundle = parse_skill_import_source(source)
            artifact = self.store.create_text_artifact(
                kind="skill_bundle",
                namespace=f"skill-version-import:{bundle.slug}",
                content=bundle.manifest_text,
                actor=actor,
            )
            content = ContentRef(kind="artifact", locator=f"artifact:{artifact['id']}", digest=artifact["digest"], path=bundle.entry_path)
        elif content_ref is not None:
            content = content_ref
        else:
            raise InvariantError("Skill version requires either content_ref or standard skill bundle source.")
        snapshot = self.store.skill_version_create_snapshot(skill_id=skill_id, actor=actor)
        resolved_version = normalize_semver(version or snapshot["next_version"])
        return self.store.insert_skill_version(
            skill_id=skill_id,
            content_ref=content,
            change_summary=change_summary or (f"Uploaded standard skill bundle with {bundle.file_count} files." if bundle else "Updated skill version."),
            display_name=display_name,
            version_number=snapshot["next_version_number"],
            version=resolved_version,
            actor=actor,
            make_current=make_current,
        )

    def update_skill_version_name(self, *, skill_version_id: str, display_name: str | None, actor: str) -> Any:
        return self.store.update_skill_version_name(skill_version_id=skill_version_id, display_name=display_name, actor=actor)
