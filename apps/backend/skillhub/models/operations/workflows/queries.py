from __future__ import annotations

from typing import Any

from sqlalchemy import select

from skillhub.models.schema import tables
from skillhub.models.operations.workflows.helpers import WorkflowHelperMixin
from skillhub.models.rules.workflows import migrate_workflow_document


class WorkflowQueryMixin(WorkflowHelperMixin):
    def workflow_detail(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            workflow = self._workflow_row(connection, skill_id=skill_id)
            document = migrate_workflow_document(workflow["document_schema_version"], dict(workflow["document"]))
            return {
                "id": workflow["id"],
                "skill_id": skill_id,
                "revision": workflow["revision"],
                "document_schema_version": workflow["document_schema_version"],
                "document": document,
                "validation": self._workflow_validation(document),
                "sync": self._workflow_sync_status(connection, workflow=workflow, skill=skill),
                "created_at": workflow["created_at"],
                "updated_at": workflow["updated_at"],
                "created_by": workflow["created_by"],
                "last_saved_by": workflow["last_saved_by"],
                "capabilities": self._skill_capabilities(connection, skill_id=skill_id, actor=actor),
            }

    def list_workflow_collections(self, *, skill_id: str, actor: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            self._workflow_row(connection, skill_id=skill_id)
            self._skill_capabilities(connection, skill_id=skill_id, actor=actor)
            rows = (
                connection.execute(
                    select(tables.workflow_collection_revisions.c.definition)
                    .join(
                        tables.workflow_collection_definitions,
                        (tables.workflow_collection_definitions.c.id == tables.workflow_collection_revisions.c.definition_id)
                        & (tables.workflow_collection_definitions.c.latest_revision == tables.workflow_collection_revisions.c.revision),
                    )
                    .order_by(tables.workflow_collection_definitions.c.id)
                )
                .scalars()
                .all()
            )
            return [dict(item) for item in rows]

    def workflow_sync_source(self, *, skill_version_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            sync = connection.execute(select(tables.workflow_syncs).where(tables.workflow_syncs.c.skill_version_id == skill_version_id)).mappings().one_or_none()
            return self._row_dict(sync) if sync is not None else None
