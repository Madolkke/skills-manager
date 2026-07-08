from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from skillhub.models.rules.eval_assertion_templates import AssertionContext
from skillhub.models.rules.opencode_skill_usage import skill_usage_evidence
from skillhub.models.store import SkillHubStore
from skillhub_worker.opencode_client import OpencodeClient
from skillhub_worker.opencode_trace import compact_message_output, extract_opencode_trace, new_opencode_messages, opencode_message_ids
from skillhub_worker.results import (
    compact_message_response,
    current_step_metadata,
    evaluate_assertion,
    merge_skill_usage,
    persist_metadata,
    public_opencode_trace,
    skipped_assertion,
    step_assertions,
)
from skillhub_worker.workspace import render_step_prompt, workspace_snapshot


logger = logging.getLogger(__name__)


def run_steps(
    *,
    steps: list[dict[str, Any]],
    store: SkillHubStore,
    client: OpencodeClient,
    eval_case_run_id: str,
    session_id: str,
    paths: dict[str, Any],
    metadata: dict[str, Any],
    opencode_model: dict[str, str],
    agent_id: str,
) -> tuple[bool, str, str]:
    """Run Opencode steps and evaluate assertions."""
    passed = True
    actual_output = ""
    failure_reason = ""
    for index, step in enumerate(steps):
        step_id = str(step.get("id") or "")
        _mark_step_running(store, eval_case_run_id, metadata, step, index, len(steps))
        logger.info("eval step started eval_case_run_id=%s step_id=%s step_index=%s step_total=%s", eval_case_run_id, step_id, index + 1, len(steps))
        before = workspace_snapshot(Path(paths["host_workdir"]))
        prompt = render_step_prompt(step=step, paths=paths, step_number=index + 1, total_steps=len(steps))
        messages_before_step = client.list_messages(session_id=session_id, directory=paths["workdir"])
        seen_message_ids = opencode_message_ids(messages_before_step)
        message_response, opencode_trace, step_messages = _send_step_message(
            client=client,
            eval_case_run_id=eval_case_run_id,
            step_id=step_id,
            session_id=session_id,
            paths=paths,
            prompt=prompt,
            opencode_model=opencode_model,
            agent_id=agent_id,
            seen_message_ids=seen_message_ids,
            seen_count=len(messages_before_step),
        )
        tool_calls = list(opencode_trace.get("tool_calls") or [])
        step_skill_usage = skill_usage_evidence(tool_calls, str(metadata["skill_installation"].get("skill_slug") or ""))
        merge_skill_usage(metadata["skill_usage"], step_skill_usage)
        trace_source: object = step_messages or message_response
        agent_output = compact_message_output(trace_source)
        after = workspace_snapshot(Path(paths["host_workdir"]))
        _mark_step_asserting(store, eval_case_run_id, metadata, step, index, len(steps))
        assertion_results = _evaluate_step(step, metadata, agent_output, before, after, opencode_trace, paths)
        step_passed = all(item["passed"] for item in assertion_results)
        failed_count = sum(1 for item in assertion_results if not item["passed"])
        step_reason = "全部判断条件通过。" if step_passed else f"{failed_count} 个判断条件未通过。"
        metadata["step_results"].append(
            _step_result(step, step_passed, step_reason, assertion_results, agent_output, message_response, opencode_trace, step_skill_usage)
        )
        actual_output = agent_output
        persist_metadata(store, eval_case_run_id, metadata)
        logger.info(
            "eval step completed eval_case_run_id=%s step_id=%s status=%s assertion_count=%s failed_count=%s skill_used=%s",
            eval_case_run_id,
            step_id,
            "passed" if step_passed else "failed",
            len(assertion_results),
            failed_count,
            step_skill_usage.get("used"),
        )
        if not step_passed:
            passed = False
            failure_reason = step_reason
            _append_skipped_steps(metadata, steps[index + 1 :])
            break
    return passed, actual_output, failure_reason


