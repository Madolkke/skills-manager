from __future__ import annotations

import json
from typing import Any

from skillhub.models.entities import digest_text
from skillhub.models.rules.workflows import DOCUMENT_SCHEMA_VERSION, validate_workflow_document


def workflow_agent_draft_digest(document: dict[str, Any]) -> str:
    return digest_text(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def build_workflow_agent_context(
    document: dict[str, Any],
    *,
    selection: dict[str, Any],
    existing_cases: list[dict[str, Any]],
    recent_history: list[dict[str, str]],
) -> dict[str, Any]:
    workflow = document["workflow"]
    selected_step = _selected_step(workflow["nodes"], selection)
    relevant_definitions = _relevant_definitions(document["collectionSnapshots"], selected_step, selection)
    return {
        "documentSchemaVersion": DOCUMENT_SCHEMA_VERSION,
        "workflow": {
            "id": workflow["id"],
            "metadata": workflow["metadata"],
            "inputs": workflow["inputs"],
            "deviceRoles": workflow["deviceRoles"],
            "nodes": [_node_summary(node) for node in workflow["nodes"]],
        },
        "selection": selection,
        "selectedStep": selected_step,
        "collectionSnapshots": relevant_definitions,
        "collectionSnapshotScope": {
            "selectedStepId": selected_step["id"] if selected_step is not None else None,
            "included": len(relevant_definitions),
            "documentTotal": len(document["collectionSnapshots"]),
            "note": "collectionSnapshots only contains definitions relevant to the current selection.",
        },
        "validationIssues": validate_workflow_document(document),
        "existingDebugCases": existing_cases,
        "recentConversation": recent_history,
        "rawSamplesIncluded": True,
    }


def _selected_step(nodes: list[dict[str, Any]], selection: dict[str, Any]) -> dict[str, Any] | None:
    if selection.get("type") != "step" or not selection.get("id"):
        return None
    return next((node for node in nodes if "stepType" in node and node.get("id") == selection["id"]), None)


def _relevant_definitions(
    definitions: list[dict[str, Any]],
    step: dict[str, Any] | None,
    selection: dict[str, Any],
) -> list[dict[str, Any]]:
    references: set[tuple[str, int]] = set()
    if step is not None:
        references.update((call["definition"]["id"], call["definition"]["revision"]) for call in step["collectionCalls"])
    if selection.get("type") == "collection" and selection.get("id") and selection.get("revision"):
        references.add((str(selection["id"]), int(selection["revision"])))
    return [definition for definition in definitions if (definition["id"], definition["revision"]) in references]


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    node_type = "step" if "stepType" in node else str(node.get("nodeType") or "conclusion")
    summary = {"id": node["id"], "type": node_type, "name": node["name"]}
    if node_type == "step":
        summary["isStart"] = node["isStart"]
        summary["collectionCalls"] = [
            {
                "id": call["id"],
                "key": call["key"],
                "definition": call["definition"],
                "sampleCount": call["sampleCount"],
            }
            for call in node["collectionCalls"]
        ]
        summary["transitions"] = [
            {
                "id": transition["id"],
                "target": transition["target"],
                "conditionText": transition["conditionText"],
                "conditionExpression": transition["conditionExpression"],
            }
            for transition in node["topology"]
        ]
    return summary


__all__ = ["build_workflow_agent_context", "workflow_agent_draft_digest"]
