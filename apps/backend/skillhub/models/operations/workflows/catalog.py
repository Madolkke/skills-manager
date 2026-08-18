from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update

from skillhub.models.entities import digest_text
from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, normalize_collection_definition
from skillhub.models.schema import orm


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
            source_system_command_id = change.get("source_system_command_id")
            definition = normalize_collection_definition(change["definition"])
            source_system_command_id = source_system_command_id or definition.get("sourceSystemCommandId")
            if source_system_command_id:
                definition["sourceSystemCommandId"] = source_system_command_id
            definition_id = definition["id"].strip()
            requested_revision = int(definition["revision"])
            if not definition_id or definition_id in seen:
                raise InvariantError("Collection changes require unique non-empty IDs.")
            seen.add(definition_id)
            existing = connection.execute(
                orm.select_entity(orm.WorkflowCollectionDefinition).where(orm.WorkflowCollectionDefinition.id == definition_id)
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
                if source_system_command_id:
                    if definition.get("spec", {}).get("collectionType") != "cli":
                        raise InvariantError("Only CLI Collections can reference a system command.")
                    source_row = connection.execute(
                        select(orm.SystemCommand).where(orm.SystemCommand.id == source_system_command_id)
                    ).scalar_one_or_none()
                    if source_row is None:
                        raise InvariantError(f"System command does not exist: {source_system_command_id}")
                    # The source row is authoritative.  Do not compare the
                    # client draft here: an administrator may have updated
                    # the system expression after the picker created this
                    # draft.  ``sync_system_sources`` materializes the latest
                    # source and performs the compatibility checks in the
                    # same transaction.
                revision = 1
                connection.execute(
                    insert(orm.WorkflowCollectionDefinition).values(
                        id=definition_id,
                        latest_revision=revision,
                        created_at=created_at,
                        updated_at=created_at,
                        created_by=actor,
                        source_system_command_id=source_system_command_id,
                    )
                )
            elif operation == "revise":
                if existing is None:
                    raise InvariantError(f"Collection does not exist: {definition_id}")
                if existing["source_system_command_id"]:
                    raise InvariantError("System source Collections are read-only and cannot be revised directly.")
                if source_system_command_id:
                    raise InvariantError("A user Collection cannot be converted into a system-source Collection.")
                revision = int(existing["latest_revision"]) + 1
                connection.execute(
                    update(orm.WorkflowCollectionDefinition)
                    .where(orm.WorkflowCollectionDefinition.id == definition_id)
                    .values(latest_revision=revision, updated_at=created_at)
                )
            else:
                raise InvariantError(f"Unsupported Collection operation: {operation}")
            definition["revision"] = revision
            serialized = self._canonical_document_text(definition)
            connection.execute(
                insert(orm.WorkflowCollectionRevision).values(
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
            applied.append(
                {
                    "operation": operation,
                    "definition_id": definition_id,
                    "revision": revision,
                    "source_system_command_id": source_system_command_id,
                }
            )
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
