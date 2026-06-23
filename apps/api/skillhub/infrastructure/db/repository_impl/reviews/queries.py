from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from skillhub.infrastructure.db import tables


class ReviewQueryMixin:
    def list_skill_reviews(self, *, skill_id: str, actor: str | None = None) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            rows = (
                connection.execute(
                    select(tables.review_requests)
                    .where(tables.review_requests.c.skill_id == skill_id)
                    .order_by(desc(tables.review_requests.c.created_at), desc(tables.review_requests.c.id))
                )
                .mappings()
                .all()
            )
            return [self._review_detail(connection, row) for row in rows]

    def list_my_reviews(self, *, actor: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(tables.review_requests)
                    .where(
                        tables.review_requests.c.id.in_(
                            select(tables.review_request_reviewers.c.review_request_id).where(
                                tables.review_request_reviewers.c.reviewer_actor == actor
                            )
                        )
                    )
                    .order_by(desc(tables.review_requests.c.created_at), desc(tables.review_requests.c.id))
                )
                .mappings()
                .all()
            )
            return [self._review_detail(connection, row) for row in rows]

    def list_my_notifications(self, *, actor: str) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(tables.notifications)
                    .where(tables.notifications.c.recipient_actor_id == actor)
                    .order_by(desc(tables.notifications.c.created_at), desc(tables.notifications.c.id))
                    .limit(100)
                )
                .mappings()
                .all()
            )
            return [self._row_dict(row) for row in rows]

    def skill_publish_overview(self, *, skill_id: str, actor: str | None = None) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            versions = (
                connection.execute(
                    select(tables.skill_versions)
                    .where(tables.skill_versions.c.skill_id == skill_id)
                    .order_by(desc(tables.skill_versions.c.version_number))
                )
                .mappings()
                .all()
            )
            targets = (
                connection.execute(
                    select(tables.publish_targets)
                    .where(tables.publish_targets.c.enabled.is_(True))
                    .order_by(tables.publish_targets.c.target_key)
                )
                .mappings()
                .all()
            )
            return {
                "skill": self._skill_record(connection, skill),
                "versions": [
                    {
                        "version": self._skill_version_detail(connection, version),
                        "review": (
                            self._review_detail(connection, review)
                            if (review := self._latest_review_for_version(connection, version["id"])) is not None
                            else None
                        ),
                    }
                    for version in versions
                ],
                "publish_targets": [self._row_dict(row) for row in targets],
                "publish_records": self._publish_records(connection, skill_id=skill_id),
            }
