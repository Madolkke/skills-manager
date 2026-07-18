from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.review_check_definitions import (
    DEFAULT_GATE_EXPRESSION,
    REVIEW_CHECK_DEFINITIONS,
    REVIEW_CHECK_LABELS,
)
from skillhub.models.rules.review_check_params import non_negative_int, number, percent_ratio, positive_int


def compute_review_checks(reviewer_count: int, responses: list[dict[str, Any]], *, min_responses: int = 1) -> list[dict[str, Any]]:
    scores = [int(item["score"]) for item in responses]
    response_count = len(scores)
    positive_count = sum(1 for score in scores if score == 1)
    neutral_count = sum(1 for score in scores if score == 0)
    negative_count = sum(1 for score in scores if score == -1)
    positive_ratio = positive_count / response_count if response_count else 0
    return [
        {
            "check_id": "no_negative_score",
            "passed": negative_count == 0,
            "details": {"negative_count": negative_count},
        },
        {
            "check_id": "no_neutral_score",
            "passed": neutral_count == 0,
            "details": {"neutral_count": neutral_count},
        },
        {
            "check_id": "positive_ratio_at_least_50",
            "passed": response_count > 0 and positive_ratio >= 0.5,
            "details": {"positive_count": positive_count, "response_count": response_count, "ratio": positive_ratio},
        },
        {
            "check_id": "all_reviewers_responded",
            "passed": reviewer_count > 0 and response_count == reviewer_count,
            "details": {"reviewer_count": reviewer_count, "response_count": response_count},
        },
        {
            "check_id": "min_responses",
            "passed": response_count >= max(1, min_responses),
            "details": {"min": max(1, min_responses), "response_count": response_count},
        },
        {
            "check_id": "total_score_at_least",
            "passed": sum(scores) >= 1,
            "details": {"min": 1, "total_score": sum(scores)},
        },
        {
            "check_id": "average_score_at_least",
            "passed": response_count > 0 and (sum(scores) / response_count) >= 0.5,
            "details": {"min": 0.5, "average_score": sum(scores) / response_count if response_count else 0, "response_count": response_count},
        },
        {
            "check_id": "positive_ratio_at_least",
            "passed": response_count > 0 and positive_ratio >= 0.5,
            "details": {"min": 0.5, "positive_count": positive_count, "response_count": response_count, "ratio": positive_ratio},
        },
        {
            "check_id": "negative_count_at_most",
            "passed": negative_count <= 0,
            "details": {"max": 0, "negative_count": negative_count},
        },
    ]


