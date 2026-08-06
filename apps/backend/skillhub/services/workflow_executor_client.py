from __future__ import annotations

from types import TracebackType
from typing import Literal, TypeAlias
from uuid import UUID

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError, field_validator

from skillhub.models.rules.executor_workflows import ExecutorWorkflow

ExecutorJsonObject: TypeAlias = dict[str, JsonValue]
RunStatus = Literal["pending", "running", "paused", "success", "failure"]
StepStatus = Literal["idle", "running", "paused", "success", "failure"]
_JSON_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_JSON_OBJECT_ADAPTER: TypeAdapter[ExecutorJsonObject] = TypeAdapter(ExecutorJsonObject)


class ExecutorProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RunStepRequest(ExecutorProtocolModel):
    task_id: str = Field(min_length=1)
    workflow_data: ExecutorWorkflow
    step_id: int


class RunStepResponse(ExecutorProtocolModel):
    run_id: str

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("run_id must be a UUID") from exc
        return value


class ResumeRequest(ExecutorProtocolModel):
    flow_run_id: str = Field(min_length=1)
    run_input: ExecutorJsonObject


class StepRunStatus(ExecutorProtocolModel):
    step_id: int
    status: StepStatus
    flow_run_id: str | None
    result: ExecutorJsonObject | None
    failure: ExecutorJsonObject | None


class RunStatusResponse(ExecutorProtocolModel):
    run_id: str
    status: RunStatus
    steps: list[StepRunStatus]
    conclusion_ids: list[int]
    message: str
    paused_flow_run_id: str | None
    paused_key: str | None = Field(validation_alias=AliasChoices("paused_key", "pause_key"))

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        try:
            UUID(value)
        except ValueError as exc:
            raise ValueError("run_id must be a UUID") from exc
        return value


class WorkflowExecutorClientError(RuntimeError):
    """Base error for calls to the external Workflow executor."""


class WorkflowExecutorTimeoutError(WorkflowExecutorClientError):
    """The executor did not respond before the configured deadline."""


class WorkflowExecutorNetworkError(WorkflowExecutorClientError):
    """The executor could not be reached due to a transport failure."""


class WorkflowExecutorHttpError(WorkflowExecutorClientError):
    def __init__(self, *, status_code: int, response_body: str) -> None:
        super().__init__(f"Workflow executor returned HTTP {status_code}.")
        self.status_code = status_code
        self.response_body = response_body


class WorkflowExecutorClientResponseError(WorkflowExecutorHttpError):
    """The executor rejected the request with a 4xx response."""


class WorkflowExecutorServerResponseError(WorkflowExecutorHttpError):
    """The executor failed while handling the request with a 5xx response."""


class WorkflowExecutorContractError(WorkflowExecutorClientError):
    """The executor returned a response outside the agreed protocol."""


class WorkflowExecutorClient:
    """Synchronous client for the executor's single-step lifecycle."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        clean_base_url = base_url.strip().rstrip("/")
        if not clean_base_url:
            raise ValueError("Workflow executor base URL must not be empty.")
        self.base_url = clean_base_url
        self.timeout = httpx.Timeout(timeout_seconds)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    def run_step(self, *, task_id: str, workflow_data: ExecutorWorkflow, step_id: int) -> UUID:
        """Start one step and return the executor run identifier."""
        request = RunStepRequest(task_id=task_id, workflow_data=workflow_data, step_id=step_id)
        response = self._request("POST", "/api/run-step", json_body=request.model_dump(mode="json"))
        payload = self._response_json(response)
        try:
            parsed = RunStepResponse.model_validate(payload)
        except ValidationError as exc:
            raise WorkflowExecutorContractError("Workflow executor run-step response does not match the contract.") from exc
        return UUID(parsed.run_id)

    def get_run_status(self, *, run_id: UUID | str) -> RunStatusResponse:
        """Read and validate the current state of an executor run."""
        response = self._request("GET", f"/api/runs/{run_id}")
        payload = self._response_json(response)
        try:
            return RunStatusResponse.model_validate(payload)
        except ValidationError as exc:
            raise WorkflowExecutorContractError("Workflow executor run status does not match the contract.") from exc

    def get_paused_schema(self, *, run_id: UUID | str, flow_run_id: str) -> ExecutorJsonObject:
        """Read the JSON Schema required to resume the deepest pause."""
        response = self._request(
            "GET",
            f"/api/runs/{run_id}/paused-schema",
            params={"flow_run_id": flow_run_id},
        )
        payload = self._response_json(response)
        try:
            return _JSON_OBJECT_ADAPTER.validate_python(payload, strict=True)
        except ValidationError as exc:
            raise WorkflowExecutorContractError("Workflow executor paused schema must be a JSON object.") from exc

    def resume(self, *, run_id: UUID | str, flow_run_id: str, run_input: ExecutorJsonObject) -> None:
        """Resume one paused flow run with schema-compatible input."""
        request = ResumeRequest(flow_run_id=flow_run_id, run_input=run_input)
        self._request(
            "POST",
            f"/api/runs/{run_id}/resume",
            json_body=request.model_dump(mode="json"),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WorkflowExecutorClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: JsonValue | None = None,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, params=params, json=json_body)
        except httpx.TimeoutException as exc:
            raise WorkflowExecutorTimeoutError("Workflow executor request timed out.") from exc
        except httpx.RequestError as exc:
            raise WorkflowExecutorNetworkError("Workflow executor request failed.") from exc
        body = response.text[:2000]
        if 400 <= response.status_code < 500:
            raise WorkflowExecutorClientResponseError(status_code=response.status_code, response_body=body)
        if 500 <= response.status_code < 600:
            raise WorkflowExecutorServerResponseError(status_code=response.status_code, response_body=body)
        if not 200 <= response.status_code < 300:
            raise WorkflowExecutorContractError(f"Workflow executor returned unexpected HTTP {response.status_code}.")
        return response

    @staticmethod
    def _response_json(response: httpx.Response) -> JsonValue:
        try:
            payload = response.json()
            return _JSON_ADAPTER.validate_python(payload, strict=True)
        except (ValueError, ValidationError) as exc:
            raise WorkflowExecutorContractError("Workflow executor response is not valid JSON.") from exc


__all__ = [
    "ExecutorJsonObject",
    "ResumeRequest",
    "RunStatusResponse",
    "RunStepRequest",
    "RunStepResponse",
    "StepRunStatus",
    "WorkflowExecutorClient",
    "WorkflowExecutorClientError",
    "WorkflowExecutorClientResponseError",
    "WorkflowExecutorContractError",
    "WorkflowExecutorHttpError",
    "WorkflowExecutorNetworkError",
    "WorkflowExecutorServerResponseError",
    "WorkflowExecutorTimeoutError",
]
