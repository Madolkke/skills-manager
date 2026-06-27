from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.views.auth import ActorContext, actor_dependency
from skillhub.views.dependencies import evaluation_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import (
    AcceptEvalRunVerificationPayload,
    AddEvalSetCasePayload,
    AggregateEvalRunPayload,
    CreateEvalCasePayload,
    CreateEvalCasesBatchPayload,
    CreateEvalCaseVersionPayload,
    CreateEvalSetPayload,
    EnqueueEvalCaseRunPayload,
    ListEvalCaseRunsQuery,
    ReorderEvalSetCasesPayload,
    RestoreEvalCaseVersionPayload,
    UpdateEvalSetPayload,
)
from skillhub.services import EvaluationService


def register_evaluation_routes(app: FastAPI) -> None:
    @app.get("/api/eval-assertion-templates")
    def eval_assertion_templates(service: EvaluationService = Depends(evaluation_service_dependency)):
        return service.list_assertion_templates()

    @app.post("/api/skills/{skill_id}/eval-sets")
    def create_eval_set(
        skill_id: str,
        payload: CreateEvalSetPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(service.create_eval_set(skill_id=skill_id, name=payload.name, description=payload.description, actor=actor.id))

    @app.patch("/api/eval-sets/{eval_set_id}")
    def update_eval_set(
        eval_set_id: str,
        payload: UpdateEvalSetPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(service.update_eval_set(eval_set_id=eval_set_id, name=payload.name, description=payload.description, actor=actor.id))

    @app.get("/api/skills/{skill_id}/eval-cases")
    def list_eval_cases_for_skill(
        skill_id: str,
        exclude_eval_set_id: str | None = None,
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(service.list_eval_cases_for_skill(skill_id=skill_id, exclude_eval_set_id=exclude_eval_set_id))

    @app.post("/api/eval-sets/{eval_set_id}/cases")
    def add_eval_case_to_set(
        eval_set_id: str,
        payload: AddEvalSetCasePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(service.add_eval_case_to_set(eval_set_id=eval_set_id, case_id=payload.case_id, position=payload.position, actor=actor.id))

    @app.delete("/api/eval-sets/{eval_set_id}/cases/{case_id}")
    def remove_eval_case_from_set(
        eval_set_id: str,
        case_id: str,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(service.remove_eval_case_from_set(eval_set_id=eval_set_id, case_id=case_id, actor=actor.id))

    @app.patch("/api/eval-sets/{eval_set_id}/cases/order")
    def reorder_eval_set_cases(
        eval_set_id: str,
        payload: ReorderEvalSetCasesPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(service.reorder_eval_set_cases(eval_set_id=eval_set_id, case_ids=payload.case_ids, actor=actor.id))

    @app.post("/api/eval-cases")
    def create_eval_case(
        payload: CreateEvalCasePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.create_eval_case(
                skill_id=payload.skill_id,
                eval_set_id=payload.eval_set_id,
                title=payload.title,
                steps=[step.model_dump() for step in payload.steps],
                workspace_name=payload.workspace_name,
                workspace_base64=payload.workspace_base64,
                runner_config=payload.runner_config.model_dump(),
                actor=actor.id,
                notes=payload.notes,
            )
        )

    @app.post("/api/eval-cases/batch")
    def create_eval_cases_batch(
        payload: CreateEvalCasesBatchPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.create_eval_cases_batch(
                skill_id=payload.skill_id,
                eval_set_id=payload.eval_set_id,
                cases=[case.model_dump() for case in payload.cases],
                actor=actor.id,
            )
        )

    @app.post("/api/eval-case-versions")
    def create_eval_case_version(
        payload: CreateEvalCaseVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.create_eval_case_version(
                case_id=payload.case_id,
                eval_set_id=payload.eval_set_id,
                title=payload.title,
                steps=[step.model_dump() for step in payload.steps],
                workspace_name=payload.workspace_name,
                workspace_base64=payload.workspace_base64,
                preserve_workspace=payload.preserve_workspace,
                runner_config=payload.runner_config.model_dump(),
                actor=actor.id,
                notes=payload.notes,
                make_current=payload.make_current,
            )
        )

    @app.patch("/api/eval-cases/{case_id}")
    def update_eval_case(
        case_id: str,
        payload: CreateEvalCaseVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.create_eval_case_version(
                case_id=case_id,
                eval_set_id=payload.eval_set_id,
                title=payload.title,
                steps=[step.model_dump() for step in payload.steps],
                workspace_name=payload.workspace_name,
                workspace_base64=payload.workspace_base64,
                preserve_workspace=payload.preserve_workspace,
                runner_config=payload.runner_config.model_dump(),
                actor=actor.id,
                notes=payload.notes,
                make_current=payload.make_current,
            )
        )

    @app.post("/api/eval-cases/{case_id}/restores")
    def restore_eval_case_version(
        case_id: str,
        payload: RestoreEvalCaseVersionPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.restore_eval_case_version(
                case_id=case_id,
                eval_set_id=payload.eval_set_id,
                source_case_version_id=payload.source_case_version_id,
                actor=actor.id,
                notes=payload.notes,
            )
        )

    @app.post("/api/eval-case-runs")
    def enqueue_eval_case_run(
        payload: EnqueueEvalCaseRunPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.enqueue_eval_case_run(
                skill_version_id=payload.skill_version_id,
                eval_set_id=payload.eval_set_id,
                case_version_id=payload.case_version_id,
                actor=actor.id,
                environment_tags=payload.environment_tags,
                run_context=payload.run_context,
            )
        )

    @app.get("/api/eval-case-runs")
    def list_eval_case_runs(
        skill_version_id: str,
        eval_set_id: str,
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        query = ListEvalCaseRunsQuery(skill_version_id=skill_version_id, eval_set_id=eval_set_id)
        return result_payload(
            service.latest_eval_case_run_details(
                skill_version_id=query.skill_version_id,
                eval_set_id=query.eval_set_id,
                environment_tags=query.environment_tags,
                run_context=query.run_context,
            )
        )

    @app.get("/api/eval-case-runs/{eval_case_run_id}")
    def eval_case_run_detail(eval_case_run_id: str, service: EvaluationService = Depends(evaluation_service_dependency)):
        return result_payload(service.eval_case_run_detail(eval_case_run_id=eval_case_run_id))

    @app.post("/api/eval-runs/aggregations")
    def aggregate_eval_run(
        payload: AggregateEvalRunPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        return result_payload(
            service.aggregate_eval_run(
                skill_version_id=payload.skill_version_id,
                eval_set_id=payload.eval_set_id,
                actor=actor.id,
                environment_tags=payload.environment_tags,
                run_context=payload.run_context,
            )
        )

    @app.post("/api/eval-runs/accepted-verifications")
    def accept_eval_run_verification(
        payload: AcceptEvalRunVerificationPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: EvaluationService = Depends(evaluation_service_dependency),
    ):
        accepted = service.accept_eval_run_verification(eval_run_id=payload.eval_run_id, note=payload.note, actor=actor.id)
        return {"ok": True, "accepted_verification": accepted}
