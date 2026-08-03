from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import httpx
import pytest

from skillhub.models.rules.executor_workflows import convert_workflow_document
from skillhub.services import workflow_executor_client
from skillhub.services.workflow_executor_client import (
    WorkflowExecutorClient,
    WorkflowExecutorClientResponseError,
    WorkflowExecutorContractError,
    WorkflowExecutorNetworkError,
    WorkflowExecutorServerResponseError,
    WorkflowExecutorTimeoutError,
)
from tests.executor_workflow_fixture import executor_workflow_document

RUN_ID = UUID("4cfe1b1e-4754-4563-8067-06c4f1949486")


def test_client_configures_base_url_timeout_and_ignores_environment_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class CapturingClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr(workflow_executor_client.httpx, "Client", CapturingClient)

    client = WorkflowExecutorClient(base_url="http://executor.test/", timeout_seconds=12)

    assert captured["base_url"] == "http://executor.test"
    assert captured["trust_env"] is False
    assert captured["follow_redirects"] is False
    assert isinstance(captured["timeout"], httpx.Timeout)
    client.close()


def test_client_calls_all_step_run_endpoints_and_validates_responses() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/run-step":
            return httpx.Response(202, json={"run_id": str(RUN_ID)})
        if request.url.path.endswith("/paused-schema"):
            return httpx.Response(200, json={"type": "object", "properties": {"value": {"type": "array"}}})
        if request.url.path.endswith("/resume"):
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "run_id": str(RUN_ID),
                "status": "paused",
                "steps": [
                    {
                        "step_id": 2,
                        "status": "paused",
                        "flow_run_id": "flow-1",
                        "result": {"transition_id": 7},
                        "failure": None,
                    }
                ],
                "conclusion_ids": [],
                "message": "Paused",
                "paused_flow_run_id": "flow-1",
                "paused_key": "echo-input",
            },
        )

    workflow = convert_workflow_document(executor_workflow_document())
    with WorkflowExecutorClient(
        base_url="http://executor.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    ) as client:
        run_id = client.run_step(task_id="task-1", workflow_data=workflow, step_id=2)
        status = client.get_run_status(run_id=run_id)
        schema = client.get_paused_schema(run_id=run_id, flow_run_id="flow-1")
        client.resume(run_id=run_id, flow_run_id="flow-1", run_input={"value": [{"collection_id": 4}]})

    assert run_id == RUN_ID
    assert status.status == "paused"
    assert status.steps[0].result == {"transition_id": 7}
    assert schema["type"] == "object"
    assert [request.method for request in requests] == ["POST", "GET", "GET", "POST"]
    run_step_body = json.loads(requests[0].content)
    assert set(run_step_body) == {"task_id", "workflow_data", "step_id"}
    assert run_step_body["task_id"] == "task-1"
    assert run_step_body["step_id"] == 2
    assert run_step_body["workflow_data"] == workflow.model_dump(mode="json")
    assert "revision" not in run_step_body["workflow_data"]
    assert requests[2].url.params["flow_run_id"] == "flow-1"
    assert json.loads(requests[3].content) == {
        "flow_run_id": "flow-1",
        "run_input": {"value": [{"collection_id": 4}]},
    }


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (httpx.ReadTimeout("timed out"), WorkflowExecutorTimeoutError),
        (httpx.ConnectError("connection failed"), WorkflowExecutorNetworkError),
    ],
)
def test_client_distinguishes_transport_failures(exception: httpx.RequestError, expected_error: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        exception.request = request
        raise exception

    client = WorkflowExecutorClient(
        base_url="http://executor.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(expected_error):
        client.get_run_status(run_id=RUN_ID)
    client.close()


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, WorkflowExecutorClientResponseError),
        (503, WorkflowExecutorServerResponseError),
    ],
)
def test_client_distinguishes_4xx_and_5xx(status_code: int, expected_error: type[Exception]) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status_code, text="executor error"))
    client = WorkflowExecutorClient(base_url="http://executor.test", timeout_seconds=5, transport=transport)

    with pytest.raises(expected_error) as error:
        client.get_run_status(run_id=RUN_ID)

    assert error.value.status_code == status_code
    assert error.value.response_body == "executor error"
    client.close()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not-json"),
        httpx.Response(200, json={"run_id": str(RUN_ID), "status": "unknown"}),
    ],
)
def test_client_rejects_invalid_run_status_contract(response: httpx.Response) -> None:
    client = WorkflowExecutorClient(
        base_url="http://executor.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(lambda _request: response),
    )

    with pytest.raises(WorkflowExecutorContractError):
        client.get_run_status(run_id=RUN_ID)
    client.close()


@pytest.mark.parametrize(
    "payload",
    [
        str(RUN_ID),
        {"run_id": str(RUN_ID), "extra": True},
        {"run_id": "not-a-uuid"},
    ],
)
def test_client_rejects_invalid_run_step_contract(payload: object) -> None:
    client = WorkflowExecutorClient(
        base_url="http://executor.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )
    workflow = convert_workflow_document(executor_workflow_document())

    with pytest.raises(WorkflowExecutorContractError):
        client.run_step(task_id="task-1", workflow_data=workflow, step_id=2)
    client.close()


def test_client_rejects_non_object_paused_schema() -> None:
    client = WorkflowExecutorClient(
        base_url="http://executor.test",
        timeout_seconds=5,
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=[])),
    )

    with pytest.raises(WorkflowExecutorContractError):
        client.get_paused_schema(run_id=RUN_ID, flow_run_id="flow-1")
    client.close()
