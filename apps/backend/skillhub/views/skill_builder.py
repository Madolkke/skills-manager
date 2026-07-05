from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.services import SkillBuilderService
from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import skill_builder_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import (
    CreateSkillBuilderSessionPayload,
    CreateSkillFromBuilderPayload,
    SkillBuilderMessagePayload,
    UpdateSkillBuilderDraftPayload,
    UpdateSkillBuilderWorkspacePayload,
)


def register_skill_builder_routes(app: FastAPI) -> None:
    @app.get("/api/skill-builder/sessions")
    def list_skill_builder_sessions(
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        return result_payload(service.list_sessions(actor=actor.id))

    @app.post("/api/skill-builder/sessions")
    def create_skill_builder_session(
        payload: CreateSkillBuilderSessionPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        return result_payload(service.create_session(actor=actor.id, title=payload.title))

    @app.get("/api/skill-builder/sessions/{session_id}")
    def skill_builder_session_detail(
        session_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        return result_payload(service.session_detail(session_id=session_id, actor=actor.id))

    @app.post("/api/skill-builder/sessions/{session_id}/messages")
    def send_skill_builder_message(
        session_id: str,
        payload: SkillBuilderMessagePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        return result_payload(
            service.send_message(
                session_id=session_id,
                actor=actor.id,
                content=payload.content,
                intent=payload.intent,
                provider_id=payload.provider_id,
                model_id=payload.model_id,
            )
        )

    @app.patch("/api/skill-builder/sessions/{session_id}/draft")
    def update_skill_builder_draft(
        session_id: str,
        payload: UpdateSkillBuilderDraftPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        return result_payload(service.update_draft(session_id=session_id, actor=actor.id, files=[item.model_dump() for item in payload.files]))

    @app.patch("/api/skill-builder/sessions/{session_id}/workspace")
    def update_skill_builder_workspace(
        session_id: str,
        payload: UpdateSkillBuilderWorkspacePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        return result_payload(service.update_workspace(session_id=session_id, actor=actor.id, files=[item.model_dump() for item in payload.files]))

    @app.post("/api/skill-builder/sessions/{session_id}/create-skill")
    def create_skill_from_builder(
        session_id: str,
        payload: CreateSkillFromBuilderPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillBuilderService = Depends(skill_builder_service_dependency),
    ):
        files = None if payload.files is None else [item.model_dump() for item in payload.files]
        return result_payload(service.create_skill(session_id=session_id, actor=actor.id, version=payload.version, tags=payload.tags, files=files))
