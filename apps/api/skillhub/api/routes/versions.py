from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import CreateSkillVersionPayload, UpdateVersionDisplayNamePayload, content_ref
from skillhub.application.skill_imports import parse_skill_import_source
from skillhub.domain.errors import InvariantError
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_version_routes(app: FastAPI) -> None:
    @app.post("/api/skill-versions")
    def create_skill_version(
        payload: CreateSkillVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        bundle = None
        if payload.source is not None:
            bundle = parse_skill_import_source(payload.source)
            artifact = repository.create_text_artifact(
                kind="skill_bundle",
                namespace=f"skill-version-import:{bundle.slug}",
                content=bundle.manifest_text,
                actor=actor.id,
            )
            content = ContentRef(kind="artifact", locator=f"artifact:{artifact['id']}", digest=artifact["digest"], path=bundle.entry_path)
        elif payload.content_ref is not None:
            content = content_ref(payload.content_ref)
        else:
            raise InvariantError("Skill version requires either content_ref or standard skill bundle source.")
        return result_payload(
            repository.create_skill_version(
                skill_id=payload.skill_id,
                content_ref=content,
                change_summary=payload.change_summary or (f"Uploaded standard skill bundle with {bundle.file_count} files." if bundle else "Updated skill version."),
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
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.update_skill_version_name(skill_version_id=skill_version_id, display_name=payload.display_name))
