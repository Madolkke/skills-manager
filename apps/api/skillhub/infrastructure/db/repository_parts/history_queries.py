from __future__ import annotations

from .case_history_queries import CaseHistoryQueryMixin
from .detail_queries import DetailQueryMixin
from .diff_queries import DiffQueryMixin
from .run_history_queries import RunHistoryQueryMixin
from .saved_view_commands import SavedViewCommandMixin


class HistoryQueryMixin(
    DetailQueryMixin,
    RunHistoryQueryMixin,
    SavedViewCommandMixin,
    CaseHistoryQueryMixin,
    DiffQueryMixin,
):
    pass
