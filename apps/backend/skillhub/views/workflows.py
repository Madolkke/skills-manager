from __future__ import annotations

from typing import Any

from fastapi import Body, Depends, FastAPI

from skillhub.services import WorkflowService
from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import workflow_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import (
    CreateWorkflowSkillPayload,
    SaveWorkflowPayload,
    SyncWorkflowPayload,
    WorkflowMetadataPayload,
    WorkflowSyncPreviewPayload,
)


def register_workflow_routes(app: FastAPI) -> None:
    @app.get("/api/workflow-skill-generators")
    def workflow_skill_generators(
        _actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(service.workflow_skill_generators())

    @app.post("/api/workflows")
    def create_workflow_skill(
        payload: CreateWorkflowSkillPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(
            service.create_workflow_skill(
                slug=payload.slug,
                owner_ref=payload.owner_ref,
                description=payload.description,
                tags=[item.model_dump() for item in payload.tags],
                actor=actor.id,
            )
        )

    @app.get("/api/skills/{skill_id}/workflow")
    def workflow_detail(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(service.workflow_detail(skill_id=skill_id, actor=actor.id))

    @app.get("/api/skills/{skill_id}/workflow/formatted")
    def formatted_workflow(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ) -> dict[str, Any]:
        return result_payload(service.formatted_workflow(skill_id=skill_id, actor=actor.id))

    @app.put("/api/skills/{skill_id}/workflow")
    def save_workflow(
        skill_id: str,
        payload: SaveWorkflowPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(
            service.save_workflow(
                skill_id=skill_id,
                document=payload.document,
                collection_changes=[item.model_dump() for item in payload.collection_changes],
                actor=actor.id,
            )
        )

    @app.patch("/api/skills/{skill_id}/workflow/metadata")
    def update_workflow_metadata(
        skill_id: str,
        payload: WorkflowMetadataPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(service.update_metadata(skill_id=skill_id, metadata=payload.model_dump(), actor=actor.id))

    @app.post("/api/skills/{skill_id}/workflow/import")
    def import_workflow_bundle(
        skill_id: str,
        payload: Any = Body(...),
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(
            service.import_workflow_bundle(
                skill_id=skill_id,
                bundle=payload,
                actor=actor.id,
            )
        )

    @app.get("/api/skills/{skill_id}/workflow/collections")
    def list_workflow_collections(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(service.list_collections(skill_id=skill_id, actor=actor.id))

    @app.post("/api/skills/{skill_id}/workflow/sync")
    def sync_workflow(
        skill_id: str,
        payload: SyncWorkflowPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(
            service.sync_workflow(
                skill_id=skill_id,
                version=payload.version,
                display_name=payload.display_name,
                change_summary=payload.change_summary,
                expected_workflow_revision=payload.expected_workflow_revision,
                generator_id=payload.generator_id,
                generator_version=payload.generator_version,
                generator_options=payload.generator_options,
                preview_digest=payload.preview_digest,
                actor=actor.id,
            )
        )

    @app.post("/api/skills/{skill_id}/workflow/sync-preview")
    def preview_workflow_sync(
        skill_id: str,
        payload: WorkflowSyncPreviewPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: WorkflowService = Depends(workflow_service_dependency),
    ):
        return result_payload(
            service.preview_workflow_sync(
                skill_id=skill_id,
                expected_workflow_revision=payload.expected_workflow_revision,
                generator_id=payload.generator_id,
                generator_options=payload.generator_options,
                actor=actor.id,
            )
        )
