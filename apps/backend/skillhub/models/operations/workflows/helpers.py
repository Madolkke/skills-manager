from __future__ import annotations

import json
from typing import Any

from skillhub.models.entities import digest_text
from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.rules.workflows import migrate_collection_definition
from skillhub.models.schema import orm


class WorkflowHelperMixin:
    def _generator_evidence_from_sync(self, sync) -> dict[str, Any]:
        return self._generator_evidence(
            generator_id=str(sync["generator_id"]),
            generator_version=str(sync["generator_version"]),
            generator_options=dict(sync["generator_options"]),
            generator_options_digest=str(sync["generator_options_digest"]),
            preview_digest=str(sync["preview_digest"]),
        )

    def _generator_evidence(
        self,
        *,
        generator_id: str,
        generator_version: str,
        generator_options: dict[str, Any],
        generator_options_digest: str,
        preview_digest: str,
    ) -> dict[str, Any]:
        return {
            "generator_id": generator_id,
            "generator_version": generator_version,
            "generator_options": dict(generator_options),
            "generator_options_digest": generator_options_digest,
            "preview_digest": preview_digest,
        }

    def _workflow_row(self, connection, *, skill_id: str):
        row = connection.execute(orm.select_entity(orm.Workflow).where(orm.Workflow.skill_id == skill_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Workflow not found for skill: {skill_id}")
        return row

    def _workflow_validation(self, document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        from skillhub.models.rules.workflows import validate_workflow_document

        issues = validate_workflow_document(document, functions=self.expression_function_contract())
        return {
            "errors": [item for item in issues if item["severity"] == "error"],
            "warnings": [item for item in issues if item["severity"] == "warning"],
        }

    def _workflow_sync_status(self, connection, *, workflow, skill) -> dict[str, Any]:
        current_sync = None
        if skill["current_version_id"]:
            current_sync = (
                connection.execute(
                    orm.select_entity(orm.WorkflowSync)
                    .where(orm.WorkflowSync.skill_version_id == skill["current_version_id"])
                )
                .mappings()
                .one_or_none()
            )
        latest = (
            connection.execute(
                orm.select_entity(orm.WorkflowSync)
                .where(orm.WorkflowSync.workflow_id == workflow["id"])
                .order_by(orm.WorkflowSync.created_at.desc(), orm.WorkflowSync.id.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        return self._workflow_sync_status_from_latest(
            latest=latest,
            current_sync=current_sync,
            workflow=workflow,
            skill=skill,
        )

    def _workflow_sync_status_from_latest(self, *, latest, workflow, skill, current_sync=None) -> dict[str, Any]:
        if latest is None:
            return {"status": "never_synced", "last_synced_revision": None, "last_synced_skill_version_id": None, "last_synced_at": None}
        if current_sync is not None:
            status = (
                "in_sync"
                if int(current_sync["workflow_revision"]) == int(workflow["revision"])
                else "workflow_changed"
            )
        else:
            status = (
                "skill_changed"
                if int(latest["workflow_revision"]) == int(workflow["revision"])
                else "diverged"
            )
        return {
            "status": status,
            "last_synced_revision": latest["workflow_revision"],
            "last_synced_skill_version_id": latest["skill_version_id"],
            "last_synced_at": latest["created_at"],
        }

    def _canonical_document_text(self, document: dict[str, Any]) -> str:
        return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _document_digest(self, document: dict[str, Any]) -> str:
        return digest_text(self._canonical_document_text(document))

    def _collection_revision(self, connection, definition_id: str, revision: int) -> dict[str, Any]:
        row = (
            connection.execute(
                orm.select_entity(orm.WorkflowCollectionRevision)
                .where(orm.WorkflowCollectionRevision.definition_id == definition_id)
                .where(orm.WorkflowCollectionRevision.revision == revision)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise InvariantError(f"Collection revision does not exist: {definition_id}@{revision}")
        return migrate_collection_definition(int(row["document_schema_version"]), dict(row["definition"]))

    def _workflow_summary(self, connection, skill) -> dict[str, Any] | None:
        workflow = connection.execute(orm.select_entity(orm.Workflow).where(orm.Workflow.skill_id == skill["id"])).mappings().one_or_none()
        if workflow is None:
            return None
        sync = self._workflow_sync_status(connection, workflow=workflow, skill=skill)
        return {
            "id": workflow["id"],
            "skill_id": workflow["skill_id"],
            "revision": workflow["revision"],
            "document_schema_version": workflow["document_schema_version"],
            "updated_at": workflow["updated_at"],
            **sync,
        }
