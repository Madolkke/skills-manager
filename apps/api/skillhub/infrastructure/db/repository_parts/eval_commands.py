from __future__ import annotations

from .artifact_commands import ArtifactCommandMixin
from .eval_case_commands import EvalCaseCommandMixin
from .eval_run_commands import EvalRunCommandMixin


class EvalCommandMixin(ArtifactCommandMixin, EvalCaseCommandMixin, EvalRunCommandMixin):
    pass
