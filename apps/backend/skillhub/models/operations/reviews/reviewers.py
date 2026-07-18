from __future__ import annotations

from typing import Any

from sqlalchemy import and_, insert, or_, select

from skillhub.models.entities import new_id
from skillhub.models.errors import ConflictError, InvariantError
from skillhub.models.schema import orm


class ReviewerSnapshotMixin:
    def _snapshot_reviewers(self, connection, *, skill_id: str, review_id: str, created_at) -> list[str]:
        resource_filters = [and_(orm.RoleAssignment.resource_type == "skill", orm.RoleAssignment.resource_id == skill_id)]
        tag_resource_ids = self._skill_tag_resource_ids(connection, skill_id)
        if tag_resource_ids:
            resource_filters.append(
                and_(orm.RoleAssignment.resource_type == "skill_tag", orm.RoleAssignment.resource_id.in_(tag_resource_ids))
            )
        rows = (
            connection.execute(
                orm.select_entity(orm.RoleAssignment)
                .where(or_(*resource_filters))
                .where(orm.RoleAssignment.role == "reviewer")
            )
            .mappings()
            .all()
        )
        reviewers: dict[str, tuple[str, str]] = {}
        for assignment in rows:
            if assignment["subject_type"] == "user":
                reviewers.setdefault(assignment["subject_id"], ("user", assignment["subject_id"]))
            elif assignment["subject_type"] == "group":
                members = (
                    connection.execute(
                        select(orm.GroupMembership.subject_id)
                        .where(orm.GroupMembership.group_id == assignment["subject_id"])
                        .where(orm.GroupMembership.subject_type == "user")
                    )
                    .scalars()
                    .all()
                )
                for member in members:
                    reviewers.setdefault(member, ("group", assignment["subject_id"]))
        self._insert_reviewers(connection, skill_id=skill_id, review_id=review_id, reviewers=reviewers, created_at=created_at)
        return sorted(reviewers)

    def _snapshot_selected_reviewers(
        self,
        connection,
        *,
        skill_id: str,
        review_id: str,
        created_at,
        reviewer_sources: list[dict[str, Any]],
    ) -> list[str]:
        groups: list[str] = []
        users: list[str] = []
        for source in reviewer_sources:
            subject_type = self._clean_subject_type(str(source.get("subject_type", "user")))
            subject_id = self._clean_subject_id(str(source.get("subject_id", "")))
            if subject_type == "group":
                if subject_id not in groups:
                    groups.append(subject_id)
            elif subject_id not in users:
                users.append(subject_id)

        reviewers: dict[str, tuple[str, str]] = {}
        for group_id in groups:
            group = self._group_row(connection, group_id)
            if group["scope_type"] != "global":
                raise InvariantError("Only global groups can be selected as review groups.")
            members = (
                connection.execute(
                    select(orm.GroupMembership.subject_id)
                    .where(orm.GroupMembership.group_id == group_id)
                    .where(orm.GroupMembership.subject_type == "user")
                    .order_by(orm.GroupMembership.subject_id)
                )
                .scalars()
                .all()
            )
            for member in members:
                reviewers.setdefault(member, ("group", group_id))

        for user in users:
            reviewers[user] = ("user", user)

        if not reviewers:
            raise ConflictError("No reviewers were resolved from selected reviewer sources.")
        self._insert_reviewers(connection, skill_id=skill_id, review_id=review_id, reviewers=reviewers, created_at=created_at)
        return sorted(reviewers)

    def _insert_reviewers(self, connection, *, skill_id: str, review_id: str, reviewers: dict[str, tuple[str, str]], created_at) -> None:
        for reviewer, source in sorted(reviewers.items()):
            connection.execute(
                insert(orm.ReviewRequestReviewer).values(
                    review_request_id=review_id,
                    skill_id=skill_id,
                    reviewer_actor=reviewer,
                    source_subject_type=source[0],
                    source_subject_id=source[1],
                    created_at=created_at,
                )
            )

    def _insert_review_notifications(self, connection, *, review_id: str, skill_slug: str, reviewers: list[str], actor: str, created_at) -> None:
        for reviewer in reviewers:
            connection.execute(
                insert(orm.Notification).values(
                    id=new_id("notification"),
                    recipient_actor_id=reviewer,
                    type="review_requested",
                    title=f"{skill_slug} 有新的评审请求",
                    body="请进入我的评审提交评分和意见。",
                    resource_type="review_request",
                    resource_id=review_id,
                    read_at=None,
                    created_at=created_at,
                    created_by=actor,
                )
            )
