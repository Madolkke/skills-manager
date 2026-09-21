"""验证可复制的引用及示例协议，不断言指令措辞。"""

import json
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from skillhub.models.rules.workflows.schema import JsonSchema
from skillhub.views.request_models.workflow_authoring import AuthoringChange

ROOT = Path(__file__).resolve().parents[1]


def json_blocks(path: Path):
    """从文档提取真正交给使用者的 JSON 示例。"""
    return [json.loads(raw) for raw in re.findall(r"```json\s+(.*?)\s+```", path.read_text(encoding="utf-8"), re.S)]


def canonical_schema(value):
    """required 是字段集合，规范化其顺序后比较其余结构原文。"""
    if isinstance(value, dict):
        return {key: sorted(item) if key == "required" else canonical_schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonical_schema(item) for item in value]
    return value


@pytest.mark.parametrize("example", json_blocks(ROOT / "references/examples.md"))
def test_examples_follow_actual_mcp_operation_schema(example):
    """所有操作经当前后端联合类型解析，保留严格字段与别名契约。"""
    adapter = TypeAdapter(AuthoringChange)
    for operation in example if isinstance(example, list) else [example]:
        parsed = adapter.validate_python(operation)
        assert parsed.model_dump(by_alias=True, exclude_unset=True)["operation"] == operation["operation"]


@pytest.mark.parametrize("schema", json_blocks(ROOT / "tests/fixtures/network-inspection.md"))
def test_fixture_output_schemas_are_valid_and_preserve_structure(schema):
    """模拟文档的根输出契约能被产品类型无损表达。"""
    model = TypeAdapter(JsonSchema).validate_python(schema)
    assert canonical_schema(model.model_dump(by_alias=True, exclude_unset=True)) == canonical_schema(schema)
    assert schema["type"] == "object"
    assert set(schema["required"]) <= set(schema["properties"])


def test_runtime_references_remain_inside_standalone_copy(tmp_path):
    """复制运行所需文件后所有本地 Markdown 引用仍然存在。"""
    import shutil

    for name in ("SKILL.md", "references", "agents"):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, tmp_path / name)
        else:
            shutil.copy2(source, tmp_path / name)
    for path in tmp_path.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_relative_to(tmp_path.resolve())
            assert resolved.is_file()


def test_fixture_requires_nested_arrays_and_distinct_sample_dimension():
    """防止整理测试输入时丢掉复杂 Schema 的真实结构。"""
    interfaces, routes, bgp, fabric, custom = json_blocks(ROOT / "tests/fixtures/network-inspection.md")
    assert interfaces["properties"]["interfaces"]["items"]["properties"]["counters"]["properties"]["errors"]["type"] == "integer"
    assert routes["properties"]["routes"]["items"]["properties"]["next_hops"]["items"]["properties"]["metric"]["type"] == "number"
    assert bgp["properties"]["peers"]["items"]["properties"]["families"]["items"]["properties"]["prefixes"]["type"] == "object"
    matrix = fabric["properties"]["matrix"]
    assert matrix["type"] == matrix["items"]["type"] == "array"
    assert matrix["items"]["items"]["type"] == "object"
    assert "value" not in matrix["items"]["items"]["required"]
    assert custom["properties"]["matched"]["type"] == "boolean"
