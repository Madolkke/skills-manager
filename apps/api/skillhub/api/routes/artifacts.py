from __future__ import annotations

import base64

from fastapi import Depends, FastAPI
from fastapi.responses import Response
from sqlalchemy import select

from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_artifact_routes(app: FastAPI) -> None:
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

    @app.get("/api/skills/{skill_id}/eval-runs")
    def eval_run_history(
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.list_eval_runs_for_skill(
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
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.eval_run_matrix_for_skill(
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
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id)
        )

    @app.get("/api/artifacts/{artifact_id}/download")
    def artifact_download(artifact_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
        with repository.engine.connect() as connection:
            artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one_or_none()
        if artifact is None or artifact["kind"] != "eval_case_attachment" or artifact["media_type"] != "application/zip":
            return Response(status_code=404)
        filename = artifact["locator"].rsplit(":", 1)[-1] or "case-attachment.zip"
        content = base64.b64decode(artifact["content_text"] or "")
        return Response(
            content=content,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
