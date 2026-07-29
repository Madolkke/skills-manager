from __future__ import annotations

from copy import deepcopy

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.rules.workflows import (
    DEFAULT_WORKFLOW_SKILL_GENERATOR_ID,
    WORKFLOW_SKILL_GENERATORS,
    WorkflowSkillGeneratorDescriptor,
    WorkflowSkillGeneratorRegistry,
    generate_workflow_skill,
    list_workflow_skill_generators,
    normalize_workflow_document,
    render_skill_markdown,
)


def test_builtin_registry_has_one_three_file_default_and_strict_empty_options():
    descriptors = list_workflow_skill_generators()

    assert [(item.id, item.version) for item in descriptors] == [
        ("builtin.single-file", "workflow-skill-v4.1.1"),
        ("builtin.three-file", "2.1.1"),
        ("builtin.node-split", "2.1.1"),
    ]
    assert DEFAULT_WORKFLOW_SKILL_GENERATOR_ID == "builtin.three-file"
    assert [item.id for item in descriptors if item.default] == ["builtin.three-file"]
    assert all(item.options_schema["additionalProperties"] is False for item in descriptors)

    with pytest.raises(InvariantError, match="must be an object"):
        WORKFLOW_SKILL_GENERATORS.normalize_options("builtin.three-file", [])
    with pytest.raises(InvariantError, match="does not support options"):
        WORKFLOW_SKILL_GENERATORS.normalize_options("builtin.three-file", {"template": "custom"})
    with pytest.raises(InvariantError, match="Unknown Workflow Skill Generator"):
        WORKFLOW_SKILL_GENERATORS.get("builtin.missing")


def test_registry_rejects_duplicate_ids_and_requires_exactly_one_default():
    with pytest.raises(InvariantError, match="Duplicate.*ID"):
        WorkflowSkillGeneratorRegistry((_StubGenerator("same", True), _StubGenerator("same", False)))
    with pytest.raises(InvariantError, match="exactly one default"):
        WorkflowSkillGeneratorRegistry((_StubGenerator("first", False), _StubGenerator("second", False)))
    with pytest.raises(InvariantError, match="exactly one default"):
        WorkflowSkillGeneratorRegistry((_StubGenerator("first", True), _StubGenerator("second", True)))


def test_single_file_is_byte_compatible_and_all_builtins_are_deterministic_valid_bundles():
    document = _document()
    expected = render_skill_markdown(slug="interface-check", document=document)

    for generator_id, file_count in (
        ("builtin.single-file", 1),
        ("builtin.three-file", 3),
        ("builtin.node-split", 5),
    ):
        first = generate_workflow_skill(
            slug="interface-check", document=document, generator_id=generator_id, generator_options={}
        )
        second = generate_workflow_skill(
            slug="interface-check", document=document, generator_id=generator_id, generator_options={}
        )
        assert first == second
        assert all(file.content_text.endswith("\n") for file in first.files)
        assert all("\r" not in file.content_text for file in first.files)
        parsed = parse_skill_import_source(first.import_source(name="interface-check"))
        assert parsed.file_count == file_count
        assert parsed.slug == "interface-check"
        rendered = "\n".join(file.content_text for file in first.files)
        assert "outputs.status[i].state" in rendered
        assert "outputs.single.state" in rendered
        assert "采集“单次采集”的输出 `outputs.single.state`" in rendered
        assert "- `state` (string, 可选):" in rendered
        assert "`single.state` (" not in rendered

    single = generate_workflow_skill(
        slug="interface-check", document=document, generator_id="builtin.single-file", generator_options={}
    )
    assert single.files[0].content_text == expected


