from __future__ import annotations

from skillhub.infrastructure.db.repository_impl.bundles.queries import DiffQueryMixin
from skillhub.infrastructure.db.repository_impl.history.cases import CaseHistoryQueryMixin
from skillhub.infrastructure.db.repository_impl.history.details import DetailQueryMixin
from skillhub.infrastructure.db.repository_impl.history.runs import RunHistoryQueryMixin


class HistoryQueryMixin(
    DetailQueryMixin,
    RunHistoryQueryMixin,
    CaseHistoryQueryMixin,
    DiffQueryMixin,
):
    pass
