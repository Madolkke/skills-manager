from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.responses import Response

from skillhub.views.dependencies import artifact_service_dependency
from skillhub.views.responses import result_payload
from skillhub.services import ArtifactService


def register_artifact_routes(app: FastAPI) -> None:
    @app.get("/api/eval-sets/{eval_set_id}")
    def eval_set_detail(eval_set_id: str, service: ArtifactService = Depends(artifact_service_dependency)):
        return result_payload(service.eval_set_detail(eval_set_id=eval_set_id))

    @app.get("/api/eval-runs/compare")
    def compare_eval_runs(
        baseline_run_id: str,
        candidate_run_id: str,
        service: ArtifactService = Depends(artifact_service_dependency),
    ):
        return result_payload(service.compare_eval_runs(baseline_run_id=baseline_run_id, candidate_run_id=candidate_run_id))

    @app.get("/api/eval-runs/{eval_run_id}")
    def eval_run_detail(eval_run_id: str, service: ArtifactService = Depends(artifact_service_dependency)):
        return result_payload(service.eval_run_detail(eval_run_id=eval_run_id))

    @app.get("/api/eval-cases/{case_id}/versions")
    def eval_case_history(case_id: str, service: ArtifactService = Depends(artifact_service_dependency)):
        return result_payload(service.eval_case_history(case_id=case_id))

    @app.get("/api/skills/{skill_id}/eval-runs")
    def eval_run_history(
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        service: ArtifactService = Depends(artifact_service_dependency),
    ):
        return result_payload(
            service.list_eval_runs_for_skill(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                status=status,
                limit=limit,
            )
        )

    @app.get("/api/skills/{skill_id}/eval-run-matrix")
    def eval_run_matrix(
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        service: ArtifactService = Depends(artifact_service_dependency),
    ):
        return result_payload(
            service.eval_run_matrix_for_skill(
                skill_id=skill_id,
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                status=status,
                limit=limit,
            )
        )

    @app.get("/api/artifacts/diff")
    def artifact_diff(
        left_skill_version_id: str,
        right_skill_version_id: str,
        service: ArtifactService = Depends(artifact_service_dependency),
    ):
        return result_payload(
            service.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id)
        )

    @app.get("/api/artifacts/{artifact_id}/download")
    def artifact_download(artifact_id: str, service: ArtifactService = Depends(artifact_service_dependency)):
        download = service.downloadable_artifact(artifact_id=artifact_id)
        if download is None:
            return Response(status_code=404)
        return Response(
            content=download.content,
            media_type=download.media_type,
            headers={"Content-Disposition": f'attachment; filename="{download.filename}"'},
        )