def test_three_file_output_has_fixed_golden_structure_and_filters_sensitive_examples():
    result = generate_workflow_skill(
        slug="interface-check", document=_document(), generator_id="builtin.three-file", generator_options={}
    )
    files = {file.path: file.content_text for file in result.files}

    assert list(files) == ["SKILL.md", "references/workflow.md", "references/collections.md"]
    assert "[完整工作流](references/workflow.md)" in files["SKILL.md"]
    assert "options-secret-key" in files["references/workflow.md"]
    assert "采集描述" in files["references/collections.md"]
    assert "核心、网络" in files["references/collections.md"]
    assert "display interface {{ interface_name }}" in files["references/collections.md"]
    assert "采集次数: 2" in files["references/collections.md"]
    assert "outputs.status[i].state" in files["references/collections.md"]
    assert "`i = 0..1`，同时支持对应负数下标 `-2..-1`" in files["references/collections.md"]
    joined = "\n".join(files.values())
    assert "接口 Down 示例" in joined
    assert "SECRET SYMPTOM" not in joined
    assert "SECRET RAW OUTPUT" not in joined
    assert "SECRET INPUT VALUE" not in joined


def test_node_split_uses_stable_hashed_paths_and_relative_links():
    document = _document()
    result = generate_workflow_skill(
        slug="interface-check", document=document, generator_id="builtin.node-split", generator_options={}
    )
    paths = {file.path for file in result.files}
    step_path = "references/step-bcde6dff113a0bb13f58e8eba023ee94b58ba7b4d1a003569504f431b9f806d5.md"
    conclusion_path = "references/conclusion-86b1910affdfeb3187a0756800368c6617aed04054f5fec8e80df28e793dae04.md"
    collection_path = "references/collection-d0214747236a6163e8b94265d017df1d41669b8890d026a97a8fd5453602bb73.md"
    assert paths == {"SKILL.md", "references/index.md", step_path, conclusion_path, collection_path}

    files = {file.path: file.content_text for file in result.files}
    assert step_path.removeprefix("references/") in files["references/index.md"]
    assert collection_path.removeprefix("references/") in files[step_path]
    assert "SECRET RAW OUTPUT" not in "\n".join(files.values())

    renamed = deepcopy(document)
    renamed["workflow"]["nodes"].reverse()
    renamed["workflow"]["nodes"][0]["name"] = "重命名结论"
    renamed["workflow"]["nodes"][1]["name"] = "重命名步骤"
    renamed["collectionSnapshots"][0]["metadata"]["name"] = "重命名采集"
    renamed_paths = {
        file.path
        for file in generate_workflow_skill(
            slug="interface-check", document=renamed, generator_id="builtin.node-split", generator_options={}
        ).files
    }
    assert renamed_paths == paths


def test_node_split_reports_bundle_limit_and_recommends_three_file():
    document = _document()
    document["workflow"]["nodes"] = [
        {
            "id": f"conclusion-{index}",
            "name": f"结论 {index}",
            "rootCause": "原因",
            "repairRecommendation": "建议",
            "nodeType": "conclusion",
        }
        for index in range(99)
    ]

    with pytest.raises(InvariantError, match=r"102 files.*100-file.*builtin\.three-file"):
        generate_workflow_skill(
            slug="interface-check", document=document, generator_id="builtin.node-split", generator_options={}
        )


def test_node_split_reports_bundle_byte_limit_and_recommends_three_file():
    document = _document()
    document["workflow"]["nodes"][0]["script"]["source"] = "x" * (5 * 1024 * 1024)

    with pytest.raises(InvariantError, match=r"bytes.*5242880-byte.*builtin\.three-file"):
        generate_workflow_skill(
            slug="interface-check", document=document, generator_id="builtin.node-split", generator_options={}
        )


class _StubGenerator:
    def __init__(self, generator_id: str, default: bool) -> None:
        self.descriptor = WorkflowSkillGeneratorDescriptor(
            id=generator_id,
            version="1.0.0",
            label=generator_id,
            default=default,
            options_schema={},
        )


