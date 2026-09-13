"""运营看板的日期口径与严格输出契约。"""

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from skillhub.models.errors import InvariantError

SHANGHAI = ZoneInfo("Asia/Shanghai")
Granularity = Literal["day", "month"]
Coverage = Literal["none", "partial", "complete"]


def shift_month(value: date, months: int) -> date:
    """按自然月移动日期，月底截断到目标月最后一天。"""
    ordinal = value.year * 12 + value.month - 1 + months
    year, month = divmod(ordinal, 12)
    return date(year, month + 1, min(value.day, monthrange(year, month + 1)[1]))


def analytics_range(start: date, end: date, now: datetime) -> tuple[datetime, datetime]:
    """将包含截止日的北京时间日期范围转换为 UTC 半开区间。"""
    if end < start or start < date(2000, 1, 1) or end > now.astimezone(SHANGHAI).date():
        raise InvariantError("日期范围无效：起始日须不早于 2000 年，截止日不能早于起始日或晚于今天。")
    if end >= shift_month(start, 24):
        raise InvariantError("日期范围不能超过 24 个月。")
    return (
        datetime.combine(start, time.min, SHANGHAI).astimezone(timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, SHANGHAI).astimezone(timezone.utc),
    )


def buckets(start: date, end: date, granularity: Granularity) -> list[date]:
    """生成连续桶标签，使无事件的日期也能展示。"""
    current = start.replace(day=1) if granularity == "month" else start
    result = []
    while current <= end:
        result.append(current)
        current = shift_month(current, 1) if granularity == "month" else current + timedelta(days=1)
    return result


def coverage(start: datetime, end: datetime, collected_from: datetime) -> Coverage:
    """区分完全未采集、部分采集和完整采集的区间。"""
    return "none" if end <= collected_from else "partial" if start < collected_from else "complete"


class AnalyticsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AnalyticsMetrics(AnalyticsModel):
    total_skills: int
    new_skills: int
    pv: int | None
    uv: int | None


class AnalyticsBucket(AnalyticsModel):
    date: date
    new_skills: int
    pv: int | None
    uv: int | None
    coverage: Coverage


class AnalyticsPopularSkill(AnalyticsModel):
    skill_id: str
    name: str
    owner_ref: str
    pv: int
    uv: int
    deleted: bool


class AnalyticsOverview(AnalyticsModel):
    start_date: date
    end_date: date
    granularity: Granularity
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    generated_at: datetime
    visits_started_at: datetime
    demo_started_at: datetime | None
    includes_demo: bool
    creation_history_note: str
    coverage: Coverage
    metrics: AnalyticsMetrics
    trend: list[AnalyticsBucket]
    popular: list[AnalyticsPopularSkill]
