"""局部更新区分字段缺省与显式 null，禁止在规则层产生内部异常。"""

import asyncio

import pytest
from pydantic import TypeAdapter, ValidationError

from skillhub.views.mcp import WorkflowMCP
from skillhub.views.mcp.tools import create_tools
from skillhub.views.request_models.workflow_authoring import AuthoringChanges

PATCHES = [
    ({"operation": "metadata.update"}, ("name", "code", "description", "symptom", "industry", "device", "versions")),
    ({"operation": "input.update", "input_id": "input-1"}, ("key", "required", "schema")),
    ({"operation": "role.update", "role_id": "role-1"}, ("key", "name", "description", "required")),
    ({"operation": "node.update", "node_id": "node-1"}, ("name", "description", "isStart", "parallelBranches", "stepType", "severity", "rootCause", "repairRecommendation")),
    ({"operation": "call.update", "node_id": "node-1", "call_id": "call-1"}, ("key", "name", "sampleCount", "inputBindings", "definition")),
    ({"operation": "transition.update", "node_id": "node-1", "transition_id": "edge-1"}, ("target", "conditionText", "conditionExpression")),
    ({"operation": "call.fork_collection", "node_id": "node-1", "call_id": "call-1"}, ("key", "metadata", "spec", "inputs", "outputs")),
]


@pytest.mark.parametrize("operation,field", [(operation, field) for operation, fields in PATCHES for field in fields])
def test_nonnullable_patch_fields_reject_null_but_can_be_omitted(operation, field):
    """空补丁不会覆盖原值，非法 null 在进入候选构造前被拒绝。"""
    adapter = TypeAdapter(AuthoringChanges)
    parsed = adapter.validate_python([{**operation, "fields": {}}])[0]
    assert parsed.model_dump(mode="json", by_alias=True, exclude_unset=True)["fields"] == {}
    with pytest.raises(ValidationError):
        adapter.validate_python([{**operation, "fields": {field: None}}])
    field_schema = type(parsed.fields).model_json_schema(by_alias=True)["properties"][field]
    assert field_schema.get("type") != "null"
    assert all(item.get("type") != "null" for item in field_schema.get("anyOf", []))


@pytest.mark.parametrize("field", ["name", "description", "industry", "device", "versions", "tags"])
def test_nested_collection_metadata_patch_rejects_null(field):
    """定义元信息的局部更新与顶层字段保持相同的空值约束。"""
    with pytest.raises(ValidationError):
        TypeAdapter(AuthoringChanges).validate_python([{
            "operation": "call.fork_collection", "node_id": "node-1", "call_id": "call-1", "fields": {"metadata": {field: None}},
        }])


@pytest.mark.parametrize("operation,field", [
    ({"operation": "role.update", "role_id": "role-1"}, "schema"),
    ({"operation": "node.update", "node_id": "node-1"}, "script"),
    ({"operation": "call.update", "node_id": "node-1", "call_id": "call-1"}, "deviceRoleId"),
])
def test_truly_nullable_fields_can_still_be_explicitly_cleared(operation, field):
    """合法清空操作在序列化时保留显式 null。"""
    parsed = TypeAdapter(AuthoringChanges).validate_python([{**operation, "fields": {field: None}}])[0]
    assert parsed.model_dump(mode="json", by_alias=True, exclude_unset=True)["fields"] == {field: None}


def test_null_patch_returns_invalid_argument_without_calling_service():
    """原崩溃路径及同类定义/目标引用在 MCP 边界返回可修复参数错误。"""
    async def invoke(*_args):
        raise AssertionError("参数无效时不得进入服务或写事务")

    server = WorkflowMCP(create_tools(invoke))
    cases = [
        ("call.fork_collection", "call_id", "inputs"), ("call.fork_collection", "call_id", "outputs"),
        ("call.fork_collection", "call_id", "spec"), ("call.update", "call_id", "definition"),
        ("transition.update", "transition_id", "target"),
    ]
    for operation, identity, field in cases:
        arguments = {"skill_id": "skill-1", "changes": [{
            "operation": operation, "node_id": "node-1", identity: "target-1", "fields": {field: None},
        }]}
        result = asyncio.run(server.call_authoring_tool("apply_workflow_changes", arguments))
        assert result.isError
        assert result.structuredContent["error"]["code"] == "INVALID_ARGUMENT"
