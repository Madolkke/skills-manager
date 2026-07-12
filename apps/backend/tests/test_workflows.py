from __future__ import annotations

import json

from sqlalchemy import select

from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


class WorkflowApiTest(ApiCommandTestCase):
    def test_workflow_create_save_sync_and_reactivate(self):
        created = self._create_workflow("interface-check")
        skill_id = created["skill_id"]
        initial = self.client.get(f"/api/skills/{skill_id}").json()
        workflow = self.client.get(f"/api/skills/{skill_id}/workflow").json()

        self.assertEqual(initial["workflow"]["status"], "never_synced")
        self.assertEqual(workflow["document"]["workflow"]["metadata"]["name"], "interface-check")
        self.assertEqual(initial["versions"][0]["bundle_files"][0]["content_text"].count("---"), 2)
        self.assertNotIn("# interface-check", initial["versions"][0]["bundle_files"][0]["content_text"])

        definition = self._definition()
        document = self._valid_document(workflow["document"], definition)
        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": document, "collection_changes": [{"operation": "create", "definition": definition}]},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["revision"], 2)
        self.assertEqual(saved.json()["validation"]["errors"], [])

        catalog = self.client.get(f"/api/skills/{skill_id}/workflow/collections").json()
        self.assertEqual(catalog["definitions"][0]["id"], "collection-interface")

        synced = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "0.0.2", "display_name": "Workflow v2", "change_summary": "同步排障流程。"},
        )
        self.assertEqual(synced.status_code, 200, synced.text)
        self.assertEqual(synced.json()["mode"], "created")
        generated_version_id = synced.json()["skill_version_id"]

        synced_detail = self.client.get(f"/api/skills/{skill_id}").json()
        generated = next(item for item in synced_detail["versions"] if item["id"] == generated_version_id)
        markdown = generated["bundle_files"][0]["content_text"]
        self.assertIn("display interface", markdown)
        self.assertIn("接口 Down 示例", markdown)
        self.assertNotIn("SECRET RAW OUTPUT", markdown)
        self.assertEqual(generated["workflow_sync"]["workflow_revision"], 2)
        self.assertEqual(synced_detail["workflow"]["status"], "in_sync")
        self.assertEqual([item["path"] for item in generated["bundle_files"]], ["SKILL.md"])
        with self.engine.connect() as connection:
            sync_row = connection.execute(select(tables.workflow_syncs).where(tables.workflow_syncs.c.skill_version_id == generated_version_id)).mappings().one()
            source_text = connection.execute(select(tables.artifacts.c.content_text).where(tables.artifacts.c.id == sync_row["source_artifact_id"])).scalar_one()
        self.assertEqual(json.loads(source_text), saved.json()["document"])

        already_current = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "8.8.8", "change_summary": "不会创建重复版本。"},
        )
        self.assertEqual(already_current.json()["mode"], "already_current")
        self.assertEqual(len(self.client.get(f"/api/skills/{skill_id}").json()["versions"]), 2)

        manual = self.client.post(
            "/api/skill-versions",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"skill_id": skill_id, "source": self.bundle_source("interface-check", skill_md_body="Manual version."), "version": "0.0.3", "make_current": True},
        )
        self.assertEqual(manual.status_code, 200)
        self.assertEqual(self.client.get(f"/api/skills/{skill_id}").json()["workflow"]["status"], "skill_changed")

        reactivated = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "9.9.9", "change_summary": "不会创建重复版本。"},
        )
        final_detail = self.client.get(f"/api/skills/{skill_id}").json()
        self.assertEqual(reactivated.status_code, 200)
        self.assertEqual(reactivated.json()["mode"], "reactivated")
        self.assertEqual(final_detail["skill"]["current_version_id"], generated_version_id)
        self.assertEqual(len(final_detail["versions"]), 3)

    def test_invalid_draft_can_save_but_cannot_sync_and_viewer_cannot_write(self):
        created = self._create_workflow("invalid-workflow")
        skill_id = created["skill_id"]
        detail = self.client.get(f"/api/skills/{skill_id}/workflow").json()
        detail["document"]["workflow"]["metadata"]["code"] = "INVALID-1"

        denied = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "viewer"},
            json={"document": detail["document"], "collection_changes": []},
        )
        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": detail["document"], "collection_changes": []},
        )
        sync = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "0.0.2", "change_summary": "invalid"},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["validation"]["errors"][0]["code"], "NO_START_STEP")
        self.assertEqual(sync.status_code, 400)
        self.assertEqual(sync.json()["field_errors"][0]["code"], "workflow.not_syncable")

    def test_incomplete_collection_can_save_but_cannot_sync(self):
        created = self._create_workflow("incomplete-collection")
        skill_id = created["skill_id"]
        detail = self.client.get(f"/api/skills/{skill_id}/workflow").json()
        definition = self._definition()
        definition["metadata"]["name"] = ""
        definition["spec"]["commandTemplate"] = ""

        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={
                "document": self._valid_document(detail["document"], definition),
                "collection_changes": [{"operation": "create", "definition": definition}],
            },
        )
        sync = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "0.0.2", "change_summary": "incomplete collection"},
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            {item["code"] for item in saved.json()["validation"]["errors"]},
            {"MISSING_COLLECTION_NAME", "MISSING_COLLECTION_COMMAND"},
        )
        self.assertEqual(sync.status_code, 400)
        self.assertEqual(sync.json()["field_errors"][0]["code"], "workflow.not_syncable")

    def test_metadata_patch_can_save_invalid_draft_but_creation_rejects_blank_description(self):
        blank_create = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"slug": "blank-description", "owner_ref": "workflow-owner", "description": "   ", "tags": []},
        )
        created = self._create_workflow("metadata-draft")
        patched = self.client.patch(
            f"/api/skills/{created['skill_id']}/workflow/metadata",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"name": "", "code": "", "description": "", "industry": "", "device": "", "versions": []},
        )

        self.assertEqual(blank_create.status_code, 400)
        self.assertEqual(blank_create.json()["field_errors"][0]["code"], "workflow.description_required")
        self.assertEqual(patched.status_code, 200)
        self.assertEqual({item["code"] for item in patched.json()["validation"]["errors"]}, {"MISSING_WORKFLOW_NAME", "MISSING_WORKFLOW_DESCRIPTION", "NO_START_STEP"})

    def test_catalog_is_global_and_revise_creates_immutable_revision(self):
        first = self._create_workflow("first-workflow")
        first_detail = self.client.get(f"/api/skills/{first['skill_id']}/workflow").json()
        definition = self._definition()
        first_document = self._valid_document(first_detail["document"], definition)
        self.client.put(
            f"/api/skills/{first['skill_id']}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": first_document, "collection_changes": [{"operation": "create", "definition": definition}]},
        )

        second = self._create_workflow("second-workflow")
        second_catalog = self.client.get(f"/api/skills/{second['skill_id']}/workflow/collections").json()["definitions"]
        self.assertEqual(second_catalog[0]["revision"], 1)
        revised = {**second_catalog[0], "metadata": {**second_catalog[0]["metadata"], "name": "接口状态 v2"}}
        second_document = self.client.get(f"/api/skills/{second['skill_id']}/workflow").json()["document"]
        response = self.client.put(
            f"/api/skills/{second['skill_id']}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": second_document, "collection_changes": [{"operation": "revise", "definition": revised}]},
        )
        latest = self.client.get(f"/api/skills/{first['skill_id']}/workflow/collections").json()["definitions"][0]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(latest["revision"], 2)
        self.assertEqual(latest["metadata"]["name"], "接口状态 v2")
        self.assertEqual(self.client.get(f"/api/skills/{first['skill_id']}/workflow").json()["document"]["collectionSnapshots"][0]["revision"], 1)
        actions = [item["action"] for item in self.client.get(f"/api/skills/{second['skill_id']}/audit-events").json()]
        self.assertIn("workflow.collection_revise", actions)

    def test_save_is_idempotent_and_uses_last_writer_wins(self):
        created = self._create_workflow("last-writer-workflow")
        skill_id = created["skill_id"]
        original = self.client.get(f"/api/skills/{skill_id}/workflow").json()
        first_document = json.loads(json.dumps(original["document"]))
        first_document["workflow"]["metadata"]["name"] = "First writer"
        first = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": first_document, "collection_changes": []},
        )

        stale_document = json.loads(json.dumps(original["document"]))
        stale_document["workflow"]["metadata"]["description"] = "Second writer replaces the whole document."
        second = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": stale_document, "collection_changes": []},
        )
        no_op = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": second.json()["document"], "collection_changes": []},
        )

        self.assertEqual(first.json()["revision"], 2)
        self.assertEqual(second.json()["revision"], 3)
        self.assertEqual(second.json()["document"]["workflow"]["metadata"]["name"], "last-writer-workflow")
        self.assertEqual(no_op.json()["revision"], 3)

    def test_sync_version_conflict_rolls_back_all_workflow_sync_writes(self):
        created = self._create_workflow("workflow-conflict")
        skill_id = created["skill_id"]
        detail = self.client.get(f"/api/skills/{skill_id}/workflow").json()
        definition = self._definition()
        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": self._valid_document(detail["document"], definition), "collection_changes": [{"operation": "create", "definition": definition}]},
        )
        self.assertEqual(saved.status_code, 200)
        manual = self.client.post(
            "/api/skill-versions",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"skill_id": skill_id, "source": self.bundle_source("workflow-conflict", skill_md_body="Manual."), "version": "0.0.2", "make_current": False},
        )
        self.assertEqual(manual.status_code, 200)

        conflict = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "0.0.2", "change_summary": "conflict"},
        )

        final_detail = self.client.get(f"/api/skills/{skill_id}").json()
        with self.engine.connect() as connection:
            sync_count = connection.execute(select(tables.workflow_syncs).where(tables.workflow_syncs.c.workflow_id == created["workflow_id"])).scalars().all()
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(sync_count, [])
        self.assertEqual(final_detail["workflow"]["status"], "never_synced")
        self.assertEqual(len(final_detail["versions"]), 2)

    def test_create_rolls_back_skill_when_required_tags_are_missing(self):
        group = self.client.post(
            "/api/admin/tag-groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"id": "required-domain", "display_name": "必选领域", "description": ""},
        )
        self.assertEqual(group.status_code, 200)
        value = self.client.post(
            "/api/admin/tag-groups/required-domain/values",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"value": "network", "description": ""},
        )
        required = self.client.patch(
            "/api/admin/tag-groups/required-domain",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"display_name": "必选领域", "description": "", "required": True},
        )
        self.assertEqual(value.status_code, 200)
        self.assertEqual(required.status_code, 200)

        response = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"slug": "workflow-missing-tag", "owner_ref": "workflow-owner", "description": "Should roll back.", "tags": []},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["code"], "skill_tag.required_group_missing")
        self.assertNotIn("workflow-missing-tag", [item["skill"]["slug"] for item in self.client.get("/api/skills").json()])

    def test_import_bundle_creates_independent_collections_and_rewrites_references(self):
        created = self._create_workflow("import-workflow")
        skill_id = created["skill_id"]
        imported = self.client.post(
            f"/api/skills/{skill_id}/workflow/import",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json=self._import_bundle(),
        )

        self.assertEqual(imported.status_code, 200, imported.text)
        result = imported.json()
        self.assertEqual(result["id"], created["workflow_id"])
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["document"]["workflow"]["id"], created["workflow_id"])
        self.assertEqual(result["validation"]["errors"], [])
        mappings = {item["local_id"]: item for item in result["import_result"]["collection_mappings"]}
        self.assertEqual(set(mappings), {"interface-status", "unused-diagnostics"})
        self.assertEqual({item["revision"] for item in mappings.values()}, {1})
        call_ref = result["document"]["workflow"]["nodes"][0]["collectionCalls"][0]["definition"]
        self.assertEqual(call_ref, {"id": mappings["interface-status"]["definition_id"], "revision": 1})
        self.assertEqual(len(result["document"]["collectionSnapshots"]), 1)

        catalog = self.client.get(f"/api/skills/{skill_id}/workflow/collections").json()["definitions"]
        self.assertEqual({item["id"] for item in catalog}, {item["definition_id"] for item in mappings.values()})
        actions = [item["action"] for item in self.client.get(f"/api/skills/{skill_id}/audit-events").json()]
        self.assertIn("workflow.imported", actions)

        synced = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"version": "0.0.2", "change_summary": "imported workflow"},
        )
        self.assertEqual(synced.status_code, 200, synced.text)
        repeated = self.client.post(
            f"/api/skills/{skill_id}/workflow/import",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json=self._import_bundle(),
        )
        repeated_mappings = {item["definition_id"] for item in repeated.json()["import_result"]["collection_mappings"]}
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["revision"], 3)
        self.assertEqual(repeated.json()["sync"]["status"], "workflow_changed")
        self.assertTrue(repeated_mappings.isdisjoint({item["definition_id"] for item in mappings.values()}))
        self.assertEqual(len(self.client.get(f"/api/skills/{skill_id}/workflow/collections").json()["definitions"]), 4)

    def test_import_bundle_rejects_bad_references_permissions_and_rolls_back(self):
        created = self._create_workflow("invalid-import-workflow")
        skill_id = created["skill_id"]
        missing = self._import_bundle()
        missing["workflow"]["nodes"][0]["collectionCalls"][0]["definitionLocalId"] = "missing"
        missing_response = self.client.post(
            f"/api/skills/{skill_id}/workflow/import",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json=missing,
        )
        duplicate = self._import_bundle()
        duplicate["collections"].append(dict(duplicate["collections"][0]))
        duplicate_response = self.client.post(
            f"/api/skills/{skill_id}/workflow/import",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json=duplicate,
        )
        denied = self.client.post(
            f"/api/skills/{skill_id}/workflow/import",
            headers={"X-SkillHub-Actor": "viewer"},
            json=self._import_bundle(),
        )

        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(denied.status_code, 403)
        detail = self.client.get(f"/api/skills/{skill_id}/workflow").json()
        self.assertEqual(detail["revision"], 1)
        self.assertEqual(self.client.get(f"/api/skills/{skill_id}/workflow/collections").json()["definitions"], [])

    def test_import_bundle_allows_domain_invalid_draft(self):
        created = self._create_workflow("draft-import-workflow")
        bundle = self._import_bundle()
        bundle["workflow"]["metadata"]["name"] = ""
        bundle["workflow"]["nodes"] = []

        response = self.client.post(
            f"/api/skills/{created['skill_id']}/workflow/import",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json=bundle,
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            {item["code"] for item in response.json()["validation"]["errors"]},
            {"MISSING_WORKFLOW_NAME", "NO_START_STEP"},
        )

    def _create_workflow(self, slug: str) -> dict:
        response = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"slug": slug, "owner_ref": "workflow-owner", "description": "排查网络接口状态。", "tags": []},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _definition(self) -> dict:
        return {
            "id": "collection-interface",
            "revision": 1,
            "key": "interface_status",
            "metadata": {"name": "接口状态", "description": "查询接口状态。", "industry": "网络", "device": "交换机", "versions": [], "tags": []},
            "spec": {
                "collectionType": "cli",
                "commandTemplate": "display interface {{ interfaceName }}",
                "outputSamples": [{"id": "sample-down", "name": "接口 Down 示例", "stdout": "SECRET RAW OUTPUT", "inputValues": {"interfaceName": "10GE1/0/1"}}],
            },
            "inputs": [],
            "outputs": [{"id": "output-state", "key": "state", "name": "状态", "description": "接口状态", "dataType": "string"}],
        }

    def _import_bundle(self) -> dict:
        used = self._definition()
        used.pop("id")
        used.pop("revision")
        used["localId"] = "interface-status"
        unused = json.loads(json.dumps(used))
        unused["localId"] = "unused-diagnostics"
        unused["key"] = "unused_diagnostics"
        unused["metadata"]["name"] = "未引用诊断采集"
        return {
            "documentType": "workflow_import_bundle",
            "workflow": {
                "metadata": {"name": "接口状态导入", "code": "IMPORT", "description": "分析接口状态。", "industry": "网络", "device": "交换机", "versions": []},
                "inputs": [],
                "deviceRoles": [],
                "nodes": [
                    {
                        "id": "step-import",
                        "name": "分析接口状态",
                        "description": "",
                        "isStart": True,
                        "inputs": [
                            {
                                "parameter": {"id": "step-input-cli", "key": "cli_text", "name": "命令回显", "description": "", "dataType": "string", "required": True},
                                "binding": {"kind": "collection_output", "reference": {"call_id": "call-interface", "output_id": "output-state"}},
                            }
                        ],
                        "collectionCalls": [{"id": "call-interface", "key": "interface", "name": "接口状态", "definitionLocalId": "interface-status", "sampleCount": 1, "inputBindings": {}}],
                        "topology": [{"id": "transition-done", "target": {"id": "conclusion-done"}, "conditionText": "分析完成", "conditionExpression": ""}],
                        "stepType": "script",
                        "script": {"language": "python", "source": "def main(context):\n    return 'transition-done'", "options": {}},
                    },
                    {"id": "conclusion-done", "name": "完成", "rootCause": "接口异常。", "repairRecommendation": "修复接口。", "nodeType": "conclusion"},
                ],
            },
            "collections": [used, unused],
        }

    def _valid_document(self, document: dict, definition: dict) -> dict:
        workflow = document["workflow"]
        workflow["nodes"] = [
            {
                "id": "step-start",
                "name": "检查接口",
                "description": "采集接口状态。",
                "isStart": True,
                "inputs": [],
                "collectionCalls": [{"id": "call-interface", "key": "interface", "name": "接口状态", "definition": {"id": definition["id"], "revision": definition["revision"]}, "sampleCount": 1, "inputBindings": {}}],
                "topology": [{"id": "transition-done", "target": {"id": "conclusion-done"}, "conditionText": "采集完成", "conditionExpression": "interface.state != ''"}],
                "stepType": "expression",
            },
            {"id": "conclusion-done", "name": "完成", "rootCause": "接口异常。", "repairRecommendation": "修复接口。", "nodeType": "conclusion"},
        ]
        workflow["metadata"]["name"] = "接口状态排查"
        document["collectionSnapshots"] = [definition]
        return document
