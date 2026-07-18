from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id
from skillhub.models.errors import InvariantError
from skillhub.models.rules.publish_policy import decide_publish_request
from skillhub.models.schema import orm


class ReviewPublishingMixin:
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
                orm.select_entity(orm.PublishRecord)
                .where(orm.PublishRecord.skill_version_id == skill_version_id)
                .where(orm.PublishRecord.publish_target_id == publish_target_id)
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if existing["status"] in {"cancelled", "failed"}:
                connection.execute(
                    update(orm.PublishRecord)
                    .where(orm.PublishRecord.id == existing["id"])
                    .values(
                        status="pending_confirmation",
                        review_request_id=review_id,
                        check_snapshot=check_snapshot,
                        metadata_payload={},
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
        connection.execute(
            insert(orm.PublishRecord).values(
                **{key: value for key, value in record.items() if key != "metadata"},
                metadata_payload=record["metadata"],
            )
        )
        return record
