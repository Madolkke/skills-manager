from .cases import WorkflowDebugCaseMixin
from .runs import WorkflowDebugRunMixin


class WorkflowDebugStoreMixin(WorkflowDebugCaseMixin, WorkflowDebugRunMixin):
    pass


__all__ = ["WorkflowDebugStoreMixin"]
