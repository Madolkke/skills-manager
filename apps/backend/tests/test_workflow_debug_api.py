from __future__ import annotations

from uuid import UUID

from fastapi import Depends

from skillhub.models.store import SkillHubStore
from skillhub.services.workflow_debug import WorkflowDebugService
from skillhub.services.workflow_debug_runtime import WorkflowDebugSettings
from skillhub.services.workflow_executor_client import RunStatusResponse
from skillhub.views.dependencies import session_dependency, workflow_debug_service_dependency
from tests.api_command_test_case import ApiCommandTestCase
from tests.executor_workflow_fixture import executor_workflow_document

RUN_ID = UUID("4cfe1b1e-4754-4563-8067-06c4f1949486")
ACTOR_HEADERS = {"X-SkillHub-Actor": "workflow-owner"}


class CapturingExecutor:
    def __init__(self) -> None:
        self.starts: list[dict] = []
        self.statuses: list[RunStatusResponse] = []

    def run_step(self, *, task_id, workflow_data, step_id):
        self.starts.append({"task_id": task_id, "workflow_data": workflow_data.model_dump(mode="json"), "step_id": step_id})
        return RUN_ID

    def get_run_status(self, *, run_id):
        assert str(run_id) == str(RUN_ID)
        return self.statuses.pop(0)

    def close(self) -> None:
        return None


class WorkflowDebugApiTest(ApiCommandTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.executor = CapturingExecutor()

        def dependency(session=Depends(session_dependency)):
            return WorkflowDebugService(
                SkillHubStore(session),
                WorkflowDebugSettings(executor_base_url="http://executor.test"),
                client_factory=lambda _url, _timeout: self.executor,
            )

        self.client.app.dependency_overrides[workflow_debug_service_dependency] = dependency

    def test_case_crud_run_contract_permissions_and_history(self) -> None:
        skill_id, document = self._create_executor_workflow("debug-api")
        denied = self.client.get(f"/api/skills/{skill_id}/workflow/debug-cases", headers={"X-SkillHub-Actor": "viewer"})
        self.assertEqual(denied.status_code, 403)

        created = self.client.post(
            f"/api/skills/{skill_id}/workflow/debug-cases",
            headers=ACTOR_HEADERS,
            json={
                "step_id": "step-prepare",
                "name": "命中复核步骤",
                "description": "检查失败也视为成功到达。",
                "expected_target_id": "step-confirm",
                "workflow_inputs": {"input-slot": None, "input-enabled": False},
                "collection_fixtures": {
                    "call-environment": {"raw_output": ["memory 82%"], "outputs": {"output-memory": 0.82}}
                },
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        case = created.json()
        self.assertIsNone(case["workflow_inputs"]["input-slot"])
        self.assertFalse(case["workflow_inputs"]["input-enabled"])
        self.assertEqual(self.client.get(f"/api/skills/{skill_id}/workflow/debug-cases", headers=ACTOR_HEADERS).json()[0]["id"], case["id"])

        patched = self.client.patch(
            f"/api/workflow-debug-cases/{case['id']}",
            headers=ACTOR_HEADERS,
            json={"name": "复核步骤失败路径"},
        )
        self.assertEqual(patched.json()["name"], "复核步骤失败路径")

        started = self.client.post(f"/api/workflow-debug-cases/{case['id']}/runs", headers=ACTOR_HEADERS)
        self.assertEqual(started.status_code, 200, started.text)
        run = started.json()["run"]
        executor_response = self.client.get(f"/api/skills/{skill_id}/workflow/executor").json()
        self.assertEqual(self.executor.starts[0]["workflow_data"], executor_response)
        self.assertEqual(set(self.executor.starts[0]), {"task_id", "workflow_data", "step_id"})
        self.assertNotIn("executor_identity", run)
        self.assertNotIn("revision", self.executor.starts[0]["workflow_data"])

        repeated = self.client.post(f"/api/workflow-debug-cases/{case['id']}/runs", headers=ACTOR_HEADERS)
        self.assertTrue(repeated.json()["reused"])
        blocked_delete = self.client.delete(f"/api/workflow-debug-cases/{case['id']}", headers=ACTOR_HEADERS)
        self.assertEqual(blocked_delete.status_code, 409)

        self.executor.statuses.append(_run_status(step_status="failure"))
        advanced = self.client.post(f"/api/workflow-debug-runs/{run['id']}/advance", headers=ACTOR_HEADERS)
        self.assertEqual(advanced.json()["status"], "completed")
        self.assertTrue(advanced.json()["passed"])
        history = self.client.get(f"/api/workflow-debug-cases/{case['id']}/runs?limit=10", headers=ACTOR_HEADERS)
        self.assertEqual(history.json()["items"][0]["id"], run["id"])
        self.assertIsNone(history.json()["next_cursor"])

        deleted = self.client.delete(f"/api/workflow-debug-cases/{case['id']}", headers=ACTOR_HEADERS)
        self.assertEqual(deleted.json(), {"deleted": True})
        self.assertEqual(self.client.get(f"/api/workflow-debug-runs/{run['id']}", headers=ACTOR_HEADERS).status_code, 404)

    def test_saving_workflow_deletes_cases_for_removed_steps(self) -> None:
        skill_id, document = self._create_executor_workflow("debug-step-delete")
        created = self.client.post(
            f"/api/skills/{skill_id}/workflow/debug-cases",
            headers=ACTOR_HEADERS,
            json={"step_id": "step-prepare", "name": "旧步骤", "expected_target_id": "step-confirm"},
        ).json()
        document["workflow"]["nodes"] = [node for node in document["workflow"]["nodes"] if node["id"] != "step-prepare"]

        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers=ACTOR_HEADERS,
            json={"document": document, "collection_changes": []},
        )

        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(self.client.get(f"/api/workflow-debug-cases/{created['id']}", headers=ACTOR_HEADERS).status_code, 404)

    def _create_executor_workflow(self, slug: str) -> tuple[str, dict]:
        created = self.client.post(
            "/api/workflows",
            headers=ACTOR_HEADERS,
            json={"slug": slug, "owner_ref": "workflow-owner", "description": "调试测试。", "tags": []},
        ).json()
        current = self.client.get(f"/api/skills/{created['skill_id']}/workflow", headers=ACTOR_HEADERS).json()
        document = executor_workflow_document(suffix=f"-{slug}")
        document["workflow"]["id"] = current["document"]["workflow"]["id"]
        saved = self.client.put(
            f"/api/skills/{created['skill_id']}/workflow",
            headers=ACTOR_HEADERS,
            json={
                "document": document,
                "collection_changes": [{"operation": "create", "definition": item} for item in document["collectionSnapshots"]],
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        return created["skill_id"], saved.json()["document"]


def _run_status(*, step_status: str) -> RunStatusResponse:
    return RunStatusResponse.model_validate(
        {
            "run_id": str(RUN_ID),
            "status": "running",
            "steps": [{"step_id": 3, "status": step_status, "flow_run_id": None, "result": None, "failure": None}],
            "conclusion_ids": [],
            "message": "Running",
            "paused_flow_run_id": None,
            "paused_key": None,
        }
    )
