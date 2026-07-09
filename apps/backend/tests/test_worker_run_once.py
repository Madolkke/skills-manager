from __future__ import annotations

from pathlib import Path
from typing import Any

from skillhub_worker.config import WorkerConfig
from skillhub_worker.laminar_client import LaminarEvalRefs
from skillhub_worker.main import run_once


class FakeStore:
    def __init__(self, detail: dict[str, Any] | None) -> None:
        self.detail = detail
        self.builder_detail: dict[str, Any] | None = None
        self.agents: dict[str, dict[str, Any]] = {}
        self.metadata_updates: list[dict[str, Any]] = []
        self.finalized: dict[str, Any] | None = None
        self.failed: str | None = None
        self.retried: str | None = None
        self.completed_builder: dict[str, Any] | None = None
        self.failed_builder: dict[str, Any] | None = None
        self.builder_progress: list[dict[str, Any]] = []
        self.heartbeats: list[dict[str, Any]] = []

    def claim_next_eval_case_run_job(self, *, worker_id: str) -> dict[str, Any] | None:
        return self.detail

    def claim_next_skill_builder_job(self, *, worker_id: str) -> dict[str, Any] | None:
        return self.builder_detail

    def update_eval_case_run_metadata(self, *, eval_case_run_id: str, runner_metadata: dict[str, Any]) -> None:
        self.metadata_updates.append(runner_metadata.copy())

    def finalize_eval_case_run(self, **kwargs: Any) -> None:
        self.finalized = kwargs

    def fail_eval_case_run(self, *, eval_case_run_id: str, error: str) -> None:
        self.failed = error

    def retry_eval_case_run_job(self, *, eval_case_run_id: str, error: str) -> None:
        self.retried = error

    def enabled_opencode_agent_for_run(self, *, agent_id: str) -> dict[str, Any]:
        agent = self.agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"Opencode Agent not found: {agent_id}")
        return agent

    def complete_skill_builder_job(self, **kwargs: Any) -> None:
        self.completed_builder = kwargs

    def fail_skill_builder_job(self, **kwargs: Any) -> None:
        self.failed_builder = kwargs

    def update_skill_builder_job_progress(self, **kwargs: Any) -> None:
        self.builder_progress.append(kwargs)

    def record_worker_heartbeat(self, **kwargs: Any) -> None:
        self.heartbeats.append(kwargs)


class FakeOpencodeClient:
    def __init__(self, *, skill_slug: str = "test-skill") -> None:
        self.message_count = 0
        self.session_kwargs: dict[str, Any] | None = None
        self.message_kwargs: list[dict[str, Any]] = []
        self.history_requests: list[dict[str, Any]] = []
        self.skill_slug = skill_slug

    def health(self) -> None:
        return None

    def create_session(self, *, title: str, directory: str) -> str:
        self.session_kwargs = {"title": title, "directory": directory}
        return "session_1"

    def list_messages(self, *, session_id: str, directory: str) -> list[dict[str, Any]]:
        self.history_requests.append({"session_id": session_id, "directory": directory})
        if self.message_count == 0:
            return [
                {
                    "id": "msg_existing",
                    "info": {"role": "assistant"},
                    "parts": [{"type": "text", "text": "previous output"}],
                }
            ]
        return [
            {
                "id": "msg_existing",
                "info": {"role": "assistant"},
                "parts": [{"type": "text", "text": "previous output"}],
            },
            {
                "id": "msg_user_1",
                "info": {"role": "user"},
                "parts": [{"type": "text", "text": "输出 helloworld"}],
            },
            {
                "id": "msg_assistant_1",
                "info": {"role": "assistant", "finish": "stop", "providerID": "deepseek", "modelID": "deepseek-v4-flash"},
                "parts": [
                    {
                        "type": "tool",
                        "tool": "skill",
                        "callID": "call_skill",
                        "state": {
                            "status": "completed",
                            "input": {"name": self.skill_slug},
                            "output": f"<skill_content name=\"{self.skill_slug}\">...</skill_content>",
                            "title": f"Loaded skill: {self.skill_slug}",
                            "metadata": {
                                "name": self.skill_slug,
                                "dir": f"/workspace/eval-runs/evalcase_1/workdir/.opencode/skills/{self.skill_slug}",
                                "truncated": False,
                            },
                        },
                    },
                    {"type": "text", "text": "helloworld"},
                ],
            },
        ]

    def send_message(self, **kwargs: Any) -> dict[str, Any]:
        self.message_count += 1
        self.message_kwargs.append(kwargs)
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

    did_work = _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    step_result = laminar.executor_output["step_results"][0]

    assert did_work is True
    assert client.message_count == 1
    assert client.session_kwargs is not None
    assert client.session_kwargs["directory"].endswith("/evalcase_1/workdir")
    assert client.message_kwargs[0]["directory"].endswith("/evalcase_1/workdir")
    assert client.message_kwargs[0]["prompt"] == "输出 helloworld"
    assert client.message_kwargs[0]["provider_id"] is None
    assert client.message_kwargs[0]["model_id"] is None
    assert len(client.history_requests) == 2
    assert step_result is not None
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
    assert laminar.executor_output["skill_installation"]["skill_slug"] == "test-skill"
    assert laminar.executor_output["skill_installation"]["mode"] == "project_isolated"
    assert laminar.executor_output["skill_usage"]["used"] is True
    assert laminar.executor_output["skill_usage"]["count"] == 1
    assert step_result["skill_usage"]["used"] is True
    assert step_result["opencode_trace"]["tool_calls"][0]["metadata"]["name"] == "test-skill"
    assert store.finalized["runner_metadata"]["skill_installation"]["opencode_skill_dir"].endswith(
        "/evalcase_1/workdir/.opencode/skills/test-skill"
    )
    assert store.finalized["runner_metadata"]["skill_usage"]["calls"][0]["tool"] == "skill"


