from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from skillhub.views.dependencies import create_postgres_engine, resolve_database_url
from skillhub.models.rules.eval_assertion_templates import AssertionContext, assertion_template
from skillhub.models.rules.opencode_skill_usage import skill_usage_evidence
from skillhub.models.store import SkillHubStore
from skillhub_worker.config import load_config
from skillhub_worker.laminar_client import LaminarClient, LaminarEvalRefs
from skillhub_worker.opencode_client import OpencodeClient
from skillhub_worker.opencode_trace import compact_message_output, extract_opencode_trace, new_opencode_messages, opencode_message_ids
from skillhub_worker.workspace import materialize_case_workspace, render_step_prompt, workspace_snapshot


def run_once(store: SkillHubStore, client: OpencodeClient, laminar: LaminarClient, *, config) -> bool:
    detail = store.claim_next_eval_case_run_job(worker_id=config.worker_id)
    if detail is None:
        return False
    run = detail["eval_case_run"]
    job = detail.get("job") or {}
    eval_case_run_id = run["id"]
    metadata: dict[str, Any] = {
        "runner": "opencode_laminar",
        "current_stage": "preparing",
        "current_stage_label": "准备工作目录",
        "step_results": [],
    }
    try:
        opencode_selection = _opencode_selection(run.get("run_context"))
        metadata["opencode_model_selection"] = opencode_selection
        paths = materialize_case_workspace(detail, host_root=config.workdir_host, container_root=config.workdir_container)
        metadata["workdir"] = paths["workdir"]
        metadata["skill_installation"] = paths["skill_installation"]
        metadata["skill_usage"] = _initial_skill_usage(paths["skill_installation"])
        _persist_metadata(store, eval_case_run_id, metadata)
        case_version = detail["case_version"]
        steps = list(case_version.get("steps") or [])
        metadata["current_stage"] = "creating_laminar_datapoint"
        metadata["current_stage_label"] = "创建 Laminar 测评记录"
        _persist_metadata(store, eval_case_run_id, metadata)
        refs = laminar.create_eval_datapoint(
            name=f"SkillHub Eval {eval_case_run_id}",
            data={"case_version_id": case_version["id"], "steps": steps},
            target={"all_steps_must_pass": True},
            metadata={"eval_case_run_id": eval_case_run_id, "skill_version_id": run["skill_version_id"]},
        )
        _record_laminar_refs(metadata, refs)
        if refs.error:
            raise RuntimeError(refs.error)

        client.health()
        metadata["current_stage"] = "creating_opencode_session"
        metadata["current_stage_label"] = "创建 Opencode 会话"
        _persist_metadata(store, eval_case_run_id, metadata)
        session_id = client.create_session(title=f"SkillHub Eval {eval_case_run_id}", directory=paths["workdir"])
        metadata["opencode_session_id"] = session_id
        metadata["session_id"] = session_id
        _persist_metadata(store, eval_case_run_id, metadata)

        passed = True
        actual_output = ""
        failure_reason = ""
        for index, step in enumerate(steps):
            metadata["current_stage"] = "running_step"
            metadata["current_stage_label"] = f"第 {index + 1}/{len(steps)} 步运行中"
            metadata["current_step"] = _current_step_metadata(step, index, len(steps), "running")
            _persist_metadata(store, eval_case_run_id, metadata)
            before = workspace_snapshot(Path(paths["host_workdir"]))
            prompt = render_step_prompt(step=step, paths=paths, step_number=index + 1, total_steps=len(steps))
            messages_before_step = client.list_messages(session_id=session_id, directory=paths["workdir"])
            seen_message_ids = opencode_message_ids(messages_before_step)
            message_response = client.send_message(
                session_id=session_id,
                prompt=prompt,
                directory=paths["workdir"],
                provider_id=opencode_selection.get("provider_id") or None,
                model_id=opencode_selection.get("model_id") or None,
            )
            message_history = client.list_messages(session_id=session_id, directory=paths["workdir"])
            step_messages = new_opencode_messages(message_history, seen_message_ids, seen_count=len(messages_before_step))
            trace_source: object = step_messages or message_response
            opencode_trace = extract_opencode_trace(trace_source)
            step_skill_usage = skill_usage_evidence(
                list(opencode_trace.get("tool_calls") or []),
                str(metadata["skill_installation"].get("skill_slug") or ""),
            )
            _merge_skill_usage(metadata["skill_usage"], step_skill_usage)
            agent_output = compact_message_output(trace_source)
            after = workspace_snapshot(Path(paths["host_workdir"]))
            metadata["current_stage"] = "asserting_step"
            metadata["current_stage_label"] = f"第 {index + 1}/{len(steps)} 步判定中"
            metadata["current_step"] = _current_step_metadata(step, index, len(steps), "asserting")
            _persist_metadata(store, eval_case_run_id, metadata)
            context = AssertionContext(
                agent_output=agent_output,
                workdir=Path(paths["host_workdir"]),
                before_snapshot=before,
                after_snapshot=after,
                step=step,
                run_metadata=metadata,
                reasoning_text=str(opencode_trace.get("reasoning_text") or ""),
                tool_calls=list(opencode_trace.get("tool_calls") or []),
            )
            assertion_results = [_evaluate_assertion(context, assertion) for assertion in _step_assertions(step)]
            step_passed = all(item["passed"] for item in assertion_results)
            failed_count = sum(1 for item in assertion_results if not item["passed"])
            step_reason = "全部判断条件通过。" if step_passed else f"{failed_count} 个判断条件未通过。"
            step_result = {
                "step_id": step["id"],
                "title": step["title"],
                "status": "passed" if step_passed else "failed",
                "passed": step_passed,
                "actual": agent_output,
                "reason": step_reason,
                "details": {"assertion_count": len(assertion_results), "failed_count": failed_count},
                "assertions": assertion_results,
                "message_response": _compact_message_response(message_response),
                "opencode_trace": _public_opencode_trace(opencode_trace),
                "skill_usage": step_skill_usage,
            }
            metadata["step_results"].append(step_result)
            actual_output = agent_output
            _persist_metadata(store, eval_case_run_id, metadata)
            if not step_passed:
                passed = False
                failure_reason = step_reason
                for skipped in steps[index + 1:]:
                    metadata["step_results"].append(
                        {
                            "step_id": skipped["id"],
                            "title": skipped["title"],
                            "status": "skipped",
                            "passed": None,
                            "actual": "",
                            "reason": "前置步骤失败，未执行。",
                            "details": {},
                            "assertions": [_skipped_assertion(assertion) for assertion in _step_assertions(skipped)],
                        }
                    )
                break

        metadata["current_stage"] = "updating_laminar"
        metadata["current_stage_label"] = "写入 Laminar 测评结果"
        metadata.pop("current_step", None)
        _persist_metadata(store, eval_case_run_id, metadata)
        scores = {"passed": 1 if passed else 0}
        for item in metadata["step_results"]:
            if item["status"] != "skipped":
                scores[f"step.{item['step_id']}"] = 1 if item["passed"] else 0
                for assertion in item.get("assertions") or []:
                    scores[f"step.{item['step_id']}.assertion.{assertion['assertion_id']}"] = 1 if assertion["passed"] else 0
        laminar_error = laminar.update_datapoint(
            refs=refs,
            executor_output={
                "step_results": metadata["step_results"],
                "opencode_model_selection": opencode_selection,
                "skill_installation": metadata["skill_installation"],
                "skill_usage": metadata["skill_usage"],
            },
            scores=scores,
            metadata=metadata,
        )
        if laminar_error:
            metadata["laminar_error"] = laminar_error
            raise RuntimeError(laminar_error)
        metadata["current_stage"] = "completed"
        metadata["current_stage_label"] = "测评完成"
        store.finalize_eval_case_run(
            eval_case_run_id=eval_case_run_id,
            passed=passed,
            actual_output=actual_output,
            actor=config.worker_id,
            runner_metadata={**metadata, "reason": failure_reason},
        )
    except Exception as exc:
        attempts = int(job.get("attempts") or 1)
        metadata["current_stage"] = "failed"
        metadata["current_stage_label"] = "测评器执行失败"
        if metadata:
            try:
                store.update_eval_case_run_metadata(eval_case_run_id=eval_case_run_id, runner_metadata=metadata)
            except Exception:
                pass
        if attempts < config.max_attempts:
            store.retry_eval_case_run_job(eval_case_run_id=eval_case_run_id, error=str(exc))
        else:
            store.fail_eval_case_run(eval_case_run_id=eval_case_run_id, error=str(exc))
    return True


