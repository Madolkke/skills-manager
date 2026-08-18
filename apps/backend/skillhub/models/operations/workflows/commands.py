from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import ContentRef, digest_text, new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.operations.workflows.catalog import WorkflowCatalogMixin
from skillhub.models.operations.workflows.helpers import WorkflowHelperMixin
from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, normalize_workflow_document
from skillhub.models.schema import orm

logger = logging.getLogger(__name__)


class WorkflowCommandMixin(WorkflowCatalogMixin, WorkflowHelperMixin):
    def create_workflow_skill(self, *, slug: str, owner_ref: str, manifest_text: str, document: dict[str, Any], tags: list[dict[str, Any]], actor: str) -> dict[str, Any]:
        created_at = utc_now()
        normalized = normalize_workflow_document(document)
        try:
            with self._write_session() as connection:
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
                    insert(orm.Workflow).values(
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
        with self._write_session() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.edit")
            workflow = self._workflow_row(connection, skill_id=skill_id)
            candidate = normalize_workflow_document(document)
            if candidate["workflow"]["id"] != workflow["id"]:
                raise InvariantError("Workflow ID cannot be changed.")
            mappings, applied_changes = self._apply_collection_changes(connection, changes=collection_changes, actor=actor, created_at=saved_at)
            source_mappings = self.sync_system_sources(connection, document=candidate, actor=actor, created_at=saved_at)
            mappings.update(source_mappings)
            candidate = self._canonicalize_collection_snapshots(connection, candidate, mappings)
            for snapshot in candidate.get("collectionSnapshots", []):
                self._sync_user_command_from_collection(
                    connection,
                    owner_ref=actor,
                    definition=snapshot,
                    collection_id=snapshot["id"],
                    collection_revision=int(snapshot["revision"]),
                    actor=actor,
                    created_at=saved_at,
                    workflow_id=workflow["id"],
                )
            # 系统来源只属于执行层 Collection，不应出现在用户命令库投影中。
            connection.execute(
                delete(orm.UserCommandLibraryEntry)
                .where(orm.UserCommandLibraryEntry.workflow_id == workflow["id"])
                .where(orm.UserCommandLibraryEntry.source_system_command_id.is_not(None))
            )
            active_collection_ids = {
                str(snapshot.get("id"))
                for snapshot in candidate.get("collectionSnapshots", [])
                if snapshot.get("id")
            }
            stale_user_commands = delete(orm.UserCommandLibraryEntry).where(
                orm.UserCommandLibraryEntry.workflow_id == workflow["id"]
            )
            if active_collection_ids:
                stale_user_commands = stale_user_commands.where(
                    orm.UserCommandLibraryEntry.collection_id.not_in(active_collection_ids)
                )
            connection.execute(stale_user_commands)
            candidate["workflow"]["revision"] = int(workflow["revision"])
            current_digest = workflow["document_digest"]
            candidate_digest = self._document_digest(candidate)
            changed = candidate_digest != current_digest or bool(collection_changes)
            if changed:
                revision = int(workflow["revision"]) + 1
                candidate["workflow"]["revision"] = revision
                candidate_digest = self._document_digest(candidate)
                connection.execute(
                    update(orm.Workflow)
                    .where(orm.Workflow.id == workflow["id"])
                    .values(revision=revision, document_schema_version=DOCUMENT_SCHEMA_VERSION, document=candidate, document_digest=candidate_digest, updated_at=saved_at, last_saved_by=actor)
                )
                step_ids = {
                    str(node.get("id"))
                    for node in candidate["workflow"]["nodes"]
                    if node.get("stepType") in {"expression", "script"} and node.get("id")
                }
                self.delete_removed_step_debug_cases(connection, skill_id=skill_id, step_ids=step_ids)
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

    def _audit_workflow(self, connection, *, skill_id: str, actor: str, action: str, payload: dict[str, Any], created_at) -> None:
        connection.execute(
            insert(orm.AuditEvent).values(
                id=new_id("audit"),
                actor_ref=actor,
                action=action,
                resource_type="skill",
                resource_id=skill_id,
                payload=payload,
                created_at=created_at,
            )
        )
