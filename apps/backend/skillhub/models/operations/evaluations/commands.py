from __future__ import annotations

from skillhub.models.operations.evaluations.artifacts import ArtifactCommandMixin
from skillhub.models.operations.evaluations.cases import EvalCaseCommandMixin
from skillhub.models.operations.evaluations.run_aggregation import EvalRunAggregationMixin
from skillhub.models.operations.evaluations.run_details import EvalCaseRunDetailMixin
from skillhub.models.operations.evaluations.runs import EvalRunCommandMixin
from skillhub.models.operations.evaluations.sets import EvalSetCommandMixin


class EvalCommandMixin(
    ArtifactCommandMixin,
    EvalSetCommandMixin,
    EvalCaseCommandMixin,
    EvalCaseRunDetailMixin,
    EvalRunAggregationMixin,
    EvalRunCommandMixin,
):
    pass
