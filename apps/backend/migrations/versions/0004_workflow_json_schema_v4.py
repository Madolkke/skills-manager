"""Upgrade current Workflow and Collection documents to JSON Schema v4.

Revision ID: 0004_workflow_json_schema_v4
Revises: 0003_workflow_skill_generators
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_workflow_json_schema_v4"
down_revision = "0003_workflow_skill_generators"
branch_labels = None
depends_on = None

MIGRATION_ACTOR = "system:migration:workflow-json-schema-v4"

collections = sa.table(
    "workflow_collection_definitions",
    sa.column("id", sa.Text()),
    sa.column("latest_revision", sa.Integer()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
collection_revisions = sa.table(
    "workflow_collection_revisions",
    sa.column("definition_id", sa.Text()),
    sa.column("revision", sa.Integer()),
    sa.column("document_schema_version", sa.Integer()),
    sa.column("definition", postgresql.JSONB()),
    sa.column("definition_digest", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("created_by", sa.Text()),
)
workflows = sa.table(
    "workflows",
    sa.column("id", sa.Text()),
    sa.column("revision", sa.Integer()),
    sa.column("document_schema_version", sa.Integer()),
    sa.column("document", postgresql.JSONB()),
    sa.column("document_digest", sa.Text()),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("last_saved_by", sa.Text()),
)


def upgrade() -> None:
    connection = op.get_bind()
    workflow_rows = connection.execute(sa.select(workflows)).mappings().all()
    catalog_rows = connection.execute(sa.select(collections)).mappings().all()
    requested = _requested_collection_revisions(workflow_rows, catalog_rows)
    mappings, migrated_definitions = _migrate_collection_revisions(connection, requested, catalog_rows)

    for row in workflow_rows:
        document = _migrate_workflow(row["document"], mappings, migrated_definitions)
        next_revision = int(row["revision"]) + 1
        document["workflow"]["revision"] = next_revision
        connection.execute(
            sa.update(workflows)
            .where(workflows.c.id == row["id"])
            .values(
                revision=next_revision,
                document_schema_version=4,
                document=document,
                document_digest=_digest(document),
                updated_at=sa.func.now(),
                last_saved_by=MIGRATION_ACTOR,
            )
        )

    op.alter_column("workflows", "document_schema_version", server_default=sa.text("4"), existing_type=sa.Integer(), nullable=False)
    op.alter_column("workflow_collection_revisions", "document_schema_version", server_default=sa.text("4"), existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    raise RuntimeError("Workflow JSON Schema v4 data migration is intentionally irreversible; restore from backup instead.")


def _requested_collection_revisions(workflow_rows, catalog_rows) -> dict[str, set[int]]:
    requested = {str(row["id"]): {int(row["latest_revision"])} for row in catalog_rows}
    for row in workflow_rows:
        for node in row["document"].get("workflow", {}).get("nodes", []):
            for call in node.get("collectionCalls", []):
                reference = call.get("definition", {})
                if reference.get("id") and reference.get("revision"):
                    requested.setdefault(str(reference["id"]), set()).add(int(reference["revision"]))
    return requested


def _migrate_collection_revisions(connection, requested, catalog_rows):
    mappings: dict[tuple[str, int], tuple[str, int]] = {}
    migrated: dict[tuple[str, int], dict[str, Any]] = {}
    latest_by_id = {str(row["id"]): int(row["latest_revision"]) for row in catalog_rows}
    for definition_id, revisions in sorted(requested.items()):
        next_revision = latest_by_id[definition_id]
        for old_revision in sorted(revisions):
            row = (
                connection.execute(
                    sa.select(collection_revisions).where(
                        (collection_revisions.c.definition_id == definition_id) & (collection_revisions.c.revision == old_revision)
                    )
                )
                .mappings()
                .one()
            )
            if int(row["document_schema_version"]) == 4:
                mappings[(definition_id, old_revision)] = (definition_id, old_revision)
                migrated[(definition_id, old_revision)] = copy.deepcopy(row["definition"])
                continue
            next_revision += 1
            definition = _migrate_collection(row["definition"])
            definition["revision"] = next_revision
            connection.execute(
                sa.insert(collection_revisions).values(
                    definition_id=definition_id,
                    revision=next_revision,
                    document_schema_version=4,
                    definition=definition,
                    definition_digest=_digest(definition),
                    created_at=sa.func.now(),
                    created_by=MIGRATION_ACTOR,
                )
            )
            mappings[(definition_id, old_revision)] = (definition_id, next_revision)
            migrated[(definition_id, next_revision)] = definition
        original_latest = latest_by_id[definition_id]
        resolved_latest = mappings.get((definition_id, original_latest), (definition_id, original_latest))[1]
        connection.execute(sa.update(collections).where(collections.c.id == definition_id).values(latest_revision=resolved_latest, updated_at=sa.func.now()))
    return mappings, migrated


def _migrate_workflow(value, mappings, definitions):
    document = copy.deepcopy(value)
    workflow = document["workflow"]
    workflow["inputs"] = [_migrate_parameter(item) for item in workflow.get("inputs", [])]
    references: list[tuple[str, int]] = []
    for node in workflow.get("nodes", []):
        for call in node.get("collectionCalls", []):
            old = (str(call["definition"]["id"]), int(call["definition"]["revision"]))
            resolved = mappings.get(old, old)
            call["definition"] = {"id": resolved[0], "revision": resolved[1]}
            if resolved not in references:
                references.append(resolved)
    document["collectionSnapshots"] = [copy.deepcopy(definitions[reference]) for reference in references]
    return document


def _migrate_collection(value):
    definition = copy.deepcopy(value)
    definition["inputs"] = [_migrate_parameter(item) for item in definition.get("inputs", [])]
    definition["outputs"] = [_migrate_output(item) for item in definition.get("outputs", [])]
    return definition


def _migrate_parameter(value):
    if "schema" in value:
        return copy.deepcopy(value)
    return {
        "id": value.get("id", ""),
        "key": value.get("key", ""),
        "required": bool(value.get("required", True)),
        "schema": _legacy_schema(value.get("dataType", "string"), value.get("name", ""), value.get("description", "")),
    }


def _migrate_output(value):
    if "schema" in value:
        return copy.deepcopy(value)
    return {
        "id": value.get("id", ""),
        "key": value.get("key", ""),
        "required": False,
        "schema": _legacy_schema(value.get("dataType", "string"), value.get("key", ""), value.get("description", "")),
    }


def _legacy_schema(data_type, title, description):
    schema = {
        "type": data_type if data_type in {"string", "integer", "number", "boolean", "array", "object"} else "string",
        "title": str(title),
        "description": str(description),
    }
    if schema["type"] == "array":
        schema.update({"items": {"x-skillhub-legacy-loose": True}, "x-skillhub-legacy-loose": True})
    elif schema["type"] == "object":
        schema.update({"properties": {}, "required": [], "additionalProperties": True, "x-skillhub-legacy-loose": True})
    return schema


def _digest(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
