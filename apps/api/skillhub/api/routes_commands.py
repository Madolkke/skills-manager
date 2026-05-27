from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import parse_skill_import_payload, result_payload
from skillhub.api.schemas import (
    AcceptEvalRunVerificationPayload,
    CreateEvalCasePayload,
    CreateEvalCasesBatchPayload,
    CreateEvalCaseVersionPayload,
    CreateSkillPayload,
    CreateSkillVersionPayload,
    ImportSkillPayload,
    RecordEvalRunPayload,
    RestoreEvalCaseVersionPayload,
    content_ref,
)
from skillhub.application.skill_imports import parse_skill_import_source
from skillhub.domain.errors import InvariantError
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_command_routes(app: FastAPI) -> None:
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
            content_ref=ContentRef(
                kind="artifact",
                locator=f"artifact:{artifact['id']}",
                digest=artifact["digest"],
                path=bundle.entry_path,
            ),
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
                change_summary=payload.change_summary
                or (f"Uploaded standard skill bundle with {bundle.file_count} files." if bundle else "Updated skill version."),
                display_name=payload.display_name,
                actor=actor.id,
                make_current=payload.make_current,
            )
        )

    @app.post("/api/eval-cases")
    def create_eval_case(
        payload: CreateEvalCasePayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_eval_case(
                skill_id=payload.skill_id,
                title=payload.title,
                input_text=payload.input_text,
                expected_output=payload.expected_output,
                actor=actor.id,
                notes=payload.notes,
                eval_set_version_display_name=payload.eval_set_version_display_name,
            )
        )

    @app.post("/api/eval-cases/batch")
    def create_eval_cases_batch(
        payload: CreateEvalCasesBatchPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.create_eval_cases_batch(skill_id=payload.skill_id, cases=[case.model_dump() for case in payload.cases], actor=actor.id))

    @app.post("/api/eval-case-versions")
    def create_eval_case_version(
        payload: CreateEvalCaseVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        if payload.title is not None:
            repository.update_eval_case_title(case_id=payload.case_id, title=payload.title)
        return result_payload(
            repository.create_eval_case_version(
                case_id=payload.case_id,
                input_text=payload.input_text,
                expected_output=payload.expected_output,
                actor=actor.id,
                notes=payload.notes,
                eval_set_version_display_name=payload.eval_set_version_display_name,
                make_current=payload.make_current,
            )
        )

    @app.patch("/api/eval-cases/{case_id}")
    def update_eval_case(
        case_id: str,
        payload: CreateEvalCaseVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        if payload.title is not None:
            repository.update_eval_case_title(case_id=case_id, title=payload.title)
        return result_payload(
            repository.create_eval_case_version(
                case_id=case_id,
                input_text=payload.input_text,
                expected_output=payload.expected_output,
                actor=actor.id,
                notes=payload.notes,
                eval_set_version_display_name=payload.eval_set_version_display_name,
                make_current=payload.make_current,
            )
        )

    @app.post("/api/eval-cases/{case_id}/restores")
    def restore_eval_case_version(
        case_id: str,
        payload: RestoreEvalCaseVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.restore_eval_case_version(case_id=case_id, source_case_version_id=payload.source_case_version_id, actor=actor.id, notes=payload.notes)
        )

    @app.delete("/api/eval-cases/{case_id}")
    def archive_eval_case(
        case_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.archive_eval_case(case_id=case_id, actor=actor.id))

    @app.post("/api/eval-runs")
    def record_eval_run(
        payload: RecordEvalRunPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.record_eval_run(
                skill_version_id=payload.skill_version_id,
                eval_set_version_id=payload.eval_set_version_id,
                strategy=payload.strategy,
                results=payload.results,
                actor=actor.id,
                environment_tags=payload.environment_tags,
                run_context=payload.run_context,
            )
        )

    @app.post("/api/eval-runs/accepted-verifications")
    def accept_eval_run_verification(
        payload: AcceptEvalRunVerificationPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        accepted = repository.accept_eval_run_verification(eval_run_id=payload.eval_run_id, note=payload.note, actor=actor.id)
        return {"ok": True, "accepted_verification": accepted}
