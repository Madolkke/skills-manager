from __future__ import annotations

from base64 import b64encode
from typing import Any

from skillhub.models.rules.semver import normalize_semver
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class ExternalSkillService(ServiceBase[SkillHubStore]):
    def upsert_skill_bundle_for_owner(
        self,
        *,
        owner_ref: str,
        archive: bytes | None = None,
        slug: str | None = None,
        actor: str,
        bundle_digest: str | None = None,
        bundle_manifest_text: str | None = None,
        file_count: int | None = None,
        entry_path: str | None = None,
        tags: list[dict[str, str]],
        change_summary: str | None,
        display_name: str | None,
        version: str | None,
        make_current: bool,
    ) -> Any:
        if archive is not None:
            bundle = parse_skill_import_source({"kind": "zip", "zip_base64": b64encode(archive).decode("ascii")})
            slug = bundle.slug
            bundle_digest = bundle.digest
            bundle_manifest_text = bundle.manifest_text
            file_count = bundle.file_count
            entry_path = bundle.entry_path
        if slug is None or bundle_digest is None or bundle_manifest_text is None or file_count is None or entry_path is None:
            raise ValueError("External skill upsert requires archive or parsed bundle fields.")
        snapshot = self.store.external_skill_upsert_snapshot(owner_ref=owner_ref, slug=slug, actor=actor, tags=tags)
        resolved_version = normalize_semver(version or snapshot["next_version"])
        return self.store.apply_external_skill_upsert(
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
            version=resolved_version,
            version_number=snapshot["next_version_number"],
            make_current=make_current,
            explicit_version=version is not None,
        )
