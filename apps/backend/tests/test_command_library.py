from __future__ import annotations

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.operations.command_library import _validate_source_compatibility
from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


def _scalar_schema(title: str) -> dict[str, str]:
    return {"type": "string", "title": title, "description": ""}


def _source_document(*, expression: str = "outputs.status", other_output: str | None = None) -> tuple[dict, dict, dict]:
    source_call = {
        "id": "call-source",
        "key": "",
        "definition": {"id": "source", "revision": 1},
        "inputBindings": {},
    }
    calls = [source_call]
    snapshots = [
        {
            "id": "source",
            "revision": 1,
            "outputs": [{"id": "output-status", "key": "status", "required": True, "schema": _scalar_schema("status")}],
        }
    ]
    if other_output:
        calls.append(
            {
                "id": "call-other",
                "key": "",
                "definition": {"id": "other", "revision": 1},
                "inputBindings": {},
            }
        )
        snapshots.append(
            {
                "id": "other",
                "revision": 1,
                "outputs": [{"id": "output-other", "key": other_output, "required": True, "schema": _scalar_schema(other_output)}],
            }
        )
    document = {
        "workflow": {
            "inputs": [],
            "nodes": [
                {
                    "id": "step",
                    "collectionCalls": calls,
                    "topology": [{"id": "path", "conditionExpression": expression}],
                }
            ],
        },
        "collectionSnapshots": snapshots,
    }
    desired = {
        "outputs": [{"id": "output-state", "key": "state", "required": True, "schema": _scalar_schema("state")}],
        "inputs": [],
    }
    return document, source_call, desired


def test_source_sync_rejects_removed_condition_output_reference() -> None:
    document, source_call, desired = _source_document()

    with pytest.raises(InvariantError, match="表达式引用"):
        _validate_source_compatibility(
            document=document,
            source_call=source_call,
            current=document["collectionSnapshots"][0],
            desired=desired,
        )


def test_source_sync_rejects_new_direct_output_conflict() -> None:
    document, source_call, desired = _source_document(expression="", other_output="state")
    desired["outputs"][0]["key"] = "state"

    with pytest.raises(InvariantError, match="直接输出"):
        _validate_source_compatibility(
            document=document,
            source_call=source_call,
            current=document["collectionSnapshots"][0],
            desired=desired,
        )


def test_source_sync_keeps_method_receiver_path_only() -> None:
    document, source_call, desired = _source_document(expression="outputs.status.lower() != ''")
    desired["outputs"] = [
        {"id": "output-status", "key": "status", "required": True, "schema": _scalar_schema("status")},
        {"id": "output-state", "key": "state", "required": True, "schema": _scalar_schema("state")},
    ]

    _validate_source_compatibility(
        document=document,
        source_call=source_call,
        current=document["collectionSnapshots"][0],
        desired=desired,
    )


@pytest.mark.parametrize("method", ["get", "keys", "values", "items"])
def test_source_sync_keeps_dict_method_receiver_path_only(method: str) -> None:
    invocation = 'outputs.status.get("child")' if method == "get" else f"outputs.status.{method}()"
    document, source_call, desired = _source_document(expression=invocation)
    object_schema = {
        "type": "object",
        "title": "status",
        "description": "",
        "properties": {"child": _scalar_schema("child")},
        "required": [],
        "additionalProperties": False,
    }
    document["collectionSnapshots"][0]["outputs"][0]["schema"] = object_schema
    desired["outputs"] = [
        {"id": "output-status", "key": "status", "required": True, "schema": object_schema},
        {"id": "output-state", "key": "state", "required": True, "schema": _scalar_schema("state")},
    ]

    _validate_source_compatibility(
        document=document,
        source_call=source_call,
        current=document["collectionSnapshots"][0],
        desired=desired,
    )


def test_source_sync_rejects_removed_field_read_through_dict_get() -> None:
    document, source_call, desired = _source_document(expression='outputs.status.get("child")')
    object_schema = {
        "type": "object",
        "title": "status",
        "description": "",
        "properties": {"child": _scalar_schema("child")},
        "required": [],
        "additionalProperties": False,
    }
    document["collectionSnapshots"][0]["outputs"][0]["schema"] = object_schema
    desired["outputs"] = [{"id": "output-status", "key": "status", "required": True, "schema": {**object_schema, "properties": {}}}]

    with pytest.raises(InvariantError, match="表达式引用"):
        _validate_source_compatibility(
            document=document,
            source_call=source_call,
            current=document["collectionSnapshots"][0],
            desired=desired,
        )


