from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select

from skillhub.models.schema import orm


class ReviewQueryMixin:
    def reviewer_candidates(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="review.manage")
            rows = (
                connection.execute(
                    orm.select_entity(orm.Group)
                    .where(orm.Group.scope_type == "global")
                    .order_by(orm.Group.name, orm.Group.id)
                )
                .mappings()
                .all()
            )
            groups = []
            for row in rows:
                members = self._group_members(connection, row["id"])
                groups.append({**self._row_dict(row), "members": members, "member_count": len(members)})
            return {"skill_id": skill_id, "groups": groups}

    def list_skill_reviews(self, *, skill_id: str, actor: str | None = None) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            rows = (
                connection.execute(
                    orm.select_entity(orm.ReviewRequest)
                    .where(orm.ReviewRequest.skill_id == skill_id)
                    .order_by(desc(orm.ReviewRequest.created_at), desc(orm.ReviewRequest.id))
                )
                .mappings()
                .all()
            )
            return [self._review_detail(connection, row) for row in rows]

    def list_my_reviews(self, *, actor: str) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = (
                connection.execute(
                    orm.select_entity(orm.ReviewRequest)
                    .where(
                        orm.ReviewRequest.id.in_(
                            select(orm.ReviewRequestReviewer.review_request_id).where(
                                orm.ReviewRequestReviewer.reviewer_actor == actor
                            )
                        )
                    )
                    .order_by(desc(orm.ReviewRequest.created_at), desc(orm.ReviewRequest.id))
                )
                .mappings()
                .all()
            )
            return [self._review_detail(connection, row) for row in rows]

    def list_my_notifications(self, *, actor: str) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = (
                connection.execute(
                    orm.select_entity(orm.Notification)
                    .where(orm.Notification.recipient_actor_id == actor)
                    .order_by(desc(orm.Notification.created_at), desc(orm.Notification.id))
                    .limit(100)
                )
                .mappings()
                .all()
            )
            return [self._row_dict(row) for row in rows]

    def skill_publish_overview(self, *, skill_id: str, actor: str | None = None) -> dict[str, Any]:
        with self._read_session() as connection:
            skill = self._skill_row(connection, skill_id)
            versions = (
                connection.execute(
                    orm.select_entity(orm.SkillVersion)
                    .where(orm.SkillVersion.skill_id == skill_id)
                    .order_by(desc(orm.SkillVersion.version_number))
                )
                .mappings()
                .all()
            )
            targets = (
                connection.execute(
                    orm.select_entity(orm.PublishTarget)
                    .where(orm.PublishTarget.enabled.is_(True))
                    .order_by(orm.PublishTarget.target_key)
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
