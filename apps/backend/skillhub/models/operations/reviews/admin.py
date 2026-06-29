from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert, select, update

from skillhub.models.errors import InvariantError
from skillhub.models.entities import new_id, utc_now
from skillhub.models.schema import tables
from skillhub.models.rules.review_checks import FIXED_PUBLISH_TARGET_KEYS, normalize_gate_expression, publish_gate_check_definitions


class ReviewAdminMixin:
    def list_publish_targets(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(tables.publish_targets).order_by(tables.publish_targets.c.target_key)).mappings().all()
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
        with self.engine.begin() as connection:
            target = self._publish_target_row(connection, publish_target_id)
            if target["target_key"] not in FIXED_PUBLISH_TARGET_KEYS:
                raise InvariantError("Only fixed publish targets can be updated.")
            connection.execute(
                update(tables.publish_targets)
                .where(tables.publish_targets.c.id == publish_target_id)
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
        with self.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(tables.publish_records)
                    .order_by(desc(tables.publish_records.c.created_at), desc(tables.publish_records.c.id))
                    .limit(200)
                )
                .mappings()
                .all()
            )
            return [self._publish_record_detail(connection, row) for row in rows]

    def confirm_publish_record(self, *, publish_record_id: str, actor: str = "admin-console") -> dict[str, Any]:
        """Legacy store facade; AdminService owns normal confirmation orchestration."""
        snapshot = self.publish_confirmation_snapshot(publish_record_id=publish_record_id, actor=actor)
        if snapshot["record"]["status"] != "pending_confirmation":
            raise InvariantError("Only pending publish records can be confirmed.")
        result = {
            "mode": "noop",
            "message": "Release hook is not configured.",
            "metadata": {
                "publish_record_id": publish_record_id,
                "publish_target_key": snapshot["release_payload"]["publish_target_key"],
                "skill_version_id": snapshot["release_payload"]["skill_version_id"],
            },
        }
        return self.apply_publish_confirmation(publish_record_id=publish_record_id, actor=actor, release_result=result)

    def publish_confirmation_snapshot(self, *, publish_record_id: str, actor: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            record = self._publish_record_row(connection, publish_record_id)
            return {
                "record": self._row_dict(record),
                "release_payload": self._publish_release_payload(connection, record, confirmed_by=actor),
            }

    def apply_publish_confirmation(self, *, publish_record_id: str, actor: str, release_result: dict[str, Any]) -> dict[str, Any]:
        confirmed_at = utc_now()
        with self.engine.begin() as connection:
            record = self._publish_record_row(connection, publish_record_id)
            if record["status"] != "pending_confirmation":
                raise InvariantError("Only pending publish records can be confirmed.")
            metadata = {"release_result": release_result}
            if actor == "system:auto_publish":
                metadata["auto_publish"] = True
            connection.execute(
                update(tables.publish_records)
                .where(tables.publish_records.c.id == publish_record_id)
                .values(status="released", metadata=metadata, confirmed_at=confirmed_at, confirmed_by=actor)
            )
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="publish.released",
                    resource_type="publish_record",
                    resource_id=publish_record_id,
                    payload={"publish_target_id": record["publish_target_id"], "skill_version_id": record["skill_version_id"]},
                    created_at=confirmed_at,
                )
            )
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def apply_publish_failure(self, *, publish_record_id: str, actor: str, error_message: str, release_result: dict[str, Any] | None = None) -> dict[str, Any]:
        failed_at = utc_now()
        with self.engine.begin() as connection:
            record = self._publish_record_row(connection, publish_record_id)
            metadata = {
                **(record["metadata"] or {}),
                "auto_publish": actor == "system:auto_publish",
                "release_error": error_message,
            }
            if release_result is not None:
                metadata["release_result"] = release_result
            connection.execute(
                update(tables.publish_records)
                .where(tables.publish_records.c.id == publish_record_id)
                .values(status="failed", metadata=metadata, confirmed_at=failed_at, confirmed_by=actor)
            )
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="publish.failed",
                    resource_type="publish_record",
                    resource_id=publish_record_id,
                    payload={"publish_target_id": record["publish_target_id"], "skill_version_id": record["skill_version_id"], "error": error_message},
                    created_at=failed_at,
                )
            )
            return self._publish_record_detail(connection, self._publish_record_row(connection, publish_record_id))

    def cancel_publish_record(self, *, publish_record_id: str, actor: str = "admin-console") -> dict[str, Any]:
        """Legacy store facade; AdminService owns normal cancellation orchestration."""
        snapshot = self.publish_cancellation_snapshot(publish_record_id=publish_record_id, actor=actor)
        if snapshot["record"]["status"] not in {"pending_confirmation", "failed"}:
            raise InvariantError("Only pending or failed publish records can be cancelled.")
        return self.apply_publish_cancellation(publish_record_id=publish_record_id, actor=actor)

    def publish_cancellation_snapshot(self, *, publish_record_id: str, actor: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            return {"record": self._row_dict(self._publish_record_row(connection, publish_record_id)), "actor": actor}

    def apply_publish_cancellation(self, *, publish_record_id: str, actor: str) -> dict[str, Any]:
        cancelled_at = utc_now()
        with self.engine.begin() as connection:
            record = self._publish_record_row(connection, publish_record_id)
            if record["status"] not in {"pending_confirmation", "failed"}:
                raise InvariantError("Only pending or failed publish records can be cancelled.")
            connection.execute(
                update(tables.publish_records)
                .where(tables.publish_records.c.id == publish_record_id)
                .values(status="cancelled", metadata={**(record["metadata"] or {}), "cancelled_by": actor})
            )
            connection.execute(
                insert(tables.audit_events).values(
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
            "skill_version_id": version["id"],
            "version": version["version"],
            "content_digest": version["content_digest"],
            "bundle_artifact_id": bundle_artifact_id,
            "content_ref": content_ref,
            "review_request_id": record["review_request_id"],
            "review_check_results": record["check_snapshot"] or [],
            "requested_by": record["created_by"],
            "confirmed_by": confirmed_by,
        }
