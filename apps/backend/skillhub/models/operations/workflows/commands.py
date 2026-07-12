from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import ContentRef, digest_text, new_id, utc_now
from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.rules.semver import normalize_semver
from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, normalize_workflow_document
from skillhub.models.schema import tables
from skillhub.models.operations.workflows.catalog import WorkflowCatalogMixin
from skillhub.models.operations.workflows.helpers import WorkflowHelperMixin


logger = logging.getLogger(__name__)


class WorkflowCommandMixin(WorkflowCatalogMixin, WorkflowHelperMixin):
    def create_workflow_skill(self, *, slug: str, owner_ref: str, manifest_text: str, document: dict[str, Any], tags: list[dict[str, Any]], actor: str) -> dict[str, Any]:
        created_at = utc_now()
        normalized = normalize_workflow_document(document)
        try:
            with self.engine.begin() as connection:
                artifact_id = self._insert_text_artifact(
                    connection,
                    kind="skill_bundle",
                    namespace=f"workflow-bootstrap:{slug}",
                    content=manifest_text,
                    actor=actor,
                    created_at=created_at,
                )
                result = self.insert_skill_with_initial_version(
                    slug=slug,
                    owner_ref=owner_ref,
                    content_ref=ContentRef(kind="artifact", locator=f"artifact:{artifact_id}", digest=digest_text(manifest_text), path="SKILL.md"),
                    change_summary="Workflow 初始化版本。",
                    version="0.0.1",
                    tags=tags,
                    actor=actor,
                    creator_role_reason="workflow.creator",
                    connection=connection,
                )
                workflow_id = normalized["workflow"]["id"]
                connection.execute(
                    insert(tables.workflows).values(
                        id=workflow_id,
                        skill_id=result.skill_id,
                        revision=1,
                        document_schema_version=DOCUMENT_SCHEMA_VERSION,
                        document=normalized,
                        document_digest=self._document_digest(normalized),
                        created_at=created_at,
                        updated_at=created_at,
                        created_by=actor,
                        last_saved_by=actor,
                    )
                )
                self._audit_workflow(connection, skill_id=result.skill_id, actor=actor, action="workflow.created", payload={"workflow_id": workflow_id, "revision": 1}, created_at=created_at)
        except IntegrityError as exc:
            raise InvariantError("Workflow Skill creation conflicted with existing data.") from exc
        logger.info("workflow skill created skill_id=%s workflow_id=%s actor=%s", result.skill_id, workflow_id, actor)
        return {**result.__dict__, "workflow_id": workflow_id, "workflow_revision": 1}

    def save_workflow(self, *, skill_id: str, document: dict[str, Any], collection_changes: list[dict[str, Any]], actor: str) -> dict[str, Any]:
        saved_at = utc_now()
        with self.engine.begin() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.edit")
            workflow = self._workflow_row(connection, skill_id=skill_id)
            candidate = normalize_workflow_document(document)
            if candidate["workflow"]["id"] != workflow["id"]:
                raise InvariantError("Workflow ID cannot be changed.")
            mappings, applied_changes = self._apply_collection_changes(connection, changes=collection_changes, actor=actor, created_at=saved_at)
            candidate = self._canonicalize_collection_snapshots(connection, candidate, mappings)
            candidate["workflow"]["revision"] = int(workflow["revision"])
            current_digest = workflow["document_digest"]
            candidate_digest = self._document_digest(candidate)
            changed = candidate_digest != current_digest or bool(collection_changes)
            if changed:
                revision = int(workflow["revision"]) + 1
                candidate["workflow"]["revision"] = revision
                candidate_digest = self._document_digest(candidate)
                connection.execute(
                    update(tables.workflows)
                    .where(tables.workflows.c.id == workflow["id"])
                    .values(revision=revision, document=candidate, document_digest=candidate_digest, updated_at=saved_at, last_saved_by=actor)
                )
                self._audit_workflow(
                    connection,
                    skill_id=skill_id,
                    actor=actor,
                    action="workflow.saved",
                    payload={"workflow_id": workflow["id"], "revision": revision, "collection_change_count": len(collection_changes)},
                    created_at=saved_at,
                )
                for item in applied_changes:
                    self._audit_workflow(
                        connection,
                        skill_id=skill_id,
                        actor=actor,
                        action=f"workflow.collection_{item['operation']}",
                        payload={"workflow_id": workflow["id"], **item},
                        created_at=saved_at,
                    )
            else:
                revision = int(workflow["revision"])
                candidate = dict(workflow["document"])
        logger.info("workflow saved skill_id=%s workflow_id=%s revision=%s actor=%s changed=%s", skill_id, workflow["id"], revision, actor, changed)
        for item in applied_changes:
            logger.info(
                "workflow collection changed skill_id=%s workflow_id=%s operation=%s definition_id=%s revision=%s actor=%s",
                skill_id,
                workflow["id"],
                item["operation"],
                item["definition_id"],
                item["revision"],
                actor,
            )
        return {"document": candidate, "revision": revision, "changed": changed, "validation": self._workflow_validation(candidate)}

    def sync_workflow(self, *, skill_id: str, version: str, display_name: str | None, change_summary: str, manifest_text: str, source_text: str, generator_version: str, actor: str) -> dict[str, Any]:
        created_at = utc_now()
        try:
            with self.engine.begin() as connection:
                skill = self._skill_row(connection, skill_id)
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.version.create")
                workflow = self._workflow_row(connection, skill_id=skill_id)
                existing = (
                    connection.execute(
                        select(tables.workflow_syncs)
                        .where(tables.workflow_syncs.c.workflow_id == workflow["id"])
                        .where(tables.workflow_syncs.c.workflow_revision == workflow["revision"])
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    current = skill["current_version_id"] == existing["skill_version_id"]
                    if not current:
                        connection.execute(update(tables.skills).where(tables.skills.c.id == skill_id).values(current_version_id=existing["skill_version_id"], updated_at=created_at))
                        self._audit_workflow(connection, skill_id=skill_id, actor=actor, action="workflow.sync_reactivated", payload={"workflow_id": workflow["id"], "revision": workflow["revision"], "skill_version_id": existing["skill_version_id"]}, created_at=created_at)
                    logger.info(
                        "workflow sync reused skill_id=%s workflow_id=%s revision=%s skill_version_id=%s actor=%s mode=%s",
                        skill_id,
                        workflow["id"],
                        workflow["revision"],
                        existing["skill_version_id"],
                        actor,
                        "already_current" if current else "reactivated",
                    )
                    return {"mode": "already_current" if current else "reactivated", "skill_id": skill_id, "skill_version_id": existing["skill_version_id"], "workflow_revision": workflow["revision"]}

                semver = normalize_semver(version)
                source_artifact_id = self._insert_text_artifact(connection, kind="workflow_source", namespace=f"workflow:{workflow['id']}:{workflow['revision']}", content=source_text, actor=actor, created_at=created_at)
                bundle_artifact_id = self._insert_text_artifact(connection, kind="skill_bundle", namespace=f"workflow-sync:{skill_id}:{workflow['revision']}", content=manifest_text, actor=actor, created_at=created_at)
                skill_version_id = new_id("skillver")
                version_number = self._next_skill_version_number(connection, skill_id)
                connection.execute(
                    insert(tables.skill_versions).values(
                        id=skill_version_id,
                        skill_id=skill_id,
                        version_number=version_number,
                        version=semver,
                        display_name=display_name.strip() if display_name and display_name.strip() else None,
                        content_ref={"kind": "artifact", "locator": f"artifact:{bundle_artifact_id}", "digest": digest_text(manifest_text), "path": "SKILL.md"},
                        content_digest=digest_text(manifest_text),
                        change_summary=change_summary.strip(),
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                sync_id = new_id("workflowsync")
                connection.execute(
                    insert(tables.workflow_syncs).values(
                        id=sync_id,
                        workflow_id=workflow["id"],
                        workflow_revision=workflow["revision"],
                        document_schema_version=workflow["document_schema_version"],
                        source_artifact_id=source_artifact_id,
                        skill_version_id=skill_version_id,
                        generator_version=generator_version,
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(update(tables.skills).where(tables.skills.c.id == skill_id).values(current_version_id=skill_version_id, updated_at=created_at))
                self._audit_workflow(connection, skill_id=skill_id, actor=actor, action="workflow.synced", payload={"workflow_id": workflow["id"], "revision": workflow["revision"], "skill_version_id": skill_version_id, "generator_version": generator_version}, created_at=created_at)
        except IntegrityError as exc:
            raise FieldInvariantError(
                "Workflow sync version conflicts with an existing SkillVersion.",
                [FieldError(field="version", message="这个 Skill 已经存在相同版本号。", code="skill_version.version_conflict")],
            ) from exc
        logger.info("workflow synced skill_id=%s workflow_id=%s revision=%s skill_version_id=%s actor=%s", skill_id, workflow["id"], workflow["revision"], skill_version_id, actor)
        return {"mode": "created", "skill_id": skill_id, "skill_version_id": skill_version_id, "workflow_revision": workflow["revision"], "version": semver, "version_number": version_number}

    def _audit_workflow(self, connection, *, skill_id: str, actor: str, action: str, payload: dict[str, Any], created_at) -> None:
        connection.execute(
            insert(tables.audit_events).values(
                id=new_id("audit"),
                actor_ref=actor,
                action=action,
                resource_type="skill",
                resource_id=skill_id,
                payload=payload,
                created_at=created_at,
            )
        )
