"""作者编辑的逐字段更新、排序及删除语义。"""

from copy import deepcopy

import pytest
from pydantic import TypeAdapter

from skillhub.models.errors import InvariantError
from skillhub.views.request_models.workflow_authoring import AuthoringChanges
from tests import test_workflow_authoring_rules as fixtures


def test_input_role_edits_are_partial_and_array_values_replace():
    result = fixtures.apply([
        {"operation": "metadata.update", "fields": {"description": "第一版", "versions": ["v1", "v2"]}},
        {"operation": "metadata.update", "fields": {"versions": ["v3"]}},
        *[{"operation": "input.add", "client_ref": key, "fields": {"key": key, "schema": {"type": "string"}}} for key in ("i1", "i2")],
        {"operation": "input.update", "input_id": "@i1", "fields": {"required": False}},
        {"operation": "input.reorder", "ids": ["@i2", "@i1"]},
        *[{"operation": "role.add", "client_ref": key, "fields": {"key": key, "name": key}} for key in ("r1", "r2")],
        {"operation": "role.update", "role_id": "@r1", "fields": {"description": "首要设备"}},
        {"operation": "role.reorder", "ids": ["@r2", "@r1"]},
    ])
    workflow = result["document"]["workflow"]
    assert workflow["metadata"]["name"] == "测试"
    assert workflow["metadata"]["description"] == "第一版"
    assert workflow["metadata"]["versions"] == ["v3"]
    assert [item["key"] for item in workflow["inputs"]] == ["i2", "i1"]
    assert workflow["inputs"][1]["required"] is False
    assert workflow["inputs"][1]["schema"]["type"] == "string"
    assert [item["key"] for item in workflow["deviceRoles"]] == ["r2", "r1"]
    assert workflow["deviceRoles"][1]["description"] == "首要设备"


def test_script_can_be_updated_then_changed_to_expression():
    script = {"operation": "node.add", "client_ref": "script", "fields": {"stepType": "script", "name": "脚本", "script": {"source": "return True", "options": {"fixture": True}}}}
    updated = fixtures.apply([script, {"operation": "node.update", "node_id": "@script", "fields": {"script": {"source": "return False"}}}])
    assert updated["document"]["workflow"]["nodes"][0]["script"] == {"language": "python", "source": "return False", "options": {"fixture": True}}
    changed = fixtures.apply([script, {"operation": "node.update", "node_id": "@script", "fields": {"stepType": "expression"}}])
    assert "script" not in changed["document"]["workflow"]["nodes"][0]


def test_call_transition_and_binding_updates_preserve_other_fields():
    changes = [fixtures.step(), fixtures.step("next")]
    changes += [{"operation": "call.add", "node_id": "@step", "client_ref": ref, "fields": {
        "key": ref, "name": ref, "definition": {"id": "c1", "revision": 3},
        "inputBindings": {"ci": {"kind": "literal", "value": "old"}},
    }} for ref in ("a", "b")]
    changes += [
        {"operation": "call.update", "node_id": "@step", "call_id": "@a", "fields": {"sampleCount": 3}},
        {"operation": "call.reorder", "node_id": "@step", "ids": ["@b", "@a"]},
        {"operation": "binding.remove", "node_id": "@step", "call_id": "@b", "input_id": "ci"},
        {"operation": "binding.set", "node_id": "@step", "call_id": "@a", "input_id": "ci", "binding": {"kind": "expression", "expression": "outputs.b.interfaces[0].up"}},
        *[{"operation": "transition.add", "node_id": "@step", "client_ref": ref, "fields": {"target": {"id": "@next"}, "conditionText": ref}} for ref in ("e1", "e2")],
        {"operation": "transition.update", "node_id": "@step", "transition_id": "@e1", "fields": {"conditionExpression": "True"}},
        {"operation": "transition.reorder", "node_id": "@step", "ids": ["@e2", "@e1"]},
        {"operation": "transition.remove", "node_id": "@step", "transition_id": "@e2"},
    ]
    result = fixtures.apply(changes)
    step = result["document"]["workflow"]["nodes"][0]
    assert [item["key"] for item in step["collectionCalls"]] == ["b", "a"]
    assert step["collectionCalls"][0]["inputBindings"] == {}
    assert step["collectionCalls"][1]["sampleCount"] == 3
    assert step["collectionCalls"][1]["inputBindings"]["ci"]["expression"] == "outputs.b.interfaces[0].up"
    assert step["topology"][0]["conditionText"] == "e1"
    assert step["topology"][0]["conditionExpression"] == "True"


def test_removed_inputs_and_roles_do_not_silently_rewrite_stale_bindings():
    result = fixtures.apply([
        {"operation": "input.add", "client_ref": "i", "fields": {"key": "i", "schema": {"type": "string"}}},
        {"operation": "role.add", "client_ref": "r", "fields": {"key": "r", "name": "r"}}, fixtures.step(),
        {"operation": "call.add", "node_id": "@step", "fields": {"key": "a", "name": "a", "definition": {"id": "c1", "revision": 3}, "deviceRoleId": "@r",
           "inputBindings": {"ci": {"kind": "workflow_input", "reference": {"input_id": "@i"}}}}},
        {"operation": "input.remove", "input_id": "@i"}, {"operation": "role.remove", "role_id": "@r"},
    ])
    workflow = result["document"]["workflow"]
    assert workflow["inputs"] == [] and workflow["deviceRoles"] == []
    assert workflow["nodes"][0]["collectionCalls"][0]["deviceRoleId"] == result["id_mappings"]["r"]
    assert workflow["nodes"][0]["collectionCalls"][0]["inputBindings"]["ci"]["reference"]["input_id"] == result["id_mappings"]["i"]


def test_invalid_target_binding_and_wrong_exact_revision_are_rejected():
    base = [fixtures.step(), {"operation": "call.add", "node_id": "@step", "client_ref": "call", "fields": {"key": "a", "name": "a", "definition": {"id": "c1", "revision": 3}}}]
    with pytest.raises(InvariantError, match="采集输入不存在"):
        fixtures.apply([*base, {"operation": "binding.set", "node_id": "@step", "call_id": "@call", "input_id": "bad", "binding": {"kind": "literal", "value": "x"}}])
    wrong = deepcopy(base)
    wrong[1]["fields"]["definition"]["revision"] = 4
    with pytest.raises(InvariantError, match="精确版本"):
        fixtures.apply(wrong)


def test_stale_binding_can_be_removed_after_fork_removes_parameter():
    initial = fixtures.apply([fixtures.step(), {"operation": "call.add", "node_id": "@step", "client_ref": "call", "fields": {
        "key": "a", "name": "a", "definition": {"id": "c1", "revision": 3}, "inputBindings": {"ci": {"kind": "literal", "value": "old"}},
    }}])
    node_id, call_id = initial["id_mappings"]["step"], initial["id_mappings"]["call"]
    result = fixtures.apply([
        {"operation": "call.fork_collection", "node_id": node_id, "call_id": call_id, "fields": {"inputs": []}},
        {"operation": "binding.remove", "node_id": node_id, "call_id": call_id, "input_id": "ci"},
    ], initial["document"])
    assert result["document"]["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"] == {}


def test_every_operation_is_discoverable_with_closed_top_level_schema():
    schema = TypeAdapter(AuthoringChanges).json_schema(by_alias=True)
    operations = schema["items"]["discriminator"]["mapping"]
    assert len(operations) == 26
    for ref in operations.values():
        assert schema["$defs"][ref.rsplit("/", 1)[-1]]["additionalProperties"] is False
