from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skillhub.models.rules.review_checks import compute_review_checks, review_summary


@dataclass(frozen=True, slots=True)
class ReviewClosureDecision:
    checks: list[dict[str, Any]]
    summary: dict[str, Any]
    auto_publish_target_ids: list[str]


def decide_review_closure(
    *,
    reviewer_count: int,
    responses: list[dict[str, Any]],
    publish_targets: list[dict[str, Any]],
) -> ReviewClosureDecision:
    checks = compute_review_checks(reviewer_count, responses)
    return ReviewClosureDecision(
        checks=checks,
        summary=review_summary(reviewer_count, responses, checks),
        auto_publish_target_ids=[
            str(target["publish_target_id"])
            for target in publish_targets
            if target.get("auto_submit_on_pass") and target.get("publish_target_id")
        ],
    )
