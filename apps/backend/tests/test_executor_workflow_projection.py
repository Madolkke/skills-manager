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


def test_projection_excludes_ignored_calls_from_the_shared_identity_map() -> None:
    document = executor_workflow_document()
    document["collectionSnapshots"][0]["spec"] = {
        "collectionType": "log",
        "sqlDialect": "duckdb",
        "queries": [],
        "outputSamples": [],
    }

    projection = project_workflow_document(document)

    assert dict(projection.id_map.call_ids) == {("step-prepare", "call-check"): 4}
    assert dict(projection.id_map.transition_ids) == {
        ("step-prepare", "transition-next"): 5,
        ("step-prepare", "transition-done"): 6,
        ("step-confirm", "transition-confirmed"): 7,
    }
    assert dict(projection.id_map.call_output_keys) == {
        ("step-prepare", "call-check", "output-ok"): "ok-flag",
    }
    assert projection.workflow.conclusions[0].id == 8


def test_projection_filters_mixed_log_and_config_calls_without_rewriting_cli_references() -> None:
    document = executor_workflow_document()
    step = document["workflow"]["nodes"][0]
    step["collectionCalls"].insert(1, {
        "id": "call-log", "key": "log_summary", "name": "日志摘要",
        "definition": {"id": "collection-log", "revision": 1}, "sampleCount": 9,
        "deviceRoleId": "missing-role", "inputBindings": {},
    })
    step["collectionCalls"].insert(2, {
        "id": "call-config", "key": "config_result", "name": "配置匹配",
        "definition": {"id": "collection-config", "revision": 1}, "sampleCount": 3,
        "deviceRoleId": "missing-role", "inputBindings": {},
    })
    step["collectionCalls"][3]["inputBindings"]["parameter-memory"] = {
        "kind": "collection_output", "reference": {"call_id": "call-log", "output_id": "output-log"},
    }
    document["collectionSnapshots"].extend([
        {"id": "collection-log", "revision": 1, "key": "log", "metadata": {"name": "日志"}, "spec": {"collectionType": "log", "sqlDialect": "duckdb", "queries": [], "outputSamples": []}, "inputs": [], "outputs": [{"id": "output-log", "key": "count", "required": True, "schema": {"type": "integer", "title": "计数", "description": ""}}]},
        {"id": "collection-config", "revision": 1, "key": "config", "metadata": {"name": "配置"}, "spec": {"collectionType": "config", "config": {"commands": []}}, "inputs": [], "outputs": []},
    ])

    projection = project_workflow_document(document)

    assert [item.command for item in projection.workflow.steps[0].collections] == ["screen-length 0 temporary", "display memory"]
    assert dict(projection.id_map.call_ids) == {("step-prepare", "call-environment"): 4, ("step-prepare", "call-check"): 5}
    assert projection.workflow.steps[0].collections[1].inputs[0].value == "outputs.log_summary.count"
