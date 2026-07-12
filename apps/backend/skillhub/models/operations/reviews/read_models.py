from __future__ import annotations

from typing import Any

from sqlalchemy import and_, desc, select

from skillhub.models.errors import NotFoundError
from skillhub.models.schema import tables


class ReviewReadMixin:
    def _review_row(self, connection, review_id: str):
        row = connection.execute(select(tables.review_requests).where(tables.review_requests.c.id == review_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"ReviewRequest not found: {review_id}")
        return row

    def _publish_target_row(self, connection, publish_target_id: str):
        row = connection.execute(select(tables.publish_targets).where(tables.publish_targets.c.id == publish_target_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"PublishTarget not found: {publish_target_id}")
        return row

    def _publish_record_row(self, connection, publish_record_id: str):
        row = connection.execute(select(tables.publish_records).where(tables.publish_records.c.id == publish_record_id)).mappings().one_or_none()
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
                select(tables.review_request_reviewers)
                .where(tables.review_request_reviewers.c.review_request_id == review_id)
                .order_by(tables.review_request_reviewers.c.reviewer_actor)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _review_responses(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(tables.review_responses)
                .where(tables.review_responses.c.review_request_id == review_id)
                .order_by(tables.review_responses.c.reviewer_actor)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _review_publish_targets(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(
                    tables.review_request_publish_targets,
                    tables.publish_targets.c.target_key,
                    tables.publish_targets.c.name,
                    tables.publish_targets.c.description,
                    tables.publish_targets.c.enabled,
                    tables.publish_targets.c.auto_publish_enabled,
                    tables.publish_targets.c.gate_expression,
                    tables.publish_targets.c.config,
                )
                .join(tables.publish_targets, tables.publish_targets.c.id == tables.review_request_publish_targets.c.publish_target_id)
                .where(tables.review_request_publish_targets.c.review_request_id == review_id)
                .order_by(tables.publish_targets.c.target_key)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _review_check_results(self, connection, review_id: str) -> list[dict[str, Any]]:
        rows = (
            connection.execute(
                select(tables.review_check_results)
                .where(tables.review_check_results.c.review_request_id == review_id)
                .order_by(tables.review_check_results.c.check_id)
            )
            .mappings()
            .all()
        )
        return [self._row_dict(row) for row in rows]

    def _publish_records(self, connection, *, review_id: str | None = None, skill_id: str | None = None) -> list[dict[str, Any]]:
        query = (
            select(
                tables.publish_records,
                tables.publish_targets.c.target_key,
                tables.publish_targets.c.name.label("target_name"),
                tables.publish_targets.c.description.label("target_description"),
                tables.publish_targets.c.enabled.label("target_enabled"),
                tables.publish_targets.c.auto_publish_enabled.label("target_auto_publish_enabled"),
                tables.publish_targets.c.gate_expression.label("target_gate_expression"),
                tables.publish_targets.c.config.label("target_config"),
            )
            .join(tables.publish_targets, tables.publish_targets.c.id == tables.publish_records.c.publish_target_id)
            .order_by(desc(tables.publish_records.c.created_at), desc(tables.publish_records.c.id))
        )
        if review_id is not None:
            query = query.where(tables.publish_records.c.review_request_id == review_id)
        if skill_id is not None:
            query = query.where(tables.publish_records.c.skill_id == skill_id)
        rows = connection.execute(query).mappings().all()
        return [self._row_dict(row) for row in rows]

    def _current_open_review_for_version(self, connection, skill_version_id: str):
        return (
            connection.execute(
                select(tables.review_requests)
                .where(tables.review_requests.c.skill_version_id == skill_version_id)
                .where(tables.review_requests.c.status == "open")
            )
            .mappings()
            .one_or_none()
        )

    def _review_response_row(self, connection, review_id: str, reviewer_actor: str):
        return (
            connection.execute(
                select(tables.review_responses)
                .where(tables.review_responses.c.review_request_id == review_id)
                .where(tables.review_responses.c.reviewer_actor == reviewer_actor)
            )
            .mappings()
            .one_or_none()
        )

    def _reviewer_row(self, connection, review_id: str, reviewer_actor: str):
        return (
            connection.execute(
                select(tables.review_request_reviewers)
                .where(tables.review_request_reviewers.c.review_request_id == review_id)
                .where(tables.review_request_reviewers.c.reviewer_actor == reviewer_actor)
            )
            .mappings()
            .one_or_none()
        )

    def _latest_review_for_version(self, connection, skill_version_id: str):
        return (
            connection.execute(
                select(tables.review_requests)
                .where(tables.review_requests.c.skill_version_id == skill_version_id)
                .order_by(desc(tables.review_requests.c.created_at), desc(tables.review_requests.c.id))
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )

    def _find_review_publish_target(self, connection, *, review_id: str, publish_target_id: str):
        return (
            connection.execute(
                select(tables.review_request_publish_targets).where(
                    and_(
                        tables.review_request_publish_targets.c.review_request_id == review_id,
                        tables.review_request_publish_targets.c.publish_target_id == publish_target_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