def _sampled_source_document(expression: str) -> tuple[dict, dict, dict]:
    document, source_call, desired = _source_document(expression="")
    source_call["key"] = "status_call"
    source_call["sampleCount"] = 2
    document["workflow"]["nodes"][0]["topology"][0]["conditionExpression"] = expression
    document["collectionSnapshots"][0]["outputs"] = [
        {"id": "output-state", "key": "state", "required": True, "schema": _scalar_schema("state")}
    ]
    desired["outputs"] = [
        {"id": "output-other", "key": "other", "required": True, "schema": _scalar_schema("other")}
    ]
    return document, source_call, desired


@pytest.mark.parametrize("index", ["0", "-1", "sample_index"])
def test_source_sync_rejects_removed_field_through_keyed_sample_index(index: str) -> None:
    document, source_call, desired = _sampled_source_document(
        expression=f'outputs.status_call[{index}].state == "up"'
    )

    with pytest.raises(InvariantError, match="表达式引用"):
        _validate_source_compatibility(
            document=document,
            source_call=source_call,
            current=document["collectionSnapshots"][0],
            desired=desired,
        )


def test_source_sync_checks_each_call_when_definition_is_reused() -> None:
    document, source_call, desired = _source_document(expression="")
    second_call = {
        "id": "call-second",
        "key": "",
        "definition": {"id": "source", "revision": 1},
        "inputBindings": {},
    }
    document["workflow"]["nodes"].append(
        {
            "id": "second-step",
            "collectionCalls": [second_call],
            "topology": [{"id": "path", "conditionExpression": "outputs.status != ''"}],
        }
    )

    with pytest.raises(InvariantError, match="表达式引用"):
        _validate_source_compatibility(
            document=document,
            source_call=second_call,
            current=document["collectionSnapshots"][0],
            desired=desired,
        )


