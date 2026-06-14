from __future__ import annotations

from skillhub.infrastructure.db.repository_impl.evaluations.eval_set_cases import EvalSetCaseHelperMixin
from skillhub.infrastructure.db.repository_impl.shared.base import RepositoryBase
from skillhub.infrastructure.db.repository_impl.shared.helpers import CoreHelperMixin


class SharedRepositoryMixin(EvalSetCaseHelperMixin, CoreHelperMixin, RepositoryBase):
    pass
