from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError, InvariantError, NotFoundError
from skillhub.models.rules.command_expression import (
    capture_catalog,
    match_command_expression,
    next_command_tokens,
    parse_command_expression,
)
from skillhub.models.rules.workflows.source_compatibility import _validate_source_compatibility as _validate_source_compatibility
from skillhub.models.schema import orm

logger = logging.getLogger(__name__)


class CommandLibraryStoreMixin:
    """Persistence and matching operations for system/user command templates."""

    def search_command_library(
        self,
        *,
        query: str,
        actor: str,
        owner_ref: str | None = None,
        include_system: bool = True,
        include_user: bool = True,
        include_disabled: bool = False,
        target_version: str | None = None,
        partial: bool = True,
        prefix: bool = True,
    ) -> list[dict[str, Any]]:
        owner = owner_ref.strip() if owner_ref else None
        with self._read_session() as session:
            entries: list[dict[str, Any]] = []
            if include_system:
                statement = select(orm.SystemCommandLibraryEntry).order_by(orm.SystemCommandLibraryEntry.key)
                if not include_disabled:
                    statement = statement.where(orm.SystemCommandLibraryEntry.enabled.is_(True))
                entries.extend(_entry_row(item, "system") for item in session.execute(statement).scalars())
            if include_user:
                statement = select(orm.UserCommandLibraryEntry).order_by(orm.UserCommandLibraryEntry.key)
                if owner is not None:
                    statement = statement.where(orm.UserCommandLibraryEntry.owner_ref == owner)
                if not include_disabled:
                    statement = statement.where(orm.UserCommandLibraryEntry.enabled.is_(True))
                entries.extend(_entry_row(item, "user") for item in session.execute(statement).scalars())
        if target_version:
            entries = [item for item in entries if _version_matches(item, target_version)]
        if not query.strip():
            for item in entries:
                item["score"] = 0
                item["match"] = None
                item["complete"] = False
                item["captures"] = {}
                item["alternatives"] = []
                item["nextTokens"] = _next_tokens(item["expression"], "")
                item["ambiguous"] = False
            ordered = sorted(entries, key=_search_sort_key)
            return ordered
        ranked: list[dict[str, Any]] = []
        for item in entries:
            if target_version and not _version_matches(item, target_version):
                continue
            try:
                match = match_command_expression(
                    item["expression"], query, partial=partial, prefix=prefix
                )
            except InvariantError:
                # A legacy/manual row must not make the whole catalog
                # unavailable.  Invalid expressions stay out of search until
                # an administrator repairs the source record.
                continue
            if match is None:
                continue
            alternatives = list(match.alternatives) or [match.captures]
            for alternative_index, captures in enumerate(alternatives):
                result = dict(item)
                result["score"] = match.score
                result["match"] = {
                    "captures": captures,
                    "alternatives": alternatives,
                    "exact": match.exact,
                    "partial": match.partial,
                    "normalizedExpression": match.normalized_expression,
                    "ambiguous": match.ambiguous,
                }
                result["complete"] = match.exact
                result["captures"] = captures
                result["alternatives"] = alternatives
                result["alternativeIndex"] = alternative_index
                result["consumedTokens"] = match.consumed_tokens
                result["nextTokens"] = _next_tokens(item["expression"], query)
                result["ambiguous"] = match.ambiguous
                ranked.append(result)
        ranked.sort(key=_search_sort_key)
        for index, item in enumerate(ranked):
            item["ambiguous"] = bool(item.get("ambiguous")) or any(
                neighbor["score"] == item["score"]
                and neighbor.get("consumedTokens") == item.get("consumedTokens")
                for neighbor in (ranked[index - 1:index] + ranked[index + 1:index + 2])
            )
        return ranked

    def list_system_commands(self, *, include_disabled: bool = True) -> list[dict[str, Any]]:
        with self._read_session() as session:
            statement = select(orm.SystemCommandLibraryEntry).order_by(orm.SystemCommandLibraryEntry.key)
            if not include_disabled:
                statement = statement.where(orm.SystemCommandLibraryEntry.enabled.is_(True))
            return [_entry_row(item, "system") for item in session.execute(statement).scalars()]

    def get_system_command(self, *, command_id: str) -> dict[str, Any]:
        with self._read_session() as session:
            item = session.get(orm.SystemCommandLibraryEntry, command_id)
            if item is None:
                raise NotFoundError(f"System command does not exist: {command_id}")
            return _entry_row(item, "system")

    def create_system_command(
        self,
        *,
        key: str,
        name: str,
        expression: str,
        description: str = "",
        captures: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        enabled: bool = True,
        command_id: str | None = None,
        actor: str = "admin-console",
        document: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        key, name, description = _required_text(key, "key"), _required_text(name, "name"), description.strip()
        parsed = parse_command_expression(expression)
        now = utc_now()
        default_document = {
            "metadata": dict(metadata or {}),
            "samples": list((metadata or {}).get("samples", [])),
            "outputSchema": dict((metadata or {}).get("outputSchema", {})),
            "ttp": str((metadata or {}).get("ttp", "")),
        }
        values = {
            "id": command_id or new_id("system-command"),
            "key": key,
            "name": name,
            "description": description,
            "expression": expression.strip(),
            "normalized_expression": parsed.normalized,
            "captures": capture_catalog(parsed.root),
            "metadata_json": dict(metadata or {}),
            "document": dict(document or default_document),
            "enabled": bool(enabled),
            "created_by": actor,
            "updated_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        with self._write_session() as session:
            try:
                session.execute(insert(orm.SystemCommandLibraryEntry).values(**values))
            except Exception as exc:
                if _is_integrity_error(exc):
                    raise ConflictError("System command key or normalized expression already exists.") from exc
                raise
            session.flush()
            return _entry_row(session.get(orm.SystemCommandLibraryEntry, values["id"]), "system")

    def update_system_command(self, *, command_id: str, actor: str = "admin-console", **changes: Any) -> dict[str, Any]:
        with self._write_session() as session:
            item = session.get(orm.SystemCommandLibraryEntry, command_id)
            if item is None:
                raise NotFoundError(f"System command does not exist: {command_id}")
            values: dict[str, Any] = {}
            for field in ("key", "name", "description", "enabled", "metadata", "document"):
                if field in changes and changes[field] is not None:
                    values[field if field != "metadata" else "metadata_json"] = changes[field]
            if "expression" in changes and changes["expression"] is not None:
                parsed = parse_command_expression(str(changes["expression"]))
                values["expression"] = str(changes["expression"]).strip()
                values["normalized_expression"] = parsed.normalized
                values["captures"] = capture_catalog(parsed.root)
            if not values:
                return _entry_row(item, "system")
            values["updated_by"] = actor
            values["updated_at"] = utc_now()
            try:
                session.execute(
                    update(orm.SystemCommandLibraryEntry)
                    .where(orm.SystemCommandLibraryEntry.id == command_id)
                    .values(**values)
                )
            except Exception as exc:
                if _is_integrity_error(exc):
                    raise ConflictError("System command update conflicted with another entry.") from exc
                raise
            session.flush()
            session.refresh(item)
            return _entry_row(item, "system")

    def delete_system_command(self, *, command_id: str) -> dict[str, Any]:
        with self._write_session() as session:
            if session.get(orm.SystemCommandLibraryEntry, command_id) is None:
                raise NotFoundError(f"System command does not exist: {command_id}")
            source_definition_ids = set(
                session.execute(
                    select(orm.WorkflowCollectionDefinition.id).where(
                        orm.WorkflowCollectionDefinition.source_system_command_id == command_id
                    )
                ).scalars()
            )
            active_definition_ids = _workflow_collection_references(session)
            active_source_ids = source_definition_ids & active_definition_ids
            if active_source_ids:
                raise ConflictError("System command is referenced by a Collection or user command.")
            # Orphaned execution snapshots remain usable, but no longer point at
            # a deleted system source and therefore must not block the delete.
            if source_definition_ids:
                session.execute(
                    update(orm.WorkflowCollectionDefinition)
                    .where(orm.WorkflowCollectionDefinition.id.in_(source_definition_ids))
                    .values(source_system_command_id=None)
                )
                # The source identity is duplicated in the immutable JSON
                # revision for editor round-tripping.  Clear it there too;
                # otherwise a later save would treat the orphan snapshot as a
                # dangling system binding after the source row is deleted.
                for revision in session.execute(
                    select(orm.WorkflowCollectionRevision).where(
                        orm.WorkflowCollectionRevision.definition_id.in_(source_definition_ids)
                    )
                ).scalars():
                    definition = dict(revision.definition or {})
                    definition.pop("sourceSystemCommandId", None)
                    definition.pop("source_system_command_id", None)
                    session.execute(
                        update(orm.WorkflowCollectionRevision)
                        .where(
                            orm.WorkflowCollectionRevision.definition_id == revision.definition_id,
                            orm.WorkflowCollectionRevision.revision == revision.revision,
                        )
                        .values(
                            definition=definition,
                            definition_digest=self._document_digest(definition),
                        )
                    )
            session.execute(
                update(orm.UserCommandLibraryEntry)
                .where(orm.UserCommandLibraryEntry.source_system_command_id == command_id)
                .values(source_system_command_id=None)
            )
            session.execute(delete(orm.SystemCommandLibraryEntry).where(orm.SystemCommandLibraryEntry.id == command_id))
        return {"id": command_id, "deleted": True}

    def delete_user_command(self, *, owner_ref: str, command_id: str) -> dict[str, Any]:
        with self._write_session() as session:
            item = session.get(orm.UserCommandLibraryEntry, command_id)
            if item is None or item.owner_ref != owner_ref:
                raise NotFoundError(f"User command does not exist: {command_id}")
            session.delete(item)
        return {"id": command_id, "deleted": True}

    def sync_system_sources(self, connection, *, document: dict[str, Any], actor: str, created_at) -> dict[tuple[str, int], tuple[str, int]]:
        """在保存事务内验证全部候选系统来源，再统一写入快照。"""
        from .command_source_sync import sync_system_sources

        return sync_system_sources(self, connection, document=document, actor=actor, created_at=created_at)

    def _sync_user_command_from_collection(
        self,
        connection,
        *,
        owner_ref: str,
        definition: Mapping[str, Any],
        collection_id: str,
        collection_revision: int,
        actor: str,
        created_at,
        workflow_id: str,
    ) -> None:
        spec = definition.get("spec") or {}
        projection_filter = delete(orm.UserCommandLibraryEntry).where(
            orm.UserCommandLibraryEntry.workflow_id == workflow_id,
            orm.UserCommandLibraryEntry.collection_id == collection_id,
        )
        source_id = definition.get("sourceSystemCommandId", definition.get("source_system_command_id"))
        if source_id:
            # System-source Collections belong to the execution layer and
            # must never remain searchable as user entries.
            source_row = connection.execute(
                select(orm.SystemCommandLibraryEntry).where(orm.SystemCommandLibraryEntry.id == source_id)
            ).scalar_one_or_none()
            if source_row is None:
                raise NotFoundError(f"System command does not exist: {source_id}")
            connection.execute(projection_filter)
            return
        if spec.get("collectionType", spec.get("collection_type")) != "cli":
            connection.execute(projection_filter)
            return
        expression = str(spec.get("commandTemplate", spec.get("command_template", ""))).strip()
        if not expression:
            connection.execute(projection_filter)
            return
        try:
            parsed = parse_command_expression(expression)
        except InvariantError as exc:
            logger.warning(
                "command-library projection skipped invalid CLI expression workflow_id=%s collection_id=%s: %s",
                workflow_id,
                collection_id,
                exc,
            )
            connection.execute(projection_filter)
            return
        metadata = definition.get("metadata") or {}
        key = str(definition.get("key") or "").strip()
        name = str(metadata.get("name") or "").strip() if isinstance(metadata, Mapping) else ""
        if not key or not name:
            # Keep unfinished drafts saveable so the regular Workflow
            # validator can report the field-level diagnostics.
            connection.execute(projection_filter)
            return
        statement = select(orm.UserCommandLibraryEntry).where(
            orm.UserCommandLibraryEntry.workflow_id == workflow_id,
            orm.UserCommandLibraryEntry.collection_id == collection_id,
        )
        existing = connection.execute(statement).scalar_one_or_none()
        values = {
            "owner_ref": owner_ref,
            "workflow_id": workflow_id,
            "key": key,
            "name": name,
            "description": metadata.get("description", "") if isinstance(metadata, Mapping) else "",
            "expression": expression,
            "normalized_expression": parsed.normalized,
            "captures": capture_catalog(parsed.root),
            "metadata_json": metadata if isinstance(metadata, Mapping) else {},
            "document": _collection_document(definition),
            "enabled": True,
            "source_system_command_id": None,
            "collection_definition_id": collection_id,
            "collection_revision": collection_revision,
            "collection_id": collection_id,
            "updated_by": actor,
            "updated_at": created_at,
        }
        if existing is None:
            connection.execute(
                insert(orm.UserCommandLibraryEntry).values(
                    id=new_id("user-command"), created_by=actor, created_at=created_at, **values
                )
            )
        else:
            connection.execute(
                update(orm.UserCommandLibraryEntry)
                .where(orm.UserCommandLibraryEntry.id == existing.id)
                .values(**values)
            )


def _entry_row(item: Any, source: str) -> dict[str, Any]:
    document = getattr(item, "document", None) or {}
    metadata = getattr(item, "metadata_json", None) or {}
    document_metadata = document.get("metadata") if isinstance(document, Mapping) else {}
    versions = (
        document_metadata.get("versions")
        if isinstance(document_metadata, Mapping) and isinstance(document_metadata.get("versions"), list)
        else metadata.get("versions", []) if isinstance(metadata, Mapping) else []
    )
    return {
        "id": item.id,
        "source": source,
        "ownerRef": getattr(item, "owner_ref", None),
        "key": item.key,
        "name": item.name,
        "description": item.description,
        "expression": item.expression,
        "normalizedExpression": item.normalized_expression,
        "captures": item.captures,
        "captureSchema": item.captures,
        "metadata": metadata,
        "versions": list(versions),
        "document": document,
        "samples": document.get("samples", []),
        "outputSchema": document.get("outputSchema", {}),
        "ttp": document.get("ttp", ""),
        "enabled": item.enabled,
        "sourceSystemCommandId": getattr(item, "source_system_command_id", None),
        "collectionDefinitionId": getattr(item, "collection_definition_id", None),
        "collectionRevision": getattr(item, "collection_revision", None),
        "workflowId": getattr(item, "workflow_id", None),
        "collectionId": getattr(item, "collection_id", None),
    }


def _search_sort_key(item: Mapping[str, Any]) -> tuple[int, int, int, str, str, str, int]:
    source_priority = 0 if item.get("source") == "system" else 1
    return (
        -int(item.get("score", 0)),
        -int(item.get("consumedTokens", 0)),
        source_priority,
        str(item.get("name", "")).casefold(),
        str(item.get("key", "")).casefold(),
        str(item.get("id", "")),
        int(item.get("alternativeIndex", 0)),
    )


def _collection_document(definition: Mapping[str, Any]) -> dict[str, Any]:
    spec = definition.get("spec") or {}
    command_template = str(spec.get("commandTemplate", ""))
    outputs = definition.get("outputs") or []
    properties = {str(item.get("key")): item.get("schema", {}) for item in outputs if item.get("key")}
    required = [str(item.get("key")) for item in outputs if item.get("key") and item.get("required", True)]
    return {
        "metadata": dict(definition.get("metadata") or {}),
        "inputs": list(definition.get("inputs") or []),
        "samples": [
            {
                "id": item.get("id"),
                "name": item.get("name", "示例"),
                "command": item.get("command") or command_template,
                "stdout": item.get("stdout", ""),
            }
            for item in spec.get("outputSamples", [])
        ],
        "outputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "ttp": "",
    }


def _version_matches(item: Mapping[str, Any], target: str) -> bool:
    document = item.get("document") if isinstance(item.get("document"), Mapping) else {}
    metadata = document.get("metadata") if isinstance(document, Mapping) else {}
    if not isinstance(metadata, Mapping) or "versions" not in metadata:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    versions = metadata.get("versions", []) if isinstance(metadata, Mapping) else []
    return not versions or any(str(target).casefold() in str(version).casefold() for version in versions)


def _workflow_collection_references(session) -> set[str]:
    """Collect current Workflow Collection IDs for source-delete protection."""
    references: set[str] = set()
    for document in session.execute(select(orm.Workflow.document)).scalars():
        if not isinstance(document, Mapping):
            continue
        for snapshot in document.get("collectionSnapshots", []):
            if isinstance(snapshot, Mapping) and snapshot.get("id"):
                references.add(str(snapshot["id"]))
        for node in (document.get("workflow", {}) or {}).get("nodes", []):
            if not isinstance(node, Mapping):
                continue
            for call in node.get("collectionCalls", []):
                reference = call.get("definition", {}) if isinstance(call, Mapping) else {}
                if isinstance(reference, Mapping) and reference.get("id"):
                    references.add(str(reference["id"]))
    return references


def _next_tokens(expression: str, query: str) -> list[str]:
    try:
        return next_command_tokens(expression, query, limit=16)
    except InvariantError:
        return []


def _source_to_collection(source: Any, *, definition_id: str, revision: int, source_id: str) -> dict[str, Any]:
    from skillhub.models.rules.workflows import normalize_collection_definition

    document = dict(source.document or {})
    metadata = dict(document.get("metadata") or source.metadata_json or {})
    metadata.setdefault("name", source.name)
    metadata.setdefault("description", source.description)
    metadata.setdefault("industry", "")
    metadata.setdefault("device", "")
    metadata.setdefault("versions", [])
    metadata.setdefault("tags", [])
    captures = source.captures or {}
    inputs = []
    for name, value in sorted(captures.items()):
        repeated = isinstance(value, Mapping) and bool(value.get("repeated"))
        input_schema: dict[str, Any] = {
            "type": "array",
            "title": f"{name} 列表",
            "description": "",
            "items": {"type": "string", "title": str(name), "description": ""},
        } if repeated else {"type": "string", "title": str(name), "description": ""}
        inputs.append(
            {
                "id": f"input_{name}",
                "key": name,
                "required": not bool(value.get("optional", False)) if isinstance(value, Mapping) else True,
                "schema": input_schema,
            }
        )
    output_schema = document.get("outputSchema") or {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    if not isinstance(output_schema, Mapping) or output_schema.get("type") != "object":
        raise InvariantError("System command root output schema must be an object.")
    properties = output_schema.get("properties")
    if not isinstance(properties, Mapping):
        raise InvariantError("System command root output schema requires properties.")
    raw_required = output_schema.get("required", [])
    if not isinstance(raw_required, list) or any(not isinstance(name, str) for name in raw_required):
        raise InvariantError("System command root output schema requires a string required list.")
    required = set(raw_required)
    outputs = [
        {"id": f"output_{name}", "key": name, "required": name in required, "schema": _workflow_schema(schema, fallback_title=str(name))}
        for name, schema in sorted(properties.items())
    ]
    return normalize_collection_definition(
        {
            "id": definition_id,
            "revision": revision,
            "key": source.key,
            "metadata": metadata,
            "spec": {
                "collectionType": "cli",
                "commandTemplate": source.expression,
                "outputSamples": [
                    {
                        "id": item.get("id") or f"sample_{source.id}_{index}",
                        "name": item.get("name", "示例"),
                        "stdout": item.get("stdout", ""),
                        "inputValues": {},
                    }
                    for index, item in enumerate(document.get("samples", []), start=1)
                ],
            },
            "inputs": inputs,
            "outputs": outputs,
            "sourceSystemCommandId": source_id,
        }
    )


def _comparable(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result.pop("revision", None)
    return result


def _workflow_schema(value: Any, *, fallback_title: str = "") -> dict[str, Any]:
    """Adapt standard JSON Schema fragments to the strict Workflow schema shape."""
    source = dict(value) if isinstance(value, Mapping) else {"x-skillhub-legacy-loose": True}
    result = {
        "title": str(source.get("title") or fallback_title),
        "description": str(source.get("description", "")),
    }
    schema_type = source.get("type")
    if schema_type == "object":
        properties = source.get("properties")
        if not isinstance(properties, Mapping):
            raise InvariantError("Object output schema requires properties.")
        additional_properties = bool(source.get("additionalProperties", False))
        result.update(
            {
                "type": "object",
                "properties": {
                    str(name): _workflow_schema(child, fallback_title=str(name))
                    for name, child in properties.items()
                },
                "required": [str(name) for name in source.get("required", [])],
                "additionalProperties": additional_properties,
            }
        )
        if additional_properties:
            result["x-skillhub-legacy-loose"] = True
        return result
    if schema_type == "array":
        if "items" not in source:
            raise InvariantError("Array output schema requires items.")
        result.update({"type": "array", "items": _workflow_schema(source["items"], fallback_title=fallback_title)})
        return result
    if schema_type in {"string", "integer", "number", "boolean"}:
        result["type"] = schema_type
        return result
    result["x-skillhub-legacy-loose"] = True
    return result


def _required_text(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise InvariantError(f"Command {field} cannot be blank.")
    return text


def _is_integrity_error(exc: Exception) -> bool:
    return exc.__class__.__name__ == "IntegrityError" or "unique" in str(exc).lower()


__all__ = ["CommandLibraryStoreMixin"]
