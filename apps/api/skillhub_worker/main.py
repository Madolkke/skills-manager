from __future__ import annotations

import time
from typing import Any

from skillhub.api.database import create_postgres_engine, resolve_database_url
from skillhub.infrastructure.db.repositories import SqlSkillRepository
from skillhub_worker.config import load_config
from skillhub_worker.opencode_client import OpencodeClient
from skillhub_worker.workspace import materialize_case_workspace, read_runner_result, render_prompt


def run_once(repository: SqlSkillRepository, client: OpencodeClient, *, config) -> bool:
    detail = repository.claim_next_eval_case_run_job(worker_id=config.worker_id)
    if detail is None:
        return False
    run = detail["eval_case_run"]
    job = detail.get("job") or {}
    eval_case_run_id = run["id"]
    try:
        paths = materialize_case_workspace(detail, host_root=config.workdir_host, container_root=config.workdir_container)
        prompt = render_prompt(detail, paths)
        case_version = detail["case_version"]
        provider_id = case_version.get("model_provider_id")
        model_id = case_version.get("model_id")
        client.health()
        session_id = client.create_session(title=f"SkillHub Eval {eval_case_run_id}", directory=paths["container_dir"])
        message_response = client.send_message(
            session_id=session_id,
            prompt=prompt,
            provider_id=provider_id,
            model_id=model_id,
            directory=paths["container_dir"],
        )
        result = read_runner_result(paths["host_result_json_path"])
        repository.finalize_eval_case_run(
            eval_case_run_id=eval_case_run_id,
            passed=bool(result["passed"]),
            actual_output=str(result["actual_output"]),
            actor=config.worker_id,
            runner_metadata={
                "runner": "opencode_server",
                "session_id": session_id,
                "provider_id": provider_id,
                "model_id": model_id,
                "prompt_template_id": case_version.get("prompt_template_id"),
                "reason": result.get("reason", ""),
                "message_response": _compact_message_response(message_response),
                "workdir": paths["workdir"],
            },
        )
    except Exception as exc:
        attempts = int(job.get("attempts") or 1)
        if attempts < config.max_attempts:
            repository.retry_eval_case_run_job(eval_case_run_id=eval_case_run_id, error=str(exc))
        else:
            repository.fail_eval_case_run(eval_case_run_id=eval_case_run_id, error=str(exc))
    return True


def main() -> None:
    config = load_config()
    config.workdir_host.mkdir(parents=True, exist_ok=True)
    repository = SqlSkillRepository(create_postgres_engine(resolve_database_url()))
    client = OpencodeClient(base_url=config.opencode_base_url, timeout_seconds=config.timeout_seconds)
    while True:
        did_work = run_once(repository, client, config=config)
        if not did_work:
            time.sleep(config.poll_interval_seconds)


def _compact_message_response(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    compact: dict[str, Any] = {}
    for key in ("id", "sessionID", "providerID", "modelID", "finish"):
        if key in response:
            compact[key] = response[key]
    return compact


if __name__ == "__main__":
    main()