def main() -> None:
    config = load_config()
    config.workdir_host.mkdir(parents=True, exist_ok=True)
    store = SkillHubStore(create_postgres_engine(resolve_database_url()))
    client = OpencodeClient(base_url=config.opencode_base_url, timeout_seconds=config.timeout_seconds)
    laminar = LaminarClient(
        base_url=config.laminar_base_url,
        http_port=config.laminar_http_port,
        project_api_key=config.laminar_project_api_key,
        timeout_seconds=config.timeout_seconds,
    )
    while True:
        did_work = run_once(store, client, laminar, config=config)
        if not did_work:
            time.sleep(config.poll_interval_seconds)


def _record_laminar_refs(metadata: dict[str, Any], refs: LaminarEvalRefs) -> None:
    metadata["laminar_configured"] = refs.configured
    if refs.evaluation_id:
        metadata["laminar_evaluation_id"] = refs.evaluation_id
    if refs.datapoint_id:
        metadata["laminar_datapoint_id"] = refs.datapoint_id
    if refs.error:
        metadata["laminar_error"] = refs.error


def _compact_message_response(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    compact: dict[str, Any] = {}
    for key in ("id", "sessionID", "providerID", "modelID", "finish"):
        if key in response:
            compact[key] = response[key]
    return compact


def _public_opencode_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "reasoning_text": str(trace.get("reasoning_text") or ""),
        "tool_calls": list(trace.get("tool_calls") or []),
        "text_output": str(trace.get("text_output") or ""),
        "finish": str(trace.get("finish") or ""),
        "model_id": str(trace.get("model_id") or ""),
        "provider_id": str(trace.get("provider_id") or ""),
    }


