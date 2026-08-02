from __future__ import annotations

import json
from pathlib import Path

from skillhub.models.rules.executor_workflows import convert_workflow_document
from skillhub.models.rules.workflows import (
    materialize_workflow_import,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    validate_workflow_document,
    validate_workflow_import_references,
)


def test_executor_integration_example_is_importable_and_convertible() -> None:
    path = Path(__file__).parents[3] / "docs" / "examples" / "executor-integration-workflow-import.json"
    bundle = normalize_workflow_import_bundle(json.loads(path.read_text(encoding="utf-8")))
    validate_workflow_import_references(bundle)
    mappings = {item["localId"]: (f"collection-{item['localId']}", 1) for item in bundle["collections"]}
    document = materialize_workflow_import(
        bundle,
        workflow_id="workflow-integration",
        revision=1,
        collection_mappings=mappings,
    )
    document["collectionSnapshots"] = [
        {
            "id": mappings[item["localId"]][0],
            "revision": 1,
            "key": item["key"],
            "metadata": item["metadata"],
            "spec": item["spec"],
            "inputs": item["inputs"],
            "outputs": item["outputs"],
        }
        for item in bundle["collections"]
    ]

    normalized = normalize_workflow_document(document)
    assert validate_workflow_document(normalized) == []

    executor = convert_workflow_document(normalized)
    ids = [executor.id]
    ids.extend(step.id for step in executor.steps)
    ids.extend(collection.id for step in executor.steps for collection in step.collections)
    ids.extend(transition.id for step in executor.steps for transition in step.transitions)
    ids.extend(conclusion.id for conclusion in executor.conclusions)
    evaluation_inputs = {item.name: item.value for item in executor.steps[1].collections[1].inputs}

    assert ids == list(range(1, 17))
    assert executor.start_step_ids == [2]
    assert evaluation_inputs == {
        "usage": "outputs.memory.usage_percentage",
        "threshold": "inputs.warning_threshold",
        "retry_limit": "inputs.max_retries",
        "include_history": "inputs.include_history",
        "mode": "fast",
        "dry_run": False,
        "baseline": 0,
        "note": None,
    }
    assert all(collection.example_outputs == [] for step in executor.steps for collection in step.collections)
