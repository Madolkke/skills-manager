from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import CreateSavedViewPayload
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_saved_view_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/saved-views")
    def saved_views(skill_id: str, view_type: str = "run_history", repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_saved_views(skill_id=skill_id, view_type=view_type))

    @app.post("/api/saved-views")
    def create_saved_view(
        payload: CreateSavedViewPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_saved_view(
                skill_id=payload.skill_id,
                name=payload.name,
                view_type=payload.view_type,
                config=payload.config,
                actor=actor.id,
            )
        )

    @app.delete("/api/saved-views/{saved_view_id}")
    def delete_saved_view(saved_view_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.delete_saved_view(saved_view_id))
