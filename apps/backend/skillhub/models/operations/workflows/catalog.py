from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from skillhub.models.errors import InvariantError
from skillhub.models.entities import digest_text
from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, normalize_collection_definition
from skillhub.models.schema import tables


class WorkflowCatalogMixin:
    def _apply_collection_changes(
        self,
        connection,
        *,
        changes: list[dict[str, Any]],
        actor: str,
        created_at,
    ) -> tuple[dict[tuple[str, int], tuple[str, int]], list[dict[str, Any]]]:
        mappings: dict[tuple[str, int], tuple[str, int]] = {}
        applied: list[dict[str, Any]] = []
        seen: set[str] = set()
        for change in changes:
            operation = change["operation"]
            definition = normalize_collection_definition(change["definition"])
            definition_id = definition["id"].strip()
            requested_revision = int(definition["revision"])
            if not definition_id or definition_id in seen:
                raise InvariantError("Collection changes require unique non-empty IDs.")
            seen.add(definition_id)
            existing = connection.execute(
                select(tables.workflow_collection_definitions).where(tables.workflow_collection_definitions.c.id == definition_id)
            ).mappings().one_or_none()
            if operation in {"create", "fork"}:
                if existing is not None:
                    raise InvariantError(f"Collection already exists: {definition_id}")
                if operation == "fork":
                    source = definition.get("forkedFrom")
                    if not source:
                        raise InvariantError("Forked Collection requires forkedFrom.")
                    self._collection_revision(connection, source["id"], source["revision"])
                elif definition.get("forkedFrom"):
                    raise InvariantError("New Collection cannot set forkedFrom without fork operation.")
                revision = 1
                connection.execute(
                    insert(tables.workflow_collection_definitions).values(
                        id=definition_id,
                        latest_revision=revision,
                        created_at=created_at,
                        updated_at=created_at,
                        created_by=actor,
                    )
                )
            elif operation == "revise":
                if existing is None:
                    raise InvariantError(f"Collection does not exist: {definition_id}")
                revision = int(existing["latest_revision"]) + 1
                connection.execute(
                    update(tables.workflow_collection_definitions)
                    .where(tables.workflow_collection_definitions.c.id == definition_id)
                    .values(latest_revision=revision, updated_at=created_at)
                )
            else:
                raise InvariantError(f"Unsupported Collection operation: {operation}")
            definition["revision"] = revision
            serialized = self._canonical_document_text(definition)
            connection.execute(
                insert(tables.workflow_collection_revisions).values(
                    definition_id=definition_id,
                    revision=revision,
                    document_schema_version=DOCUMENT_SCHEMA_VERSION,
                    definition=definition,
                    definition_digest=digest_text(serialized),
                    created_at=created_at,
                    created_by=actor,
                )
            )
            mappings[(definition_id, requested_revision)] = (definition_id, revision)
            applied.append({"operation": operation, "definition_id": definition_id, "revision": revision})
        return mappings, applied

    def _canonicalize_collection_snapshots(self, connection, document: dict[str, Any], mappings: dict[tuple[str, int], tuple[str, int]]) -> dict[str, Any]:
        calls = [call for node in document["workflow"]["nodes"] if "stepType" in node for call in node["collectionCalls"]]
        refs: list[tuple[str, int]] = []
        for call in calls:
            original = (call["definition"]["id"], int(call["definition"]["revision"]))
            resolved = mappings.get(original, original)
            call["definition"] = {"id": resolved[0], "revision": resolved[1]}
            if resolved not in refs:
                refs.append(resolved)
        document["collectionSnapshots"] = [self._collection_revision(connection, definition_id, revision) for definition_id, revision in refs]
        return document
