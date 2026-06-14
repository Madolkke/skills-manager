from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import CreateSavedViewPayload
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_history_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/eval-runs")
    def eval_run_history(
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        limit: int = 50,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.list_eval_runs_for_skill(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                strategy=strategy,
                status=status,
                limit=limit,
            )
        )

    @app.get("/api/skills/{skill_id}/eval-run-matrix")
    def eval_run_matrix(
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        limit: int = 50,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.eval_run_matrix_for_skill(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                strategy=strategy,
                status=status,
                limit=limit,
            )
        )

    @app.get("/api/skills/{skill_id}/saved-views")
    def saved_views(skill_id: str, view_type: str = "run_history", repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_saved_views(skill_id=skill_id, view_type=view_type))

    @app.post("/api/saved-views")
    def create_saved_view(
        payload: CreateSavedViewPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_saved_view(
                skill_id=payload.skill_id,
                name=payload.name,
                view_type=payload.view_type,
                config=payload.config,
                actor=actor.id,
            )
        )

    @app.delete("/api/saved-views/{saved_view_id}")
    def delete_saved_view(saved_view_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.delete_saved_view(saved_view_id))

    @app.get("/api/eval-sets/{eval_set_id}")
    def eval_set_detail(eval_set_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.eval_set_detail(eval_set_id))

    @app.get("/api/eval-runs/compare")
    def compare_eval_runs(
        baseline_run_id: str,
        candidate_run_id: str,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.compare_eval_runs(baseline_run_id=baseline_run_id, candidate_run_id=candidate_run_id))

    @app.get("/api/eval-runs/{eval_run_id}")
    def eval_run_detail(eval_run_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.eval_run_detail(eval_run_id))

    @app.get("/api/eval-cases/{case_id}/versions")
    def eval_case_history(case_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.eval_case_history(case_id))

    @app.get("/api/artifacts/diff")
    def artifact_diff(
        left_skill_version_id: str,
        right_skill_version_id: str,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id)
        )
