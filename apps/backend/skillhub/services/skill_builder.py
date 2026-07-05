from __future__ import annotations

from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class SkillBuilderService(ServiceBase[SkillHubStore]):
    def list_sessions(self, *, actor: str) -> Any:
        return self.store.list_skill_builder_sessions(actor=actor)

    def create_session(self, *, actor: str, title: str | None = None) -> Any:
        return self.store.create_skill_builder_session(actor=actor, title=title)

    def session_detail(self, *, session_id: str, actor: str) -> Any:
        return self.store.skill_builder_session_detail(session_id=session_id, actor=actor)

    def send_message(
        self,
        *,
        session_id: str,
        actor: str,
        content: str,
        intent: str,
        provider_id: str | None,
        model_id: str | None,
    ) -> Any:
        return self.store.enqueue_skill_builder_message(
            session_id=session_id,
            actor=actor,
            content=content,
            intent=intent,
            run_selection={"provider_id": provider_id or "", "model_id": model_id or ""},
        )

    def update_workspace(self, *, session_id: str, actor: str, files: list[dict[str, Any]]) -> Any:
        return self.store.update_skill_builder_workspace(session_id=session_id, actor=actor, files=files)

    def update_draft(self, *, session_id: str, actor: str, files: list[dict[str, Any]]) -> Any:
        return self.update_workspace(session_id=session_id, actor=actor, files=files)

    def create_skill(self, *, session_id: str, actor: str, version: str | None, tags: list[Any], files: list[dict[str, Any]] | None = None) -> Any:
        return self.store.create_skill_from_builder_session(session_id=session_id, actor=actor, version=version, tags=tags, files=files)
