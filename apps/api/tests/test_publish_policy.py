from __future__ import annotations

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.publish_policy import decide_publish_request


def test_publish_policy_returns_gate_snapshot_when_target_passes() -> None:
    result = decide_publish_request(
        target={"enabled": True, "gate_expression": {"type": "group", "op": "and", "children": [{"type": "check", "check_id": "min_responses", "params": {"min": 1}}]}},
        reviewer_count=1,
        responses=[{"score": 1}],
        stored_checks=[],
    )

    assert result[0]["check_id"] == "publish_gate"
    assert result[0]["passed"] is True


def test_publish_policy_rejects_disabled_or_failed_target() -> None:
    with pytest.raises(InvariantError, match="disabled"):
        decide_publish_request(target={"enabled": False, "gate_expression": None}, reviewer_count=1, responses=[{"score": 1}], stored_checks=[])

    with pytest.raises(InvariantError, match="Review checks failed"):
        decide_publish_request(
            target={"enabled": True, "gate_expression": {"type": "group", "op": "and", "children": [{"type": "check", "check_id": "no_negative_score"}]}},
            reviewer_count=1,
            responses=[{"score": -1}],
            stored_checks=[],
        )
