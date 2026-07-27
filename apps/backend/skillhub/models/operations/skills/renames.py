from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import digest_text, new_id, utc_now
from skillhub.models.errors import ConflictError, InvariantError
from skillhub.models.operations.shared.errors import skill_slug_conflict
from skillhub.models.operations.skills.active_work import reject_active_skill_work
from skillhub.models.rules.skill_renames import normalize_skill_display_name, rename_skill_bundle
from skillhub.models.schema import orm


class SkillRenameCommandMixin:
    def rename_skill(
        self,
        *,
        skill_id: str,
        slug: str,
        expected_slug: str | None,
        owner_ref: str,
        actor: str,
        tags: list[dict[str, Any]] | None,
        display_name: str | None,
        display_name_provided: bool,
        require_permission: bool = True,
    ) -> dict[str, Any]:
        renamed_at = utc_now()
        try:
            with self._write_session() as session:
                skill = (
                    session.execute(
                        orm.select_entity(orm.Skill)
                        .where(orm.Skill.id == skill_id)
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
                if skill is None:
                    return self._row_dict(self._skill_row(session, skill_id))
                if require_permission:
                    self._require_skill_permission(session, skill_id=skill_id, actor=actor, permission="skill.edit")
                if expected_slug is not None and expected_slug != skill["slug"]:
                    raise ConflictError("Skill ID 已被其他操作修改，请刷新后重试。")
                if slug == skill["slug"]:
                    return self._apply_non_slug_updates(
                        session,
                        skill=skill,
                        owner_ref=owner_ref,
                        tags=tags,
                        display_name=display_name,
                        display_name_provided=display_name_provided,
                        actor=actor,
                        updated_at=renamed_at,
                    )

                reject_active_skill_work(session, skill_id=skill_id, action="重命名")
                version = self._current_version_for_rename(session, skill)
                try:
                    bundle = self._renamed_bundle(session, version=version, slug=slug)
                except InvariantError as exc:
                    raise ConflictError(f"当前 Skill 内容无法安全重命名：{exc}") from exc
                artifact_id = self._insert_text_artifact(
                    session,
                    kind="skill_bundle",
                    namespace=f"skill-rename:{skill_id}:{slug}",
                    content=bundle.manifest_text,
                    actor=actor,
                    created_at=renamed_at,
                )
                skill_version_id = new_id("skillver")
                version_number = self._next_skill_version_number(session, skill_id)
                semver = self._next_skill_semver(session, skill_id)
                session.execute(
                    insert(orm.SkillVersion).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=version_number,
                        version=semver,
                        display_name=version["display_name"],
                        content_ref={
                            "kind": "artifact",
                            "locator": f"artifact:{artifact_id}",
                            "digest": bundle.digest,
                            "path": "SKILL.md",
                        },
                        content_digest=bundle.digest,
                        change_summary=f"Renamed Skill ID from {skill['slug']} to {slug}.",
                        created_at=renamed_at,
                        created_by=actor,
                    )
                )
                workflow_revision = self._sync_in_sync_workflow_rename(
                    session,
                    skill=skill,
                    skill_version_id=skill_version_id,
                    actor=actor,
                    renamed_at=renamed_at,
                )
                values: dict[str, Any] = {
                    "slug": slug,
                    "owner_ref": owner_ref,
                    "current_version_id": skill_version_id,
                    "updated_at": renamed_at,
                }
                if display_name_provided:
                    values["display_name"] = normalize_skill_display_name(display_name)
                session.execute(update(orm.Skill).where(orm.Skill.id == skill_id).values(**values))
                if tags is not None:
                    self._set_skill_tags(session, skill_id=skill_id, tags=tags, actor=actor, created_at=renamed_at)
                session.execute(
                    insert(orm.AuditEvent).values(
                        id=new_id("audit"),
                        actor_ref=actor,
                        action="skill.renamed",
                        resource_type="skill",
                        resource_id=skill_id,
                        payload={
                            "previous_slug": skill["slug"],
                            "slug": slug,
                            "skill_version_id": skill_version_id,
                            "version": semver,
                            "workflow_revision": workflow_revision,
                        },
                        created_at=renamed_at,
                    )
                )
                return {**self._row_dict(self._skill_row(session, skill_id)), "tags": self._skill_tags(session, skill_id)}
        except IntegrityError as exc:
            if getattr(getattr(exc, "orig", None), "diag", None) and exc.orig.diag.constraint_name == "skills_slug_unique":
                raise skill_slug_conflict(slug, owner_ref) from exc
            raise

    def _current_version_for_rename(self, session, skill):
        if not skill["current_version_id"]:
            raise InvariantError("Skill has no current version.")
        return self._skill_version_row(session, skill["current_version_id"])

    def _renamed_bundle(self, session, *, version, slug: str):
        content_ref = version["content_ref"] if isinstance(version["content_ref"], dict) else {}
        locator = content_ref.get("locator")
        if content_ref.get("kind") != "artifact" or not isinstance(locator, str) or not locator.startswith("artifact:"):
            raise InvariantError("Current SkillVersion does not reference an Artifact.")
        artifact_id = locator.split(":", 1)[1]
        artifact = session.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == artifact_id)).mappings().one_or_none()
        if artifact is None or artifact["kind"] != "skill_bundle":
            raise InvariantError("Current SkillVersion Artifact is not a Skill Bundle.")
        if artifact["digest"] != content_ref.get("digest") or artifact["digest"] != version["content_digest"]:
            raise InvariantError("Current SkillVersion Artifact digest does not match.")
        return rename_skill_bundle(str(artifact["content_text"] or ""), new_slug=slug)

    def _sync_in_sync_workflow_rename(self, session, *, skill, skill_version_id: str, actor: str, renamed_at) -> int | None:
        workflow = session.execute(
            orm.select_entity(orm.Workflow)
            .where(orm.Workflow.skill_id == skill["id"])
            .with_for_update()
        ).mappings().one_or_none()
        if workflow is None:
            return None
        current_sync = session.execute(
            orm.select_entity(orm.WorkflowSync)
            .where(orm.WorkflowSync.workflow_id == workflow["id"])
            .where(orm.WorkflowSync.skill_version_id == skill["current_version_id"])
        ).mappings().one_or_none()
        if (
            current_sync is None
            or int(current_sync["workflow_revision"]) != int(workflow["revision"])
        ):
            return None
        revision = int(workflow["revision"]) + 1
        document = deepcopy(workflow["document"])
        document["workflow"]["revision"] = revision
        source_text = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        document_digest = digest_text(source_text)
        source_artifact_id = self._insert_text_artifact(
            session,
            kind="workflow_source",
            namespace=f"workflow:{workflow['id']}:{revision}",
            content=source_text,
            actor=actor,
            created_at=renamed_at,
        )
        session.execute(
            update(orm.Workflow)
            .where(orm.Workflow.id == workflow["id"])
            .values(
                revision=revision,
                document=document,
                document_digest=document_digest,
                updated_at=renamed_at,
                last_saved_by=actor,
            )
        )
        session.execute(
            insert(orm.WorkflowSync).values(
                id=new_id("workflowsync"),
                workflow_id=workflow["id"],
                workflow_revision=revision,
                document_schema_version=workflow["document_schema_version"],
                source_artifact_id=source_artifact_id,
                skill_version_id=skill_version_id,
                generator_id=current_sync["generator_id"],
                generator_version=current_sync["generator_version"],
                generator_options=current_sync["generator_options"],
                generator_options_digest=current_sync["generator_options_digest"],
                preview_digest=self._rename_preview_digest(
                    session,
                    workflow_id=str(workflow["id"]),
                    workflow_revision=revision,
                    document_digest=document_digest,
                    skill_version_id=skill_version_id,
                    generator_id=str(current_sync["generator_id"]),
                    generator_version=str(current_sync["generator_version"]),
                    generator_options=dict(current_sync["generator_options"]),
                ),
                created_at=renamed_at,
                created_by=actor,
            )
        )
        return revision

    def _rename_preview_digest(
        self,
        session,
        *,
        workflow_id: str,
        workflow_revision: int,
        document_digest: str,
        skill_version_id: str,
        generator_id: str,
        generator_version: str,
        generator_options: dict[str, Any],
    ) -> str:
        skill_version = self._skill_version_row(session, skill_version_id)
        evidence = {
            "workflow_id": workflow_id,
            "workflow_revision": workflow_revision,
            "workflow_document_digest": document_digest,
            "generator_id": generator_id,
            "generator_version": generator_version,
            "generator_options": generator_options,
            "bundle_digest": skill_version["content_digest"],
        }
        canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return digest_text(canonical)

    def _apply_non_slug_updates(
        self,
        session,
        *,
        skill,
        owner_ref: str,
        tags: list[dict[str, Any]] | None,
        display_name: str | None,
        display_name_provided: bool,
        actor: str,
        updated_at,
    ) -> dict[str, Any]:
        values: dict[str, Any] = {"owner_ref": owner_ref, "updated_at": updated_at}
        if display_name_provided:
            values["display_name"] = normalize_skill_display_name(display_name)
        session.execute(update(orm.Skill).where(orm.Skill.id == skill["id"]).values(**values))
        if tags is not None:
            self._set_skill_tags(session, skill_id=skill["id"], tags=tags, actor=actor, created_at=updated_at)
        return {**self._row_dict(self._skill_row(session, skill["id"])), "tags": self._skill_tags(session, skill["id"])}
