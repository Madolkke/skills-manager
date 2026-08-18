"""Add system and user command-library entries.

Revision ID: 0007_command_library
Revises: 0006_workflow_log_debug_merge
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from skillhub.models.rules.command_expression import capture_catalog, parse_command_expression

revision = "0007_command_library"
down_revision = "0006_workflow_log_debug_merge"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def _jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "system_command_library_entries",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("normalized_expression", sa.Text(), nullable=False),
        sa.Column("captures", jsonb, server_default=_jsonb_default(), nullable=False),
        sa.Column("metadata", jsonb, server_default=_jsonb_default(), nullable=False),
        sa.Column("document", jsonb, server_default=_jsonb_default(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(trim(key)) > 0", name="system_command_library_entries_key_nonempty"),
        sa.CheckConstraint("length(trim(name)) > 0", name="system_command_library_entries_name_nonempty"),
        sa.CheckConstraint("length(trim(expression)) > 0", name="system_command_library_entries_expression_nonempty"),
        sa.CheckConstraint("length(trim(normalized_expression)) > 0", name="system_command_library_entries_normalized_expression_nonempty"),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="system_command_library_entries_metadata_object"),
        sa.CheckConstraint("jsonb_typeof(captures) = 'object'", name="system_command_library_entries_captures_object"),
        sa.CheckConstraint("jsonb_typeof(document) = 'object'", name="system_command_library_entries_document_object"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="system_command_library_entries_key_unique"),
        sa.UniqueConstraint("normalized_expression", name="system_command_library_entries_normalized_expression_unique"),
    )
    op.create_index(
        "system_command_library_entries_enabled_key_idx",
        "system_command_library_entries",
        ["enabled", "key"],
    )
    op.create_index(
        "system_command_library_entries_expression_idx",
        "system_command_library_entries",
        ["normalized_expression"],
    )

    op.create_table(
        "user_command_library_entries",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("owner_ref", sa.Text(), nullable=False),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("collection_id", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("normalized_expression", sa.Text(), nullable=False),
        sa.Column("captures", jsonb, server_default=_jsonb_default(), nullable=False),
        sa.Column("metadata", jsonb, server_default=_jsonb_default(), nullable=False),
        sa.Column("document", jsonb, server_default=_jsonb_default(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source_system_command_id", sa.Text(), nullable=True),
        sa.Column("collection_definition_id", sa.Text(), nullable=True),
        sa.Column("collection_revision", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(trim(owner_ref)) > 0", name="user_command_library_entries_owner_nonempty"),
        sa.CheckConstraint("length(trim(key)) > 0", name="user_command_library_entries_key_nonempty"),
        sa.CheckConstraint("length(trim(name)) > 0", name="user_command_library_entries_name_nonempty"),
        sa.CheckConstraint("length(trim(expression)) > 0", name="user_command_library_entries_expression_nonempty"),
        sa.CheckConstraint("length(trim(normalized_expression)) > 0", name="user_command_library_entries_normalized_expression_nonempty"),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="user_command_library_entries_metadata_object"),
        sa.CheckConstraint("jsonb_typeof(captures) = 'object'", name="user_command_library_entries_captures_object"),
        sa.CheckConstraint("jsonb_typeof(document) = 'object'", name="user_command_library_entries_document_object"),
        sa.ForeignKeyConstraint(
            ["source_system_command_id"],
            ["system_command_library_entries.id"],
            name="user_command_library_entries_source_system_command_fk",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name="user_command_library_entries_workflow_fk",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "collection_id", name="user_command_library_entries_workflow_collection_unique"),
    )
    op.create_index(
        "user_command_library_entries_owner_enabled_idx",
        "user_command_library_entries",
        ["owner_ref", "enabled"],
    )
    op.create_index(
        "user_command_library_entries_source_idx",
        "user_command_library_entries",
        ["source_system_command_id"],
    )

    op.add_column(
        "workflow_collection_definitions",
        sa.Column("source_system_command_id", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "workflow_collection_definitions_source_system_command_fk",
        "workflow_collection_definitions",
        "system_command_library_entries",
        ["source_system_command_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "workflow_collection_definitions_source_system_command_idx",
        "workflow_collection_definitions",
        ["source_system_command_id"],
    )
    _migrate_legacy_cli_collections(op.get_bind())


def downgrade() -> None:
    raise RuntimeError(
        "The command-library migration is irreversible because it removes orphan legacy CLI Collections."
    )


def _migrate_legacy_cli_collections(connection) -> None:
    """Project referenced CLI snapshots and remove valid orphan entries."""
    workflows = sa.table(
        "workflows",
        sa.column("id", sa.Text()),
        sa.column("created_by", sa.Text()),
        sa.column("document", postgresql.JSONB()),
    )
    collections = sa.table(
        "workflow_collection_definitions",
        sa.column("id", sa.Text()),
        sa.column("latest_revision", sa.Integer()),
    )
    revisions = sa.table(
        "workflow_collection_revisions",
        sa.column("definition_id", sa.Text()),
        sa.column("revision", sa.Integer()),
        sa.column("definition", postgresql.JSONB()),
    )
    user_entries = sa.table(
        "user_command_library_entries",
        sa.column("id", sa.Text()),
        sa.column("owner_ref", sa.Text()),
        sa.column("workflow_id", sa.Text()),
        sa.column("collection_id", sa.Text()),
        sa.column("key", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("expression", sa.Text()),
        sa.column("normalized_expression", sa.Text()),
        sa.column("captures", postgresql.JSONB()),
        sa.column("metadata", postgresql.JSONB()),
        sa.column("document", postgresql.JSONB()),
        sa.column("enabled", sa.Boolean()),
        sa.column("collection_definition_id", sa.Text()),
        sa.column("collection_revision", sa.Integer()),
        sa.column("created_by", sa.Text()),
        sa.column("updated_by", sa.Text()),
    )

    workflow_rows = connection.execute(sa.select(workflows)).mappings().all()
    referenced_ids: set[str] = set()
    migrated = 0
    invalid = 0
    migrated_keys: set[tuple[str, str]] = set()
    for workflow in workflow_rows:
        document = workflow.get("document") or {}
        if not isinstance(document, Mapping):
            continue
        workflow_body = document.get("workflow")
        if not isinstance(workflow_body, Mapping):
            logger.warning(
                "command-library migration skipped malformed workflow document workflow=%s: workflow is not an object",
                workflow.get("id"),
            )
            continue
        nodes = workflow_body.get("nodes")
        if not isinstance(nodes, list):
            logger.warning(
                "command-library migration skipped malformed workflow nodes workflow=%s",
                workflow.get("id"),
            )
            nodes = []
        call_revisions: dict[str, int] = {}
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            calls = node.get("collectionCalls", [])
            if not isinstance(calls, list):
                continue
            for call in calls:
                if not isinstance(call, Mapping):
                    continue
                reference = call.get("definition", {})
                if isinstance(reference, Mapping) and reference.get("id"):
                    collection_id = str(reference["id"])
                    referenced_ids.add(collection_id)
                    revision = _safe_int(reference.get("revision"), 0)
                    call_revisions[collection_id] = max(call_revisions.get(collection_id, 0), revision)
        snapshots = [
            item
            for item in (document.get("collectionSnapshots", []) if isinstance(document.get("collectionSnapshots", []), list) else [])
            if isinstance(item, Mapping) and item.get("id")
        ]
        snapshots.sort(key=lambda item: _safe_int(item.get("revision"), 0), reverse=True)
        for snapshot in snapshots:
            if not isinstance(snapshot, Mapping) or not snapshot.get("id"):
                continue
            collection_id = str(snapshot["id"])
            preferred_revision = call_revisions.get(collection_id)
            if preferred_revision and _safe_int(snapshot.get("revision"), 0) != preferred_revision:
                continue
            referenced_ids.add(collection_id)
            spec = snapshot.get("spec") or {}
            if not isinstance(spec, Mapping):
                invalid += 1
                logger.warning(
                    "command-library migration retained malformed CLI collection=%s workflow=%s: spec is not an object",
                    collection_id,
                    workflow.get("id"),
                )
                continue
            if spec.get("collectionType", spec.get("collection_type")) != "cli":
                continue
            expression = str(spec.get("commandTemplate", spec.get("command_template", ""))).strip()
            migration_key = (str(workflow["id"]), collection_id)
            if migration_key in migrated_keys:
                continue
            try:
                parsed = parse_command_expression(expression)
            except Exception as exc:
                invalid += 1
                logger.warning(
                    "command-library migration retained invalid CLI collection=%s workflow=%s: %s",
                    collection_id,
                    workflow["id"],
                    exc,
                )
                continue
            raw_metadata = snapshot.get("metadata") or {}
            metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
            raw_outputs = snapshot.get("outputs") or []
            outputs = [item for item in raw_outputs if isinstance(item, Mapping)] if isinstance(raw_outputs, list) else []
            output_schema = _output_schema(outputs)
            key = str(snapshot.get("key") or metadata.get("name") or f"legacy-{collection_id}")[:160]
            name = str(metadata.get("name") or key)
            owner_ref = str(workflow.get("created_by") or "system:migration")
            row_id = "migration-user-command-" + hashlib.sha256(
                f"{workflow['id']}:{collection_id}".encode()
            ).hexdigest()[:32]
            document_value = {
                "metadata": metadata,
                "samples": [
                    {**dict(sample), "command": sample.get("command") or expression}
                    for sample in (spec.get("outputSamples") or [])
                    if isinstance(sample, Mapping)
                ],
                "outputSchema": output_schema,
                "ttp": "",
            }
            connection.execute(
                sa.insert(user_entries).values(
                    id=row_id,
                    owner_ref=owner_ref,
                    workflow_id=str(workflow["id"]),
                    collection_id=collection_id,
                    key=key,
                    name=name,
                    description=str(metadata.get("description") or ""),
                    expression=expression,
                    normalized_expression=parsed.normalized,
                    captures=capture_catalog(parsed.root),
                    metadata=metadata,
                    document=document_value,
                    enabled=True,
                    collection_definition_id=collection_id,
                    collection_revision=_safe_int(snapshot.get("revision"), 1),
                    created_by=owner_ref,
                    updated_by=owner_ref,
                )
            )
            migrated_keys.add(migration_key)
            migrated += 1

    orphan_candidates: list[str] = []
    latest_rows = connection.execute(
        sa.select(collections.c.id, collections.c.latest_revision).order_by(collections.c.id)
    ).mappings().all()
    for collection in latest_rows:
        collection_id = str(collection["id"])
        if collection_id in referenced_ids:
            continue
        latest = connection.execute(
            sa.select(revisions.c.definition).where(
                revisions.c.definition_id == collection_id,
                revisions.c.revision == _safe_int(collection["latest_revision"], 1),
            )
        ).scalar_one_or_none()
        spec = (latest or {}).get("spec", {}) if isinstance(latest, Mapping) else {}
        if not isinstance(spec, Mapping):
            invalid += 1
            logger.warning("command-library migration retained malformed orphan collection=%s: spec is not an object", collection_id)
            continue
        if spec.get("collectionType", spec.get("collection_type")) != "cli":
            continue
        try:
            parse_command_expression(str(spec.get("commandTemplate", spec.get("command_template", ""))))
        except Exception as exc:
            invalid += 1
            logger.warning("command-library migration retained invalid orphan CLI collection=%s: %s", collection_id, exc)
            continue
        orphan_candidates.append(collection_id)

    # This migration intentionally removes data.  Emit the complete candidate
    # set before the first DELETE so deployment logs can be reviewed while the
    # transaction is still reversible on failure.
    logger.warning(
        "command-library migration orphan CLI deletion candidates count=%s ids=%s referenced_count=%s",
        len(orphan_candidates),
        orphan_candidates,
        len(referenced_ids),
    )
    orphaned = 0
    for collection_id in orphan_candidates:
        if collection_id in referenced_ids:
            logger.error("command-library migration refused to delete referenced CLI collection=%s", collection_id)
            continue
        connection.execute(revisions.delete().where(revisions.c.definition_id == collection_id))
        connection.execute(collections.delete().where(collections.c.id == collection_id))
        orphaned += 1
    logger.info("command-library migration migrated=%s invalid=%s orphaned_deleted=%s", migrated, invalid, orphaned)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _output_schema(outputs: list[Mapping[str, object]]) -> dict[str, object]:
    properties: dict[str, object] = {}
    required: list[str] = []
    for output in outputs:
        key = str(output.get("key") or "").strip()
        if not key:
            continue
        schema = output.get("schema") or {"type": "string"}
        properties[key] = schema
        # v3 outputs did not carry a required flag.  Their migrated schema is
        # marked legacy-loose, so retain the historical "present in output"
        # semantics instead of silently making every legacy field optional.
        if output.get("required", True) or (
            isinstance(schema, Mapping) and schema.get("x-skillhub-legacy-loose") is True
        ):
            required.append(key)
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}