def review_summary(reviewer_count: int, responses: list[dict[str, Any]], checks: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [int(item["score"]) for item in responses]
    return {
        "reviewer_count": reviewer_count,
        "response_count": len(scores),
        "positive_count": sum(1 for score in scores if score == 1),
        "neutral_count": sum(1 for score in scores if score == 0),
        "negative_count": sum(1 for score in scores if score == -1),
        "checks_passed": all(bool(item["passed"]) for item in checks),
    }


def normalize_gate_expression(value: Any) -> dict[str, Any]:
    if value is None:
        return DEFAULT_GATE_EXPRESSION
    normalized = _normalize_gate_node(value, depth=0)
    if normalized["type"] != "group":
        raise InvariantError("Publish gate expression root must be a group.")
    return normalized


def evaluate_gate_expression(
    expression: dict[str, Any],
    *,
    reviewer_count: int,
    responses: list[dict[str, Any]],
    stored_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = normalize_gate_expression(expression)
    return _evaluate_gate_node(
        normalized,
        reviewer_count=reviewer_count,
        responses=responses,
        stored_checks=stored_checks,
    )


def _normalize_gate_node(value: Any, *, depth: int) -> dict[str, Any]:
    if depth > 6:
        raise InvariantError("Publish gate expression is too deeply nested.")
    if not isinstance(value, dict):
        raise InvariantError("Publish gate expression nodes must be objects.")
    node_type = str(value.get("type", "")).strip()
    if node_type == "group":
        op = str(value.get("op", "")).strip().lower()
        if op not in {"and", "or"}:
            raise InvariantError("Publish gate group op must be and or or.")
        children_value = value.get("children")
        if not isinstance(children_value, list) or not children_value:
            raise InvariantError("Publish gate group must contain at least one child.")
        if len(children_value) > 20:
            raise InvariantError("Publish gate group has too many children.")
        return {"type": "group", "op": op, "children": [_normalize_gate_node(item, depth=depth + 1) for item in children_value]}
    if node_type == "check":
        check_id = str(value.get("check_id", "")).strip()
        params = value.get("params") or {}
        if not isinstance(params, dict):
            raise InvariantError("Publish gate check params must be an object.")
        return {"type": "check", "check_id": check_id, "params": _normalize_gate_params(check_id, params)}
    raise InvariantError("Publish gate expression node type must be group or check.")


def _normalize_gate_params(check_id: str, params: dict[str, Any]) -> dict[str, Any]:
    if check_id not in REVIEW_CHECK_DEFINITIONS:
        raise InvariantError(f"Unsupported review check: {check_id}")
    if check_id == "min_responses":
        return {"min": positive_int(params.get("min", 1), "min_responses.min")}
    if check_id == "total_score_at_least":
        return {"min": number(params.get("min", 1), "total_score_at_least.min")}
    if check_id == "average_score_at_least":
        return {"min": number(params.get("min", 0.5), "average_score_at_least.min")}
    if check_id == "positive_ratio_at_least":
        return {"min": percent_ratio(params.get("min", 50), "positive_ratio_at_least.min")}
    if check_id == "negative_count_at_most":
        return {"max": non_negative_int(params.get("max", 0), "negative_count_at_most.max")}
    return {}


def _evaluate_gate_node(
    node: dict[str, Any],
    *,
    reviewer_count: int,
    responses: list[dict[str, Any]],
    stored_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    if node["type"] == "group":
        children = [
            _evaluate_gate_node(child, reviewer_count=reviewer_count, responses=responses, stored_checks=stored_checks)
            for child in node["children"]
        ]
        passed = all(child["passed"] for child in children) if node["op"] == "and" else any(child["passed"] for child in children)
        return {"type": "group", "op": node["op"], "passed": passed, "children": children}
    result = _evaluate_gate_check(
        node["check_id"],
        node.get("params", {}),
        reviewer_count=reviewer_count,
        responses=responses,
        stored_checks=stored_checks,
    )
    return {"type": "check", "check_id": node["check_id"], "params": node.get("params", {}), "passed": result["passed"], "result": result}


def _evaluate_gate_check(
    check_id: str,
    params: dict[str, Any],
    *,
    reviewer_count: int,
    responses: list[dict[str, Any]],
    stored_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    scores = [int(item["score"]) for item in responses]
    response_count = len(scores)
    positive_count = sum(1 for score in scores if score == 1)
    neutral_count = sum(1 for score in scores if score == 0)
    negative_count = sum(1 for score in scores if score == -1)
    total_score = sum(scores)
    average_score = total_score / response_count if response_count else 0
    positive_ratio = positive_count / response_count if response_count else 0
    label = REVIEW_CHECK_LABELS[check_id]
    if check_id == "no_negative_score":
        return _gate_result(check_id, label, negative_count == 0, {"negative_count": negative_count}, params)
    if check_id == "no_neutral_score":
        return _gate_result(check_id, label, neutral_count == 0, {"neutral_count": neutral_count}, params)
    if check_id == "all_reviewers_responded":
        return _gate_result(
            check_id,
            label,
            reviewer_count > 0 and response_count == reviewer_count,
            {"reviewer_count": reviewer_count, "response_count": response_count},
            params,
        )
    if check_id == "min_responses":
        min_count = positive_int(params.get("min", 1), "min_responses.min")
        return _gate_result(check_id, label, response_count >= min_count, {"min": min_count, "response_count": response_count}, params)
    if check_id == "total_score_at_least":
        min_score = number(params.get("min", 1), "total_score_at_least.min")
        return _gate_result(check_id, label, total_score >= min_score, {"min": min_score, "total_score": total_score}, params)
    if check_id == "average_score_at_least":
        min_score = number(params.get("min", 0.5), "average_score_at_least.min")
        return _gate_result(
            check_id,
            label,
            response_count > 0 and average_score >= min_score,
            {"min": min_score, "average_score": average_score, "response_count": response_count},
            params,
        )
    if check_id == "positive_ratio_at_least":
        min_ratio = percent_ratio(params.get("min", 50), "positive_ratio_at_least.min")
        return _gate_result(
            check_id,
            label,
            response_count > 0 and positive_ratio >= min_ratio,
            {"min": min_ratio, "positive_count": positive_count, "response_count": response_count, "ratio": positive_ratio},
            params,
        )
    if check_id == "negative_count_at_most":
        max_count = non_negative_int(params.get("max", 0), "negative_count_at_most.max")
        return _gate_result(check_id, label, negative_count <= max_count, {"max": max_count, "negative_count": negative_count}, params)
    stored = next((item for item in stored_checks if item["check_id"] == check_id), None)
    if stored is None:
        raise InvariantError(f"Review check result is missing: {check_id}")
    return {**stored, "label": label, "required_params": params}


def _gate_result(check_id: str, label: str, passed: bool, details: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    return {"check_id": check_id, "label": label, "passed": passed, "details": details, "required_params": params}
