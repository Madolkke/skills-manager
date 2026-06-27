from __future__ import annotations

from typing import Any

from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.rules.saved_views import normalize_saved_view_config, validate_saved_view_type
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class SavedViewService(ServiceBase[SkillHubStore]):
    def list_saved_views(self, *, skill_id: str, view_type: str) -> Any:
        validate_saved_view_type(view_type)
        return self.store.list_saved_views(skill_id=skill_id, view_type=view_type)

    def create_saved_view(self, *, skill_id: str, name: str, view_type: str, config: dict[str, Any], actor: str) -> Any:
        validate_saved_view_type(view_type)
        clean_name = name.strip()
        if not clean_name:
            raise FieldInvariantError("Saved view name is required.", [FieldError("name", "填写保存视图名称。", "saved_view.name_required")])
        return self.store.insert_saved_view(
            skill_id=skill_id,
            name=clean_name,
            view_type=view_type,
            config=normalize_saved_view_config(config),
            actor=actor,
        )

    def delete_saved_view(self, *, saved_view_id: str, actor: str) -> Any:
        return self.store.delete_saved_view_record(saved_view_id=saved_view_id, actor=actor)
