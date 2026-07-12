from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.entities import digest_text
from skillhub.models.schema import tables


class WorkflowHelperMixin:
    def _workflow_row(self, connection, *, skill_id: str):
        row = connection.execute(select(tables.workflows).where(tables.workflows.c.skill_id == skill_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Workflow not found for skill: {skill_id}")
        return row

    def _workflow_validation(self, document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        from skillhub.models.rules.workflows import validate_workflow_document

        issues = validate_workflow_document(document)
        return {
            "errors": [item for item in issues if item["severity"] == "error"],
            "warnings": [item for item in issues if item["severity"] == "warning"],
        }

    def _workflow_sync_status(self, connection, *, workflow, skill) -> dict[str, Any]:
        latest = (
            connection.execute(
                select(tables.workflow_syncs)
                .where(tables.workflow_syncs.c.workflow_id == workflow["id"])
                .order_by(tables.workflow_syncs.c.workflow_revision.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )
        if latest is None:
            return {"status": "never_synced", "last_synced_revision": None, "last_synced_skill_version_id": None, "last_synced_at": None}
        workflow_changed = int(latest["workflow_revision"]) != int(workflow["revision"])
        skill_changed = str(skill["current_version_id"] or "") != str(latest["skill_version_id"])
        if workflow_changed and skill_changed:
            status = "diverged"
        elif workflow_changed:
            status = "workflow_changed"
        elif skill_changed:
            status = "skill_changed"
        else:
            status = "in_sync"
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
                select(tables.workflow_collection_revisions)
                .where(tables.workflow_collection_revisions.c.definition_id == definition_id)
                .where(tables.workflow_collection_revisions.c.revision == revision)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise InvariantError(f"Collection revision does not exist: {definition_id}@{revision}")
        return dict(row["definition"])

    def _workflow_summary(self, connection, skill) -> dict[str, Any] | None:
        workflow = connection.execute(select(tables.workflows).where(tables.workflows.c.skill_id == skill["id"])).mappings().one_or_none()
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
