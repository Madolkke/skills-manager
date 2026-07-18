from __future__ import annotations

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class EvaluationReadService(ServiceBase[SkillHubStore]):
    def eval_set_detail(self, *, eval_set_id: str) -> object:
        return self.store.eval_set_detail(eval_set_id)

    def compare_eval_runs(self, *, baseline_run_id: str, candidate_run_id: str) -> object:
        return self.store.compare_eval_runs(baseline_run_id=baseline_run_id, candidate_run_id=candidate_run_id)

    def eval_run_detail(self, *, eval_run_id: str) -> object:
        return self.store.eval_run_detail(eval_run_id)

    def eval_case_history(self, *, case_id: str) -> object:
        return self.store.eval_case_history(case_id)

    def list_eval_runs_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None,
        eval_set_id: str | None,
        status: str | None,
        limit: int,
    ) -> object:
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
    ) -> object:
        return self.store.eval_run_matrix_for_skill(
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            status=status,
            limit=limit,
        )
