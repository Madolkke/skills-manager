from __future__ import annotations

from copy import deepcopy

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import (
    export_workflow_import_bundle,
    normalize_workflow_import_bundle,
    validate_workflow_import_references,
)


def test_export_builds_deterministic_portable_collection_references() -> None:
    document = workflow_document()
    repeated = deepcopy(document["workflow"]["nodes"][0]["collectionCalls"][0])
    repeated["id"] = "call-2"
    document["workflow"]["nodes"][0]["collectionCalls"].append(repeated)

    first = export_workflow_import_bundle(document).model_dump(by_alias=True)
    second = export_workflow_import_bundle(document).model_dump(by_alias=True)

    assert first == second
    assert [item["localId"] for item in first["collections"]] == ["collection_1"]
    assert [item["definitionLocalId"] for item in first["workflow"]["nodes"][0]["collectionCalls"]] == [
        "collection_1",
        "collection_1",
    ]
    assert "id" not in first["workflow"]
    assert "revision" not in first["workflow"]
    assert "id" not in first["collections"][0]
    assert "revision" not in first["collections"][0]
    validate_workflow_import_references(normalize_workflow_import_bundle(first))


def test_export_ignores_unreferenced_snapshots_and_supports_empty_workflow() -> None:
    document = workflow_document()
    unreferenced = deepcopy(document["collectionSnapshots"][0])
    unreferenced["id"] = "collection-unused"
    unreferenced["key"] = "unused"
    document["collectionSnapshots"].append(unreferenced)

    exported = export_workflow_import_bundle(document).model_dump(by_alias=True)
    assert [item["key"] for item in exported["collections"]] == ["interface_status"]

    document["workflow"]["nodes"] = []
    empty = export_workflow_import_bundle(document).model_dump(by_alias=True)
    assert empty["collections"] == []


def test_export_rejects_missing_and_ambiguous_snapshots() -> None:
    missing = workflow_document()
    missing["collectionSnapshots"] = []
    with pytest.raises(InvariantError, match="does not exist"):
        export_workflow_import_bundle(missing)

    ambiguous = workflow_document()
    ambiguous["collectionSnapshots"].append(deepcopy(ambiguous["collectionSnapshots"][0]))
    with pytest.raises(InvariantError, match="ambiguous"):
        export_workflow_import_bundle(ambiguous)


def workflow_document() -> dict:
    definition = {
        "id": "collection-interface",
        "revision": 3,
        "key": "interface_status",
        "metadata": {
            "name": "接口状态",
            "description": "采集接口状态。",
            "industry": "网络",
            "device": "交换机",
            "versions": [],
            "tags": [],
        },
        "spec": {"collectionType": "cli", "commandTemplate": "display interface", "outputSamples": []},
        "inputs": [],
        "outputs": [],
        "forkedFrom": {"id": "collection-origin", "revision": 1},
    }
    return {
        "documentType": "workflow_bundle",
        "workflow": {
            "id": "workflow-1",
            "revision": 8,
            "metadata": {
                "name": "接口排查",
                "code": "IFACE",
                "description": "检查接口状态。",
                "symptom": "",
                "industry": "网络",
                "device": "交换机",
                "versions": [],
            },
            "inputs": [],
            "deviceRoles": [],
            "nodes": [
                {
                    "id": "step-1",
                    "name": "采集接口",
                    "description": "",
                    "isStart": True,
                    "collectionCalls": [
                        {
                            "id": "call-1",
                            "key": "interface_status",
                            "name": "接口状态",
                            "definition": {"id": definition["id"], "revision": definition["revision"]},
                            "sampleCount": 1,
                            "inputBindings": {},
                        }
                    ],
                    "topology": [],
                    "stepType": "expression",
                }
            ],
        },
        "collectionSnapshots": [definition],
    }
