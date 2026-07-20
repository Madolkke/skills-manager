from __future__ import annotations

from typing import Any

from skillhub.models.rules.workflows import format_workflow_document
from skillhub.services import WorkflowService
from tests.api_command_test_case import ApiCommandTestCase


def test_format_workflow_document_returns_deep_copy() -> None:
    document = {
        "documentType": "workflow_bundle",
        "workflow": {"id": "workflow_1", "nodes": [{"id": "node_1"}]},
    }

    formatted = format_workflow_document(document)

    assert formatted == document
    assert formatted is not document
    assert formatted["workflow"] is not document["workflow"]
    assert formatted["workflow"]["nodes"] is not document["workflow"]["nodes"]


def test_workflow_service_formats_only_document() -> None:
    class WorkflowDetailStore:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def workflow_detail(self, **kwargs: str) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {
                "id": "workflow_1",
                "revision": 3,
                "document": {"documentType": "workflow_bundle", "workflow": {"id": "workflow_1"}},
                "validation": {"errors": []},
            }

    store = WorkflowDetailStore()
    service = WorkflowService(store)  # type: ignore[arg-type]

    result = service.formatted_workflow(skill_id="skill_1", actor="owner")

    assert result == {"documentType": "workflow_bundle", "workflow": {"id": "workflow_1"}}
    assert store.calls == [{"skill_id": "skill_1", "actor": "owner"}]


class FormattedWorkflowApiTest(ApiCommandTestCase):
    def test_formatted_workflow_returns_only_current_document(self) -> None:
        created = self._create_workflow("formatted-workflow")
        skill_id = created["skill_id"]

        ordinary = self.client.get(f"/api/skills/{skill_id}/workflow")
        formatted = self.client.get(f"/api/skills/{skill_id}/workflow/formatted")

        self.assertEqual(formatted.status_code, 200, formatted.text)
        self.assertEqual(formatted.json(), ordinary.json()["document"])
        for field in ("revision", "validation", "sync", "capabilities"):
            self.assertNotIn(field, formatted.json())

    def test_formatted_workflow_preserves_existing_not_found_errors(self) -> None:
        standard_skill = self.create_skill("formatted-standard")

        missing = self.client.get("/api/skills/missing/workflow/formatted")
        standard = self.client.get(f"/api/skills/{standard_skill['skill_id']}/workflow/formatted")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), {"detail": "Skill not found: missing"})
        self.assertEqual(standard.status_code, 404)
        self.assertEqual(
            standard.json(),
            {"detail": f"Workflow not found for skill: {standard_skill['skill_id']}"},
        )

    def _create_workflow(self, slug: str) -> dict[str, Any]:
        response = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={
                "slug": slug,
                "owner_ref": "workflow-owner",
                "description": "验证格式化 Workflow 接口。",
                "tags": [],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()
