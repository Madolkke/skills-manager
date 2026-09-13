"""运营统计 HTTP 接口。"""

from datetime import date

from fastapi import Depends, FastAPI

from skillhub.models.rules.analytics import AnalyticsOverview, Granularity
from skillhub.services.analytics import AnalyticsService
from skillhub.views.auth import ActorContext, actor_dependency, admin_key_dependency
from skillhub.views.dependencies import analytics_service_dependency
from skillhub.views.schemas import SkillVisitPayload, SkillVisitResult


def register_analytics_routes(app: FastAPI) -> None:
    """注册后台聚合和普通 actor 页面访问采集接口。"""
    @app.get("/api/admin/analytics/overview", response_model=AnalyticsOverview)
    def overview(
        start_date: date, end_date: date, granularity: Granularity = "month",
        _: None = Depends(admin_key_dependency), service: AnalyticsService = Depends(analytics_service_dependency),
    ) -> AnalyticsOverview:
        """验证查询参数后读取聚合结果。"""
        return service.overview(start_date=start_date, end_date=end_date, granularity=granularity)

    @app.post("/api/skills/{skill_id}/visits", response_model=SkillVisitResult)
    def visit(
        skill_id: str, payload: SkillVisitPayload, actor: ActorContext = Depends(actor_dependency),
        service: AnalyticsService = Depends(analytics_service_dependency),
    ) -> SkillVisitResult:
        """服务端取得 actor，客户端不传身份和事件时间。"""
        service.record_visit(skill_id=skill_id, actor=actor.id, event_id=payload.event_id)
        return SkillVisitResult()
