"""有序作者操作的纯规则回归，不依赖数据库。"""

from copy import deepcopy

import pytest
from pydantic import TypeAdapter, ValidationError

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.authoring import build_authoring_candidate
from skillhub.models.rules.workflows.schema import normalize_collection_definition, normalize_workflow_document
from skillhub.views.request_models.workflow_authoring import AuthoringChanges


def empty_document():
    """生成现有作者模型的空白文档。"""
    return normalize_workflow_document({"documentType": "workflow_bundle", "workflow": {"id": "wf1", "revision": 7, "metadata": {"name": "测试"}}})


def definition():
    """构造带对象数组和字段身份的已保存采集。"""
    return normalize_collection_definition({
        "id": "c1", "revision": 3, "key": "interfaces", "metadata": {"name": "接口"},
        "spec": {"collectionType": "cli", "commandTemplate": "show interfaces <interface>"},
        "inputs": [{"id": "ci", "key": "interface", "schema": {"type": "string"}}],
        "outputs": [{"id": "co", "key": "interfaces", "schema": {
            "type": "array", "items": {"type": "object", "properties": {"up": {"type": "boolean"}}, "required": ["up"], "additionalProperties": False},
        }}],
    })


def apply(changes, document=None, stored=None):
    """使用真实输入模型，再执行具有只读替身的候选构造。"""
    parsed = TypeAdapter(AuthoringChanges).validate_python(changes)
    wire = [item.model_dump(mode="json", by_alias=True, exclude_unset=True) for item in parsed]
    return build_authoring_candidate(
        document or empty_document(), wire,
        resolve_system_command=lambda command_id, new_id: {**definition(), "id": new_id, "revision": 1, "sourceSystemCommandId": command_id},
        resolve_collection=lambda definition_id, revision: deepcopy(stored or definition()),
    )


def step(ref="step", name="采集"):
    """提供最小新增步骤操作。"""
    return {"operation": "node.add", "client_ref": ref, "fields": {"stepType": "expression", "name": name, "isStart": True}}


def test_ordered_edit_maps_references_without_rewriting_text_or_literals():
    original = empty_document()
    result = apply([
        {"operation": "input.add", "client_ref": "iface", "fields": {"key": "interface", "schema": {"type": "string"}}},
        {"operation": "role.add", "client_ref": "device", "fields": {"key": "router", "name": "路由器"}},
        step(),
        {"operation": "node.add", "client_ref": "end", "fields": {"nodeType": "conclusion", "name": "结束", "rootCause": "@iface {{ inputs.interface }}"}},
        {"operation": "call.add", "node_id": "@step", "client_ref": "call", "fields": {
            "key": "interfaces", "name": "接口", "definition": {"id": "c1", "revision": 3}, "deviceRoleId": "@device", "sampleCount": 3,
        }},
        {"operation": "binding.set", "node_id": "@step", "call_id": "@call", "input_id": "ci", "binding": {"kind": "workflow_input", "reference": {"input_id": "@iface"}}},
        {"operation": "transition.add", "node_id": "@step", "client_ref": "edge", "fields": {"target": {"id": "@end"}, "conditionText": "@iface", "conditionExpression": "inputs.interface == '@iface'"}},
        {"operation": "node.update", "node_id": "@step", "fields": {"parallelBranches": True}},
    ], original)
    workflow = result["document"]["workflow"]
    node = workflow["nodes"][0]
    mapping = result["id_mappings"]
    assert node["collectionCalls"][0]["inputBindings"]["ci"]["reference"]["input_id"] == mapping["iface"]
    assert node["collectionCalls"][0]["deviceRoleId"] == mapping["device"]
    assert node["topology"][0]["target"]["id"] == mapping["end"]
    assert node["topology"][0]["conditionExpression"] == "inputs.interface == '@iface'"
    assert workflow["nodes"][1]["rootCause"] == "@iface {{ inputs.interface }}"
    assert node["parallelBranches"] is True
    assert workflow["revision"] == 7
    assert original == empty_document()
    assert result["collection_changes"] == []


def test_reorder_requires_every_member_and_preserves_ids():
    result = apply([step("a"), step("b"), {"operation": "node.reorder", "ids": ["@b", "@a"]}])
    assert [item["id"] for item in result["document"]["workflow"]["nodes"]] == [result["id_mappings"]["b"], result["id_mappings"]["a"]]
    for ids in (["@a"], ["@a", "@a"], ["@a", "missing"]):
        with pytest.raises(InvariantError, match="全部 ID"):
            apply([step("a"), step("b"), {"operation": "node.reorder", "ids": ids}])


def test_node_delete_cleans_incoming_edges_without_changing_other_expressions():
    result = apply([
        step("a"), step("b"), step("c"),
        {"operation": "transition.add", "node_id": "@a", "fields": {"target": {"id": "@b"}}},
        {"operation": "transition.add", "node_id": "@a", "fields": {"target": {"id": "@c"}, "conditionExpression": "outputs.old.status"}},
        {"operation": "node.remove", "node_id": "@b"},
    ])
    edges = result["document"]["workflow"]["nodes"][0]["topology"]
    assert len(edges) == 1
    assert edges[0]["conditionExpression"] == "outputs.old.status"


