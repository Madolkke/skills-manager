from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import parse_skill_import_payload, result_payload
from skillhub.api.schemas import AssignSkillRolePayload, CreateSkillPayload, ImportSkillPayload, UpdateSkillPayload, content_ref
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_skill_routes(app: FastAPI) -> None:
    @app.get("/api/skills")
    def list_skills(repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_skills())

    @app.post("/api/skills")
    def create_skill(
        payload: CreateSkillPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_skill(
                slug=payload.slug,
                owner_ref=payload.owner_ref,
                content_ref=content_ref(payload.content_ref),
                change_summary=payload.change_summary,
                display_name=payload.display_name,
                actor=actor.id,
            )
        )

    @app.post("/api/skill-imports")
    def import_skill(
        payload: ImportSkillPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        bundle = parse_skill_import_payload(payload.source)
        artifact = repository.create_text_artifact(
            kind="skill_bundle",
            namespace=f"skill-import:{bundle.slug}",
            content=bundle.manifest_text,
            actor=actor.id,
        )
        result = repository.create_skill(
            slug=bundle.slug,
            owner_ref=payload.owner_ref,
            content_ref=ContentRef(kind="artifact", locator=f"artifact:{artifact['id']}", digest=artifact["digest"], path=bundle.entry_path),
            change_summary=f"Imported standard skill bundle with {bundle.file_count} files.",
            display_name=payload.display_name,
            actor=actor.id,
        )
        return {
            **result_payload(result),
            "slug": bundle.slug,
            "description": bundle.description,
            "file_count": bundle.file_count,
            "entry_path": bundle.entry_path,
            "bundle_artifact_id": artifact["id"],
            "bundle_digest": bundle.digest,
        }

    @app.get("/api/skills/{skill_id}")
    def skill_detail(skill_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.skill_detail(skill_id))

    @app.patch("/api/skills/{skill_id}")
    def update_skill(skill_id: str, payload: UpdateSkillPayload, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.update_skill(skill_id=skill_id, slug=payload.slug, owner_ref=payload.owner_ref))

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
            repository.list_skill_audit_events(skill_id=skill_id, limit=max(1, min(limit, 200)), actor=actor, action=action, resource_type=resource_type)
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
