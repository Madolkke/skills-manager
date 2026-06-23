from __future__ import annotations

from .repository_domains.bundles import BundleRepositoryMixin
from .repository_domains.evaluations import EvaluationRepositoryMixin
from .repository_domains.history import HistoryRepositoryMixin
from .repository_domains.reviews import ReviewRepositoryMixin
from .repository_domains.saved_views import SavedViewRepositoryMixin
from .repository_domains.shared import SharedRepositoryMixin
from .repository_domains.skills import SkillRepositoryMixin
from .repository_impl.shared.errors import skill_slug_conflict
from .repository_impl.shared.results import (
    CreateEvalCaseResult,
    CreateEvalCasesBatchResult,
    CreatedEvalCaseResult,
    CreateSkillResult,
    CreateSkillVersionResult,
    EvalRunDetail,
    EvalSetDetail,
    RecordEvalRunResult,
)


class SqlSkillRepository(
    SkillRepositoryMixin,
    EvaluationRepositoryMixin,
    HistoryRepositoryMixin,
    ReviewRepositoryMixin,
    SavedViewRepositoryMixin,
    BundleRepositoryMixin,
    SharedRepositoryMixin,
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
    "SqlSkillRepository",
    "skill_slug_conflict",
]