def test_run_once_uses_opencode_model_from_run_context(tmp_path: Path):
    detail = _case_detail()
    detail["eval_case_run"]["run_context"] = {"opencode": {"provider_id": "deepseek", "model_id": "deepseek-v4-pro"}}
    store = FakeStore(detail)
    client = FakeOpencodeClient()
    laminar = FakeLaminarClient()

    _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    assert client.message_kwargs[0]["provider_id"] == "deepseek"
    assert client.message_kwargs[0]["model_id"] == "deepseek-v4-pro"
    assert store.finalized is not None
    assert store.finalized["runner_metadata"]["opencode_model_selection"] == {"provider_id": "deepseek", "model_id": "deepseek-v4-pro"}
    assert laminar.executor_output["opencode_model_selection"] == {"provider_id": "deepseek", "model_id": "deepseek-v4-pro"}


def test_run_once_materializes_selected_opencode_agent_and_overrides_model(tmp_path: Path):
    detail = _case_detail()
    detail["eval_case_run"]["run_context"] = {
        "opencode": {"agent_id": "strict-reviewer", "provider_id": "deepseek", "model_id": "deepseek-v4-pro"}
    }
    store = FakeStore(detail)
    store.agents["strict-reviewer"] = {
        "id": "strict-reviewer",
        "name": "严格评审",
        "description": "严格检查。",
        "prompt": "你是严格的评审 Agent。",
        "provider_id": "deepseek",
        "model_id": "deepseek-v4-agent-default",
        "temperature": "0.2",
        "permission": {"read": True},
        "steps": ["检查输入"],
    }
    client = FakeOpencodeClient()
    laminar = FakeLaminarClient()

    _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    agent_file = tmp_path / "evalcase_1" / "workdir" / ".opencode" / "agents" / "strict-reviewer.md"
    assert agent_file.is_file()
    assert "你是严格的评审 Agent。" in agent_file.read_text(encoding="utf-8")
    assert client.message_kwargs[0]["agent_id"] == "strict-reviewer"
    assert client.message_kwargs[0]["provider_id"] == "deepseek"
    assert client.message_kwargs[0]["model_id"] == "deepseek-v4-pro"
    assert store.finalized is not None
    assert store.finalized["runner_metadata"]["opencode_agent"]["agent_id"] == "strict-reviewer"
    assert laminar.executor_output["opencode_agent"]["agent_id"] == "strict-reviewer"


