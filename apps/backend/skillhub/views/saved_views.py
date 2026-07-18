from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.services import SavedViewService
from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import saved_view_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import CreateSavedViewPayload


def register_saved_view_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/saved-views")
    def saved_views(skill_id: str, view_type: str = "run_history", service: SavedViewService = Depends(saved_view_service_dependency)):
        return result_payload(service.list_saved_views(skill_id=skill_id, view_type=view_type))

    @app.post("/api/saved-views")
    def create_saved_view(
        payload: CreateSavedViewPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SavedViewService = Depends(saved_view_service_dependency),
    ):
        return result_payload(
            service.create_saved_view(
                skill_id=payload.skill_id,
                name=payload.name,
                view_type=payload.view_type,
                config=payload.config,
                actor=actor.id,
            )
        )

    @app.delete("/api/saved-views/{saved_view_id}")
    def delete_saved_view(
        saved_view_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SavedViewService = Depends(saved_view_service_dependency),
    ):
        return result_payload(service.delete_saved_view(saved_view_id=saved_view_id, actor=actor.id))
