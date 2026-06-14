from __future__ import annotations

from skillhub.infrastructure.db.repository_impl.evaluations.artifacts import ArtifactCommandMixin
from skillhub.infrastructure.db.repository_impl.evaluations.cases import EvalCaseCommandMixin
from skillhub.infrastructure.db.repository_impl.evaluations.runs import EvalRunCommandMixin


class EvalCommandMixin(ArtifactCommandMixin, EvalCaseCommandMixin, EvalRunCommandMixin):
    pass
