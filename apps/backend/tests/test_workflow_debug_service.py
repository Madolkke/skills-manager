from __future__ import annotations

import pytest

from skillhub.models.errors import FieldInvariantError, ServiceUnavailableError
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
from tests.workflow_debug_service_fakes import (
    RUN_ID,
    FakeExecutorClient,
    FakeStore,
    insert_racing_run,
)
from tests.workflow_debug_service_fakes import (
    debug_service as _service,
)
from tests.workflow_debug_service_fakes import (
    paused_status as _paused_status,
)
from tests.workflow_debug_service_fakes import (
    run_status as _status,
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


def test_start_rejects_log_or_config_collection_on_the_debugged_step() -> None:
    document = executor_workflow_document()
    document["collectionSnapshots"][0]["spec"] = {
        "collectionType": "log",
        "sqlDialect": "duckdb",
        "queries": [],
        "outputSamples": [],
    }
    store = FakeStore(document)
    client = FakeExecutorClient()

    with pytest.raises(FieldInvariantError) as error:
        _service(store, client).start_run(case_id="case-1", actor="owner")

    assert error.value.field_errors[0].code == "workflow_debug.unsupported_collection_type"
    assert store.run is None
    assert client.started is None


def test_other_step_log_collection_is_filtered_from_exact_start_payload() -> None:
    document = executor_workflow_document()
    log_definition = {
        **document["collectionSnapshots"][0],
        "id": "collection-log",
        "spec": {"collectionType": "log", "sqlDialect": "duckdb", "queries": [], "outputSamples": []},
    }
    document["collectionSnapshots"].append(log_definition)
    document["workflow"]["nodes"][1]["collectionCalls"].append(
        {
            "id": "call-log",
            "key": "logs",
            "name": "日志",
            "definition": {"id": "collection-log", "revision": 1},
            "sampleCount": 9,
            "inputBindings": {},
        }
    )
    store = FakeStore(document)
    client = FakeExecutorClient()

    _service(store, client).start_run(case_id="case-1", actor="owner")

    expected = project_workflow_document(document).workflow.model_dump(mode="json")
    assert client.started is not None
    assert client.started["workflow_data"] == expected
    assert all(step["collections"] == [] for step in expected["steps"] if step["id"] == 3)


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


def test_selected_transition_passes_without_running_the_target_step() -> None:
    store = FakeStore(executor_workflow_document())
    client = FakeExecutorClient()
    service = _service(store, client)
    started = service.start_run(case_id="case-1", actor="owner")["run"]
    client.closed = False
    client.statuses.append(
        RunStatusResponse.model_validate(
            {
                "run_id": str(RUN_ID),
                "status": "success",
                "steps": [
                    {
                        "step_id": 2,
                        "status": "success",
                        "flow_run_id": str(RUN_ID),
                        "result": {
                            "reason": "模型判断",
                            "status": "success",
                            "step_id": 2,
                            "collection_results": [],
                            "selected_transition_id": 6,
                        },
                        "failure": None,
                    }
                ],
                "conclusion_ids": [],
                "message": "Completed",
                "paused_flow_run_id": None,
                "pause_key": None,
            }
        )
    )

    completed = service.advance_run(run_id=started["id"], actor="owner")

    assert completed["status"] == "completed"
    assert completed["passed"] is True
    assert completed["latest_executor_status"]["steps"][0]["result"]["selected_transition_id"] == 6


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
            insert_racing_run(self, values)
            raise AssertionError("unreachable")

    store = RacingStore(executor_workflow_document())
    client = FakeExecutorClient()

    result = _service(store, client).start_run(case_id="case-1", actor="owner")

    assert result["reused"] is True
    assert result["run"]["id"] == "winning-run"
    assert client.started is None
