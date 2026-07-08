from __future__ import annotations

from typing import Any

from skillhub.models.rules.eval_assertion_templates import AssertionContext, assertion_template
from skillhub.models.store import SkillHubStore
from skillhub_worker.laminar_client import LaminarEvalRefs


def record_laminar_refs(metadata: dict[str, Any], refs: LaminarEvalRefs) -> None:
    """Store public Laminar identifiers in runner metadata."""
    metadata["laminar_configured"] = refs.configured
    if refs.evaluation_id:
        metadata["laminar_evaluation_id"] = refs.evaluation_id
    if refs.datapoint_id:
        metadata["laminar_datapoint_id"] = refs.datapoint_id
    if refs.error:
        metadata["laminar_error"] = refs.error


def compact_message_response(response: Any) -> dict[str, Any]:
    """Return non-content fields from an Opencode message response."""
    if not isinstance(response, dict):
        return {}
    compact: dict[str, Any] = {}
    for key in ("id", "sessionID", "providerID", "modelID", "finish"):
        if key in response:
            compact[key] = response[key]
    return compact


def public_opencode_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Return the trace shape persisted for UI/debug inspection."""
    return {
        "reasoning_text": str(trace.get("reasoning_text") or ""),
        "tool_calls": list(trace.get("tool_calls") or []),
        "text_output": str(trace.get("text_output") or ""),
        "finish": str(trace.get("finish") or ""),
        "model_id": str(trace.get("model_id") or ""),
        "provider_id": str(trace.get("provider_id") or ""),
    }


def opencode_selection(run_context: Any) -> dict[str, str]:
    """Extract explicit Opencode provider/model selection from run context."""
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


def opencode_agent_id(run_context: Any) -> str:
    """Extract explicit Opencode agent selection from run context."""
    if not isinstance(run_context, dict):
        return ""
    opencode = run_context.get("opencode")
    if not isinstance(opencode, dict):
        return ""
    return str(opencode.get("agent_id") or "").strip()


def payload_text(payload: Any, key: str) -> str:
    """Read a trimmed string from a job payload."""
    if not isinstance(payload, dict):
        return ""
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def initial_skill_usage(skill_installation: dict[str, Any]) -> dict[str, Any]:
    """Create empty skill usage metadata for a case run."""
    return {
        "skill_slug": str(skill_installation.get("skill_slug") or ""),
        "used": False,
        "count": 0,
        "calls": [],
    }


def merge_skill_usage(total: dict[str, Any], step_usage: dict[str, Any]) -> None:
    """Accumulate step-level skill usage evidence."""
    calls = step_usage.get("calls")
    if not isinstance(calls, list):
        calls = []
    total["used"] = bool(total.get("used")) or bool(step_usage.get("used"))
    total["count"] = int(total.get("count") or 0) + len(calls)
    total.setdefault("calls", []).extend(calls)


def evaluate_assertion(context: AssertionContext, assertion: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one assertion and return the persisted result shape."""
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


def skipped_assertion(assertion: dict[str, Any]) -> dict[str, Any]:
    """Return a skipped assertion result after an earlier step failure."""
    return {
        "assertion_id": assertion["id"],
        "assertion_template_id": assertion["assertion_template_id"],
        "status": "skipped",
        "passed": None,
        "actual": "",
        "reason": "前置步骤失败，未执行。",
        "details": {},
    }


def step_assertions(step: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize legacy single-assertion steps into assertion lists."""
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


def current_step_metadata(step: dict[str, Any], index: int, total: int, stage: str) -> dict[str, Any]:
    """Return current step progress metadata for polling clients."""
    return {
        "id": step.get("id"),
        "title": step.get("title"),
        "index": index + 1,
        "total": total,
        "stage": stage,
    }


def persist_metadata(store: SkillHubStore, eval_case_run_id: str, metadata: dict[str, Any]) -> None:
    """Best-effort metadata persistence while a runner is progressing."""
    try:
        store.update_eval_case_run_metadata(eval_case_run_id=eval_case_run_id, runner_metadata=metadata)
    except Exception:
        pass
