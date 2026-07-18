from __future__ import annotations

from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class AdminCatalogService(ServiceBase[SkillHubStore]):
    def list_skills(self) -> object:
        return self.store.list_skills()

    def update_skill(self, *, skill_id: str, slug: str | None, owner_ref: str | None, tags: list[Any] | None) -> object:
        return self.store.update_skill_admin(skill_id=skill_id, slug=slug, owner_ref=owner_ref, tags=tags)

    def list_tag_groups(self) -> object:
        return self.store.list_tag_groups()

    def create_tag_group(self, *, group_id: str, display_name: str, description: str | None, sort_order: int, required: bool = False, free_form: bool = False) -> object:
        return self.store.create_tag_group(
            group_id=group_id,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            required=required,
            free_form=free_form,
            actor="admin-console",
        )

    def update_tag_group(self, *, group_id: str, display_name: str, description: str | None, sort_order: int, required: bool = False, free_form: bool = False) -> object:
        return self.store.update_tag_group(
            group_id=group_id,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            required=required,
            free_form=free_form,
            actor="admin-console",
        )

    def delete_tag_group(self, *, group_id: str) -> object:
        return self.store.delete_tag_group_admin(group_id=group_id)

    def create_tag_value(self, *, group_id: str, value: str, display_name: str | None, description: str | None, sort_order: int) -> object:
        return self.store.create_tag_value(
            group_id=group_id,
            value=value,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            actor="admin-console",
        )

    def update_tag_value(self, *, group_id: str, value: str, display_name: str | None, description: str | None, sort_order: int) -> object:
        return self.store.update_tag_value(
            group_id=group_id,
            value=value,
            display_name=display_name,
            description=description,
            sort_order=sort_order,
            actor="admin-console",
        )

    def delete_tag_value(self, *, group_id: str, value: str) -> object:
        return self.store.delete_tag_value_admin(group_id=group_id, value=value)

    def tag_cascade_overview(self) -> object:
        return self.store.tag_cascade_overview()

    def create_tag_cascade(self, *, parent_group_id: str, parent_value: str, child_group_id: str) -> object:
        return self.store.create_tag_cascade(
            parent_group_id=parent_group_id,
            parent_value=parent_value,
            child_group_id=child_group_id,
            actor="admin-console",
        )

    def delete_tag_cascade(self, *, child_group_id: str) -> object:
        return self.store.delete_tag_cascade(child_group_id=child_group_id, actor="admin-console")
