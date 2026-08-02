from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from skillhub.models.errors import FieldInvariantError
from skillhub.models.rules.executor_workflows import ExecutorWorkflow, convert_workflow_document
from skillhub.services import ExecutorWorkflowService
from tests.executor_workflow_fixture import executor_workflow_document


def test_conversion_matches_executor_contract_and_is_deterministic() -> None:
    document = executor_workflow_document()

    first = convert_workflow_document(document)
    second = convert_workflow_document(deepcopy(document))

    assert first == second
    assert first.model_dump() == {
        "id": 1,
        "name": "PTN故障快排",
        "start_step_ids": [2, 3],
        "inputs": [
            {"name": "slot-id", "description": "要检查的槽位号", "value": "inputs.slot-id", "type": "string"},
            {"name": "limit", "description": "重试次数", "value": "inputs.limit", "type": "integer"},
            {"name": "ratio", "description": "阈值", "value": "inputs.ratio", "type": "number"},
            {"name": "enabled", "description": "是否启用", "value": "inputs.enabled", "type": "boolean"},
        ],
        "steps": [
            {
                "id": 2,
                "name": "准备环境",
                "condition": "执行准备命令。",
                "collections": [
                    {
                        "id": 4,
                        "kind": "command",
                        "command": "screen-length 0 temporary",
                        "example_outputs": [],
                        "inputs": [
                            {"name": "slot-id", "description": "要检查的槽位号", "value": "inputs.slot-id", "type": "string"},
                            {"name": "threshold", "description": "内存阈值", "value": 0.8, "type": "number"},
                            {"name": "enabled", "description": "是否启用", "value": False, "type": "boolean"},
                            {"name": "note", "description": "备注", "value": None, "type": "string"},
                            {"name": "unbound", "description": "未绑定参数", "value": None, "type": "integer"},
                        ],
                        "outputs": [
                            {
                                "name": "memory-percentage",
                                "description": "内存使用率",
                                "value": "outputs.memory-percentage",
                                "type": "number",
                            }
                        ],
                    },
                    {
                        "id": 5,
                        "kind": "command",
                        "command": "display memory",
                        "example_outputs": [],
                        "inputs": [
                            {
                                "name": "memory",
                                "description": "内存使用率",
                                "value": "outputs.memory-percentage",
                                "type": "number",
                            }
                        ],
                        "outputs": [
                            {
                                "name": "ok-flag",
                                "description": "是否正常",
                                "value": "outputs.memory.stats.ok-flag",
                                "type": "boolean",
                            }
                        ],
                    },
                ],
                "transitions": [
                    {
                        "id": 6,
                        "target_type": "step",
                        "target_id": 3,
                        "condition": "outputs.memory-percentage > 0.8",
                        "description": "需要复核",
                    },
                    {"id": 7, "target_type": "conclusion", "target_id": 9, "condition": "", "description": "检查完成"},
                ],
            },
            {
                "id": 3,
                "name": "确认状态",
                "condition": "确认设备状态。",
                "collections": [],
                "transitions": [
                    {"id": 8, "target_type": "conclusion", "target_id": 9, "condition": "true", "description": "确认完成"}
                ],
            },
        ],
        "conclusions": [{"id": 9, "conclusion": "无异常"}],
    }
    assert _all_ids(first) == list(range(1, 10))


def test_conversion_does_not_apply_domain_validation() -> None:
    document = executor_workflow_document()
    for node in document["workflow"]["nodes"]:
        if "isStart" in node:
            node["isStart"] = False
    document["workflow"]["nodes"][0]["topology"][0]["conditionExpression"] = "not valid python ("
    document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"].pop("parameter-slot")

    result = convert_workflow_document(document)

    assert result.start_step_ids == []
    assert result.steps[0].transitions[0].condition == "not valid python ("
    assert result.steps[0].collections[0].inputs[0].value is None


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        {"type": "array", "items": {"type": "string"}},
        {"x-skillhub-legacy-loose": True},
    ],
)
def test_conversion_rejects_non_scalar_schemas(schema: dict) -> None:
    document = executor_workflow_document()
    document["workflow"]["inputs"][0]["schema"] = schema

    with pytest.raises(FieldInvariantError) as error:
        convert_workflow_document(document)

    assert error.value.field_errors[0].code == "executor_workflow.unsupported_schema"
    assert error.value.field_errors[0].field == "workflow.inputs[0].schema"


def test_conversion_aggregates_unsupported_features_and_broken_references() -> None:
    document = executor_workflow_document()
    call = document["workflow"]["nodes"][0]["collectionCalls"][0]
    call["deviceRoleId"] = "device-primary"
    call["sampleCount"] = 2
    call["inputBindings"]["parameter-threshold"]["value"] = {"invalid": True}
    document["workflow"]["nodes"][0]["collectionCalls"][1]["definition"]["id"] = "missing"
    document["workflow"]["nodes"].append(
        {
            "id": "step-script",
            "name": "脚本",
            "description": "",
            "isStart": False,
            "collectionCalls": [],
            "topology": [],
            "stepType": "script",
            "script": {"language": "python", "source": "", "options": {}},
        }
    )

    with pytest.raises(FieldInvariantError, match="Workflow 无法转换为执行器定义") as error:
        convert_workflow_document(document)

    assert [item.code for item in error.value.field_errors] == [
        "executor_workflow.unsupported_device_role",
        "executor_workflow.unsupported_sample_count",
        "executor_workflow.unsupported_literal",
        "executor_workflow.unresolvable_reference",
        "executor_workflow.unsupported_step_type",
    ]


