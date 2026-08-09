from .proposals import WorkflowAgentProposalMixin
from .runs import WorkflowAgentRunMixin
from .sessions import WorkflowAgentSessionMixin


class WorkflowAgentStoreMixin(WorkflowAgentSessionMixin, WorkflowAgentRunMixin, WorkflowAgentProposalMixin):
    pass


__all__ = ["WorkflowAgentStoreMixin"]
