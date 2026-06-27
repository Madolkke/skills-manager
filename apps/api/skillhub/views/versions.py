from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import version_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import CreateSkillVersionPayload, UpdateVersionDisplayNamePayload, content_ref
from skillhub.services import VersionService


def register_version_routes(app: FastAPI) -> None:
    @app.post("/api/skill-versions")
    def create_skill_version(
        payload: CreateSkillVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: VersionService = Depends(version_service_dependency),
    ):
        return result_payload(
            service.create_skill_version(
                skill_id=payload.skill_id,
                source=payload.source,
                content_ref=content_ref(payload.content_ref) if payload.content_ref is not None else None,
                change_summary=payload.change_summary,
                display_name=payload.display_name,
                version=payload.version,
                actor=actor.id,
                make_current=payload.make_current,
            )
        )

    @app.patch("/api/skill-versions/{skill_version_id}")
    def update_skill_version_name(
        skill_version_id: str,
        payload: UpdateVersionDisplayNamePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: VersionService = Depends(version_service_dependency),
    ):
        return result_payload(service.update_skill_version_name(skill_version_id=skill_version_id, display_name=payload.display_name, actor=actor.id))
