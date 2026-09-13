"""运营看板读取与访问采集服务。"""

import logging
from datetime import date
from uuid import UUID

from skillhub.models.rules.analytics import AnalyticsOverview, Granularity
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase

logger = logging.getLogger(__name__)


class AnalyticsService(ServiceBase[SkillHubStore]):
    def overview(self, *, start_date: date, end_date: date, granularity: Granularity) -> AnalyticsOverview:
        """读取指定日期范围的运营聚合。"""
        return self.store.analytics_overview(start_date=start_date, end_date=end_date, granularity=granularity)

    def record_visit(self, *, skill_id: str, actor: str, event_id: UUID) -> None:
        """记录页面访问并保留失败日志供排查。"""
        try:
            self.store.record_skill_visit(skill_id=skill_id, actor=actor, event_id=event_id)
        except Exception:
            logger.exception("Skill visit recording failed skill_id=%s event_id=%s", skill_id, event_id)
            raise
