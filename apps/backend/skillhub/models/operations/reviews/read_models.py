from __future__ import annotations

from typing import Any

from sqlalchemy import and_, desc, select

from skillhub.models.errors import NotFoundError
from skillhub.models.schema import orm


class ReviewReadMixin:
    def _review_row(self, connection, review_id: str):
        row = connection.execute(orm.select_entity(orm.ReviewRequest).where(orm.ReviewRequest.id == review_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"ReviewRequest not found: {review_id}")
        return row

    def _publish_target_row(self, connection, publish_target_id: str):
        row = connection.execute(orm.select_entity(orm.PublishTarget).where(orm.PublishTarget.id == publish_target_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"PublishTarget not found: {publish_target_id}")
        return row

    def _publish_record_row(self, connection, publish_record_id: str):
        row = connection.execute(orm.select_entity(orm.PublishRecord).where(orm.PublishRecord.id == publish_record_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"PublishRecord not found: {publish_record_id}")
        return row

    def _review_detail(self, connection, review) -> dict[str, Any]:
        return {
            **self._row_dict(review),
            "skill": self._skill_record(connection, self._skill_row(connection, review["skill_id"])),
            "skill_version": self._skill_version_detail(connection, self._skill_version_row(connection, review["skill_version_id"])),
            "reviewers": self._reviewers(connection, review["id"]),
            "responses": self._review_responses(connection, review["id"]),
            "publish_targets": self._review_publish_targets(connection, review["id"]),
            "check_results": self._review_check_results(connection, review["id"]),
            "publish_records": self._publish_records(connection, review_id=review["id"]),
        }

    def _reviewers(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                orm.select_entity(orm.ReviewRequestReviewer)
                .where(orm.ReviewRequestReviewer.review_request_id == review_id)
                .order_by(orm.ReviewRequestReviewer.reviewer_actor)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _review_responses(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                orm.select_entity(orm.ReviewResponse)
                .where(orm.ReviewResponse.review_request_id == review_id)
                .order_by(orm.ReviewResponse.reviewer_actor)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _review_publish_targets(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(
                    *orm.entity_columns(orm.ReviewRequestPublishTarget),
                    orm.PublishTarget.target_key,
                    orm.PublishTarget.name,
                    orm.PublishTarget.description,
                    orm.PublishTarget.enabled,
                    orm.PublishTarget.auto_publish_enabled,
                    orm.PublishTarget.gate_expression,
                    orm.PublishTarget.config,
                )
                .join(orm.PublishTarget, orm.PublishTarget.id == orm.ReviewRequestPublishTarget.publish_target_id)
                .where(orm.ReviewRequestPublishTarget.review_request_id == review_id)
                .order_by(orm.PublishTarget.target_key)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _review_check_results(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                orm.select_entity(orm.ReviewCheckResult)
                .where(orm.ReviewCheckResult.review_request_id == review_id)
                .order_by(orm.ReviewCheckResult.check_id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _publish_records(self, connection, *, review_id: str | None = None, skill_id: str | None = None) -> list[dict[str, Any]]:
        query = (
            select(
                *orm.entity_columns(orm.PublishRecord),
                orm.PublishTarget.target_key,
                orm.PublishTarget.name.label("target_name"),
                orm.PublishTarget.description.label("target_description"),
                orm.PublishTarget.enabled.label("target_enabled"),
                orm.PublishTarget.auto_publish_enabled.label("target_auto_publish_enabled"),
                orm.PublishTarget.gate_expression.label("target_gate_expression"),
                orm.PublishTarget.config.label("target_config"),
            )
            .join(orm.PublishTarget, orm.PublishTarget.id == orm.PublishRecord.publish_target_id)
            .order_by(desc(orm.PublishRecord.created_at), desc(orm.PublishRecord.id))
        )
        if review_id is not None:
            query = query.where(orm.PublishRecord.review_request_id == review_id)
        if skill_id is not None:
            query = query.where(orm.PublishRecord.skill_id == skill_id)
        rows = connection.execute(query).mappings().all()
        return [self._row_dict(row) for row in rows]

    def _current_open_review_for_version(self, connection, skill_version_id: str):
        return (
            connection.execute(
                orm.select_entity(orm.ReviewRequest)
                .where(orm.ReviewRequest.skill_version_id == skill_version_id)
                .where(orm.ReviewRequest.status == "open")
            )
            .mappings()
            .one_or_none()
        )

    def _review_response_row(self, connection, review_id: str, reviewer_actor: str):
        return (
            connection.execute(
                orm.select_entity(orm.ReviewResponse)
                .where(orm.ReviewResponse.review_request_id == review_id)
                .where(orm.ReviewResponse.reviewer_actor == reviewer_actor)
            )
            .mappings()
            .one_or_none()
        )

    def _reviewer_row(self, connection, review_id: str, reviewer_actor: str):
        return (
            connection.execute(
                orm.select_entity(orm.ReviewRequestReviewer)
                .where(orm.ReviewRequestReviewer.review_request_id == review_id)
                .where(orm.ReviewRequestReviewer.reviewer_actor == reviewer_actor)
            )
            .mappings()
            .one_or_none()
        )

    def _latest_review_for_version(self, connection, skill_version_id: str):
        return (
            connection.execute(
                orm.select_entity(orm.ReviewRequest)
                .where(orm.ReviewRequest.skill_version_id == skill_version_id)
                .order_by(desc(orm.ReviewRequest.created_at), desc(orm.ReviewRequest.id))
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )

    def _find_review_publish_target(self, connection, *, review_id: str, publish_target_id: str):
        return (
            connection.execute(
                orm.select_entity(orm.ReviewRequestPublishTarget).where(
                    and_(
                        orm.ReviewRequestPublishTarget.review_request_id == review_id,
                        orm.ReviewRequestPublishTarget.publish_target_id == publish_target_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
