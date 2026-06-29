from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError, PermissionDeniedError
from skillhub.models.rules.publish_policy import decide_publish_request
from skillhub.models.rules.review_policy import decide_review_closure
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase
from skillhub.services.publish_release import perform_publish_release


AUTO_PUBLISH_ACTOR = "system:auto_publish"


class ReviewService(ServiceBase[SkillHubStore]):
    def list_skill_reviews(self, *, skill_id: str, actor: str) -> Any:
        return self.store.list_skill_reviews(skill_id=skill_id, actor=actor)

    def create_review_request(self, *, skill_id: str, skill_version_id: str, publish_targets: list[dict[str, Any]], actor: str) -> Any:
        opened = self.store.open_review_request(skill_id=skill_id, skill_version_id=skill_version_id, actor=actor)
        self.store.attach_review_publish_targets(review_id=opened["review_id"], skill_id=skill_id, publish_targets=publish_targets)
        self.store.create_review_notifications(
            review_id=opened["review_id"],
            skill_slug=opened["skill_slug"],
            reviewers=opened["reviewers"],
            actor=actor,
        )
        self.store.record_review_created_audit(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            review_id=opened["review_id"],
            reviewer_count=len(opened["reviewers"]),
            actor=actor,
        )
        return self.store.review_detail(review_id=opened["review_id"])

    def submit_review_response(self, *, review_id: str, score: int, comment: str | None, actor: str) -> Any:
        if score not in {-1, 0, 1}:
            raise InvariantError("Review score must be -1, 0 or 1.")
        snapshot = self.store.review_response_snapshot(review_id=review_id, actor=actor)
        if snapshot["review"]["status"] != "open":
            raise InvariantError("Review is closed.")
        if not snapshot["is_reviewer"]:
            raise PermissionDeniedError("Only snapshotted reviewers can respond to this review.")
        return self.store.apply_review_response(
            review_id=review_id,
            skill_id=snapshot["review"]["skill_id"],
            score=score,
            comment=(comment or "").strip(),
            actor=actor,
            exists=snapshot["response_exists"],
        )

    def close_review(self, *, review_id: str, actor: str) -> Any:
        snapshot = self.store.review_closure_snapshot(review_id=review_id, actor=actor)
        decision = decide_review_closure(
            reviewer_count=snapshot["reviewer_count"],
            responses=snapshot["responses"],
            publish_targets=snapshot["publish_targets"],
        )
        closed = self.store.apply_review_closure(
            review_id=review_id,
            actor=actor,
            checks=decision.checks,
            summary=decision.summary,
            auto_publish_target_ids=decision.auto_publish_target_ids,
        )
        if self._auto_publish_closed_review(closed):
            return self.store.review_detail(review_id=review_id)
        return closed

    def list_my_reviews(self, *, actor: str) -> Any:
        return self.store.list_my_reviews(actor=actor)

    def list_my_notifications(self, *, actor: str) -> Any:
        return self.store.list_my_notifications(actor=actor)

    def mark_notification(self, *, notification_id: str, read: bool, actor: str) -> Any:
        return self.store.mark_notification(notification_id=notification_id, read=read, actor=actor)

    def skill_publish_overview(self, *, skill_id: str, actor: str) -> Any:
        return self.store.skill_publish_overview(skill_id=skill_id, actor=actor)

    def create_publish_record(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        review_request_id: str,
        publish_target_id: str,
        actor: str,
    ) -> Any:
        snapshot = self.store.publish_request_snapshot(
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
        return self.store.apply_publish_request(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            review_request_id=review_request_id,
            publish_target_id=publish_target_id,
            actor=actor,
            check_snapshot=check_snapshot,
        )

    def _auto_publish_closed_review(self, review: dict[str, Any]) -> bool:
        handled = False
        for record in review.get("publish_records", []):
            target = record.get("publish_target") or {}
            auto_enabled = bool(target.get("auto_publish_enabled") or record.get("target_auto_publish_enabled"))
            if record.get("status") != "pending_confirmation" or not auto_enabled:
                continue
            handled = True
            try:
                snapshot = self.store.publish_confirmation_snapshot(publish_record_id=record["id"], actor=AUTO_PUBLISH_ACTOR)
                if snapshot["record"]["status"] != "pending_confirmation":
                    continue
                release_result = perform_publish_release(snapshot["release_payload"])
                self.store.apply_publish_confirmation(
                    publish_record_id=record["id"],
                    actor=AUTO_PUBLISH_ACTOR,
                    release_result={**release_result, "metadata": {**release_result.get("metadata", {}), "auto_publish": True}},
                )
            except Exception as exc:
                try:
                    self.store.apply_publish_failure(
                        publish_record_id=record["id"],
                        actor=AUTO_PUBLISH_ACTOR,
                        error_message=str(exc) or exc.__class__.__name__,
                    )
                except Exception:
                    continue
        return handled