def _document() -> dict:
    return normalize_workflow_document(
        {
            "documentType": "workflow_bundle",
            "workflow": {
                "id": "workflow-interface",
                "revision": 7,
                "metadata": {
                    "name": "接口状态排查",
                    "code": "IFACE",
                    "description": "检查接口状态。",
                    "symptom": "SECRET SYMPTOM",
                    "industry": "网络",
                    "device": "交换机",
                    "versions": ["V1"],
                },
                "inputs": [
                    {
                        "id": "input-interface",
                        "key": "interface_name",
                        "name": "接口名称",
                        "description": "待检查接口。",
                        "dataType": "string",
                        "required": True,
                    }
                ],
                "deviceRoles": [
                    {"id": "role-device", "key": "device", "name": "目标设备", "description": "被检查设备。", "required": True}
                ],
                "nodes": [
                    {
                        "id": "step-start",
                        "name": "采集接口",
                        "description": "读取接口状态。",
                        "isStart": True,
                        "collectionCalls": [
                            {
                                "id": "call-status",
                                "key": "status",
                                "name": "状态采集",
                                "definition": {"id": "collection-status", "revision": 4},
                                "deviceRoleId": "role-device",
                                "sampleCount": 2,
                                "inputBindings": {
                                    "parameter-interface": {
                                        "kind": "workflow_input",
                                        "reference": {"input_id": "input-interface"},
                                    }
                                },
                            },
                            {
                                "id": "call-single",
                                "key": "single",
                                "name": "单次采集",
                                "definition": {"id": "collection-status", "revision": 4},
                                "deviceRoleId": "role-device",
                                "sampleCount": 1,
                                "inputBindings": {
                                    "parameter-interface": {
                                        "kind": "workflow_input",
                                        "reference": {"input_id": "input-interface"},
                                    }
                                },
                            },
                            {
                                "id": "call-direct",
                                "key": "",
                                "name": "直接输出",
                                "definition": {"id": "collection-status", "revision": 4},
                                "deviceRoleId": "role-device",
                                "sampleCount": 1,
                                "inputBindings": {
                                    "parameter-interface": {
                                        "kind": "collection_output",
                                        "reference": {"call_id": "call-single", "output_id": "output-state"},
                                    }
                                },
                            },
                        ],
                        "topology": [
                            {
                                "id": "transition-end",
                                "target": {"id": "conclusion-end"},
                                "conditionText": "采集完成",
                                "conditionExpression": "status.state != ''",
                            }
                        ],
                        "stepType": "script",
                        "script": {"language": "python", "source": "print('status')\n", "options": {"token": "options-secret-key"}},
                    },
                    {
                        "id": "conclusion-end",
                        "name": "接口异常",
                        "rootCause": "接口状态异常。",
                        "repairRecommendation": "修复接口。",
                        "nodeType": "conclusion",
                    },
                ],
            },
            "collectionSnapshots": [
                {
                    "id": "collection-status",
                    "revision": 4,
                    "key": "interface_status",
                    "metadata": {
                        "name": "接口状态",
                        "description": "采集描述",
                        "industry": "网络",
                        "device": "交换机",
                        "versions": ["V1"],
                        "tags": ["核心", "网络"],
                    },
                    "spec": {
                        "collectionType": "cli",
                        "commandTemplate": "display interface {{ interface_name }}",
                        "outputSamples": [
                            {
                                "id": "sample-down",
                                "name": "接口 Down 示例",
                                "stdout": "SECRET RAW OUTPUT",
                                "inputValues": {"interface_name": "SECRET INPUT VALUE"},
                            }
                        ],
                    },
                    "inputs": [
                        {
                            "id": "parameter-interface",
                            "key": "interface_name",
                            "name": "接口名称",
                            "description": "命令参数。",
                            "dataType": "string",
                            "required": True,
                        }
                    ],
                    "outputs": [{"id": "output-state", "key": "state", "description": "接口状态。", "dataType": "string"}],
                }
            ],
        }
    )
