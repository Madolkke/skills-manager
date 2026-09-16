"""Collection 修改的只读计划与事务内落库。"""

from typing import Any

from sqlalchemy import insert, select, update

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, normalize_collection_definition
from skillhub.models.schema import orm


def plan_collection_changes(store, connection, changes: list[dict[str, Any]]) -> dict[str, Any]:
    """验证修改并分配候选版本，不写入定义或审计。"""
    mappings, records, definitions, applied, normalized = {}, {}, {}, [], []
    for change in changes:
        operation = change["operation"]
        definition = normalize_collection_definition(change["definition"])
        source_id = change.get("source_system_command_id") or definition.get("sourceSystemCommandId")
        if source_id:
            definition["sourceSystemCommandId"] = source_id
        definition_id = definition["id"].strip()
        requested_revision = int(definition["revision"])
        if not definition_id or definition_id in records:
            raise InvariantError("Collection changes require unique non-empty IDs.")
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
                source_identity = (source["id"], source["revision"])
                if source_identity not in definitions:
                    store._collection_revision(connection, *source_identity)
            elif definition.get("forkedFrom"):
                raise InvariantError("New Collection cannot set forkedFrom without fork operation.")
            if source_id:
                if definition.get("spec", {}).get("collectionType") != "cli":
                    raise InvariantError("Only CLI Collections can reference a system command.")
                source = connection.execute(select(orm.SystemCommand).where(orm.SystemCommand.id == source_id)).scalar_one_or_none()
                if source is None:
                    raise InvariantError(f"System command does not exist: {source_id}")
                if definition.get("sourceBindingMode") == "concrete-command":
                    from skillhub.models.rules.workflows.command_instances import project_instance_source

                    if not source.enabled and operation == "create":
                        raise InvariantError("系统命令已停用，不能创建新实例。")
                    definition = project_instance_source(source, definition, revision=1)
            revision = 1
        elif operation == "revise":
            if existing is None:
                raise InvariantError(f"Collection does not exist: {definition_id}")
            if existing["source_system_command_id"]:
                raise InvariantError("System source Collections are read-only and cannot be revised directly.")
            if source_id:
                raise InvariantError("A user Collection cannot be converted into a system-source Collection.")
            revision = int(existing["latest_revision"]) + 1
        else:
            raise InvariantError(f"Unsupported Collection operation: {operation}")
        normalized.append({"operation": operation, "definition": dict(definition), "source_system_command_id": source_id})
        definition["revision"] = revision
        records[definition_id] = {"latest_revision": revision, "source_system_command_id": source_id}
        definitions[(definition_id, revision)] = definition
        mappings[(definition_id, requested_revision)] = (definition_id, revision)
        applied.append({"operation": operation, "definition_id": definition_id, "revision": revision, "source_system_command_id": source_id})
    return {"mappings": mappings, "records": records, "definitions": definitions, "applied": applied, "changes": normalized}


def persist_collection_plan(store, connection, plan: dict[str, Any], *, actor: str, created_at) -> None:
    """在调用者事务中写入已完整校验的 Collection 计划。"""
    for item in plan["applied"]:
        definition_id, revision = item["definition_id"], item["revision"]
        if item["operation"] in {"create", "fork"}:
            connection.execute(insert(orm.WorkflowCollectionDefinition).values(
                id=definition_id, latest_revision=revision, created_at=created_at, updated_at=created_at,
                created_by=actor, source_system_command_id=item["source_system_command_id"],
            ))
        else:
            connection.execute(update(orm.WorkflowCollectionDefinition).where(orm.WorkflowCollectionDefinition.id == definition_id)
                               .values(latest_revision=revision, updated_at=created_at))
        definition = plan["definitions"][(definition_id, revision)]
        connection.execute(insert(orm.WorkflowCollectionRevision).values(
            definition_id=definition_id, revision=revision, document_schema_version=DOCUMENT_SCHEMA_VERSION,
            definition=definition, definition_digest=store._document_digest(definition), created_at=created_at, created_by=actor,
        ))


def canonicalize_planned_snapshots(store, connection, document, plan):
    """只从存储或本批已验证的定义构造快照，忽略客户端伪造内容。"""
    refs = []
    for node in document["workflow"]["nodes"]:
        for call in node.get("collectionCalls", []):
            reference = call["definition"]
            identity = (reference["id"], int(reference["revision"]))
            resolved = plan["mappings"].get(identity, identity)
            call["definition"] = {"id": resolved[0], "revision": resolved[1]}
            if resolved not in refs:
                refs.append(resolved)
    document["collectionSnapshots"] = [
        plan["definitions"][identity] if identity in plan["definitions"]
        else store._collection_revision(connection, *identity)
        for identity in refs
    ]
    return document
