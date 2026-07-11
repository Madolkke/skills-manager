from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase
from skillhub.services.publish_release import perform_publish_release


class AdminService(ServiceBase[SkillHubStore]):
    def list_skills(self) -> Any:
        return self.store.list_skills()

    def update_skill(self, *, skill_id: str, slug: str | None, owner_ref: str | None, tags: list[Any] | None) -> Any:
        return self.store.update_skill_admin(skill_id=skill_id, slug=slug, owner_ref=owner_ref, tags=tags)

    def list_groups(self) -> Any:
        return self.store.list_groups()

    def create_group(self, *, name: str, description: str | None) -> Any:
        return self.store.create_group(name=name, description=description, actor="admin-console")

    def update_group(self, *, group_id: str, name: str, description: str | None) -> Any:
        return self.store.update_group(group_id=group_id, name=name, description=description, actor="admin-console")

    def delete_group(self, *, group_id: str) -> Any:
        return self.store.delete_group_admin(group_id=group_id)

    def add_group_member(self, *, group_id: str, subject_id: str, subject_type: str) -> Any:
        return self.store.add_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type, actor="admin-console")

    def remove_group_member(self, *, group_id: str, subject_id: str, subject_type: str) -> Any:
        return self.store.remove_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type)

    def list_tag_groups(self) -> Any:
        return self.store.list_tag_groups()

    def create_tag_group(self, *, group_id: str, display_name: str, description: str | None, sort_order: int, required: bool = False, free_form: bool = False) -> Any:
        return self.store.create_tag_group(
            group_id=group_id,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            required=required,
            free_form=free_form,
            actor="admin-console",
        )

    def update_tag_group(self, *, group_id: str, display_name: str, description: str | None, sort_order: int, required: bool = False, free_form: bool = False) -> Any:
        return self.store.update_tag_group(
            group_id=group_id,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            required=required,
            free_form=free_form,
            actor="admin-console",
        )

    def delete_tag_group(self, *, group_id: str) -> Any:
        return self.store.delete_tag_group_admin(group_id=group_id)

    def create_tag_value(self, *, group_id: str, value: str, display_name: str | None, description: str | None, sort_order: int) -> Any:
        return self.store.create_tag_value(
            group_id=group_id,
            value=value,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            actor="admin-console",
        )

    def update_tag_value(self, *, group_id: str, value: str, display_name: str | None, description: str | None, sort_order: int) -> Any:
        return self.store.update_tag_value(
            group_id=group_id,
            value=value,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            actor="admin-console",
        )

    def delete_tag_value(self, *, group_id: str, value: str) -> Any:
        return self.store.delete_tag_value_admin(group_id=group_id, value=value)

    def tag_cascade_overview(self) -> Any:
        return self.store.tag_cascade_overview()

    def create_tag_cascade(self, *, parent_group_id: str, parent_value: str, child_group_id: str) -> Any:
        return self.store.create_tag_cascade(
            parent_group_id=parent_group_id,
            parent_value=parent_value,
            child_group_id=child_group_id,
            actor="admin-console",
        )

    def delete_tag_cascade(self, *, child_group_id: str) -> Any:
        return self.store.delete_tag_cascade(child_group_id=child_group_id, actor="admin-console")

    def list_all_role_assignments(self) -> Any:
        return self.store.list_all_role_assignments()

    def assign_role(self, *, resource_type: str, resource_id: str, subject_id: str, subject_type: str, role: str) -> Any:
        return self.store.assign_role(
            resource_type=resource_type,
            resource_id=resource_id,
            subject_id=subject_id,
            subject_type=subject_type,
            role=role,
            actor="admin-console",
            require_permission=False,
        )

    def revoke_role_assignment(self, *, role_assignment_id: str) -> Any:
        return self.store.revoke_role_assignment_admin(role_assignment_id=role_assignment_id)

    def list_publish_targets(self) -> Any:
        return self.store.list_publish_targets()

    def list_publish_gate_checks(self) -> Any:
        return self.store.list_publish_gate_checks()

    def update_publish_target(self, *, publish_target_id: str, enabled: bool, auto_publish_enabled: bool, gate_expression: dict[str, Any]) -> Any:
        return self.store.update_publish_target(
            publish_target_id=publish_target_id,
            enabled=enabled,
            auto_publish_enabled=auto_publish_enabled,
            gate_expression=gate_expression,
        )

    def list_publish_records(self) -> Any:
        return self.store.list_publish_records()

    def list_workers(self) -> Any:
        return self.store.admin_worker_status_overview()

    def confirm_publish_record(self, *, publish_record_id: str) -> Any:
        snapshot = self.store.publish_confirmation_snapshot(publish_record_id=publish_record_id, actor="admin-console")
        if snapshot["record"]["status"] != "pending_confirmation":
            raise InvariantError("Only pending publish records can be confirmed.")
        result = perform_publish_release(snapshot["release_payload"])
        return self.store.apply_publish_confirmation(
            publish_record_id=publish_record_id,
            actor="admin-console",
            release_result=result,
        )

    def cancel_publish_record(self, *, publish_record_id: str) -> Any:
        snapshot = self.store.publish_cancellation_snapshot(publish_record_id=publish_record_id, actor="admin-console")
        if snapshot["record"]["status"] not in {"pending_confirmation", "failed"}:
            raise InvariantError("Only pending or failed publish records can be cancelled.")
        return self.store.apply_publish_cancellation(publish_record_id=publish_record_id, actor="admin-console")

    def list_opencode_agents(self) -> Any:
        return self.store.list_opencode_agents_admin()

    def create_opencode_agent(self, *, payload: dict[str, Any]) -> Any:
        return self.store.create_opencode_agent(payload=payload, actor="admin-console")

    def update_opencode_agent(self, *, agent_id: str, payload: dict[str, Any]) -> Any:
        return self.store.update_opencode_agent(agent_id=agent_id, payload=payload, actor="admin-console")

    def delete_opencode_agent(self, *, agent_id: str) -> Any:
        return self.store.delete_opencode_agent(agent_id=agent_id, actor="admin-console")
