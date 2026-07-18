from __future__ import annotations

from typing import Any

from sqlalchemy import insert

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.rules.publish_policy import decide_publish_request
from skillhub.models.schema import orm


class ReviewPublishCommandMixin:
    def create_publish_record(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        review_request_id: str,
        publish_target_id: str,
        actor: str,
    ) -> dict[str, Any]:
        """Legacy store facade; ReviewService owns publish-request orchestration."""
        snapshot = self.publish_request_snapshot(
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
        return self.apply_publish_request(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            review_request_id=review_request_id,
            publish_target_id=publish_target_id,
            actor=actor,
            check_snapshot=check_snapshot,
        )

    def publish_request_snapshot(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        review_request_id: str,
        publish_target_id: str,
        actor: str,
    ) -> dict[str, Any]:
        with self._read_session() as connection:
            review = self._review_row(connection, review_request_id)
            if review["skill_id"] != skill_id or review["skill_version_id"] != skill_version_id:
                raise InvariantError("Review does not match the requested skill version.")
            if review["status"] != "closed":
                raise InvariantError("Review must be closed before requesting publish.")
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="publish.request")
            return {
                "review": self._row_dict(review),
                "target": self._row_dict(self._publish_target_row(connection, publish_target_id)),
                "reviewer_count": len(self._reviewers(connection, review_request_id)),
                "responses": self._review_responses(connection, review_request_id),
                "stored_checks": self._review_check_results(connection, review_request_id),
            }

    def apply_publish_request(
        self,
        *,
        skill_id: str,
        skill_version_id: str,
        review_request_id: str,
        publish_target_id: str,
        actor: str,
        check_snapshot: list[dict[str, Any]],
    ) -> dict[str, Any]:
        created_at = utc_now()
        with self._write_session() as connection:
            review = self._review_row(connection, review_request_id)
            if review["skill_id"] != skill_id or review["skill_version_id"] != skill_version_id:
                raise InvariantError("Review does not match the requested skill version.")
            self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="publish.request")
            record = self._upsert_publish_record(
                connection,
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                review_id=review_request_id,
                publish_target_id=publish_target_id,
                actor=actor,
                created_at=created_at,
                check_snapshot=check_snapshot,
            )
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="publish.requested",
                    resource_type="skill",
                    resource_id=skill_id,
                    payload={"publish_record_id": record["id"], "publish_target_id": publish_target_id},
                    created_at=created_at,
                )
            )
            return self._publish_record_row(connection, record["id"])
