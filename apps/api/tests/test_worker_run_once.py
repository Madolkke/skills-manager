from __future__ import annotations

from pathlib import Path
from typing import Any

from skillhub_worker.config import WorkerConfig
from skillhub_worker.laminar_client import LaminarEvalRefs
from skillhub_worker.main import run_once


class FakeStore:
    def __init__(self, detail: dict[str, Any]) -> None:
        self.detail = detail
        self.metadata_updates: list[dict[str, Any]] = []
        self.finalized: dict[str, Any] | None = None
        self.failed: str | None = None
        self.retried: str | None = None

    def claim_next_eval_case_run_job(self, *, worker_id: str) -> dict[str, Any]:
        return self.detail

    def update_eval_case_run_metadata(self, *, eval_case_run_id: str, runner_metadata: dict[str, Any]) -> None:
        self.metadata_updates.append(runner_metadata.copy())

    def finalize_eval_case_run(self, **kwargs: Any) -> None:
        self.finalized = kwargs

    def fail_eval_case_run(self, *, eval_case_run_id: str, error: str) -> None:
        self.failed = error

    def retry_eval_case_run_job(self, *, eval_case_run_id: str, error: str) -> None:
        self.retried = error


class FakeOpencodeClient:
    def __init__(self) -> None:
        self.message_count = 0

    def health(self) -> None:
        return None

    def create_session(self, *, title: str, directory: str) -> str:
        return "session_1"

    def send_message(self, **kwargs: Any) -> dict[str, Any]:
        self.message_count += 1
        return {
            "id": "message_1",
            "finish": "stop",
            "providerID": "deepseek",
            "modelID": "deepseek-v4-flash",
            "parts": [{"type": "text", "text": "helloworld"}],
        }


class FakeLaminarClient:
    def __init__(self) -> None:
        self.executor_output: dict[str, Any] | None = None
        self.scores: dict[str, Any] | None = None

    def create_eval_datapoint(self, *, name: str, data: dict[str, Any], target: dict[str, Any], metadata: dict[str, Any]) -> LaminarEvalRefs:
        return LaminarEvalRefs(configured=True, evaluation_id="11111111-1111-1111-1111-111111111111", datapoint_id="22222222-2222-2222-2222-222222222222")

    def update_datapoint(self, *, refs: LaminarEvalRefs, executor_output: dict[str, Any], scores: dict[str, Any], metadata: dict[str, Any]) -> None:
        self.executor_output = executor_output
        self.scores = scores
        return None


def test_run_once_evaluates_all_assertions_in_one_step(tmp_path: Path):
    store = FakeStore(_case_detail())
    client = FakeOpencodeClient()
    laminar = FakeLaminarClient()

    did_work = run_once(
        store,
        client,
        laminar,
        config=WorkerConfig(
            opencode_base_url="http://opencode.test",
            laminar_base_url="http://laminar.test",
            laminar_http_port=8000,
            laminar_project_api_key="key",
            workdir_host=tmp_path,
            workdir_container="/workspace/eval-runs",
            poll_interval_seconds=0.1,
            timeout_seconds=30,
            max_attempts=1,
            worker_id="test-worker",
        ),
    )

    step_result = laminar.executor_output["step_results"][0]

    assert did_work is True
    assert client.message_count == 1
    assert store.failed is None
    assert store.retried is None
    assert store.finalized is not None
    assert store.finalized["passed"] is False
    assert step_result["passed"] is False
    assert [item["status"] for item in step_result["assertions"]] == ["passed", "failed"]
    assert laminar.scores == {
        "passed": 0,
        "step.step-1": 0,
        "step.step-1.assertion.assertion-1": 1,
        "step.step-1.assertion.assertion-2": 0,
    }


def _case_detail() -> dict[str, Any]:
    return {
        "eval_case_run": {
            "id": "evalcase_1",
            "skill_version_id": "skillver_1",
        },
        "job": {"id": "job_1", "attempts": 1},
        "skill_version": {
            "id": "skillver_1",
            "content_ref": {"kind": "skill_bundle", "locator": "memory:test"},
            "bundle_files": [{"path": "SKILL.md", "content_text": "# Test Skill\nOutput exactly what the user asks for.\n"}],
        },
        "case_version": {
            "id": "casever_1",
            "runner_config": {},
            "workspace_artifact": None,
            "steps": [
                {
                    "id": "step-1",
                    "title": "输出与严格校验",
                    "input": "输出 helloworld",
                    "assertions": [
                        {
                            "id": "assertion-1",
                            "assertion_template_id": "agent_output_contains",
                            "assertion_params": {"text": "helloworld"},
                        },
                        {
                            "id": "assertion-2",
                            "assertion_template_id": "agent_output_exact",
                            "assertion_params": {"expected": "not helloworld"},
                        },
                    ],
                }
            ],
        },
    }
