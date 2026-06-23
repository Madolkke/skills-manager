import pytest

from skillhub.domain.errors import InvariantError
from skillhub.infrastructure.db.repository_impl.reviews.checks import evaluate_gate_expression, normalize_gate_expression


RESPONSES = [{"score": 1}, {"score": 0}, {"score": -1}]


def test_gate_expression_supports_nested_and_or():
    expression = {
        "type": "group",
        "op": "or",
        "children": [
            {"type": "check", "check_id": "no_negative_score"},
            {
                "type": "group",
                "op": "and",
                "children": [
                    {"type": "check", "check_id": "min_responses", "params": {"min": 3}},
                    {"type": "check", "check_id": "total_score_at_least", "params": {"min": 0}},
                ],
            },
        ],
    }

    result = evaluate_gate_expression(expression, reviewer_count=3, responses=RESPONSES, stored_checks=[])

    assert result["passed"] is True
    assert result["children"][0]["passed"] is False
    assert result["children"][1]["passed"] is True


def test_gate_expression_rejects_empty_groups():
    with pytest.raises(InvariantError, match="at least one child"):
        normalize_gate_expression({"type": "group", "op": "and", "children": []})


def test_gate_expression_validates_percentage_parameters():
    with pytest.raises(InvariantError, match="between 0 and 100"):
        normalize_gate_expression(
            {
                "type": "group",
                "op": "and",
                "children": [{"type": "check", "check_id": "positive_ratio_at_least", "params": {"min": 120}}],
            }
        )
