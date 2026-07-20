from __future__ import annotations

from skillhub.models.operations.evaluations.eval_set_cases import EvalSetCaseHelperMixin
from skillhub.models.operations.shared.artifacts import ArtifactQueryMixin
from skillhub.models.operations.shared.base import StoreBase
from skillhub.models.operations.shared.helpers import CoreHelperMixin
from skillhub.models.operations.shared.job_leases import JobLeaseMixin
from skillhub.models.operations.shared.jobs import JobHelperMixin
from skillhub.models.operations.shared.tagging import TaggingHelperMixin


class SharedStoreMixin(
    ArtifactQueryMixin,
    EvalSetCaseHelperMixin,
    TaggingHelperMixin,
    JobLeaseMixin,
    JobHelperMixin,
    CoreHelperMixin,
    StoreBase,
):
    pass
