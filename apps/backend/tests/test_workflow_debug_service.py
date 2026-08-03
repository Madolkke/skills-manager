from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from skillhub.models.errors import ConflictError, ServiceUnavailableError
from skillhub.models.rules.executor_workflows import project_workflow_document
from skillhub.services.workflow_debug import WorkflowDebugService
from skillhub.services.workflow_debug_runtime import WorkflowDebugSettings
from skillhub.services.workflow_executor_client import (
    RunStatusResponse,
    WorkflowExecutorNetworkError,
    WorkflowExecutorServerResponseError,
    WorkflowExecutorTimeoutError,
)
from tests.executor_workflow_fixture import executor_workflow_document

RUN_ID = UUID("4cfe1b1e-4754-4563-8067-06c4f1949486")


class FakeStore:
    def __init__(self, document: dict) -> None:
        self.document = document
        self.run: dict | None = None
        self.case = {
            "id": "case-1",
            "skill_id": "skill-1",
            "step_id": "step-prepare",
            "name": "命中复核步骤",
            "description": "",
            "expected_target_id": "step-confirm",
            "workflow_inputs": {"input-slot": "1"},
            "collection_fixtures": {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    def workflow_debug_start_source(self, *, case_id: str, actor: str) -> dict:
        assert (case_id, actor) == ("case-1", "owner")
        return {
            "case": self.case,
            "active_run": self.run if self.run and self.run["status"] in {"starting", "running", "paused", "external_state_unknown"} else None,
            "workflow_revision": 7,
            "workflow_digest": "d" * 64,
            "document": self.document,
        }

    def insert_workflow_debug_run(self, *, values: dict) -> dict:
        self.run = {"id": "debug-run-1", **values, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}
        return dict(self.run)

    def update_workflow_debug_run(self, *, run_id: str, values: dict, actor: str) -> dict:
        assert self.run is not None and run_id == self.run["id"] and actor == "owner"
        self.run.update(values)
        self.run["updated_at"] = datetime.now(timezone.utc)
        return dict(self.run)

    def workflow_debug_run(self, *, run_id: str, actor: str, for_update: bool = False) -> dict:
        assert self.run is not None and run_id == self.run["id"] and actor == "owner"
        return dict(self.run)


class FakeExecutorClient:
    def __init__(self) -> None:
        self.started = None
        self.statuses: list[RunStatusResponse] = []
        self.paused_schema: dict | None = None
        self.resume_calls: list[dict] = []
        self.resume_attempts = 0
        self.resume_error: Exception | None = None
        self.closed = False
        self.start_error: Exception | None = None
        self.status_error: Exception | None = None

    def run_step(self, *, task_id: str, workflow_data, step_id: int) -> UUID:
        if self.start_error is not None:
            raise self.start_error
        self.started = {"task_id": task_id, "workflow_data": workflow_data.model_dump(mode="json"), "step_id": step_id}
        return RUN_ID

    def get_run_status(self, *, run_id):
        assert str(run_id) == str(RUN_ID)
        if self.status_error is not None:
            error, self.status_error = self.status_error, None
            raise error
        return self.statuses.pop(0)

    def get_paused_schema(self, *, run_id, flow_run_id):
        assert str(run_id) == str(RUN_ID) and flow_run_id == "flow-1"
        assert self.paused_schema is not None
        return self.paused_schema

    def resume(self, *, run_id, flow_run_id, run_input):
        self.resume_attempts += 1
        if self.resume_error is not None:
            raise self.resume_error
        self.resume_calls.append({"run_id": str(run_id), "flow_run_id": flow_run_id, "run_input": run_input})

    def close(self) -> None:
        self.closed = True


def _service(store: FakeStore, client: FakeExecutorClient) -> WorkflowDebugService:
    return WorkflowDebugService(
        store,
        WorkflowDebugSettings(executor_base_url="http://executor.test"),
        client_factory=lambda _url, _timeout: client,
    )


def _status(*, status: str, step_status: str = "running") -> RunStatusResponse:
    return RunStatusResponse.model_validate(
        {
            "run_id": str(RUN_ID),
            "status": status,
            "steps": [{"step_id": 3, "status": step_status, "flow_run_id": None, "result": None, "failure": None}],
            "conclusion_ids": [],
            "message": status,
            "paused_flow_run_id": None,
            "paused_key": None,
        }
    )


def _paused_status() -> RunStatusResponse:
    return RunStatusResponse.model_validate(
        {
            "run_id": str(RUN_ID),
            "status": "paused",
            "steps": [{"step_id": 2, "status": "paused", "flow_run_id": "flow-1", "result": None, "failure": None}],
            "conclusion_ids": [],
            "message": "Paused",
            "paused_flow_run_id": "flow-1",
            "paused_key": "inputs",
        }
    )


def test_start_uses_exact_executor_projection_and_hides_internal_mapping() -> None:
    document = executor_workflow_document()
    store = FakeStore(document)
    client = FakeExecutorClient()

    result = _service(store, client).start_run(case_id="case-1", actor="owner")

    assert client.started is not None
    assert client.started["workflow_data"] == project_workflow_document(document).workflow.model_dump(mode="json")
    assert set(client.started) == {"task_id", "workflow_data", "step_id"}
    assert client.started["step_id"] == 2
    assert "executor_identity" not in result["run"]
    assert result["run"]["workflow_revision"] == 7
    assert result["run"]["poll_interval_seconds"] == 2
    assert result["reused"] is False


def test_step_failure_still_passes_when_expected_target_was_reached() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    service = _service(store, client)
    started = service.start_run(case_id="case-1", actor="owner")["run"]
    client.closed = False
    client.statuses.append(_status(status="running", step_status="failure"))

    completed = service.advance_run(run_id=started["id"], actor="owner")

    assert completed["status"] == "completed"
    assert completed["passed"] is True
    assert completed["latest_executor_status"]["steps"][0]["status"] == "failure"


def test_executor_terminal_without_expected_target_is_failed_assertion() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    service = _service(store, client)
    started = service.start_run(case_id="case-1", actor="owner")["run"]
    client.closed = False
    client.statuses.append(_status(status="success", step_status="running"))

    completed = service.advance_run(run_id=started["id"], actor="owner")

    assert completed["status"] == "completed"
    assert completed["passed"] is False


def test_pause_is_resumed_once_with_case_input_and_schema_default() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    client.paused_schema = {
        "type": "object",
        "properties": {
            "slot-id": {"type": "string"},
            "limit": {"type": "integer", "default": 2},
        },
        "required": ["slot-id", "limit"],
    }
    service = _service(store, client)
    started = service.start_run(case_id="case-1", actor="owner")["run"]
    client.statuses.append(_paused_status())

    resumed = service.advance_run(run_id=started["id"], actor="owner")

    assert resumed["status"] == "running"
    assert client.resume_calls == [
        {"run_id": str(RUN_ID), "flow_run_id": "flow-1", "run_input": {"slot-id": "1", "limit": 2}}
    ]
    client.statuses.append(_paused_status())
    repeated = service.advance_run(run_id=started["id"], actor="owner")
    assert repeated["status"] == "paused"
    assert len(client.resume_calls) == 1


def test_start_timeout_is_persisted_as_unknown_and_not_retried() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    client.start_error = WorkflowExecutorTimeoutError("timed out")
    service = _service(store, client)

    first = service.start_run(case_id="case-1", actor="owner")
    second = service.start_run(case_id="case-1", actor="owner")

    assert first["run"]["status"] == "external_state_unknown"
    assert first["run"]["passed"] is None
    assert first["run"]["error"]["retryable"] is False
    assert second["reused"] is True


def test_ambiguous_resume_failure_does_not_submit_the_same_pause_twice() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    client.paused_schema = {
        "type": "object",
        "properties": {"slot-id": {"type": "string"}},
        "required": ["slot-id"],
    }
    client.resume_error = WorkflowExecutorNetworkError("connection lost after submission")
    service = _service(store, client)
    started = service.start_run(case_id="case-1", actor="owner")["run"]
    client.statuses.append(_paused_status())

    transient = service.advance_run(run_id=started["id"], actor="owner")

    assert transient["status"] == "paused"
    assert transient["error"]["retryable"] is True
    assert client.resume_attempts == 1
    client.statuses.append(_paused_status())
    repeated = service.advance_run(run_id=started["id"], actor="owner")
    assert repeated["status"] == "paused"
    assert client.resume_attempts == 1


def test_advance_retries_transient_5xx_on_a_later_request() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    service = _service(store, client)
    started = service.start_run(case_id="case-1", actor="owner")["run"]
    client.status_error = WorkflowExecutorServerResponseError(status_code=503, response_body="unavailable")

    transient = service.advance_run(run_id=started["id"], actor="owner")
    assert transient["status"] == "running"
    assert transient["error"]["retryable"] is True

    client.statuses.append(_status(status="running", step_status="success"))
    completed = service.advance_run(run_id=started["id"], actor="owner")
    assert completed["status"] == "completed"
    assert completed["passed"] is True


def test_start_requires_executor_base_url_before_creating_run() -> None:
    store = FakeStore(executor_workflow_document())
    service = WorkflowDebugService(store, WorkflowDebugSettings(executor_base_url=None))

    with pytest.raises(ServiceUnavailableError):
        service.start_run(case_id="case-1", actor="owner")

    assert store.run is None


def test_concurrent_start_returns_the_run_that_won_the_insert_race() -> None:
    class RacingStore(FakeStore):
        def insert_workflow_debug_run(self, *, values: dict) -> dict:
            now = datetime.now(timezone.utc)
            self.run = {"id": "winning-run", **values, "created_at": now, "updated_at": now}
            raise ConflictError("active run already exists")

    store = RacingStore(executor_workflow_document())
    client = FakeExecutorClient()

    result = _service(store, client).start_run(case_id="case-1", actor="owner")

    assert result["reused"] is True
    assert result["run"]["id"] == "winning-run"
    assert client.started is None
