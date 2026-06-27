from __future__ import annotations

from skillhub.models.rules.review_policy import decide_review_closure


def test_review_closure_policy_computes_summary_and_auto_publish_targets() -> None:
    decision = decide_review_closure(
        reviewer_count=2,
        responses=[{"score": 1}, {"score": 0}],
        publish_targets=[
            {"publish_target_id": "target_auto", "auto_submit_on_pass": True},
            {"publish_target_id": "target_manual", "auto_submit_on_pass": False},
            {"publish_target_id": "", "auto_submit_on_pass": True},
        ],
    )

    assert decision.summary["reviewer_count"] == 2
    assert decision.summary["response_count"] == 2
    assert decision.summary["positive_count"] == 1
    assert decision.summary["neutral_count"] == 1
    assert decision.auto_publish_target_ids == ["target_auto"]
    assert {item["check_id"] for item in decision.checks} >= {"no_negative_score", "min_responses"}
