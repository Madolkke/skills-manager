from __future__ import annotations

from typing import Any

from sqlalchemy import and_, desc, insert, or_, select, update

from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.entities import new_id
from skillhub.models.rules.publish_policy import decide_publish_request
from skillhub.models.schema import tables


class ReviewHelperMixin:
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

    def _snapshot_reviewers(self, connection, *, skill_id: str, review_id: str, created_at) -> list[str]:
        resource_filters = [and_(tables.role_assignments.c.resource_type == "skill", tables.role_assignments.c.resource_id == skill_id)]
        tag_resource_ids = self._skill_tag_resource_ids(connection, skill_id)
        if tag_resource_ids:
            resource_filters.append(
                and_(tables.role_assignments.c.resource_type == "skill_tag", tables.role_assignments.c.resource_id.in_(tag_resource_ids))
            )
        rows = (
            connection.execute(
                select(tables.role_assignments)
                .where(or_(*resource_filters))
                .where(tables.role_assignments.c.role == "reviewer")
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
                        select(tables.group_memberships.c.subject_id)
                        .where(tables.group_memberships.c.group_id == assignment["subject_id"])
                        .where(tables.group_memberships.c.subject_type == "user")
                    )
                    .scalars()
                    .all()
                )
                for member in members:
                    reviewers.setdefault(member, ("group", assignment["subject_id"]))
        for reviewer, source in sorted(reviewers.items()):
            connection.execute(
                insert(tables.review_request_reviewers).values(
                    review_request_id=review_id,
                    skill_id=skill_id,
                    reviewer_actor=reviewer,
                    source_subject_type=source[0],
                    source_subject_id=source[1],
                    created_at=created_at,
                )
            )
        return sorted(reviewers)

    def _insert_review_notifications(self, connection, *, review_id: str, skill_slug: str, reviewers: list[str], actor: str, created_at) -> None:
        for reviewer in reviewers:
            connection.execute(
                insert(tables.notifications).values(
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

    def _required_results_for_target(self, connection, *, target, review) -> list[dict[str, Any]]:
        return decide_publish_request(
            target=target,
            reviewer_count=len(self._reviewers(connection, review["id"])),
            responses=self._review_responses(connection, review["id"]),
            stored_checks=self._review_check_results(connection, review["id"]),
        )

    def _assert_review_passes_target(self, connection, *, target, review) -> list[dict[str, Any]]:
        if not target["enabled"]:
            raise InvariantError("Publish target is disabled.")
        results = self._required_results_for_target(connection, target=target, review=review)
        if not all(item["passed"] for item in results):
            raise InvariantError("Review checks failed for publish target: publish_gate")
        return results

    def _ensure_publish_record(
        self,
        connection,
        *,
        skill_id: str,
        skill_version_id: str,
        review_id: str,
        publish_target_id: str,
        actor: str,
        created_at,
    ) -> dict[str, Any]:
        review = self._review_row(connection, review_id)
        if review["status"] != "closed":
            raise InvariantError("Review must be closed before requesting publish.")
        target = self._publish_target_row(connection, publish_target_id)
        check_snapshot = self._assert_review_passes_target(connection, target=target, review=review)
        return self._upsert_publish_record(
            connection,
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            review_id=review_id,
            publish_target_id=publish_target_id,
            actor=actor,
            created_at=created_at,
            check_snapshot=check_snapshot,
        )

    def _upsert_publish_record(
        self,
        connection,
        *,
        skill_id: str,
        skill_version_id: str,
        review_id: str,
        publish_target_id: str,
        actor: str,
        created_at,
        check_snapshot: list[dict[str, Any]],
    ) -> dict[str, Any]:
        existing = (
            connection.execute(
                select(tables.publish_records)
                .where(tables.publish_records.c.skill_version_id == skill_version_id)
                .where(tables.publish_records.c.publish_target_id == publish_target_id)
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if existing["status"] in {"cancelled", "failed"}:
                connection.execute(
                    update(tables.publish_records)
                    .where(tables.publish_records.c.id == existing["id"])
                    .values(
                        status="pending_confirmation",
                        review_request_id=review_id,
                        check_snapshot=check_snapshot,
                        metadata={},
                        confirmed_at=None,
                        confirmed_by=None,
                        created_by=actor,
                        created_at=created_at,
                    )
                )
                return self._row_dict(self._publish_record_row(connection, existing["id"]))
            return self._row_dict(existing)
        record = {
            "id": new_id("publish"),
            "skill_id": skill_id,
            "skill_version_id": skill_version_id,
            "review_request_id": review_id,
            "publish_target_id": publish_target_id,
            "status": "pending_confirmation",
            "check_snapshot": check_snapshot,
            "metadata": {},
            "confirmed_at": None,
            "confirmed_by": None,
            "created_at": created_at,
            "created_by": actor,
        }
        connection.execute(insert(tables.publish_records).values(**record))
        return record

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
