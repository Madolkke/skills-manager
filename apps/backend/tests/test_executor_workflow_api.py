from __future__ import annotations

from typing import Any

from tests.api_command_test_case import ApiCommandTestCase
from tests.executor_workflow_fixture import executor_workflow_document


class ExecutorWorkflowApiTest(ApiCommandTestCase):
    def test_executor_workflow_is_unauthenticated_flat_current_projection(self) -> None:
        created, document = self._create_executor_workflow("executor-current")
        skill_id = created["skill_id"]

        response = self.client.get(f"/api/skills/{skill_id}/workflow/executor")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], 1)
        self.assertEqual(response.json()["name"], "PTN故障快排")
        self.assertNotIn("revision", response.json())
        self.assertNotIn("document", response.json())
        self.assertNotIn("validation", response.json())

        document["workflow"]["metadata"]["name"] = "PTN故障快排 v2"
        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": document, "collection_changes": []},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        current = self.client.get(f"/api/skills/{skill_id}/workflow/executor", headers={"X-SkillHub-Actor": "unrelated"})
        self.assertEqual(current.status_code, 200, current.text)
        self.assertEqual(current.json()["name"], "PTN故障快排 v2")

    def test_executor_workflow_preserves_not_found_semantics(self) -> None:
        standard_skill = self.create_skill("executor-standard")

        missing = self.client.get("/api/skills/missing/workflow/executor")
        standard = self.client.get(f"/api/skills/{standard_skill['skill_id']}/workflow/executor")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), {"detail": "Skill not found: missing"})
        self.assertEqual(standard.status_code, 404)
        self.assertEqual(standard.json(), {"detail": f"Workflow not found for skill: {standard_skill['skill_id']}"})

    def test_executor_workflow_returns_structured_conversion_errors(self) -> None:
        created, document = self._create_executor_workflow("executor-invalid")
        document["workflow"]["nodes"][0]["collectionCalls"][0]["sampleCount"] = 2
        saved = self.client.put(
            f"/api/skills/{created['skill_id']}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": document, "collection_changes": []},
        )
        self.assertEqual(saved.status_code, 200, saved.text)

        response = self.client.get(f"/api/skills/{created['skill_id']}/workflow/executor")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Workflow 无法转换为执行器定义。")
        self.assertEqual(response.json()["field_errors"][0]["code"], "executor_workflow.unsupported_sample_count")

    def _create_executor_workflow(self, slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
        created_response = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"slug": slug, "owner_ref": "workflow-owner", "description": "执行器测试。", "tags": []},
        )
        self.assertEqual(created_response.status_code, 200, created_response.text)
        created = created_response.json()
        current = self.client.get(
            f"/api/skills/{created['skill_id']}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
        ).json()
        document = executor_workflow_document(suffix=f"-{slug}")
        document["workflow"]["id"] = current["document"]["workflow"]["id"]
        collection_changes = [{"operation": "create", "definition": item} for item in document["collectionSnapshots"]]
        saved = self.client.put(
            f"/api/skills/{created['skill_id']}/workflow",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"document": document, "collection_changes": collection_changes},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        return created, saved.json()["document"]
