from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError, InvariantError
from skillhub.models.rules.review_check_definitions import FIXED_PUBLISH_TARGET_KEYS, publish_gate_check_definitions
from skillhub.models.rules.review_checks import normalize_gate_expression
from skillhub.models.schema import orm


class ReviewAdminMixin:
    def list_publish_targets(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = connection.execute(orm.select_entity(orm.PublishTarget).order_by(orm.PublishTarget.target_key)).mappings().all()
            return [self._row_dict(row) for row in rows]

    def list_publish_gate_checks(self) -> list[dict[str, Any]]:
        return publish_gate_check_definitions()

    def update_publish_target(
        self,
        *,
        publish_target_id: str,
        enabled: bool,
        auto_publish_enabled: bool,
        gate_expression: dict[str, Any],
    ) -> dict[str, Any]:
        updated_at = utc_now()
        normalized_expression = normalize_gate_expression(gate_expression)
        with self._write_session() as connection:
            target = self._publish_target_row(connection, publish_target_id)
            if target["target_key"] not in FIXED_PUBLISH_TARGET_KEYS:
                raise InvariantError("Only fixed publish targets can be updated.")
            connection.execute(
                update(orm.PublishTarget)
                .where(orm.PublishTarget.id == publish_target_id)
                .values(
                    enabled=enabled,
                    auto_publish_enabled=auto_publish_enabled,
                    gate_expression=normalized_expression,
                    config={},
                    updated_at=updated_at,
                )
            )
            return self._row_dict(self._publish_target_row(connection, publish_target_id))

    def list_publish_records(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = (
                connection.execute(
                    orm.select_entity(orm.PublishRecord)
                    .order_by(desc(orm.PublishRecord.created_at), desc(orm.PublishRecord.id))
                    .limit(200)
                )
                .mappings()
                .all()
            )
            return [self._publish_record_detail(connection, row) for row in rows]

    def confirm_publish_record(self, *, publish_record_id: str, actor: str = "admin-console") -> dict[str, Any]:
        queued_at = utc_now()
        with self._write_session() as connection:
            record = self._locked_publish_record(connection, publish_record_id)
            if record["status"] != "pending_confirmation":
                raise InvariantError("Only pending publish records can be confirmed.")
            self._queue_publish_record(connection, record=record, actor=actor, queued_at=queued_at)
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def retry_publish_record(self, *, publish_record_id: str, actor: str = "admin-console") -> dict[str, Any]:
        queued_at = utc_now()
        with self._write_session() as connection:
            record = self._locked_publish_record(connection, publish_record_id)
            if record["status"] != "failed":
                raise InvariantError("Only failed publish records can be retried.")
            self._queue_publish_record(connection, record=record, actor=actor, queued_at=queued_at)
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def cancel_publish_record(self, *, publish_record_id: str, actor: str = "admin-console") -> dict[str, Any]:
        cancelled_at = utc_now()
        with self._write_session() as connection:
            snapshot = self._publish_record_row(connection, publish_record_id)
            queued_job = None
            if snapshot["status"] == "queued":
                queued_job = (
                    connection.execute(
                        orm.select_entity(orm.Job)
                        .where(orm.Job.type == "publish_release")
                        .where(orm.Job.status == "queued")
                        .where(orm.Job.payload["publish_record_id"].as_string() == publish_record_id)
                        .with_for_update()
                    )
                    .mappings()
                    .one_or_none()
                )
            record = self._locked_publish_record(connection, publish_record_id)
            if record["status"] == "releasing":
                raise ConflictError("A release in progress cannot be cancelled.")
            if record["status"] not in {"pending_confirmation", "queued"}:
                raise InvariantError("Only pending or queued publish records can be cancelled.")
            if record["status"] == "queued":
                if queued_job is None:
                    raise ConflictError("The queued publish job is already being claimed.")
                connection.execute(
                    update(orm.Job)
                    .where(orm.Job.id == queued_job["id"])
                    .values(status="canceled", finished_at=cancelled_at, error="Publish record was cancelled.")
                )
            connection.execute(
                update(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .values(metadata_payload={**(record["metadata"] or {}), "cancelled_by": actor}, status="cancelled")
            )
            connection.execute(
                insert(orm.AuditEvent).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="publish.cancelled",
                    resource_type="publish_record",
                    resource_id=publish_record_id,
                    payload={},
                    created_at=cancelled_at,
                )
            )
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def _locked_publish_record(self, connection, publish_record_id: str):
        row = (
            connection.execute(
                orm.select_entity(orm.PublishRecord)
                .where(orm.PublishRecord.id == publish_record_id)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return self._publish_record_row(connection, publish_record_id)
        return row

    def _publish_record_detail(self, connection, record) -> dict[str, Any]:
        skill = self._skill_row(connection, record["skill_id"])
        version = self._skill_version_row(connection, record["skill_version_id"])
        target = self._publish_target_row(connection, record["publish_target_id"])
        return {
            **self._row_dict(record),
            "skill": self._skill_record(connection, skill),
            "skill_version": self._skill_version_detail(connection, version),
            "publish_target": self._row_dict(target),
            "review": self._review_detail(connection, self._review_row(connection, record["review_request_id"])),
        }

    def _publish_release_payload(self, connection, record, *, confirmed_by: str) -> dict[str, Any]:
        skill = self._skill_row(connection, record["skill_id"])
        version = self._skill_version_row(connection, record["skill_version_id"])
        target = self._publish_target_row(connection, record["publish_target_id"])
        content_ref = version["content_ref"] or {}
        bundle_artifact_id = None
        locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
        if isinstance(locator, str) and locator.startswith("artifact:"):
            bundle_artifact_id = locator.split(":", 1)[1]
        return {
            "publish_record_id": record["id"],
            "publish_target_id": target["id"],
            "publish_target_key": target["target_key"],
            "publish_target_name": target["name"],
            "publish_target_config": target["config"] or {},
            "skill_id": skill["id"],
            "skill_slug": skill["slug"],
            "skill_tags": [
                {"group_id": str(tag["group_id"]), "value": str(tag["value"])}
                for tag in self._skill_tags(connection, skill["id"])
            ],
            "skill_version_id": version["id"],
            "version": version["version"],
            "content_digest": version["content_digest"],
            "bundle_artifact_id": bundle_artifact_id,
            "content_ref": content_ref,
            "review_request_id": record["review_request_id"],
            "review_check_results": record["check_snapshot"] or [],
            "requested_by": record["created_by"],
            "confirmed_by": confirmed_by,
            "idempotency_key": f"publish_release:{record['id']}",
        }
