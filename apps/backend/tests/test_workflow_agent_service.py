from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from skillhub.models.rules.workflow_agent_context import workflow_agent_draft_digest
from skillhub.models.rules.workflows import normalize_workflow_document
from skillhub.services.workflow_agent import WorkflowAgentService
from skillhub.services.workflow_agent_runtime import WorkflowAgentRuntime
from skillhub.services.workflow_agent_settings import WorkflowAgentSettings
from tests.executor_workflow_fixture import executor_workflow_document


class AgentStoreFake:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.inserted: dict[str, Any] | None = None

    def require_workflow_agent_access(self, **_):
        return None

    def workflow_agent_run_source(self, **_):
        return {
            "session": {"id": "session-1", "skill_id": "skill-1", "status": "active", "actor_ref": "actor-1", "title": "", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)},
            "workflow_revision": 4,
            "workflow_digest": "saved-digest",
            "workflow_id": self.document["workflow"]["id"],
            "recent_history": [],
        }

    def list_workflow_debug_cases(self, **_):
        return []

    def insert_workflow_agent_run(self, *, values):
        self.inserted = values
        return {"id": "run-1", **values}


def test_service_persists_context_projection_without_full_workflow_document() -> None:
    document = normalize_workflow_document(executor_workflow_document(suffix="-service"))
    store = AgentStoreFake(document)
    runtime = WorkflowAgentRuntime(
        lambda: store,  # type: ignore[arg-type]
        WorkflowAgentSettings(
            database_url="postgresql+psycopg://localhost/skillhub",
            base_url="https://provider.example/v1",
            api_key="key",
            model="model",
        ),
    )
    service = WorkflowAgentService(store, runtime)  # type: ignore[arg-type]

    service.create_run(
        session_id="session-1",
        agent_id="workflow_assistant",
        content="解释当前流程",
        base_revision=4,
        draft=document,
        selection={"type": "metadata"},
        actor="actor-1",
    )

    assert store.inserted is not None
    assert "document" not in store.inserted["context_snapshot"]
    assert store.inserted["context_snapshot"]["agent_context"]["workflow"]["id"] == document["workflow"]["id"]
    assert store.inserted["draft_digest"] == workflow_agent_draft_digest(document)


def test_service_schedules_run_from_an_async_background_task() -> None:
    scheduled: list[str] = []

    class RuntimeFake:
        def schedule(self, run_id: str) -> None:
            scheduled.append(run_id)

    service = WorkflowAgentService(object(), RuntimeFake())  # type: ignore[arg-type]

    asyncio.run(service.schedule_run("run-1"))

    assert scheduled == ["run-1"]
