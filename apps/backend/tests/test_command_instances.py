"""具体命令的参数、来源所有权及真实保存回归。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.command_instances import (
    command_match_warnings,
    instantiate_command,
    project_instance_source,
    set_instance_command,
)
from skillhub.models.schema import orm
from tests.api_command_test_case import ApiCommandTestCase


def source():
    """含数组输出及可选输入的来源。"""
    return SimpleNamespace(id="system", key="routes", name="路由", description="说明", enabled=True,
                           expression="show routes [vrf <vrf>] [detail]", metadata_json={},
                           captures={"vrf": {"optional": True}}, document={"outputSchema": {
                               "type": "object", "properties": {"routes": {"type": "array", "items": {
                                   "type": "object", "properties": {"vrf": {"type": "string"}},
                                   "required": ["vrf"], "additionalProperties": False}}},
                               "required": ["routes"], "additionalProperties": False}})


def test_parameters_and_source_ownership():
    entry = source()
    fixed = instantiate_command(entry, "show routes vrf default detail", definition_id="fixed")
    assert fixed["inputs"] == []
    dynamic = set_instance_command(fixed, "show routes vrf <tenant> <tenant>")
    assert [item["key"] for item in dynamic["inputs"]] == ["tenant"]
    dynamic["inputs"][0]["id"] = "kept-id"
    assert set_instance_command(dynamic, "show routes <tenant> detail")["inputs"][0]["id"] == "kept-id"
    assert set_instance_command(dynamic, "show routes")["inputs"] == []
    entry.expression, entry.name = "different <parameter>", "更新名称"
    projected = project_instance_source(entry, dynamic, revision=2)
    assert projected["spec"]["commandTemplate"] == dynamic["spec"]["commandTemplate"]
    assert projected["inputs"] == dynamic["inputs"]
    assert projected["metadata"]["name"] == "更新名称"
    assert projected["outputs"][0]["schema"]["items"]["properties"]["vrf"]["type"] == "string"
    assert command_match_warnings(dynamic, entry.expression)[0]["code"] == "COMMAND_MATCH_DYNAMIC"
    assert command_match_warnings(fixed, entry.expression)[0]["code"] == "COMMAND_SOURCE_MISMATCH"
    dynamic["inputs"].append(deepcopy(fixed["outputs"][0]))
    with pytest.raises(InvariantError, match="占位符一致"):
        project_instance_source(entry, dynamic, revision=2)


@pytest.mark.parametrize("command", ["", "show\nroutes", "show <invalid-name>", "show <open"])
def test_invalid_command(command):
    with pytest.raises(InvariantError):
        instantiate_command(source(), command, definition_id="invalid")


class CommandInstanceApiTest(ApiCommandTestCase):
    def test_preview_save_sync_and_rollback(self):
        admin = {"X-SkillHub-Admin-Key": "test-admin-key"}
        actor = {"X-SkillHub-Actor": "workflow-owner"}
        entry = source()
        result = self.client.post("/api/admin/system-commands", headers=admin, json={
            "key": entry.key, "expression": entry.expression, "name": entry.name,
            "outputSchema": entry.document["outputSchema"],
        })
        assert result.status_code == 200, result.text
        source_id = result.json()["id"]
        for query in [entry.key, entry.name]:
            found = self.client.post("/api/command-library/search", json={"command": query}).json()["results"]
            assert any(item["id"] == source_id for item in found)
        preview_url = f"/api/command-library/system-commands/{source_id}/instantiate-preview"
        with self.store._read_session() as session:
            before = session.scalar(select(func.count()).select_from(orm.WorkflowCollectionRevision))
        previews = [self.client.post(preview_url, json={"commandTemplate": command}) for command in
                    ["show routes vrf default detail", "show routes vrf <tenant>"]]
        assert all(item.status_code == 200 for item in previews)
        with self.store._read_session() as session:
            assert session.scalar(select(func.count()).select_from(orm.WorkflowCollectionRevision)) == before
        created = self.client.post("/api/workflows", headers=actor, json={
            "slug": "instance-test", "owner_ref": "workflow-owner", "description": "测试", "tags": []})
        assert created.status_code == 200, created.text
        url = f"/api/skills/{created.json()['skill_id']}/workflow"
        document = self.client.get(url, headers=actor).json()["document"]
        definitions = [item.json()["definition"] for item in previews]
        for index, definition in enumerate(definitions):
            definition["id"] = f"instance-{index}"
            definition["metadata"]["name"] = "客户端伪造"
        calls = [{"id": f"call-{index}", "key": f"routes{index}", "name": "路由", "sampleCount": 1,
                  "definition": {"id": definition["id"], "revision": 1}, "inputBindings": {
                      item["id"]: {"kind": "literal", "reference": {}, "value": "default"} for item in definition["inputs"]}}
                 for index, definition in enumerate(definitions)]
        document["workflow"]["nodes"] = [{"id": "step", "name": "查询", "description": "", "isStart": True,
            "stepType": "expression", "collectionCalls": calls, "topology": [{"id": "path", "target": {"id": "done"},
            "conditionText": "", "conditionExpression": "outputs.routes0.routes[0].vrf != ''"}]},
            {"id": "done", "name": "完成", "rootCause": "完成", "repairRecommendation": "无", "nodeType": "conclusion"}]
        document["collectionSnapshots"] = definitions
        saved = self.client.put(url, headers=actor, json={"document": document, "collection_changes": [
            {"operation": "create", "definition": definition} for definition in definitions]})
        assert saved.status_code == 200, saved.text
        document = saved.json()["document"]
        assert all(item["metadata"]["name"] == entry.name for item in document["collectionSnapshots"])
        assert saved.json()["validation"]["warnings"]
        unchanged = self.client.put(url, headers=actor, json={"document": document, "collection_changes": []})
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["revision"] == saved.json()["revision"]
        portable = self.client.get(url + "/export", headers=actor)
        assert portable.status_code == 200, portable.text
        assert "sourceBindingMode" not in portable.text and "sourceSystemCommandId" not in portable.text
        assert "show routes vrf <tenant>" in portable.text
        changed = self.client.patch(f"/api/admin/system-commands/{source_id}", headers=admin,
                                   json={"expression": "show other <new>", "name": "更新"})
        assert changed.status_code == 200, changed.text
        synced = self.client.put(url, headers=actor, json={"document": document, "collection_changes": []})
        assert synced.status_code == 200, synced.text
        for original, updated in zip(document["collectionSnapshots"], synced.json()["document"]["collectionSnapshots"], strict=True):
            assert original["spec"]["commandTemplate"] == updated["spec"]["commandTemplate"]
            assert original["inputs"] == updated["inputs"]
            assert updated["metadata"]["name"] == "更新"
        changed = self.client.patch(f"/api/admin/system-commands/{source_id}", headers=admin,
            json={"outputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}})
        assert changed.status_code == 200, changed.text
        rejected = self.client.put(url, headers=actor, json={"document": synced.json()["document"], "collection_changes": []})
        assert rejected.status_code == 400, rejected.text
        assert self.client.get(url, headers=actor).json()["revision"] == synced.json()["revision"]
