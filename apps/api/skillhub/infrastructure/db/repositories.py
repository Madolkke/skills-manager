from __future__ import annotations

from .repository_parts.base import RepositoryBase
from .repository_parts.bundle_diff import BundleDiffMixin
from .repository_parts.core_helpers import CoreHelperMixin
from .repository_parts.errors import skill_slug_conflict
from .repository_parts.eval_commands import EvalCommandMixin
from .repository_parts.history_queries import HistoryQueryMixin
from .repository_parts.read_models import ReadModelMixin
from .repository_parts.results import (
    CreateEvalCaseResult,
    CreateEvalCasesBatchResult,
    CreatedEvalCaseResult,
    CreateSkillResult,
    CreateSkillVersionResult,
    EvalRunDetail,
    EvalSetVersionDetail,
    RecordEvalRunResult,
)
from .repository_parts.roles import RoleMixin
from .repository_parts.skill_commands import SkillCommandMixin


class SqlSkillRepository(
    SkillCommandMixin,
    EvalCommandMixin,
    ReadModelMixin,
    RoleMixin,
    HistoryQueryMixin,
    CoreHelperMixin,
    BundleDiffMixin,
    RepositoryBase,
):
    pass


__all__ = [
    "CreateEvalCaseResult",
    "CreateEvalCasesBatchResult",
    "CreatedEvalCaseResult",
    "CreateSkillResult",
    "CreateSkillVersionResult",
    "EvalRunDetail",
    "EvalSetVersionDetail",
    "RecordEvalRunResult",
    "SqlSkillRepository",
    "skill_slug_conflict",
]