class CommandLibraryApiTest(ApiCommandTestCase):
    admin_headers = {"X-SkillHub-Admin-Key": "test-admin-key"}

    def test_system_command_crud_and_default_system_search(self) -> None:
        denied = self.client.get("/api/admin/system-commands")
        created = self.client.post(
            "/api/admin/system-commands",
            headers=self.admin_headers,
            json={
                "key": "display_interface",
                "expression": "display interface [brief] <name>",
                "metadata": {"name": "接口状态", "versions": ["V200R"]},
                "samples": [{"id": "sample-1", "name": "正常", "command": "display interface ge0", "stdout": "up"}],
                "outputSchema": {
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                    "additionalProperties": False,
                },
                "ttp": "Value STATUS (\\S+)",
            },
        )
        duplicate = self.client.post(
            "/api/admin/system-commands",
            headers=self.admin_headers,
            json={
                "key": "display_interface_duplicate",
                "expression": "display   interface [ brief ] <name>",
                "metadata": {"name": "重复"},
                "outputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            },
        )
        search = self.client.post(
            "/api/command-library/search",
            json={"command": "DISP int", "includeUser": False, "targetVersion": "v200r"},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(search.status_code, 200, search.text)
        self.assertEqual(search.json()["results"][0]["source"], "system")
        self.assertFalse(search.json()["results"][0]["complete"])
        self.assertEqual(search.json()["results"][0]["captures"], {})

        ambiguous = self.client.post(
            "/api/admin/system-commands",
            headers=self.admin_headers,
            json={
                "key": "show_status_or_value",
                "expression": "show { <value> | status }",
                "metadata": {"name": "状态或值"},
                "outputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            },
        )
        ambiguous_search = self.client.post(
            "/api/command-library/search",
            json={"command": "show status", "includeUser": False},
        )
        self.assertEqual(ambiguous.status_code, 200, ambiguous.text)
        ambiguous_results = [item for item in ambiguous_search.json()["results"] if item["id"] == ambiguous.json()["id"]]
        self.assertEqual(ambiguous_search.status_code, 200, ambiguous_search.text)
        self.assertEqual(len(ambiguous_results), 2)
        self.assertEqual({item["alternativeIndex"] for item in ambiguous_results}, {0, 1})
        self.assertTrue(all(item["ambiguous"] for item in ambiguous_results))

        command_id = created.json()["id"]
        updated = self.client.put(
            f"/api/admin/system-commands/{command_id}",
            headers=self.admin_headers,
            json={"metadata": {"name": "接口摘要"}, "outputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
        )
        deleted = self.client.delete(f"/api/admin/system-commands/{command_id}", headers=self.admin_headers)

        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["name"], "接口摘要")
        self.assertEqual(deleted.status_code, 200, deleted.text)

    def test_search_include_user_reads_entries_from_all_workflows(self) -> None:
        workflow = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"slug": "command-search-workflow", "owner_ref": "workflow-owner", "description": "命令库搜索测试。", "tags": []},
        )
        self.assertEqual(workflow.status_code, 200, workflow.text)
        with self.store._write_session() as connection:
            connection.execute(
                tables.user_command_library_entries.insert().values(
                    id="user-command-1",
                    owner_ref="another-user",
                    workflow_id=workflow.json()["workflow_id"],
                    collection_id="collection-memory",
                    key="display_memory",
                    name="内存",
                    description="",
                    expression="display memory",
                    normalized_expression="display memory",
                    captures={},
                    metadata={},
                    document={"metadata": {}, "samples": [], "outputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}, "ttp": ""},
                    enabled=True,
                    created_by="another-user",
                    updated_by="another-user",
                )
            )

        hidden = self.client.post("/api/command-library/search", json={"command": "display memory", "includeUser": False})
        visible = self.client.post("/api/command-library/search", json={"command": "display memory", "includeUser": True})

        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.json()["results"], [])
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(visible.json()["results"][0]["source"], "user")

    def test_system_source_refresh_rolls_back_when_a_condition_output_is_removed(self) -> None:
        system = self.client.post(
            "/api/admin/system-commands",
            headers=self.admin_headers,
            json={
                "key": "display_status",
                "expression": "display <name>",
                "metadata": {"name": "状态查询"},
                "outputSchema": {
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                    "additionalProperties": False,
                },
            },
        )
        workflow = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"slug": "system-source-workflow", "owner_ref": "workflow-owner", "description": "系统命令同步测试。", "tags": []},
        )
        self.assertEqual(system.status_code, 200, system.text)
        self.assertEqual(workflow.status_code, 200, workflow.text)
        skill_id = workflow.json()["skill_id"]
        document = self.client.get(f"/api/skills/{skill_id}/workflow").json()["document"]
        definition = {
            "id": "collection-system-source",
            "revision": 1,
            "key": "display_status",
            "metadata": {"name": "状态查询", "description": "", "industry": "", "device": "", "versions": [], "tags": []},
            "spec": {"collectionType": "cli", "commandTemplate": "display <name>", "outputSamples": []},
            "inputs": [{"id": "input_name", "key": "name", "required": True, "schema": _scalar_schema("name")}],
            "outputs": [{"id": "output_status", "key": "status", "required": True, "schema": _scalar_schema("status")}],
            "sourceSystemCommandId": system.json()["id"],
        }
        document["workflow"]["metadata"]["name"] = "系统命令同步"
        document["workflow"]["nodes"] = [
            {
                "id": "step",
                "name": "查询",
                "description": "",
                "isStart": True,
                "stepType": "expression",
                "collectionCalls": [
                    {
                        "id": "call-source",
                        "key": "",
                        "name": "状态查询",
                        "definition": {"id": definition["id"], "revision": 1},
                        "sampleCount": 1,
                        "inputBindings": {"input_name": {"kind": "literal", "reference": {}, "value": "ge0"}},
                    }
                ],
                "topology": [{"id": "path", "target": {"id": "done"}, "conditionText": "", "conditionExpression": "outputs.status != ''"}],
            },
            {"id": "done", "name": "完成", "rootCause": "", "repairRecommendation": "", "nodeType": "conclusion"},
        ]
        document["collectionSnapshots"] = [definition]
        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": document, "collection_changes": [{"operation": "create", "definition": definition, "sourceSystemCommandId": system.json()["id"]}]},
        )
        changed_system = self.client.put(
            f"/api/admin/system-commands/{system.json()['id']}",
            headers=self.admin_headers,
            json={
                "outputSchema": {
                    "type": "object",
                    "properties": {"state": {"type": "string"}},
                    "required": ["state"],
                    "additionalProperties": False,
                }
            },
        )
        rejected = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": saved.json()["document"], "collection_changes": []},
        )

        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(changed_system.status_code, 200, changed_system.text)
        self.assertEqual(rejected.status_code, 400, rejected.text)
        self.assertIn("表达式引用", rejected.json()["detail"])
        current = self.client.get(f"/api/skills/{skill_id}/workflow").json()["document"]
        self.assertEqual(current["collectionSnapshots"][0]["outputs"][0]["key"], "status")
