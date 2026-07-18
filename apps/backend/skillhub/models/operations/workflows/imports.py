from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.entities import digest_text, new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import (
    DOCUMENT_SCHEMA_VERSION,
    materialize_workflow_import,
    normalize_collection_definition,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    validate_workflow_import_references,
)
from skillhub.models.schema import orm

logger = logging.getLogger(__name__)


class WorkflowImportMixin:
    def import_workflow_bundle(self, *, skill_id: str, bundle: dict[str, Any], actor: str) -> dict[str, Any]:
        imported_at = utc_now()
        normalized = normalize_workflow_import_bundle(bundle)
        try:
            with self._write_session() as connection:
                self._skill_row(connection, skill_id)
                self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="skill.edit")
                workflow = self._workflow_row(connection, skill_id=skill_id)
                validate_workflow_import_references(normalized)
                mappings = self._insert_imported_collections(
                    connection,
                    definitions=normalized["collections"],
                    actor=actor,
                    created_at=imported_at,
                )
                revision = int(workflow["revision"]) + 1
                candidate = materialize_workflow_import(
                    normalized,
                    workflow_id=workflow["id"],
                    revision=revision,
                    collection_mappings=mappings,
                )
                candidate = normalize_workflow_document(candidate)
                candidate = self._canonicalize_collection_snapshots(connection, candidate, {})
                connection.execute(
                    update(orm.Workflow)
                    .where(orm.Workflow.id == workflow["id"])
                    .values(
                        revision=revision,
                        document=candidate,
                        document_digest=self._document_digest(candidate),
                        updated_at=imported_at,
                        last_saved_by=actor,
                    )
                )
                self._audit_workflow(
                    connection,
                    skill_id=skill_id,
                    actor=actor,
                    action="workflow.imported",
                    payload={
                        "workflow_id": workflow["id"],
                        "revision": revision,
                        "collection_count": len(mappings),
                    },
                    created_at=imported_at,
                )
        except IntegrityError as exc:
            raise InvariantError("Workflow import conflicted with existing data.") from exc

        collection_mappings = [
            {"local_id": local_id, "definition_id": definition_id, "revision": definition_revision}
            for local_id, (definition_id, definition_revision) in mappings.items()
        ]
        logger.info(
            "workflow imported skill_id=%s workflow_id=%s revision=%s collection_count=%s actor=%s",
            skill_id,
            workflow["id"],
            revision,
            len(collection_mappings),
            actor,
        )
        return {"revision": revision, "collection_mappings": collection_mappings}

    def _insert_imported_collections(self, connection, *, definitions, actor: str, created_at) -> dict[str, tuple[str, int]]:
        mappings: dict[str, tuple[str, int]] = {}
        for imported in definitions:
            definition_id = new_id("collection")
            revision = 1
            definition = normalize_collection_definition(
                {
                    "id": definition_id,
                    "revision": revision,
                    "key": imported["key"],
                    "metadata": imported["metadata"],
                    "spec": imported["spec"],
                    "inputs": imported["inputs"],
                    "outputs": imported["outputs"],
                }
            )
            connection.execute(
                insert(orm.WorkflowCollectionDefinition).values(
                    id=definition_id,
                    latest_revision=revision,
                    created_at=created_at,
                    updated_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                insert(orm.WorkflowCollectionRevision).values(
                    definition_id=definition_id,
                    revision=revision,
                    document_schema_version=DOCUMENT_SCHEMA_VERSION,
                    definition=definition,
                    definition_digest=digest_text(self._canonical_document_text(definition)),
                    created_at=created_at,
                    created_by=actor,
                )
            )
            mappings[imported["localId"]] = (definition_id, revision)
        return mappings
