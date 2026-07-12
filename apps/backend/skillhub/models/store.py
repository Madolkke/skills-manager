from __future__ import annotations

from skillhub.models.operations.bundles import BundleStoreMixin
from skillhub.models.operations.evaluations import EvaluationStoreMixin
from skillhub.models.operations.history import HistoryStoreMixin
from skillhub.models.operations.opencode import OpencodeStoreMixin
from skillhub.models.operations.reviews import ReviewStoreMixin
from skillhub.models.operations.saved_views import SavedViewStoreMixin
from skillhub.models.operations.shared import SharedStoreMixin
from skillhub.models.operations.workers import WorkerStatusMixin
from skillhub.models.operations.workflows import WorkflowStoreMixin
from skillhub.models.operations.shared.errors import skill_slug_conflict
from skillhub.models.operations.shared.results import (
    CreateEvalCaseResult,
    CreateEvalCasesBatchResult,
    CreatedEvalCaseResult,
    CreateSkillResult,
    CreateSkillVersionResult,
    EvalRunDetail,
    EvalSetDetail,
    RecordEvalRunResult,
)
from skillhub.models.operations.skills import SkillStoreMixin
from skillhub.models.operations.skill_builder import SkillBuilderStoreMixin


class SkillHubStore(
    SkillStoreMixin,
    EvaluationStoreMixin,
    HistoryStoreMixin,
    OpencodeStoreMixin,
    ReviewStoreMixin,
    SavedViewStoreMixin,
    BundleStoreMixin,
    SkillBuilderStoreMixin,
    WorkerStatusMixin,
    WorkflowStoreMixin,
    SharedStoreMixin,
):
    pass


__all__ = [
    "CreateEvalCaseResult",
    "CreateEvalCasesBatchResult",
    "CreatedEvalCaseResult",
    "CreateSkillResult",
    "CreateSkillVersionResult",
    "EvalRunDetail",
    "EvalSetDetail",
    "RecordEvalRunResult",
    "SkillHubStore",
    "skill_slug_conflict",
]
