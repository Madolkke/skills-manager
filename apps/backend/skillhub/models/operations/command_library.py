from __future__ import annotations

import ast
import logging
import re
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
from skillhub.models.rules.workflows.expression.environment import is_expression_identifier
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
        """在 Workflow 保存事务内把来源系统命令投影为新的执行层 revision。"""
        mappings: dict[tuple[str, int], tuple[str, int]] = {}
        # A definition can be called more than once (possibly from different
        # steps).  Cache the source pair so the revision is written once while
        # still validating every call's bindings and expression context.
        source_pairs: dict[
            tuple[str, int], tuple[Mapping[str, Any] | None, Mapping[str, Any]]
        ] = {}
        snapshots = {
            (item.get("id"), int(item.get("revision", 0))): item
            for item in document.get("collectionSnapshots", [])
            if isinstance(item, dict)
        }
        for node in document.get("workflow", {}).get("nodes", []):
            for call in node.get("collectionCalls", []):
                ref = call.get("definition", {})
                identity = (ref.get("id"), int(ref.get("revision", 0)))
                if identity in mappings:
                    current, desired = source_pairs[identity]
                    _validate_source_compatibility(
                        document=document,
                        source_call=call,
                        current=current,
                        desired=desired,
                    )
                    definition_id, revision = mappings[identity]
                    call["definition"] = {"id": definition_id, "revision": revision}
                    continue
                definition_row = connection.execute(
                    orm.select_entity(orm.WorkflowCollectionDefinition).where(
                        orm.WorkflowCollectionDefinition.id == identity[0]
                    )
                ).mappings().one_or_none()
                source_id = definition_row.get("source_system_command_id") if definition_row else None
                if not source_id:
                    continue
                if definition_row is None:
                    raise InvariantError(
                        f"System-source Collection definition does not exist: {identity[0]}"
                    )
                source = connection.execute(
                    select(orm.SystemCommandLibraryEntry).where(orm.SystemCommandLibraryEntry.id == source_id)
                ).scalar_one_or_none()
                if source is None:
                    raise NotFoundError(f"System command does not exist: {source_id}")
                desired = _source_to_collection(source, definition_id=identity[0], revision=int(definition_row["latest_revision"]), source_id=source_id)
                current = snapshots.get(identity)
                if current is not None and _comparable(current) == _comparable(desired):
                    continue
                # Project the desired definition into the in-memory snapshot
                # map before validating.  This makes scope and downstream
                # binding checks see the new definition for every call that
                # reuses this source, not only the first call encountered.
                snapshots[identity] = desired
                _validate_source_compatibility(
                    document=document,
                    source_call=call,
                    current=current,
                    desired=desired,
                )
                source_pairs[identity] = (current, desired)
                next_revision = int(definition_row["latest_revision"]) + 1
                desired["revision"] = next_revision
                # The first call is rewritten immediately.  Keep the
                # projected definition addressable by both the original
                # snapshot key and the new revision while later calls in the
                # same document are validated.
                snapshots[(identity[0], next_revision)] = desired
                connection.execute(
                    update(orm.WorkflowCollectionDefinition)
                    .where(orm.WorkflowCollectionDefinition.id == identity[0])
                    .values(latest_revision=next_revision, updated_at=created_at)
                )
                connection.execute(
                    insert(orm.WorkflowCollectionRevision).values(
                        definition_id=identity[0],
                        revision=next_revision,
                        document_schema_version=5,
                        definition=desired,
                        definition_digest=self._document_digest(desired),
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                mappings[identity] = (identity[0], next_revision)
                call["definition"] = {"id": identity[0], "revision": next_revision}
        return mappings

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


def _validate_source_compatibility(
    *,
    document: Mapping[str, Any],
    source_call: Mapping[str, Any],
    current: Mapping[str, Any] | None,
    desired: Mapping[str, Any],
) -> None:
    """Reject source updates that would leave existing bindings dangling."""
    desired_input_ids = {str(item.get("id")) for item in desired.get("inputs", []) if item.get("id")}
    bindings = source_call.get("inputBindings", {}) or {}
    invalid_inputs = sorted(set(bindings) - desired_input_ids)
    if invalid_inputs:
        raise InvariantError(f"系统命令同步会移除已绑定输入: {', '.join(invalid_inputs)}")
    missing_required = sorted(
        str(item["id"])
        for item in desired.get("inputs", [])
        if item.get("required", True) and item.get("id") not in bindings
    )
    if missing_required:
        raise InvariantError(f"系统命令同步新增了未绑定的必填输入: {', '.join(missing_required)}")

    workflow_inputs = {
        str(item.get("id")): item
        for item in (document.get("workflow", {}) or {}).get("inputs", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    snapshots = {
        (str(item.get("id")), int(item.get("revision", 0))): item
        for item in document.get("collectionSnapshots", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    calls_by_id = {
        str(call.get("id")): call
        for node in (document.get("workflow", {}) or {}).get("nodes", [])
        if isinstance(node, Mapping)
        for call in node.get("collectionCalls", [])
        if isinstance(call, Mapping) and call.get("id")
    }
    from skillhub.models.rules.workflows.device_bindings import resolve_device_role_field
    from skillhub.models.rules.workflows.expression import validate_expression
    from skillhub.models.rules.workflows.expression.environment import binding_expression_environment
    from skillhub.models.rules.workflows.expression.types import type_spec_assignable_to_schema, type_spec_from_serialized
    from skillhub.models.rules.workflows.json_schema import schemas_assignable, value_matches_schema

    for input_definition in desired.get("inputs", []):
        input_id = str(input_definition.get("id", ""))
        binding = bindings.get(input_id)
        if not isinstance(binding, Mapping):
            continue
        if input_definition.get("required", True) and binding.get("kind") == "literal" and binding.get("value") in (None, ""):
            raise InvariantError(f"系统命令同步会使必填输入“{input_id}”失去绑定值")
        source_schema: Mapping[str, Any] | None = None
        kind = binding.get("kind")
        reference = binding.get("reference") if isinstance(binding.get("reference"), Mapping) else {}
        if kind == "workflow_input":
            source = workflow_inputs.get(str(reference.get("input_id")))
            if source is None:
                raise InvariantError(f"系统命令同步发现无效的全局输入绑定: {input_id}")
            source_schema = source.get("schema")
        elif kind == "collection_output":
            bound_call = calls_by_id.get(str(reference.get("call_id")))
            source_definition = None
            if bound_call:
                source_ref = bound_call.get("definition", {})
                source_definition = snapshots.get((str(source_ref.get("id")), int(source_ref.get("revision", 0))))
            output_id = str(reference.get("output_id", ""))
            source_output = next(
                (item for item in (source_definition or {}).get("outputs", []) if item.get("id") == output_id),
                None,
            )
            if source_output is None:
                raise InvariantError(f"系统命令同步发现无效的前序输出绑定: {input_id}")
            source_schema = source_output.get("schema")
        elif kind == "device_role_field":
            resolution = resolve_device_role_field(
                (document.get("workflow", {}) or {}).get("deviceRoles", []),
                str(reference.get("role_id", "")),
                str(reference.get("path", "")),
            )
            if resolution.status != "ok" or resolution.schema is None:
                raise InvariantError(f"系统命令同步发现无效的设备角色字段绑定: {input_id}")
            source_schema = resolution.schema
        elif kind == "expression":
            expression = binding.get("expression")
            if not isinstance(expression, str) or not expression.strip():
                raise InvariantError(f"系统命令同步发现空表达式绑定: {input_id}")
            source_step = next(
                (node for node in (document.get("workflow", {}) or {}).get("nodes", [])
                 if isinstance(node, Mapping) and any(call.get("id") == source_call.get("id") for call in node.get("collectionCalls", []))),
                None,
            )
            if source_step is None:
                raise InvariantError(f"系统命令同步无法定位表达式绑定调用: {input_id}")
            input_environment = {
                str(item.get("key", "")).strip(): item.get("schema", {})
                for item in (document.get("workflow", {}) or {}).get("inputs", [])
                if str(item.get("key", "")).strip()
            }
            definitions = snapshots
            environment = binding_expression_environment(
                (document.get("workflow", {}) or {}).get("nodes", []),
                str(source_step.get("id")),
                str(source_call.get("id")),
                definitions,
                input_environment,
                (document.get("workflow", {}) or {}).get("deviceRoles", []),
            )
            result = validate_expression(expression, environment)
            if result["diagnostics"]:
                raise InvariantError(f"系统命令同步发现无效表达式绑定: {input_id}")
            if not type_spec_assignable_to_schema(type_spec_from_serialized(result["inferredType"]), input_definition.get("schema", {})):
                raise InvariantError(f"系统命令同步会使输入“{input_id}”的表达式结果与新 Schema 不兼容")
            continue
        elif kind == "literal":
            if binding.get("value") in (None, "") and not input_definition.get("required", True):
                continue
            if not value_matches_schema(binding.get("value"), input_definition.get("schema", {})):
                raise InvariantError(f"系统命令同步会使输入“{input_id}”的固定值与新 Schema 不兼容")
            continue
        else:
            raise InvariantError(f"系统命令同步发现未知输入绑定类型: {kind}")
        if not schemas_assignable(dict(source_schema or {}), dict(input_definition.get("schema", {}))):
            raise InvariantError(f"系统命令同步会使输入“{input_id}”的绑定 Schema 不兼容")

    desired_outputs = {
        str(item.get("id")): item
        for item in desired.get("outputs", [])
        if item.get("id")
    }
    all_calls = [
        call
        for node in (document.get("workflow", {}) or {}).get("nodes", [])
        if isinstance(node, Mapping)
        for call in node.get("collectionCalls", [])
        if isinstance(call, Mapping)
    ]
    source_call_id = source_call.get("id")
    for consumer in all_calls:
        for input_id, binding in (consumer.get("inputBindings", {}) or {}).items():
            reference = (binding or {}).get("reference", {})
            if (binding or {}).get("kind") != "collection_output" or reference.get("call_id") != source_call_id:
                continue
            output_id = str(reference.get("output_id", ""))
            output = desired_outputs.get(output_id)
            if output is None:
                raise InvariantError(f"系统命令同步会移除已绑定输出: {output_id}")
            consumer_ref = consumer.get("definition", {})
            consumer_definition = snapshots.get(
                (str(consumer_ref.get("id")), int(consumer_ref.get("revision", 0)))
            )
            target = next(
                (item for item in (consumer_definition or {}).get("inputs", []) if item.get("id") == input_id),
                None,
            )
            if target is None:
                continue
            from skillhub.models.rules.workflows.json_schema import schemas_assignable

            if not schemas_assignable(output.get("schema", {}), target.get("schema", {})):
                raise InvariantError(f"系统命令同步会使输出“{output_id}”与绑定输入不兼容。")

    _validate_source_output_scope(document=document, source_call=source_call, desired=desired, snapshots=snapshots)
    if current is not None:
        _validate_source_expression_references(
            document=document,
            source_call=source_call,
            current=current,
            desired=desired,
        )


def _validate_source_output_scope(
    *,
    document: Mapping[str, Any],
    source_call: Mapping[str, Any],
    desired: Mapping[str, Any],
    snapshots: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    """Keep direct output names unambiguous while a source is refreshed."""
    workflow = document.get("workflow") if isinstance(document.get("workflow"), Mapping) else {}
    reserved = {
        str(item.get("key", "")).strip()
        for item in workflow.get("inputs", [])
        if isinstance(item, Mapping) and str(item.get("key", "")).strip()
    }
    source_id = str(source_call.get("id", ""))
    source_step = next(
        (
            node
            for node in workflow.get("nodes", [])
            if isinstance(node, Mapping)
            and any(
                isinstance(call, Mapping) and str(call.get("id", "")) == source_id
                for call in node.get("collectionCalls", [])
            )
        ),
        None,
    )
    if source_step is None:
        return
    names: dict[str, str] = {}
    for call in source_step.get("collectionCalls", []):
        if not isinstance(call, Mapping):
            continue
        call_id = str(call.get("id", ""))
        if call_id == source_id:
            definition = desired
        else:
            reference = call.get("definition") if isinstance(call.get("definition"), Mapping) else {}
            definition = snapshots.get((str(reference.get("id", "")), int(reference.get("revision", 0))))
        if not isinstance(definition, Mapping) or str(call.get("key", "")).strip():
            continue
        for output in definition.get("outputs", []):
            if not isinstance(output, Mapping):
                continue
            key = str(output.get("key", "")).strip()
            if not is_expression_identifier(key):
                continue
            if key in reserved:
                raise InvariantError(f"系统命令同步会使直接输出“{key}”与 Workflow 全局输入冲突。")
            previous = names.get(key)
            if previous is not None and previous != call_id:
                raise InvariantError(f"系统命令同步会使直接输出“{key}”与同一步骤的其他采集冲突。")
            names[key] = call_id


_OUTPUT_PATH_RE = re.compile(
    r"\boutputs(?P<tail>(?:(?:\s*\.\s*[A-Za-z_]\w*)|(?:\s*\[\s*['\"][^'\"]+['\"]\s*\]))+)"
)


def _validate_source_expression_references(
    *,
    document: Mapping[str, Any],
    source_call: Mapping[str, Any],
    current: Mapping[str, Any],
    desired: Mapping[str, Any],
) -> None:
    """Reject source updates that invalidate condition/script output paths."""
    workflow = document.get("workflow") if isinstance(document.get("workflow"), Mapping) else {}
    source_id = str(source_call.get("id", ""))
    step = next(
        (
            node
            for node in workflow.get("nodes", [])
            if isinstance(node, Mapping)
            and any(
                isinstance(call, Mapping) and str(call.get("id", "")) == source_id
                for call in node.get("collectionCalls", [])
            )
        ),
        None,
    )
    if step is None:
        return
    call_key = str(source_call.get("key", "")).strip()
    old_outputs = {
        str(item.get("key", "")).strip(): item.get("schema", {})
        for item in current.get("outputs", [])
        if isinstance(item, Mapping) and str(item.get("key", "")).strip()
    }
    new_outputs = {
        str(item.get("key", "")).strip(): item.get("schema", {})
        for item in desired.get("outputs", [])
        if isinstance(item, Mapping) and str(item.get("key", "")).strip()
    }
    for text in _source_expression_texts(step):
        for path in _extract_output_paths(text):
            reference = _source_output_reference(path, call_key=call_key)
            if reference is None:
                continue
            output_key, nested = reference
            if output_key not in old_outputs:
                continue
            if output_key not in new_outputs:
                raise InvariantError(f"系统命令同步会移除表达式引用的输出“{output_key}”。")
            old_schema = _schema_at_path(old_outputs[output_key], nested)
            new_schema = _schema_at_path(new_outputs[output_key], nested)
            if old_schema is None or new_schema is None:
                raise InvariantError(f"系统命令同步会使表达式引用的输出路径失效: outputs.{output_key}")
            old_type = old_schema.get("type") if isinstance(old_schema, Mapping) else None
            new_type = new_schema.get("type") if isinstance(new_schema, Mapping) else None
            if old_type and new_type and old_type != new_type:
                raise InvariantError(f"系统命令同步会改变表达式引用输出“{output_key}”的类型。")


def _source_output_reference(
    path: tuple[str, ...],
    *,
    call_key: str,
) -> tuple[str, tuple[str, ...]] | None:
    """将 ``outputs`` AST 路径解码为当前 Call 的输出字段和子路径。

    Keyed 多次采集的数组索引在 AST 中统一表示为 ``*``，因此
    ``outputs.call[0].status`` 和 ``outputs.call[index].status`` 都映射到
    输出字段 ``status``，而不是把索引误识别为字段名。
    """
    if not path:
        return None
    if call_key:
        if path[0] != call_key or len(path) < 2:
            return None
        # ``outputs.<callKey>[index].<outputKey>...``
        if path[1] == "*":
            if len(path) < 3:
                return None
            return path[2], path[3:]
        # ``outputs.<callKey>.<outputKey>...``
        return path[1], path[2:]
    # Direct output: an index belongs to the output's own schema.
    return path[0], path[1:]


def _source_expression_texts(step: Mapping[str, Any]) -> list[str]:
    values = [
        str(item.get("conditionExpression", ""))
        for item in step.get("topology", [])
        if isinstance(item, Mapping) and str(item.get("conditionExpression", "")).strip()
    ]
    script = step.get("script")
    if isinstance(script, Mapping) and str(script.get("source", "")).strip():
        values.append(str(script["source"]))
    return values


def _extract_output_paths(text: str) -> set[tuple[str, ...]]:
    paths: set[tuple[str, ...]] = set()
    for mode in ("eval", "exec"):
        try:
            tree = ast.parse(text, mode=mode)
        except (SyntaxError, ValueError):
            continue
        method_attributes = {
            id(item.func)
            for item in ast.walk(tree)
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
        }
        for node in ast.walk(tree):
            # The attribute naming a method (for example ``lower`` in
            # ``outputs.status.lower()``) is not an output property.  The
            # receiver path is still visited separately and retained.
            if isinstance(node, ast.Attribute) and id(node) in method_attributes:
                continue
            path = _ast_output_path(node)
            if path:
                paths.add(path)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                receiver = _ast_output_path(node.func.value)
                if receiver is not None:
                    paths.add((*receiver, node.args[0].value))
    for match in _OUTPUT_PATH_RE.finditer(text):
        tail = match.group("tail")
        tail_start = match.start("tail")
        parts: list[str] = []
        segments = list(
            re.finditer(
                r"\.\s*([A-Za-z_]\w*)|\[\s*['\"]([^'\"]+)['\"]\s*\]",
                tail,
            )
        )
        for segment in segments:
            # In the non-Python fallback, stop at the first method call.  This
            # keeps ``outputs.status`` while excluding ``.lower`` and any
            # properties accessed on the method result.
            if re.match(r"\s*\(", text[tail_start + segment.end() :]):
                break
            parts.append(segment.group(1) or segment.group(2))
        if parts:
            paths.add(tuple(parts))
    return paths


def _ast_output_path(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return () if node.id == "outputs" else None
    if isinstance(node, ast.Attribute):
        parent = _ast_output_path(node.value)
        return None if parent is None else (*parent, node.attr)
    if isinstance(node, ast.Subscript):
        parent = _ast_output_path(node.value)
        if parent is None:
            return None
        value = node.slice
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return (*parent, value.value)
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            return (*parent, "*")
        # Negative indexes are represented as ``UnaryOp(USub, Constant)``;
        # dynamic indexes and slices have the same schema meaning as any
        # other array element and therefore use the wildcard component.
        if isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd)):
            return (*parent, "*")
        if isinstance(value, ast.Slice):
            return (*parent, "*")
        return (*parent, "*")
    return None


def _schema_at_path(schema: Any, path: tuple[str, ...]) -> Mapping[str, Any] | None:
    current = schema if isinstance(schema, Mapping) else None
    for component in path:
        if current is None:
            return None
        if current.get("type") == "array":
            current = current.get("items") if component == "*" else None
            continue
        if current.get("type") != "object":
            return None
        properties = current.get("properties")
        if isinstance(properties, Mapping) and component in properties:
            current = properties[component]
        elif current.get("additionalProperties") is True:
            return {"type": None}
        else:
            return None
    return current


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
