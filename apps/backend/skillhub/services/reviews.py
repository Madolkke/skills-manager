from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError, PermissionDeniedError
from skillhub.models.rules.publish_policy import decide_publish_request
from skillhub.models.rules.review_policy import decide_review_closure
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class ReviewService(ServiceBase[SkillHubStore]):
    def list_skill_reviews(self, *, skill_id: str, actor: str) -> object:
        return self.store.list_skill_reviews(skill_id=skill_id, actor=actor)

    def create_review_request(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        publish_targets: list[dict[str, Any]],
        reviewer_sources: list[dict[str, Any]] | None = None,
        actor: str,
    ) -> object:
        with self.transaction_store() as store:
            opened = store.open_review_request(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                reviewer_sources=reviewer_sources or [],
                actor=actor,
            )
            store.attach_review_publish_targets(review_id=opened["review_id"], skill_id=skill_id, publish_targets=publish_targets)
            store.create_review_notifications(
                review_id=opened["review_id"],
                skill_slug=opened["skill_slug"],
                reviewers=opened["reviewers"],
                actor=actor,
            )
            store.record_review_created_audit(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                review_id=opened["review_id"],
                reviewer_count=len(opened["reviewers"]),
                actor=actor,
            )
            return store.review_detail(review_id=opened["review_id"])

    def reviewer_candidates(self, *, skill_id: str, actor: str) -> object:
        return self.store.reviewer_candidates(skill_id=skill_id, actor=actor)

    def submit_review_response(self, *, review_id: str, score: int, comment: str | None, actor: str) -> object:
        if score not in {-1, 0, 1}:
            raise InvariantError("Review score must be -1, 0 or 1.")
        with self.transaction_store() as store:
            snapshot = store.review_response_snapshot(review_id=review_id, actor=actor)
            if snapshot["review"]["status"] != "open":
                raise InvariantError("Review is closed.")
            if not snapshot["is_reviewer"]:
                raise PermissionDeniedError("Only snapshotted reviewers can respond to this review.")
            return store.apply_review_response(
                review_id=review_id,
                skill_id=snapshot["review"]["skill_id"],
                score=score,
                comment=(comment or "").strip(),
                actor=actor,
                exists=snapshot["response_exists"],
            )

    def close_review(self, *, review_id: str, actor: str) -> object:
        with self.transaction_store() as store:
            snapshot = store.review_closure_snapshot(review_id=review_id, actor=actor)
            decision = decide_review_closure(
                reviewer_count=snapshot["reviewer_count"],
                responses=snapshot["responses"],
                publish_targets=snapshot["publish_targets"],
            )
            closed = store.apply_review_closure(
                review_id=review_id,
                actor=actor,
                checks=decision.checks,
                summary=decision.summary,
                auto_publish_target_ids=decision.auto_publish_target_ids,
            )
        return closed

    def list_my_reviews(self, *, actor: str) -> object:
        return self.store.list_my_reviews(actor=actor)

    def list_my_notifications(self, *, actor: str) -> object:
        return self.store.list_my_notifications(actor=actor)

    def mark_notification(self, *, notification_id: str, read: bool, actor: str) -> object:
        return self.store.mark_notification(notification_id=notification_id, read=read, actor=actor)

    def skill_publish_overview(self, *, skill_id: str, actor: str) -> object:
        return self.store.skill_publish_overview(skill_id=skill_id, actor=actor)

    def create_publish_record(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        review_request_id: str,
        publish_target_id: str,
        actor: str,
    ) -> object:
        with self.transaction_store() as store:
            snapshot = store.publish_request_snapshot(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                review_request_id=review_request_id,
                publish_target_id=publish_target_id,
                actor=actor,
            )
            check_snapshot = decide_publish_request(
                target=snapshot["target"],
                reviewer_count=snapshot["reviewer_count"],
                responses=snapshot["responses"],
                stored_checks=snapshot["stored_checks"],
            )
            return store.apply_publish_request(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                review_request_id=review_request_id,
                publish_target_id=publish_target_id,
                actor=actor,
                check_snapshot=check_snapshot,
            )
