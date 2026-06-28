from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.eval_assertion_templates import normalize_assertion_step


def legacy_eval_case_steps(input_text: str | None, expected_output: str | None) -> list[dict[str, Any]]:
    if input_text is None and expected_output is None:
        return []
    return [
        {
            "title": "步骤 1",
            "input": input_text or "",
            "assertion_template_id": "agent_output_contains",
            "assertion_params": {"text": expected_output or ""},
        }
    ]


def normalize_eval_case_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not steps:
        raise InvariantError("Eval case requires at least one step.")
    return [normalize_assertion_step(step, index) for index, step in enumerate(steps)]


def normalize_eval_case_runner_config(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    return {
        "timeout_seconds": raw.get("timeout_seconds"),
    }


def normalize_eval_case_title(value: str | None) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise InvariantError("Each eval case requires title.")
    return clean
