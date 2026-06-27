from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


@dataclass(frozen=True, slots=True)
class ArtifactDownload:
    filename: str
    content: bytes
    media_type: str


class ArtifactService(ServiceBase[SkillHubStore]):
    def eval_set_detail(self, *, eval_set_id: str) -> Any:
        return self.store.eval_set_detail(eval_set_id)

    def compare_eval_runs(self, *, baseline_run_id: str, candidate_run_id: str) -> Any:
        return self.store.compare_eval_runs(baseline_run_id=baseline_run_id, candidate_run_id=candidate_run_id)

    def eval_run_detail(self, *, eval_run_id: str) -> Any:
        return self.store.eval_run_detail(eval_run_id)

    def eval_case_history(self, *, case_id: str) -> Any:
        return self.store.eval_case_history(case_id)

    def list_eval_runs_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None,
        eval_set_id: str | None,
        status: str | None,
        limit: int,
    ) -> Any:
        return self.store.list_eval_runs_for_skill(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            status=status,
            limit=limit,
        )

    def eval_run_matrix_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None,
        eval_set_id: str | None,
        status: str | None,
        limit: int,
    ) -> Any:
        return self.store.eval_run_matrix_for_skill(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            status=status,
            limit=limit,
        )

    def bundle_diff(self, *, left_skill_version_id: str, right_skill_version_id: str) -> Any:
        return self.store.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id)

    def downloadable_artifact(self, *, artifact_id: str) -> ArtifactDownload | None:
        artifact = self.store.downloadable_artifact(artifact_id)
        if artifact is None:
            return None
        filename = artifact["locator"].rsplit(":", 1)[-1] or "workspace.zip"
        return ArtifactDownload(filename=filename, content=b64decode(artifact["content_text"] or ""), media_type="application/zip")
