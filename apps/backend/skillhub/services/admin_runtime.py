from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase
from skillhub.services.publish_release import perform_publish_release


class AdminRuntimeService(ServiceBase[SkillHubStore]):
    def list_publish_targets(self) -> object:
        return self.store.list_publish_targets()

    def list_publish_gate_checks(self) -> object:
        return self.store.list_publish_gate_checks()

    def update_publish_target(self, *, publish_target_id: str, enabled: bool, auto_publish_enabled: bool, gate_expression: dict[str, Any]) -> object:
        return self.store.update_publish_target(
            publish_target_id=publish_target_id,
            enabled=enabled,
            auto_publish_enabled=auto_publish_enabled,
            gate_expression=gate_expression,
        )

    def list_publish_records(self) -> object:
        return self.store.list_publish_records()

    def list_workers(self) -> object:
        return self.store.admin_worker_status_overview()

    def confirm_publish_record(self, *, publish_record_id: str) -> object:
        snapshot = self.store.publish_confirmation_snapshot(publish_record_id=publish_record_id, actor="admin-console")
        if snapshot["record"]["status"] != "pending_confirmation":
            raise InvariantError("Only pending publish records can be confirmed.")
        result = perform_publish_release(snapshot["release_payload"])
        return self.store.apply_publish_confirmation(
            publish_record_id=publish_record_id,
            actor="admin-console",
            release_result=result,
        )

    def cancel_publish_record(self, *, publish_record_id: str) -> object:
        snapshot = self.store.publish_cancellation_snapshot(publish_record_id=publish_record_id, actor="admin-console")
        if snapshot["record"]["status"] not in {"pending_confirmation", "failed"}:
            raise InvariantError("Only pending or failed publish records can be cancelled.")
        return self.store.apply_publish_cancellation(publish_record_id=publish_record_id, actor="admin-console")

    def list_opencode_agents(self) -> object:
        return self.store.list_opencode_agents_admin()

    def create_opencode_agent(self, *, payload: dict[str, Any]) -> object:
        return self.store.create_opencode_agent(payload=payload, actor="admin-console")

    def update_opencode_agent(self, *, agent_id: str, payload: dict[str, Any]) -> object:
        return self.store.update_opencode_agent(agent_id=agent_id, payload=payload, actor="admin-console")

    def delete_opencode_agent(self, *, agent_id: str) -> object:
        return self.store.delete_opencode_agent(agent_id=agent_id, actor="admin-console")
