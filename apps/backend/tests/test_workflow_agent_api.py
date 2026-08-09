from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillhub.views.dependencies import workflow_agent_service_dependency
from skillhub.views.workflow_agent import register_workflow_agent_routes


class FakeWorkflowAgentService:
    def __init__(self) -> None:
        self.scheduled: list[str] = []

    def catalog(self, **_):
        return {"agents": [], "available": True, "unavailable_reason": "", "agentscope_version": "2.0.6"}

    def create_run(self, **values):
        return _run(values["selection"])

    def schedule_run(self, run_id: str) -> None:
        self.scheduled.append(run_id)

    def get_run(self, **_):
        return _run({"type": "metadata"}, status="completed")

    def event_stream(self, **_):
        async def events():
            yield {"sequence": 4, "payload": {"id": "native-4", "type": "THINKING_BLOCK_DELTA", "delta": "reason"}}

        return events()


def _client(service: FakeWorkflowAgentService) -> TestClient:
    app = FastAPI()
    register_workflow_agent_routes(app)
    app.dependency_overrides[workflow_agent_service_dependency] = lambda: service
    return TestClient(app)


def test_start_schedules_run_and_preserves_selection_aliases() -> None:
    service = FakeWorkflowAgentService()
    response = _client(service).post(
        "/api/workflow-agent-sessions/session-1/runs",
        json={
            "agent_id": "workflow_assistant",
            "content": "检查当前步骤",
            "base_revision": 3,
            "draft": {},
            "selection": {"type": "step", "id": "step-1", "itemId": "call-1"},
        },
    )

    assert response.status_code == 200
    assert response.json()["selection"]["itemId"] == "call-1"
    assert service.scheduled == ["run-1"]


def test_sse_wraps_native_event_and_uses_sequence_id() -> None:
    response = _client(FakeWorkflowAgentService()).get(
        "/api/workflow-agent-runs/run-1/events?after=2",
        headers={"Last-Event-ID": "3"},
    )

    assert response.status_code == 200
    assert "id: 4" in response.text
    assert "event: agentscope" in response.text
    assert '"event_id":4' in response.text
    assert '"type":"THINKING_BLOCK_DELTA"' in response.text


def _run(selection, *, status="starting"):
    return {
        "id": "run-1",
        "session_id": "session-1",
        "skill_id": "skill-1",
        "agent_id": "workflow_assistant",
        "status": status,
        "user_input": "检查当前步骤",
        "response_text": "",
        "selection": selection,
        "base_revision": 3,
        "base_workflow_digest": "saved",
        "draft_digest": "draft",
        "cancel_requested": False,
        "usage": {},
        "error": None,
        "created_by": "product-operator",
        "started_at": None,
        "finished_at": None,
        "created_at": "2026-08-09T00:00:00Z",
        "updated_at": "2026-08-09T00:00:00Z",
        "proposal": None,
    }