def test_run_once_can_assert_tested_skill_was_used(tmp_path: Path):
    detail = _case_detail(
        assertions=[
            {
                "id": "assertion-1",
                "assertion_template_id": "tested_skill_used",
                "assertion_params": {},
            }
        ]
    )
    store = FakeStore(detail)
    client = FakeOpencodeClient(skill_slug="test-skill")
    laminar = FakeLaminarClient()

    _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    step_result = laminar.executor_output["step_results"][0]
    assert store.finalized["passed"] is True
    assert step_result["assertions"][0]["status"] == "passed"
    assert step_result["assertions"][0]["details"]["skill_slug"] == "test-skill"


def test_run_once_processes_skill_builder_job_when_no_eval_job(tmp_path: Path):
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

    did_work = _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    agent_file = tmp_path / "builder_1" / "workdir" / ".opencode" / "agents" / "skillhub-skill-builder.md"
    skill_file = tmp_path / "builder_1" / "workdir" / "SKILL.md"
    assert did_work is True
    assert agent_file.is_file()
    assert skill_file.read_text(encoding="utf-8").startswith("---\nname: writer")
    assert client.session_kwargs is not None
    assert client.session_kwargs["directory"].endswith("/builder_1/workdir")
    assert client.message_kwargs[0]["agent_id"] == "skillhub-skill-builder"
    assert client.message_kwargs[0]["provider_id"] == "deepseek"
    assert client.message_kwargs[0]["model_id"] == "deepseek-v4"
    assert client.message_kwargs[0]["tools"]["bash"] is False
    assert client.message_kwargs[0]["prompt"] == "请继续完善 SKILL.md"
    assert store.completed_builder is not None
    assert store.completed_builder["opencode_session_id"] == "session_1"
    assert store.completed_builder["intent"] == "chat"
    assert store.completed_builder["draft_files"][0]["path"] == "SKILL.md"
    assert [item["stage"] for item in store.builder_progress] == [
        "preparing_workspace",
        "checking_opencode",
        "creating_opencode_session",
        "loading_message_history",
        "sending_message",
        "scanning_workspace",
        "saving_result",
    ]
    assert store.failed_builder is None


def test_run_once_fails_when_another_skill_is_used(tmp_path: Path):
    detail = _case_detail(
        assertions=[
            {
                "id": "assertion-1",
                "assertion_template_id": "no_other_skill_used",
                "assertion_params": {},
            }
        ]
    )
    store = FakeStore(detail)
    client = FakeOpencodeClient(skill_slug="other-skill")
    laminar = FakeLaminarClient()

    _run_worker(tmp_path, store=store, client=client, laminar=laminar)

    step_result = laminar.executor_output["step_results"][0]
    assert store.finalized["passed"] is False
    assert step_result["assertions"][0]["status"] == "failed"
    assert step_result["assertions"][0]["details"]["used_other_skill"] is True


def _run_worker(tmp_path: Path, *, store: FakeStore, client: FakeOpencodeClient, laminar: FakeLaminarClient) -> bool:
    return run_once(
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


def _case_detail(*, assertions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    step_assertions = assertions or [
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
    ]
    return {
        "eval_case_run": {
            "id": "evalcase_1",
            "skill_id": "skill_1",
            "skill_version_id": "skillver_1",
        },
        "job": {"id": "job_1", "attempts": 1},
        "skill": {"id": "skill_1", "slug": "test-skill"},
        "skill_version": {
            "id": "skillver_1",
            "skill_id": "skill_1",
            "version": "0.0.1",
            "content_digest": "digest-1",
            "content_ref": {"kind": "skill_bundle", "locator": "memory:test"},
            "bundle_files": [
                {
                    "path": "SKILL.md",
                    "content_text": "---\nname: test-skill\ndescription: Test skill.\n---\nOutput exactly what the user asks for.\n",
                }
            ],
        },
        "case_version": {
            "id": "casever_1",
            "runner_config": {"model_provider_id": "deepseek", "model_id": "deepseek-v4-flash"},
            "workspace_artifact": None,
            "steps": [
                {
                    "id": "step-1",
                    "title": "输出与严格校验",
                    "input": "输出 helloworld",
                    "assertions": step_assertions,
                }
            ],
        },
    }