def _mark_step_running(store: SkillHubStore, eval_case_run_id: str, metadata: dict[str, Any], step: dict[str, Any], index: int, total: int) -> None:
    metadata["current_stage"] = "running_step"
    metadata["current_stage_label"] = f"第 {index + 1}/{total} 步运行中"
    metadata["current_step"] = current_step_metadata(step, index, total, "running")
    persist_metadata(store, eval_case_run_id, metadata)


def _mark_step_asserting(store: SkillHubStore, eval_case_run_id: str, metadata: dict[str, Any], step: dict[str, Any], index: int, total: int) -> None:
    metadata["current_stage"] = "asserting_step"
    metadata["current_stage_label"] = f"第 {index + 1}/{total} 步判定中"
    metadata["current_step"] = current_step_metadata(step, index, total, "asserting")
    persist_metadata(store, eval_case_run_id, metadata)


def _send_step_message(
    *,
    client: OpencodeClient,
    eval_case_run_id: str,
    step_id: str,
    session_id: str,
    paths: dict[str, Any],
    prompt: str,
    opencode_model: dict[str, str],
    agent_id: str,
    seen_message_ids: set[str],
    seen_count: int,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    logger.debug(
        "opencode message sending eval_case_run_id=%s step_id=%s provider_id=%s model_id=%s agent_id=%s",
        eval_case_run_id,
        step_id,
        opencode_model.get("provider_id") or "",
        opencode_model.get("model_id") or "",
        agent_id,
    )
    message_response = client.send_message(
        session_id=session_id,
        prompt=prompt,
        directory=paths["workdir"],
        provider_id=opencode_model.get("provider_id") or None,
        model_id=opencode_model.get("model_id") or None,
        agent_id=agent_id or None,
    )
    message_history = client.list_messages(session_id=session_id, directory=paths["workdir"])
    step_messages = new_opencode_messages(message_history, seen_message_ids, seen_count=seen_count)
    trace_source: object = step_messages or message_response
    opencode_trace = extract_opencode_trace(trace_source)
    logger.debug(
        "opencode message completed eval_case_run_id=%s step_id=%s new_message_count=%s tool_call_count=%s",
        eval_case_run_id,
        step_id,
        len(step_messages),
        len(list(opencode_trace.get("tool_calls") or [])),
    )
    return message_response, opencode_trace, step_messages


def _evaluate_step(
    step: dict[str, Any],
    metadata: dict[str, Any],
    agent_output: str,
    before: dict[str, Any],
    after: dict[str, Any],
    opencode_trace: dict[str, Any],
    paths: dict[str, Any],
) -> list[dict[str, Any]]:
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
    return [evaluate_assertion(context, assertion) for assertion in step_assertions(step)]


def _step_result(
    step: dict[str, Any],
    passed: bool,
    reason: str,
    assertions: list[dict[str, Any]],
    agent_output: str,
    message_response: Any,
    opencode_trace: dict[str, Any],
    skill_usage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step_id": step["id"],
        "title": step["title"],
        "status": "passed" if passed else "failed",
        "passed": passed,
        "actual": agent_output,
        "reason": reason,
        "details": {"assertion_count": len(assertions), "failed_count": sum(1 for item in assertions if not item["passed"])},
        "assertions": assertions,
        "message_response": compact_message_response(message_response),
        "opencode_trace": public_opencode_trace(opencode_trace),
        "skill_usage": skill_usage,
    }


def _append_skipped_steps(metadata: dict[str, Any], skipped_steps: list[dict[str, Any]]) -> None:
    for skipped in skipped_steps:
        metadata["step_results"].append(
            {
                "step_id": skipped["id"],
                "title": skipped["title"],
                "status": "skipped",
                "passed": None,
                "actual": "",
                "reason": "前置步骤失败，未执行。",
                "details": {},
                "assertions": [skipped_assertion(assertion) for assertion in step_assertions(skipped)],
            }
        )
