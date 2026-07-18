from __future__ import annotations

from typing import Any

from sqlalchemy import delete, insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError, PermissionDeniedError
from skillhub.models.rules.review_policy import decide_review_closure
from skillhub.models.schema import orm


class ReviewCommandMixin:
    def create_review_request(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        publish_targets: list[dict[str, Any]],
        reviewer_sources: list[dict[str, Any]] | None = None,
        actor: str,
    ) -> dict[str, Any]:
        """Legacy store facade; ReviewService owns the normal create-review orchestration."""
        opened = self.open_review_request(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            reviewer_sources=reviewer_sources or [],
            actor=actor,
        )
        self.attach_review_publish_targets(review_id=opened["review_id"], skill_id=skill_id, publish_targets=publish_targets)
        self.create_review_notifications(review_id=opened["review_id"], skill_slug=opened["skill_slug"], reviewers=opened["reviewers"], actor=actor)
        self.record_review_created_audit(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            review_id=opened["review_id"],
            reviewer_count=len(opened["reviewers"]),
            actor=actor,
        )
        return self.review_detail(review_id=opened["review_id"])

    def open_review_request(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        actor: str,
        reviewer_sources: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self._write_session() as connection:
            skill = self._skill_row(connection, skill_id)
            version = self._skill_version_row(connection, skill_version_id)
            if version["skill_id"] != skill_id:
                raise InvariantError("Skill version does not belong to this skill.")
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="review.manage")
            if self._current_open_review_for_version(connection, skill_version_id) is not None:
                raise InvariantError("This skill version already has an open review.")
            review_id = new_id("review")
            connection.execute(
                insert(orm.ReviewRequest).values(
                    id=review_id,
                    skill_id=skill_id,
                    skill_version_id=skill_version_id,
                    status="open",
                    summary={},
                    closed_at=None,
                    closed_by=None,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            reviewers = (
                self._snapshot_selected_reviewers(
                    connection,
                    skill_id=skill_id,
                    review_id=review_id,
                    created_at=created_at,
                    reviewer_sources=reviewer_sources or [],
                )
                if reviewer_sources
                else self._snapshot_reviewers(connection, skill_id=skill_id, review_id=review_id, created_at=created_at)
            )
            if not reviewers:
                raise InvariantError("No reviewer role assignments are available for this skill.")
            return {"review_id": review_id, "skill_slug": skill["slug"], "reviewers": reviewers}

    def attach_review_publish_targets(self, *, review_id: str, skill_id: str, publish_targets: list[dict[str, Any]]) -> None:
        created_at = utc_now()
        with self._write_session() as connection:
            self._review_row(connection, review_id)
            for target in publish_targets:
                publish_target_id = str(target.get("publish_target_id", "")).strip()
                if not publish_target_id:
                    continue
                self._publish_target_row(connection, publish_target_id)
                connection.execute(
                    insert(orm.ReviewRequestPublishTarget).values(
                        review_request_id=review_id,
                        skill_id=skill_id,
                        publish_target_id=publish_target_id,
                        auto_submit_on_pass=bool(target.get("auto_submit_on_pass", True)),
                        created_at=created_at,
                    )
                )

    def create_review_notifications(self, *, review_id: str, skill_slug: str, reviewers: list[str], actor: str) -> None:
        created_at = utc_now()
        with self._write_session() as connection:
            self._review_row(connection, review_id)
            self._insert_review_notifications(connection, review_id=review_id, skill_slug=skill_slug, reviewers=reviewers, actor=actor, created_at=created_at)

    def record_review_created_audit(self, *, skill_id: str, skill_version_id: str, review_id: str, reviewer_count: int, actor: str) -> None:
        created_at = utc_now()
        with self._write_session() as connection:
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="review.created",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={"review_request_id": review_id, "skill_version_id": skill_version_id, "reviewer_count": reviewer_count},
                    created_at=created_at,
                )
            )

    def review_detail(self, *, review_id: str) -> dict[str, Any]:
        with self._read_session() as connection:
            review = self._review_row(connection, review_id)
            return self._review_detail(connection, review)

    def submit_review_response(self, *, review_id: str, score: int, comment: str, actor: str) -> dict[str, Any]:
        """Legacy store facade; ReviewService owns normal response validation."""
        if score not in {-1, 0, 1}:
            raise InvariantError("Review score must be -1, 0 or 1.")
        snapshot = self.review_response_snapshot(review_id=review_id, actor=actor)
        if snapshot["review"]["status"] != "open":
            raise InvariantError("Review is closed.")
        if not snapshot["is_reviewer"]:
            raise PermissionDeniedError("Only snapshotted reviewers can respond to this review.")
        return self.apply_review_response(
            review_id=review_id,
            skill_id=snapshot["review"]["skill_id"],
            score=score,
            comment=comment.strip(),
            actor=actor,
            exists=snapshot["response_exists"],
        )

    def review_response_snapshot(self, *, review_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as connection:
            review = self._review_row(connection, review_id)
            return {
                "review": self._row_dict(review),
                "is_reviewer": self._reviewer_row(connection, review_id, actor) is not None,
                "response_exists": self._review_response_row(connection, review_id, actor) is not None,
            }

    def apply_review_response(
        self,
        *,
        review_id: str,
        skill_id: str,
        score: int,
        comment: str,
        actor: str,
        exists: bool,
    ) -> dict[str, Any]:
        updated_at = utc_now()
        with self._write_session() as connection:
            review = self._review_row(connection, review_id)
            if review["skill_id"] != skill_id:
                raise InvariantError("Review does not match the requested skill.")
            if exists:
                connection.execute(
                    update(orm.ReviewResponse)
                    .where(orm.ReviewResponse.review_request_id == review_id)
                    .where(orm.ReviewResponse.reviewer_actor == actor)
                    .values(score=score, comment=comment, updated_at=updated_at)
                )
            else:
                connection.execute(
                    insert(orm.ReviewResponse).values(
                        review_request_id=review_id,
                        skill_id=review["skill_id"],
                        reviewer_actor=actor,
                        score=score,
                        comment=comment,
                        created_at=updated_at,
                        updated_at=updated_at,
                    )
                )
            return self._review_detail(connection, review)

    def close_review(self, *, review_id: str, actor: str) -> dict[str, Any]:
        """Legacy store facade; ReviewService owns the normal close-review orchestration."""
        snapshot = self.review_closure_snapshot(review_id=review_id, actor=actor)
        decision = decide_review_closure(
            reviewer_count=snapshot["reviewer_count"],
            responses=snapshot["responses"],
            publish_targets=snapshot["publish_targets"],
        )
        return self.apply_review_closure(
            review_id=review_id,
            actor=actor,
            checks=decision.checks,
            summary=decision.summary,
            auto_publish_target_ids=decision.auto_publish_target_ids,
        )

    def review_closure_snapshot(self, *, review_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as connection:
            review = self._review_row(connection, review_id)
            self._require_skill_permission(connection, skill_id=review["skill_id"], actor=actor, permission="review.manage")
            if review["status"] != "open":
                raise InvariantError("Review is already closed.")
            reviewers = self._reviewers(connection, review_id)
            responses = self._review_responses(connection, review_id)
            publish_targets = self._review_publish_targets(connection, review_id)
            return {
                "review": self._row_dict(review),
                "reviewer_count": len(reviewers),
                "responses": responses,
                "publish_targets": publish_targets,
            }

    def apply_review_closure(
        self,
        *,
        review_id: str,
        actor: str,
        checks: list[dict[str, Any]],
        summary: dict[str, Any],
        auto_publish_target_ids: list[str],
    ) -> dict[str, Any]:
        closed_at = utc_now()
        with self._write_session() as connection:
            review = self._review_row(connection, review_id)
            self._require_skill_permission(connection, skill_id=review["skill_id"], actor=actor, permission="review.manage")
            if review["status"] != "open":
                raise InvariantError("Review is already closed.")
            connection.execute(delete(orm.ReviewCheckResult).where(orm.ReviewCheckResult.review_request_id == review_id))
            for check in checks:
                connection.execute(
                    insert(orm.ReviewCheckResult).values(
                        review_request_id=review_id,
                        skill_id=review["skill_id"],
                        check_id=check["check_id"],
                        passed=check["passed"],
                        details=check["details"],
                        created_at=closed_at,
                    )
                )
            connection.execute(
                update(orm.ReviewRequest)
                .where(orm.ReviewRequest.id == review_id)
                .values(status="closed", summary=summary, closed_at=closed_at, closed_by=actor)
            )
            closed_review = self._review_row(connection, review_id)
            for publish_target_id in auto_publish_target_ids:
                try:
                    record = self._ensure_publish_record(
                        connection,
                        skill_id=review["skill_id"],
                        skill_version_id=review["skill_version_id"],
                        review_id=review_id,
                        publish_target_id=publish_target_id,
                        actor=actor,
                        created_at=closed_at,
                    )
                    self._enqueue_publish_release_job(
                        connection,
                        publish_record_id=record["id"],
                        actor=actor,
                        created_at=closed_at,
                    )
                except InvariantError:
                    continue
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="review.closed",
                    resource_type="skill",
                    resource_id=review["skill_id"],
                    payload={"review_request_id": review_id, "skill_version_id": review["skill_version_id"]},
                    created_at=closed_at,
                )
            )
            return self._review_detail(connection, closed_review)
