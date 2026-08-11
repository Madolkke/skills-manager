from __future__ import annotations

from copy import deepcopy
from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.import_schema import WorkflowImportBundle
from skillhub.models.rules.workflows.schema import normalize_workflow_document


def export_workflow_import_bundle(document: dict[str, Any]) -> WorkflowImportBundle:
    """Build a portable import bundle from one saved Workflow document."""
    normalized = normalize_workflow_document(document)
    workflow = deepcopy(normalized["workflow"])
    workflow.pop("id", None)
    workflow.pop("revision", None)

    snapshots = _snapshot_map(normalized["collectionSnapshots"])
    local_ids: dict[tuple[str, int], str] = {}
    collections: list[dict[str, Any]] = []

    for node in workflow["nodes"]:
        if "stepType" not in node:
            continue
        for call in node["collectionCalls"]:
            reference = call.pop("definition")
            identity = (reference["id"], int(reference["revision"]))
            local_id = local_ids.get(identity)
            if local_id is None:
                definition = snapshots.get(identity)
                if definition is None:
                    raise InvariantError(
                        f"Workflow export Collection does not exist: {identity[0]}@{identity[1]}"
                    )
                local_id = f"collection_{len(local_ids) + 1}"
                local_ids[identity] = local_id
                collections.append(_portable_collection(definition, local_id=local_id))
            call["definitionLocalId"] = local_id

    return WorkflowImportBundle.model_validate(
        {
            "documentType": "workflow_import_bundle",
            "workflow": workflow,
            "collections": collections,
        }
    )


def _snapshot_map(definitions: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for definition in definitions:
        identity = (definition["id"], int(definition["revision"]))
        if identity in result:
            raise InvariantError(
                f"Workflow export Collection reference is ambiguous: {identity[0]}@{identity[1]}"
            )
        result[identity] = definition
    return result


def _portable_collection(definition: dict[str, Any], *, local_id: str) -> dict[str, Any]:
    result = deepcopy(definition)
    result.pop("id", None)
    result.pop("revision", None)
    result.pop("forkedFrom", None)
    result["localId"] = local_id
    return result
