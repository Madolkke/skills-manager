from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import skill_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import AssignSkillRolePayload, CreateSkillPayload, ImportSkillPayload, SkillGroupMemberPayload, SkillGroupPayload, UpdateSkillPayload, content_ref
from skillhub.services import SkillService


def register_skill_routes(app: FastAPI) -> None:
    @app.get("/api/skills")
    def list_skills(service: SkillService = Depends(skill_service_dependency)):
        return result_payload(service.list_skills())

    @app.get("/api/tag-groups")
    def list_tag_groups(service: SkillService = Depends(skill_service_dependency)):
        return result_payload(service.list_tag_groups())

    @app.post("/api/skills")
    def create_skill(
        payload: CreateSkillPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(
            service.create_skill(
                slug=payload.slug,
                owner_ref=payload.owner_ref,
                content_ref=content_ref(payload.content_ref),
                change_summary=payload.change_summary,
                display_name=payload.display_name,
                version=payload.version,
                tags=payload.tags,
                actor=actor.id,
            )
        )

    @app.post("/api/skill-imports")
    def import_skill(
        payload: ImportSkillPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(
            service.import_skill(
                source=payload.source,
                owner_ref=payload.owner_ref,
                display_name=payload.display_name,
                version=payload.version,
                tags=payload.tags,
                actor=actor.id,
            )
        )

    @app.get("/api/skills/{skill_id}")
    def skill_detail(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.skill_detail(skill_id=skill_id, actor=actor.id))

    @app.patch("/api/skills/{skill_id}")
    def update_skill(
        skill_id: str,
        payload: UpdateSkillPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.update_skill(skill_id=skill_id, slug=payload.slug, owner_ref=payload.owner_ref, tags=payload.tags, actor=actor.id))

    @app.delete("/api/skills/{skill_id}")
    def archive_skill(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        service.archive_skill(skill_id=skill_id, actor=actor.id)
        return {"ok": True}

    @app.get("/api/skills/{skill_id}/role-assignments")
    def skill_role_assignments(skill_id: str, service: SkillService = Depends(skill_service_dependency)):
        return result_payload(service.list_skill_role_assignments(skill_id=skill_id))

    @app.get("/api/skills/{skill_id}/groups")
    def skill_groups(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.list_skill_groups(skill_id=skill_id, actor=actor.id))

    @app.post("/api/skills/{skill_id}/groups")
    def create_skill_group(
        skill_id: str,
        payload: SkillGroupPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.create_skill_group(skill_id=skill_id, name=payload.name, description=payload.description, actor=actor.id))

    @app.patch("/api/skills/{skill_id}/groups/{group_id}")
    def update_skill_group(
        skill_id: str,
        group_id: str,
        payload: SkillGroupPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.update_skill_group(skill_id=skill_id, group_id=group_id, name=payload.name, description=payload.description, actor=actor.id))

    @app.delete("/api/skills/{skill_id}/groups/{group_id}")
    def delete_skill_group(
        skill_id: str,
        group_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.delete_skill_group(skill_id=skill_id, group_id=group_id, actor=actor.id))

    @app.post("/api/skills/{skill_id}/groups/{group_id}/members")
    def add_skill_group_member(
        skill_id: str,
        group_id: str,
        payload: SkillGroupMemberPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.add_skill_group_member(skill_id=skill_id, group_id=group_id, subject_id=payload.subject_id, subject_type=payload.subject_type, actor=actor.id))

    @app.delete("/api/skills/{skill_id}/groups/{group_id}/members/{subject_id}")
    def remove_skill_group_member(
        skill_id: str,
        group_id: str,
        subject_id: str,
        subject_type: str = "user",
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.remove_skill_group_member(skill_id=skill_id, group_id=group_id, subject_id=subject_id, subject_type=subject_type, actor=actor.id))

    @app.get("/api/skills/{skill_id}/capabilities")
    def skill_capabilities(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.skill_capabilities(skill_id=skill_id, actor=actor.id, subject_type=actor.subject_type))

    @app.get("/api/skills/{skill_id}/audit-events")
    def skill_audit_events(
        skill_id: str,
        limit: int = 50,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(
            service.list_skill_audit_events(skill_id=skill_id, limit=limit, actor=actor, action=action, resource_type=resource_type)
        )

    @app.post("/api/skills/{skill_id}/role-assignments")
    def assign_skill_role(
        skill_id: str,
        payload: AssignSkillRolePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(
            service.assign_skill_role(
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
        service: SkillService = Depends(skill_service_dependency),
    ):
        return result_payload(service.revoke_role_assignment(role_assignment_id=role_assignment_id, actor=actor.id))
