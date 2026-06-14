from __future__ import annotations

from fastapi import Depends, FastAPI, Response

from skillhub.api.auth import (
    ActorContext,
    DEFAULT_LOCAL_ACTOR,
    actor_dependency,
    clear_actor_cookie,
    normalize_actor,
    set_actor_cookie,
    verify_local_session_access_code,
)
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import AssignSkillRolePayload, SetSessionPayload, UpdateSkillPayload, UpdateVersionDisplayNamePayload
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_core_routes(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/session")
    def current_session(actor: ActorContext = Depends(actor_dependency)):
        return {"actor": actor.id, "subject_type": actor.subject_type}

    @app.post("/api/session")
    def set_session(payload: SetSessionPayload, response: Response):
        verify_local_session_access_code(payload.access_code)
        actor = normalize_actor(payload.actor)
        set_actor_cookie(response, actor)
        return {"actor": actor, "subject_type": "user"}

    @app.delete("/api/session")
    def clear_session(response: Response):
        clear_actor_cookie(response)
        return {"actor": DEFAULT_LOCAL_ACTOR, "subject_type": "user"}

    @app.get("/api/skills")
    def list_skills(repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_skills())

    @app.get("/api/skills/{skill_id}")
    def skill_detail(skill_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.skill_detail(skill_id))

    @app.patch("/api/skills/{skill_id}")
    def update_skill(skill_id: str, payload: UpdateSkillPayload, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.update_skill(skill_id=skill_id, slug=payload.slug, owner_ref=payload.owner_ref))

    @app.patch("/api/skill-versions/{skill_version_id}")
    def update_skill_version_name(
        skill_version_id: str,
        payload: UpdateVersionDisplayNamePayload,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.update_skill_version_name(skill_version_id=skill_version_id, display_name=payload.display_name))

    @app.delete("/api/skills/{skill_id}")
    def archive_skill(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        repository.archive_skill(skill_id=skill_id, actor=actor.id)
        return {"ok": True}

    @app.get("/api/skills/{skill_id}/role-assignments")
    def skill_role_assignments(skill_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_skill_role_assignments(skill_id=skill_id))

    @app.get("/api/skills/{skill_id}/capabilities")
    def skill_capabilities(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.skill_capabilities(skill_id=skill_id, actor=actor.id, subject_type=actor.subject_type))

    @app.get("/api/skills/{skill_id}/audit-events")
    def skill_audit_events(
        skill_id: str,
        limit: int = 50,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.list_skill_audit_events(
                skill_id=skill_id,
                limit=max(1, min(limit, 200)),
                actor=actor,
                action=action,
                resource_type=resource_type,
            )
        )

    @app.post("/api/skills/{skill_id}/role-assignments")
    def assign_skill_role(
        skill_id: str,
        payload: AssignSkillRolePayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.assign_skill_role(
                skill_id=skill_id,
                subject_id=payload.subject_id,
                role=payload.role,
                subject_type=payload.subject_type,
                actor=actor.id,
            )
        )

    @app.delete("/api/role-assignments/{role_assignment_id}")
    def revoke_role_assignment(
        role_assignment_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.revoke_role_assignment(role_assignment_id=role_assignment_id, actor=actor.id))
