from __future__ import annotations

from typing import Any

from sqlalchemy import select

from skillhub.models.operations.workflows.helpers import WorkflowHelperMixin
from skillhub.models.rules.workflows import migrate_collection_definition, migrate_workflow_document
from skillhub.models.schema import orm


class WorkflowQueryMixin(WorkflowHelperMixin):
    def executor_workflow_source(self, *, skill_id: str) -> dict[str, Any]:
        """Return the current migrated Workflow document without editor read models."""
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            workflow = self._workflow_row(connection, skill_id=skill_id)
            return migrate_workflow_document(workflow["document_schema_version"], dict(workflow["document"]))

    def workflow_detail(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as connection:
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
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            self._workflow_row(connection, skill_id=skill_id)
            self._skill_capabilities(connection, skill_id=skill_id, actor=actor)
            rows = (
                connection.execute(
                    select(orm.WorkflowCollectionRevision.document_schema_version, orm.WorkflowCollectionRevision.definition)
                    .join(
                        orm.WorkflowCollectionDefinition,
                        (orm.WorkflowCollectionDefinition.id == orm.WorkflowCollectionRevision.definition_id)
                        & (orm.WorkflowCollectionDefinition.latest_revision == orm.WorkflowCollectionRevision.revision),
                    )
                    .order_by(orm.WorkflowCollectionDefinition.id)
                )
                .all()
            )
            return [migrate_collection_definition(int(item.document_schema_version), dict(item.definition)) for item in rows]

    def workflow_sync_source(self, *, skill_version_id: str) -> dict[str, Any] | None:
        with self._read_session() as connection:
            sync = connection.execute(orm.select_entity(orm.WorkflowSync).where(orm.WorkflowSync.skill_version_id == skill_version_id)).mappings().one_or_none()
            return self._row_dict(sync) if sync is not None else None
