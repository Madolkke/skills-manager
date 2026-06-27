from __future__ import annotations

from skillhub.models.operations.evaluations.eval_set_cases import EvalSetCaseHelperMixin
from skillhub.models.operations.shared.artifacts import ArtifactQueryMixin
from skillhub.models.operations.shared.base import StoreBase
from skillhub.models.operations.shared.helpers import CoreHelperMixin


class SharedStoreMixin(ArtifactQueryMixin, EvalSetCaseHelperMixin, CoreHelperMixin, StoreBase):
    pass