def test_script_step_still_aggregates_nested_call_errors() -> None:
    document = executor_workflow_document()
    step = document["workflow"]["nodes"][0]
    step["stepType"] = "script"
    call = step["collectionCalls"][0]
    call["deviceRoleId"] = "   "
    call["sampleCount"] = 2
    call["inputBindings"]["parameter-threshold"]["value"] = [0.8]

    with pytest.raises(FieldInvariantError) as error:
        convert_workflow_document(document)

    assert [item.code for item in error.value.field_errors[:4]] == [
        "executor_workflow.unsupported_step_type",
        "executor_workflow.unsupported_device_role",
        "executor_workflow.unsupported_sample_count",
        "executor_workflow.unsupported_literal",
    ]


def test_broken_source_definition_is_located_on_source_call() -> None:
    document = executor_workflow_document()
    document["workflow"]["nodes"][0]["collectionCalls"][0]["definition"]["id"] = "missing"

    with pytest.raises(FieldInvariantError) as error:
        convert_workflow_document(document)

    definition_errors = [item for item in error.value.field_errors if item.code == "executor_workflow.unresolvable_reference"]
    assert [item.field for item in definition_errors] == ["workflow.nodes[0].collectionCalls[0].definition"]


def test_id_categories_keep_step_ids_stable_when_call_is_inserted() -> None:
    document = executor_workflow_document()
    extra_call = deepcopy(document["workflow"]["nodes"][0]["collectionCalls"][0])
    extra_call["id"] = "call-extra"
    extra_call["inputBindings"] = {}
    document["workflow"]["nodes"][1]["collectionCalls"].append(extra_call)

    result = convert_workflow_document(document)

    assert [step.id for step in result.steps] == [2, 3]
    assert [collection.id for step in result.steps for collection in step.collections] == [4, 5, 6]
    assert result.conclusions[0].id == 10


def test_literal_bindings_preserve_string_and_integer_values() -> None:
    document = executor_workflow_document()
    bindings = document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"]
    bindings["parameter-note"]["value"] = "memo"
    bindings["parameter-unbound"] = {"kind": "literal", "reference": {}, "value": 2}

    result = convert_workflow_document(document)
    values = {item.name: item.value for item in result.steps[0].collections[0].inputs}

    assert values["note"] == "memo"
    assert values["unbound"] == 2


@pytest.mark.parametrize(("section", "index"), [("inputs", 0), ("outputs", 0)])
def test_conversion_rejects_complex_collection_schemas(section: str, index: int) -> None:
    document = executor_workflow_document()
    document["collectionSnapshots"][0][section][index]["schema"] = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    with pytest.raises(FieldInvariantError) as error:
        convert_workflow_document(document)

    assert error.value.field_errors[0].field == f"collectionSnapshots[0].{section}[{index}].schema"
    assert error.value.field_errors[0].code == "executor_workflow.unsupported_schema"


def test_conversion_reports_ambiguous_and_unresolvable_references() -> None:
    document = executor_workflow_document()
    document["workflow"]["inputs"][1]["id"] = "input-slot"
    binding = document["workflow"]["nodes"][0]["collectionCalls"][1]["inputBindings"]["parameter-memory"]
    binding["reference"]["output_id"] = "missing-output"
    duplicate = deepcopy(document["workflow"]["nodes"][2])
    duplicate["name"] = "重复结论"
    document["workflow"]["nodes"].append(duplicate)

    with pytest.raises(FieldInvariantError) as error:
        convert_workflow_document(document)

    codes = [item.code for item in error.value.field_errors]
    assert "executor_workflow.ambiguous_reference" in codes
    assert "executor_workflow.unresolvable_reference" in codes


def test_documented_success_example_matches_executor_schema() -> None:
    path = Path(__file__).parents[3] / "docs" / "executor-workflow-api.md"
    blocks = re.findall(r"```json\s*(.*?)\s*```", path.read_text(encoding="utf-8"), re.DOTALL)

    assert len(blocks) >= 2
    parsed = [json.loads(block) for block in blocks]
    ExecutorWorkflow.model_validate(parsed[0])


def test_executor_service_reads_only_current_source() -> None:
    class SourceStore:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def executor_workflow_source(self, **kwargs: str) -> dict:
            self.calls.append(kwargs)
            return executor_workflow_document()

    store = SourceStore()
    service = ExecutorWorkflowService(store)  # type: ignore[arg-type]

    result = service.current(skill_id="skill-1")

    assert result.name == "PTN故障快排"
    assert store.calls == [{"skill_id": "skill-1"}]


def _all_ids(workflow: ExecutorWorkflow) -> list[int]:
    result = [workflow.id]
    result.extend(step.id for step in workflow.steps)
    result.extend(collection.id for step in workflow.steps for collection in step.collections)
    result.extend(transition.id for step in workflow.steps for transition in step.transitions)
    result.extend(conclusion.id for conclusion in workflow.conclusions)
    return result
