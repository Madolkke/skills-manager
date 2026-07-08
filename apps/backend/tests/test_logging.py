from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.bootstrap.logging_config import configure_logging
from skillhub.bootstrap.middleware import register_middleware
from skillhub.models.errors import PermissionDeniedError
from skillhub_worker.config import WorkerConfig
from skillhub_worker.main import run_once
from tests.test_worker_run_once import FakeLaminarClient, FakeOpencodeClient, FakeStore, _case_detail, _run_worker


class _Payload(BaseModel):
    name: str


class _FailingOpencodeClient(FakeOpencodeClient):
    def health(self) -> None:
        raise RuntimeError("opencode unavailable")


def test_configure_logging_uses_debug_level() -> None:
    configure_logging({"SKILLHUB_LOG_LEVEL": "DEBUG"})

    assert logging.getLogger("skillhub").getEffectiveLevel() == logging.DEBUG
    assert logging.getLogger("skillhub_worker").getEffectiveLevel() == logging.DEBUG

    configure_logging({"SKILLHUB_LOG_LEVEL": "INFO"})


def test_api_access_log_includes_request_id_and_status(caplog) -> None:
    caplog.set_level(logging.INFO, logger="skillhub.bootstrap.middleware")
    client = TestClient(_logging_app())

    response = client.get("/ping", headers={"X-Request-ID": "req-test-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-test-1"
    assert "request completed" in caplog.text
    assert "request_id=req-test-1" in caplog.text
    assert "status=200" in caplog.text
    assert "method=GET" in caplog.text
    assert "path=/ping" in caplog.text


def test_api_validation_warning_omits_sensitive_headers(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="skillhub.bootstrap.exceptions")
    client = TestClient(_logging_app())
    secret = "super-secret-admin-key"

    response = client.post(
        "/payload",
        json={},
        headers={"X-Request-ID": "req-validation", "X-SkillHub-Admin-Key": secret, "Cookie": "skillhub_actor=secret"},
    )

    assert response.status_code == 422
    assert "request validation error" in caplog.text
    assert "request_id=req-validation" in caplog.text
    assert secret not in caplog.text
    assert "skillhub_actor" not in caplog.text


def test_api_permission_warning_includes_request_context(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="skillhub.bootstrap.exceptions")
    client = TestClient(_logging_app())

    response = client.get("/denied", headers={"X-Request-ID": "req-denied"})

    assert response.status_code == 403
    assert "request rejected" in caplog.text
    assert "request_id=req-denied" in caplog.text
    assert "status=403" in caplog.text
    assert "PermissionDeniedError" in caplog.text


def test_worker_eval_success_logs_job_and_step_without_prompt(caplog, tmp_path: Path) -> None:
    caplog.set_level(logging.INFO, logger="skillhub_worker")
    store = FakeStore(_case_detail())
    client = FakeOpencodeClient()
    laminar = FakeLaminarClient()

    did_work = _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    assert did_work is True
    assert "eval job claimed" in caplog.text
    assert "eval_case_run_id=evalcase_1" in caplog.text
    assert "eval step completed" in caplog.text
    assert "eval job completed" in caplog.text
    assert "输出 helloworld" not in caplog.text


def test_worker_eval_failure_retry_logs_context(caplog, tmp_path: Path) -> None:
    caplog.set_level(logging.INFO, logger="skillhub_worker")
    store = FakeStore(_case_detail())
    client = _FailingOpencodeClient()
    laminar = FakeLaminarClient()

    did_work = run_once(store, client, laminar, config=_worker_config(tmp_path, max_attempts=2))

    assert did_work is True
    assert store.retried == "opencode unavailable"
    assert store.failed is None
    assert "eval job failed" in caplog.text
    assert "stage=checking_opencode_health" in caplog.text
    assert "eval job retry scheduled" in caplog.text


def test_worker_builder_success_logs_job_without_message_content(caplog, tmp_path: Path) -> None:
    caplog.set_level(logging.INFO, logger="skillhub_worker")
    store = FakeStore(None)
    store.builder_detail = {
        "session": {
            "id": "builder_1",
            "opencode_session_id": None,
            "workspace_files": [{"path": "SKILL.md", "content_text": "---\nname: writer\ndescription: Write docs.\n---\nBody"}],
        },
        "message": {"id": "buildermsg_1", "content": "请继续完善 SKILL.md", "intent": "chat"},
        "job": {"id": "job_builder_1", "payload": {"provider_id": "deepseek", "model_id": "deepseek-v4"}},
    }
    client = FakeOpencodeClient()
    laminar = FakeLaminarClient()

    did_work = run_once(store, client, laminar, config=_worker_config(tmp_path))

    assert did_work is True
    assert "skill builder job claimed" in caplog.text
    assert "session_id=builder_1" in caplog.text
    assert "skill builder job completed" in caplog.text
    assert "请继续完善" not in caplog.text


def _logging_app() -> FastAPI:
    app = FastAPI()
    register_middleware(app, {})
    register_exception_handlers(app)

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/payload")
    def payload(payload: _Payload) -> dict[str, str]:
        return {"name": payload.name}

    @app.get("/denied")
    def denied() -> None:
        raise PermissionDeniedError("Invalid test permission.")

    return app


def _worker_config(tmp_path: Path, *, max_attempts: int = 1) -> WorkerConfig:
    return WorkerConfig(
        opencode_base_url="http://opencode.test",
        laminar_base_url="http://laminar.test",
        laminar_http_port=8000,
        laminar_project_api_key="key",
        workdir_host=tmp_path,
        workdir_container="/workspace/eval-runs",
        poll_interval_seconds=0.1,
        timeout_seconds=30,
        max_attempts=max_attempts,
        worker_id="test-worker",
    )
