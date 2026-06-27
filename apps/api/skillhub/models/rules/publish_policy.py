from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.review_checks import evaluate_gate_expression, normalize_gate_expression


def decide_publish_request(*, target: dict[str, Any], reviewer_count: int, responses: list[dict[str, Any]], stored_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not target["enabled"]:
        raise InvariantError("Publish target is disabled.")
    evaluation = evaluate_gate_expression(
        normalize_gate_expression(target["gate_expression"]),
        reviewer_count=reviewer_count,
        responses=responses,
        stored_checks=stored_checks,
    )
    result = {"gate_expression": evaluation, "passed": evaluation["passed"], "check_id": "publish_gate", "label": "发布门禁", "details": {}}
    if not result["passed"]:
        raise InvariantError("Review checks failed for publish target: publish_gate")
    return [result]
