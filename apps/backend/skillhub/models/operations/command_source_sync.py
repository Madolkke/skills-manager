from copy import deepcopy

from sqlalchemy import insert, select, update

from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.rules.workflows.source_compatibility import _validate_source_compatibility
from skillhub.models.rules.workflows.source_diagnostics import validate_source_diagnostics
from skillhub.models.schema import orm


def sync_system_sources(store, connection, *, document, actor, created_at):
    """先投影全部来源，再验证候选文档，最后统一写入版本。"""
    from skillhub.models.rules.workflows.command_instances import project_instance_source

    from .command_library import _comparable

    candidate = deepcopy(document)
    snapshots = {(item["id"], int(item["revision"])): item for item in candidate.get("collectionSnapshots", [])}
    mappings = {}
    revisions = {}
    pairs = {}
    calls = [call for node in candidate.get("workflow", {}).get("nodes", []) for call in node.get("collectionCalls", [])]
    original_calls = deepcopy(calls)
    checked = set()
    for call in calls:
        ref = call.get("definition", {})
        identity = (ref.get("id"), int(ref.get("revision", 0)))
        if identity in checked:
            continue
        checked.add(identity)
        definition_id = identity[0]
        if definition_id not in revisions:
            row = connection.execute(
                orm.select_entity(orm.WorkflowCollectionDefinition).where(orm.WorkflowCollectionDefinition.id == definition_id)
            ).mappings().one_or_none()
            source_id = row.get("source_system_command_id") if row else None
            if not source_id:
                revisions[definition_id] = None
                continue
            source = connection.execute(
                select(orm.SystemCommandLibraryEntry).where(orm.SystemCommandLibraryEntry.id == source_id)
            ).scalar_one_or_none()
            if source is None:
                raise NotFoundError(f"System command does not exist: {source_id}")
            current = snapshots.get(identity) or store._collection_revision(connection, definition_id, identity[1])
            desired = project_instance_source(source, current, revision=int(row["latest_revision"]) + 1)
            revisions[definition_id] = desired
        desired = revisions[definition_id]
        current = snapshots.get(identity)
        if desired is None or (current is not None and _comparable(current) == _comparable(desired)):
            continue
        pairs[identity] = (current, desired)
        mappings[identity] = (definition_id, desired["revision"])
        snapshots[identity] = desired

    if not mappings:
        return {}
    for call in calls:
        ref = call.get("definition", {})
        identity = (ref.get("id"), int(ref.get("revision", 0)))
        if identity in mappings:
            definition_id, revision = mappings[identity]
            call["definition"] = {"id": definition_id, "revision": revision}
    candidate["collectionSnapshots"] = list({(value["id"], value["revision"]): value for value in snapshots.values()}.values())
    for original, call in zip(original_calls, calls, strict=True):
        ref = original.get("definition", {})
        pair = pairs.get((ref.get("id"), int(ref.get("revision", 0))))
        if pair is not None:
            current, desired = pair
            try:
                _validate_source_compatibility(document=candidate, source_call=call, current=current, desired=desired)
            except InvariantError as candidate_error:
                if current is None:
                    raise
                try:
                    _validate_source_compatibility(document=document, source_call=original, current=current, desired=current)
                except InvariantError as original_error:
                    if str(original_error) == str(candidate_error):
                        continue
                raise candidate_error
    validate_source_diagnostics(document, candidate)

    for definition_id in dict.fromkeys(identity[0] for identity in mappings):
        desired = revisions[definition_id]
        connection.execute(
            update(orm.WorkflowCollectionDefinition).where(orm.WorkflowCollectionDefinition.id == definition_id)
            .values(latest_revision=desired["revision"], updated_at=created_at)
        )
        connection.execute(insert(orm.WorkflowCollectionRevision).values(
            definition_id=definition_id, revision=desired["revision"], document_schema_version=5,
            definition=desired, definition_digest=store._document_digest(desired), created_at=created_at, created_by=actor,
        ))
    document.update(candidate)
    return mappings
