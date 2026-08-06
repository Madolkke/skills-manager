from __future__ import annotations

from copy import deepcopy

from skillhub.models.rules.executor_workflows import convert_workflow_document, project_workflow_document
from tests.executor_workflow_fixture import executor_workflow_document


def test_projection_preserves_executor_workflow_and_source_mapping() -> None:
    document = executor_workflow_document()

    projection = project_workflow_document(document)

    assert projection.workflow == convert_workflow_document(deepcopy(document))
    assert dict(projection.id_map.step_ids) == {"step-prepare": 2, "step-confirm": 3}
    assert dict(projection.id_map.conclusion_ids) == {"conclusion-normal": 9}
    assert dict(projection.id_map.call_ids) == {
        ("step-prepare", "call-environment"): 4,
        ("step-prepare", "call-check"): 5,
    }
    assert dict(projection.id_map.transition_ids) == {
        ("step-prepare", "transition-next"): 6,
        ("step-prepare", "transition-done"): 7,
        ("step-confirm", "transition-confirmed"): 8,
    }
    assert dict(projection.id_map.workflow_input_keys) == {
        "input-slot": "slot-id",
        "input-limit": "limit",
        "input-ratio": "ratio",
        "input-enabled": "enabled",
    }
    assert dict(projection.id_map.call_output_keys) == {
        ("step-prepare", "call-environment", "output-memory"): "memory-percentage",
        ("step-prepare", "call-check", "output-ok"): "ok-flag",
    }


def test_projection_mapping_is_deterministic_and_matches_allocated_ids() -> None:
    document = executor_workflow_document()

    first = project_workflow_document(document)
    second = project_workflow_document(deepcopy(document))

    assert first == second
    for source_id, executor_id in first.id_map.step_ids.items():
        step = next(item for item in document["workflow"]["nodes"] if item["id"] == source_id)
        projected = next(item for item in first.workflow.steps if item.name == step["name"])
        assert projected.id == executor_id
    for (step_source_id, call_source_id), executor_id in first.id_map.call_ids.items():
        step = next(item for item in document["workflow"]["nodes"] if item["id"] == step_source_id)
        call_index = next(index for index, item in enumerate(step["collectionCalls"]) if item["id"] == call_source_id)
        projected_step = next(item for item in first.workflow.steps if item.id == first.id_map.step_ids[step_source_id])
        assert projected_step.collections[call_index].id == executor_id
