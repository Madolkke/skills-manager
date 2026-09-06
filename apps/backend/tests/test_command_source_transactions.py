from copy import deepcopy
from types import SimpleNamespace

from sqlalchemy import func, select

from skillhub.models.operations.command_library import _source_to_collection
from skillhub.models.schema import orm
from tests.api_command_test_case import ApiCommandTestCase


class CommandSourceTransactionsTest(ApiCommandTestCase):
    admin = {"X-SkillHub-Admin-Key": "test-admin-key"}
    actor = {"X-SkillHub-Actor": "workflow-owner"}

    def _create_workflow(self, *, repeated=False):
        """通过 HTTP 建立可用的系统来源工作流。"""
        payload = {
            "key": "display_status", "expression": "display <name>", "metadata": {"name": "状态查询"},
            "samples": [{"id": "sample", "name": "正常", "command": "display eth0", "stdout": "up"}], "ttp": "parser",
            "outputSchema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
        }
        response = self.client.post("/api/admin/system-commands", headers=self.admin, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        system = response.json()
        response = self.client.post("/api/workflows", headers=self.actor, json={
            "slug": "system-source-transaction", "owner_ref": "workflow-owner", "description": "来源同步测试", "tags": [],
        })
        self.assertEqual(response.status_code, 200, response.text)
        skill_id = response.json()["skill_id"]
        document = self.client.get(f"/api/skills/{skill_id}/workflow").json()["document"]
        source = SimpleNamespace(**{key: system[key] for key in ("key", "name", "description", "expression", "captures", "document")}, metadata_json=system["metadata"])
        definition = _source_to_collection(source, definition_id="collection-source", revision=1, source_id=system["id"])
        first = {
            "id": "first", "key": "first" if repeated else "", "name": "查询", "sampleCount": 1,
            "definition": {"id": definition["id"], "revision": 1},
            "inputBindings": {"input_name": {"kind": "literal", "reference": {}, "value": "eth0"}},
        }
        calls = [first]
        if repeated:
            second = deepcopy(first)
            second.update(id="second", key="second")
            second["inputBindings"] = {"input_name": {"kind": "collection_output", "reference": {"call_id": "first", "output_id": "output_status"}}}
            calls.append(second)
        document["workflow"]["nodes"] = [
            {"id": "step", "name": "查询", "isStart": True, "stepType": "expression", "collectionCalls": calls,
             "topology": [{"id": "next", "target": {"id": "later"}, "conditionExpression": "True"}]},
            {"id": "later", "name": "判断", "stepType": "expression", "collectionCalls": [],
             "topology": [{"id": "done", "target": {"id": "done"}, "conditionExpression": "True"}]},
            {"id": "done", "name": "完成", "nodeType": "conclusion", "rootCause": "", "repairRecommendation": ""},
        ]
        document["collectionSnapshots"] = [definition]
        saved = self.client.put(f"/api/skills/{skill_id}/workflow", headers=self.actor, json={
            "document": document, "collection_changes": [{"operation": "create", "definition": definition, "sourceSystemCommandId": system["id"]}],
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        return skill_id, system, saved.json()["document"]

    def _version_count(self):
        """检查执行层版本计数，以发现失败同步留下的写入。"""
        with self.engine.connect() as connection:
            return connection.execute(select(func.count()).select_from(orm.WorkflowCollectionRevision)).scalar_one()

    def test_partial_patch_and_repeated_binding_increment_once(self):
        skill_id, system, document = self._create_workflow(repeated=True)
        count = self._version_count()
        patched = self.client.patch(f"/api/admin/system-commands/{system['id']}", headers=self.admin, json={"name": "新名称"})
        self.assertEqual(patched.status_code, 200, patched.text)
        self.assertEqual(patched.json()["samples"], system["samples"])
        self.assertEqual(patched.json()["ttp"], "parser")
        saved = self.client.put(f"/api/skills/{skill_id}/workflow", headers=self.actor, json={"document": document, "collection_changes": []})
        self.assertEqual(saved.status_code, 200, saved.text)
        calls = saved.json()["document"]["workflow"]["nodes"][0]["collectionCalls"]
        self.assertEqual(calls[0]["definition"], calls[1]["definition"])
        self.assertEqual(self._version_count(), count + 1)

    def test_downstream_template_failure_rolls_back_workflow_and_versions(self):
        skill_id, system, document = self._create_workflow()
        document["workflow"]["nodes"][2]["rootCause"] = "state={{ outputs.status }}"
        saved = self.client.put(f"/api/skills/{skill_id}/workflow", headers=self.actor, json={"document": document, "collection_changes": []})
        self.assertEqual(saved.status_code, 200, saved.text)
        original = saved.json()["document"]
        count = self._version_count()
        changed = self.client.patch(f"/api/admin/system-commands/{system['id']}", headers=self.admin, json={
            "outputSchema": {"type": "object", "properties": {"state": {"type": "string"}}, "required": []},
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        rejected = self.client.put(f"/api/skills/{skill_id}/workflow", headers=self.actor, json={"document": original, "collection_changes": []})
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertIn("表达式引用", rejected.json()["detail"])
        self.assertEqual(self._version_count(), count)
        self.assertEqual(self.client.get(f"/api/skills/{skill_id}/workflow").json()["document"], original)