def test_definition_fork_changes_only_target_call_and_removes_system_source():
    source = {**definition(), "sourceSystemCommandId": "system-1"}
    original = apply([
        step(),
        *[{"operation": "call.add", "node_id": "@step", "client_ref": f"call{i}", "fields": {
            "key": f"i{i}", "name": "接口", "definition": {"id": "c1", "revision": 3},
        }} for i in range(2)],
    ], stored=source)
    saved = deepcopy(original["document"])
    result = apply([{"operation": "call.fork_collection", "node_id": original["id_mappings"]["step"], "call_id": original["id_mappings"]["call0"],
                     "definition_ref": "fork", "fields": {"metadata": {"name": "我的副本"}}}], saved)
    calls = result["document"]["workflow"]["nodes"][0]["collectionCalls"]
    assert calls[0]["definition"]["id"] == result["id_mappings"]["fork"]
    assert calls[1]["definition"] == {"id": "c1", "revision": 3}
    fork = result["collection_changes"][0]
    assert fork["operation"] == "fork"
    assert fork["definition"]["forkedFrom"] == {"id": "c1", "revision": 3}
    assert "sourceSystemCommandId" not in fork["definition"]
    assert fork["definition"]["outputs"] == source["outputs"]
    assert saved == original["document"]


def test_system_projection_and_removed_new_calls_leave_no_new_definitions():
    changes = [step(), {"operation": "call.from_system", "node_id": "@step", "client_ref": "newcall", "definition_ref": "def",
                        "command_id": "system-1", "fields": {"key": "iface", "name": "接口"}}]
    result = apply(changes)
    assert result["collection_changes"][0]["definition"]["sourceSystemCommandId"] == "system-1"
    assert result["document"]["collectionSnapshots"][0]["outputs"] == definition()["outputs"]
    removed = apply([*changes, {"operation": "call.remove", "node_id": "@step", "call_id": "@newcall"}])
    assert removed["collection_changes"] == []
    assert removed["document"]["collectionSnapshots"] == []


def test_same_batch_forks_keep_only_reachable_source_chain_in_creation_order():
    changes = [step(), {"operation": "call.from_system", "node_id": "@step", "client_ref": "call", "definition_ref": "source",
                        "command_id": "system-1", "fields": {"key": "iface", "name": "接口"}},
               {"operation": "call.fork_collection", "node_id": "@step", "call_id": "@call", "definition_ref": "fork",
                "fields": {"metadata": {"description": "独立副本"}}}]
    result = apply(changes)
    assert [item["operation"] for item in result["collection_changes"]] == ["create", "fork"]
    assert len(result["document"]["collectionSnapshots"]) == 1
    fork = result["document"]["collectionSnapshots"][0]
    assert fork["metadata"]["name"] == "接口"
    assert fork["metadata"]["description"] == "独立副本"
    assert fork["forkedFrom"]["id"] == result["id_mappings"]["source"]
    removed = apply([*changes, {"operation": "call.remove", "node_id": "@step", "call_id": "@call"}])
    assert removed["collection_changes"] == []


def test_custom_collection_assigns_fields_and_binding_refs_in_same_batch():
    custom = {key: value for key, value in definition().items() if key not in {"id", "revision"}}
    for section in ("inputs", "outputs"):
        custom[section][0].pop("id")
        custom[section][0]["client_ref"] = section
    result = apply([
        step(), {"operation": "call.create_collection", "node_id": "@step", "client_ref": "call", "definition": custom,
                 "fields": {"key": "iface", "name": "自定义"}},
        {"operation": "binding.set", "node_id": "@step", "call_id": "@call", "input_id": "@inputs", "binding": {"kind": "literal", "value": "@outputs"}},
    ])
    call = result["document"]["workflow"]["nodes"][0]["collectionCalls"][0]
    assert call["inputBindings"][result["id_mappings"]["inputs"]]["value"] == "@outputs"
    assert "client_ref" not in result["document"]["collectionSnapshots"][0]["inputs"][0]


@pytest.mark.parametrize("changes,error", [
    ([step(), step()], "client_ref 重复"),
    ([{"operation": "node.update", "node_id": "@missing", "fields": {"name": "x"}}], "尚未定义"),
    ([{"operation": "node.remove", "node_id": "missing"}], "编辑目标不存在"),
])
def test_invalid_operations_fail_without_mutating_document(changes, error):
    original = empty_document()
    with pytest.raises(InvariantError, match=error):
        apply(changes, original)
    assert original == empty_document()


@pytest.mark.parametrize("change", [
    {"operation": "node.update", "node_id": "s", "fields": {"id": "other"}},
    {"operation": "metadata.update", "fields": {"revision": 99}},
    {"operation": "node.add", "fields": {"name": "x", "stepType": "expression"}, "actor": "root"},
    {"operation": "call.from_system", "node_id": "n", "command_id": "c", "fields": {"name": "c", "key": "c", "sampleCount": "3"}},
    {"operation": "input.add", "fields": {"key": "i", "schema": {"type": "array"}}},
])
def test_strict_operation_schema_rejects_identity_mutation_extra_fields_and_bad_types(change):
    with pytest.raises(ValidationError):
        TypeAdapter(AuthoringChanges).validate_python([change])
