from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from skillhub.models.operations.bundles import BundleStoreMixin
from skillhub.models.operations.evaluations import EvaluationStoreMixin
from skillhub.models.operations.history import HistoryStoreMixin
from skillhub.models.operations.opencode import OpencodeStoreMixin
from skillhub.models.operations.reviews import ReviewStoreMixin
from skillhub.models.operations.saved_views import SavedViewStoreMixin
from skillhub.models.operations.shared import SharedStoreMixin
from skillhub.models.operations.shared.errors import skill_slug_conflict
from skillhub.models.operations.shared.results import (
    CreatedEvalCaseResult,
    CreateEvalCaseResult,
    CreateEvalCasesBatchResult,
    CreateSkillResult,
    CreateSkillVersionResult,
    EvalRunDetail,
    EvalSetDetail,
    RecordEvalRunResult,
)
from skillhub.models.operations.skill_builder import SkillBuilderStoreMixin
from skillhub.models.operations.skills import SkillStoreMixin
from skillhub.models.operations.workers import WorkerStatusMixin
from skillhub.models.operations.workflows import WorkflowStoreMixin


class _StoreOperations(
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


class SkillHubStore:
    """Session-bound composition root with a temporary legacy method facade."""

    def __init__(self, bind: Engine | Session):
        self._operations = _StoreOperations(bind)
        self._engine = self._operations.engine
        self._session = self._operations.session
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )
        self.skills = self._operations
        self.evaluations = self._operations
        self.reviews = self._operations
        self.workflows = self._operations
        self.admin = self._operations
        self.builder = self._operations
        self.workers = self._operations
        self.artifacts = self._operations

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def session(self) -> Session | None:
        return self._session

    @contextmanager
    def transaction(self) -> Iterator["SkillHubStore"]:
        if self._session is not None:
            yield self
            return
        with self._session_factory.begin() as session:
            yield SkillHubStore(session)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._operations, name)


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