def _opencode_selection(run_context: Any) -> dict[str, str]:
    if not isinstance(run_context, dict):
        return {"provider_id": "", "model_id": ""}
    opencode = run_context.get("opencode")
    if not isinstance(opencode, dict):
        return {"provider_id": "", "model_id": ""}
    provider_id = str(opencode.get("provider_id") or "").strip()
    model_id = str(opencode.get("model_id") or "").strip()
    if provider_id and model_id:
        return {"provider_id": provider_id, "model_id": model_id}
    return {"provider_id": "", "model_id": ""}


def _initial_skill_usage(skill_installation: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_slug": str(skill_installation.get("skill_slug") or ""),
        "used": False,
        "count": 0,
        "calls": [],
    }


def _merge_skill_usage(total: dict[str, Any], step_usage: dict[str, Any]) -> None:
    calls = step_usage.get("calls")
    if not isinstance(calls, list):
        calls = []
    total["used"] = bool(total.get("used")) or bool(step_usage.get("used"))
    total["count"] = int(total.get("count") or 0) + len(calls)
    total.setdefault("calls", []).extend(calls)


def _evaluate_assertion(context: AssertionContext, assertion: dict[str, Any]) -> dict[str, Any]:
    result = assertion_template(str(assertion["assertion_template_id"])).evaluate(context, dict(assertion.get("assertion_params") or {}))
    return {
        "assertion_id": assertion["id"],
        "assertion_template_id": assertion["assertion_template_id"],
        "status": "passed" if result.passed else "failed",
        "passed": result.passed,
        "actual": result.actual,
        "reason": result.reason,
        "details": result.details,
    }


def _skipped_assertion(assertion: dict[str, Any]) -> dict[str, Any]:
    return {
        "assertion_id": assertion["id"],
        "assertion_template_id": assertion["assertion_template_id"],
        "status": "skipped",
        "passed": None,
        "actual": "",
        "reason": "前置步骤失败，未执行。",
        "details": {},
    }


def _step_assertions(step: dict[str, Any]) -> list[dict[str, Any]]:
    assertions = step.get("assertions")
    if isinstance(assertions, list) and assertions:
        return [dict(assertion) for assertion in assertions if isinstance(assertion, dict)]
    return [
        {
            "id": "assertion-1",
            "assertion_template_id": step.get("assertion_template_id") or "agent_output_semantic",
            "assertion_params": step.get("assertion_params") if isinstance(step.get("assertion_params"), dict) else {},
        }
    ]


def _current_step_metadata(step: dict[str, Any], index: int, total: int, stage: str) -> dict[str, Any]:
    return {
        "id": step.get("id"),
        "title": step.get("title"),
        "index": index + 1,
        "total": total,
        "stage": stage,
    }


def _persist_metadata(store: SkillHubStore, eval_case_run_id: str, metadata: dict[str, Any]) -> None:
    try:
        store.update_eval_case_run_metadata(eval_case_run_id=eval_case_run_id, runner_metadata=metadata)
    except Exception:
        pass


if __name__ == "__main__":
    main()
