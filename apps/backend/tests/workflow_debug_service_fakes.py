from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from skillhub.models.errors import ConflictError
from skillhub.services.workflow_debug import WorkflowDebugService
from skillhub.services.workflow_debug_runtime import WorkflowDebugSettings
from skillhub.services.workflow_executor_client import RunStatusResponse

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
        active_statuses = {"starting", "running", "paused", "external_state_unknown"}
        return {
            "case": self.case,
            "active_run": self.run if self.run and self.run["status"] in active_statuses else None,
            "workflow_revision": 7,
            "workflow_digest": "d" * 64,
            "document": self.document,
        }

    def insert_workflow_debug_run(self, *, values: dict) -> dict:
        self.run = {
            "id": "debug-run-1",
            **values,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
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
        self.started = {
            "task_id": task_id,
            "workflow_data": workflow_data.model_dump(mode="json"),
            "step_id": step_id,
        }
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


def debug_service(store: FakeStore, client: FakeExecutorClient) -> WorkflowDebugService:
    return WorkflowDebugService(
        store,
        WorkflowDebugSettings(executor_base_url="http://executor.test"),
        client_factory=lambda _url, _timeout: client,
    )


def run_status(*, status: str, step_status: str = "running") -> RunStatusResponse:
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


def paused_status() -> RunStatusResponse:
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


def insert_racing_run(store: FakeStore, values: dict) -> None:
    now = datetime.now(timezone.utc)
    store.run = {"id": "winning-run", **values, "created_at": now, "updated_at": now}
    raise ConflictError("active run already exists")
