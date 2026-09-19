"""前端分页查询组合入口。"""
from .access import AccessPageMixin
from .history import HistoryPageMixin
from .skills import SkillPageMixin
from .versions import VersionPageMixin


class PaginationMixin(AccessPageMixin, HistoryPageMixin, SkillPageMixin, VersionPageMixin):
    pass
