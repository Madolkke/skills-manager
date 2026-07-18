from __future__ import annotations

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class AdminAccessService(ServiceBase[SkillHubStore]):
    def list_groups(self) -> object:
        return self.store.list_groups()

    def create_group(self, *, name: str, description: str | None) -> object:
        return self.store.create_group(name=name, description=description, actor="admin-console")

    def update_group(self, *, group_id: str, name: str, description: str | None) -> object:
        return self.store.update_group(group_id=group_id, name=name, description=description, actor="admin-console")

    def delete_group(self, *, group_id: str) -> object:
        return self.store.delete_group_admin(group_id=group_id)

    def add_group_member(self, *, group_id: str, subject_id: str, subject_type: str) -> object:
        return self.store.add_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type, actor="admin-console")

    def remove_group_member(self, *, group_id: str, subject_id: str, subject_type: str) -> object:
        return self.store.remove_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type)

    def list_all_role_assignments(self) -> object:
        return self.store.list_all_role_assignments()

    def assign_role(self, *, resource_type: str, resource_id: str, subject_id: str, subject_type: str, role: str) -> object:
        return self.store.assign_role(
            resource_type=resource_type,
            resource_id=resource_id,
            subject_id=subject_id,
            subject_type=subject_type,
            role=role,
            actor="admin-console",
            require_permission=False,
        )

    def revoke_role_assignment(self, *, role_assignment_id: str) -> object:
        return self.store.revoke_role_assignment_admin(role_assignment_id=role_assignment_id)
