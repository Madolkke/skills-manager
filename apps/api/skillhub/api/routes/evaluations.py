from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import (
    AcceptEvalRunVerificationPayload,
    AggregateEvalRunPayload,
    CreateEvalCasePayload,
    CreateEvalCasesBatchPayload,
    CreateEvalCaseVersionPayload,
    EnqueueEvalCaseRunPayload,
    FinalizeEvalCaseRunPayload,
    RecordEvalRunPayload,
    RestoreEvalCaseVersionPayload,
)
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_evaluation_routes(app: FastAPI) -> None:
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
                attachment_name=payload.attachment_name,
                attachment_base64=payload.attachment_base64,
                actor=actor.id,
                notes=payload.notes,
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
                attachment_name=payload.attachment_name,
                attachment_base64=payload.attachment_base64,
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
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        if payload.title is not None:
            repository.update_eval_case_title(case_id=case_id, title=payload.title)
        return result_payload(
            repository.create_eval_case_version(
                case_id=case_id,
                input_text=payload.input_text,
                expected_output=payload.expected_output,
                attachment_name=payload.attachment_name,
                attachment_base64=payload.attachment_base64,
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
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.restore_eval_case_version(case_id=case_id, source_case_version_id=payload.source_case_version_id, actor=actor.id, notes=payload.notes))

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
                eval_set_id=payload.eval_set_id,
                strategy=payload.strategy,
                results=payload.results,
                actor=actor.id,
                environment_tags=payload.environment_tags,
                run_context=payload.run_context,
            )
        )

    @app.post("/api/eval-case-runs")
    def enqueue_eval_case_run(
        payload: EnqueueEvalCaseRunPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.enqueue_eval_case_run(
                skill_version_id=payload.skill_version_id,
                eval_set_id=payload.eval_set_id,
                case_version_id=payload.case_version_id,
                strategy=payload.strategy,
                actor=actor.id,
                environment_tags=payload.environment_tags,
                run_context=payload.run_context,
            )
        )

    @app.post("/api/eval-case-runs/{eval_case_run_id}/completion")
    def complete_eval_case_run(
        eval_case_run_id: str,
        payload: FinalizeEvalCaseRunPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.finalize_eval_case_run(
                eval_case_run_id=eval_case_run_id,
                passed=payload.passed,
                actual_output=payload.actual_output,
                actor=actor.id,
            )
        )

    @app.post("/api/eval-runs/aggregations")
    def aggregate_eval_run(
        payload: AggregateEvalRunPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.aggregate_eval_run(
                skill_version_id=payload.skill_version_id,
                eval_set_id=payload.eval_set_id,
                strategy=payload.strategy,
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
