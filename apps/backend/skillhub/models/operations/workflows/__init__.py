from .commands import WorkflowCommandMixin
from .imports import WorkflowImportMixin
from .queries import WorkflowQueryMixin


class WorkflowStoreMixin(WorkflowCommandMixin, WorkflowImportMixin, WorkflowQueryMixin):
    pass


__all__ = ["WorkflowStoreMixin"]
