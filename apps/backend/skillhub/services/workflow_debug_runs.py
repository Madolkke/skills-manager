from __future__ import annotations

from typing import Any
from uuid import uuid4

from skillhub.models.entities import utc_now
from skillhub.models.errors import ConflictError, InvariantError, ServiceUnavailableError
from skillhub.models.rules.executor_workflows import project_workflow_document
from skillhub.models.rules.workflow_debug import build_executor_identity, paused_run_input, target_reached
from skillhub.services.workflow_debug_runtime import decode_run_cursor, encode_run_cursor, public_debug_run
from skillhub.services.workflow_executor_client import (
    WorkflowExecutorClientResponseError,
    WorkflowExecutorContractError,
    WorkflowExecutorNetworkError,
    WorkflowExecutorServerResponseError,
    WorkflowExecutorTimeoutError,
)


class WorkflowDebugRunServiceMixin:
    store: Any
    settings: Any
    client_factory: Any

    def start_run(self, *, case_id: str, actor: str) -> dict[str, Any]:
        source = self.store.workflow_debug_start_source(case_id=case_id, actor=actor)
        active = source["active_run"]
        if active is not None and not self._expired(active):
            return {"run": self._public_run(active), "reused": True}
        if active is not None:
            self._fail_timeout(active, actor=actor)
        if self.settings.executor_base_url is None:
            raise ServiceUnavailableError("WORKFLOW_EXECUTOR_BASE_URL is not configured.")

        projection = project_workflow_document(source["document"])
        identity = build_executor_identity(projection, document=source["document"], case=source["case"])
        task_id = str(uuid4())
        try:
            row = self.store.insert_workflow_debug_run(
                values={
                    "case_id": case_id,
                    "skill_id": source["case"]["skill_id"],
                    "step_id": source["case"]["step_id"],
                    "expected_target_id": source["case"]["expected_target_id"],
                    "case_snapshot": _case_snapshot(source["case"]),
                    "workflow_revision": source["workflow_revision"],
                    "workflow_digest": source["workflow_digest"],
                    "task_id": task_id,
                    "executor_run_id": None,
                    "executor_identity": identity,
                    "status": "starting",
                    "passed": None,
                    "executor_status": None,
                    "error": None,
                    "resumed_pauses": [],
                    "created_by": actor,
                    "completed_at": None,
                }
            )
        except ConflictError:
            raced = self.store.workflow_debug_start_source(case_id=case_id, actor=actor)["active_run"]
            if raced is not None:
                return {"run": self._public_run(raced), "reused": True}
            raise
        client = self._executor_client()
        try:
            executor_run_id = client.run_step(
                task_id=task_id,
                workflow_data=projection.workflow,
                step_id=identity["step_id"],
            )
        except (WorkflowExecutorTimeoutError, WorkflowExecutorNetworkError, WorkflowExecutorServerResponseError) as exc:
            row = self._update_error(row, actor=actor, status="external_state_unknown", exc=exc, retryable=False, completed=False)
        except (WorkflowExecutorClientResponseError, WorkflowExecutorContractError) as exc:
            row = self._update_error(row, actor=actor, status="failed", exc=exc, retryable=False, completed=True)
        else:
            row = self.store.update_workflow_debug_run(
                run_id=row["id"],
                values={"executor_run_id": str(executor_run_id), "status": "running", "error": None},
                actor=actor,
            )
        finally:
            client.close()
        return {"run": self._public_run(row), "reused": False}

    def get_run(self, *, run_id: str, actor: str) -> dict[str, Any]:
        return self._public_run(self.store.workflow_debug_run(run_id=run_id, actor=actor))

    def list_runs(self, *, case_id: str, actor: str, cursor: str | None, limit: int) -> dict[str, Any]:
        before = None
        if cursor:
            try:
                before = decode_run_cursor(cursor)
            except ValueError as exc:
                raise InvariantError(str(exc)) from exc
        page_size = max(1, min(limit, 100))
        rows = self.store.list_workflow_debug_runs(case_id=case_id, actor=actor, limit=page_size + 1, before=before)
        has_more = len(rows) > page_size
        items = rows[:page_size]
        next_cursor = encode_run_cursor(items[-1]["created_at"], items[-1]["id"]) if has_more else None
        return {"items": [self._public_run(row) for row in items], "next_cursor": next_cursor}

    def advance_run(self, *, run_id: str, actor: str) -> dict[str, Any]:
        row = self.store.workflow_debug_run(run_id=run_id, actor=actor, for_update=True)
        if row["status"] in {"completed", "failed", "external_state_unknown"}:
            return self._public_run(row)
        if self._expired(row):
            return self._public_run(self._fail_timeout(row, actor=actor))
        if not row["executor_run_id"]:
            return self._public_run(self._terminal_error(row, actor=actor, code="workflow_debug.missing_executor_run_id", message="运行缺少执行器 run_id。"))
        if self.settings.executor_base_url is None:
            return self._public_run(self._terminal_error(row, actor=actor, code="workflow_debug.executor_not_configured", message="执行器未配置。"))
        return self._public_run(self._poll(row, actor=actor))

    def _public_run(self, row: dict[str, Any]) -> dict[str, Any]:
        return public_debug_run(row, poll_interval_seconds=self.settings.poll_interval_seconds)

    def _poll(self, row: dict[str, Any], *, actor: str) -> dict[str, Any]:
        client = self._executor_client()
        try:
            status_model = client.get_run_status(run_id=row["executor_run_id"])
            status = status_model.model_dump(mode="json")
            if target_reached(status, row["executor_identity"]["expected_target"]):
                return self._complete(row, actor=actor, passed=True, executor_status=status)
            if status["status"] in {"success", "failure"}:
                return self._complete(row, actor=actor, passed=False, executor_status=status)
            if status["status"] == "paused":
                row = self.store.update_workflow_debug_run(
                    run_id=row["id"], values={"status": "paused", "executor_status": status, "error": None}, actor=actor
                )
                return self._resume_paused(row, status=status, client=client, actor=actor)
            return self.store.update_workflow_debug_run(
                run_id=row["id"], values={"status": "running", "executor_status": status, "error": None}, actor=actor
            )
        except (WorkflowExecutorTimeoutError, WorkflowExecutorNetworkError, WorkflowExecutorServerResponseError) as exc:
            return self._update_error(row, actor=actor, status=row["status"], exc=exc, retryable=True, completed=False)
        except (WorkflowExecutorClientResponseError, WorkflowExecutorContractError) as exc:
            return self._update_error(row, actor=actor, status="failed", exc=exc, retryable=False, completed=True)
        finally:
            client.close()

    def _resume_paused(self, row, *, status, client, actor):
        flow_run_id = status.get("paused_flow_run_id")
        if not flow_run_id:
            return self._terminal_error(row, actor=actor, code="workflow_debug.invalid_pause", message="暂停状态缺少 flow_run_id。", executor_status=status)
        pause = {"flow_run_id": flow_run_id, "paused_key": status.get("paused_key")}
        if pause in row["resumed_pauses"]:
            return self.store.update_workflow_debug_run(
                run_id=row["id"], values={"status": "paused", "executor_status": status, "error": None}, actor=actor
            )
        schema = client.get_paused_schema(run_id=row["executor_run_id"], flow_run_id=flow_run_id)
        try:
            run_input = paused_run_input(schema, snapshot=row["case_snapshot"], identity=row["executor_identity"])
        except ValueError as exc:
            return self._terminal_error(row, actor=actor, code="workflow_debug.pause_input_missing", message=str(exc), executor_status=status)
        resumed = [*row["resumed_pauses"], pause]
        row = self.store.update_workflow_debug_run(
            run_id=row["id"],
            values={"status": "paused", "executor_status": status, "error": None, "resumed_pauses": resumed},
            actor=actor,
        )
        client.resume(run_id=row["executor_run_id"], flow_run_id=flow_run_id, run_input=run_input)
        return self.store.update_workflow_debug_run(
            run_id=row["id"], values={"status": "running", "executor_status": status, "error": None}, actor=actor
        )

    def _executor_client(self):
        assert self.settings.executor_base_url is not None
        return self.client_factory(self.settings.executor_base_url, self.settings.request_timeout_seconds)

    def _expired(self, row: dict[str, Any]) -> bool:
        return (utc_now() - row["created_at"]).total_seconds() >= self.settings.max_duration_seconds

    def _fail_timeout(self, row, *, actor):
        return self._terminal_error(row, actor=actor, code="workflow_debug.max_duration_exceeded", message="调试运行已超过最大时长。")

    def _complete(self, row, *, actor, passed, executor_status):
        return self.store.update_workflow_debug_run(
            run_id=row["id"], values={"status": "completed", "passed": passed, "executor_status": executor_status, "error": None, "completed_at": utc_now()}, actor=actor
        )

    def _terminal_error(self, row, *, actor, code, message, executor_status=None):
        return self.store.update_workflow_debug_run(
            run_id=row["id"],
            values={"status": "failed", "passed": None, "error": {"code": code, "message": message, "retryable": False}, "executor_status": executor_status, "completed_at": utc_now()},
            actor=actor,
        )

    def _update_error(self, row, *, actor, status, exc, retryable, completed):
        code = f"workflow_debug.executor_{exc.__class__.__name__.removeprefix('WorkflowExecutor').removesuffix('Error').lower()}"
        return self.store.update_workflow_debug_run(
            run_id=row["id"],
            values={"status": status, "passed": None, "error": {"code": code, "message": str(exc), "retryable": retryable}, "completed_at": utc_now() if completed else None},
            actor=actor,
        )


def _case_snapshot(case: dict[str, Any]) -> dict[str, Any]:
    return {key: case[key] for key in ("name", "description", "step_id", "expected_target_id", "workflow_inputs", "collection_fixtures")}


__all__ = ["WorkflowDebugRunServiceMixin"]
