from __future__ import annotations

from skillhub.models.operations.bundles.queries import DiffQueryMixin
from skillhub.models.operations.history.cases import CaseHistoryQueryMixin
from skillhub.models.operations.history.details import DetailQueryMixin
from skillhub.models.operations.history.runs import RunHistoryQueryMixin


class HistoryQueryMixin(
    DetailQueryMixin,
    RunHistoryQueryMixin,
    CaseHistoryQueryMixin,
    DiffQueryMixin,
):
    pass
