"""运营事实采集与固定次数的 SQL 聚合。"""

from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import distinct, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from skillhub.models.entities import utc_now
from skillhub.models.errors import ConflictError
from skillhub.models.rules.analytics import (
    SHANGHAI,
    AnalyticsBucket,
    AnalyticsMetrics,
    AnalyticsOverview,
    AnalyticsPopularSkill,
    Granularity,
    analytics_range,
    buckets,
    coverage,
    shift_month,
)
from skillhub.models.schema import orm
from skillhub.models.schema.analytics import AnalyticsCollectionState, SkillCreationFact, SkillVisitEvent


class AnalyticsStoreMixin:
    def _record_skill_creation(self, session, *, skill_id: str, name: str, owner_ref: str, created_at: datetime) -> None:
        """在业务创建事务中写入唯一创建事实。"""
        session.execute(insert(SkillCreationFact).values(skill_id=skill_id, name=name, owner_ref=owner_ref, created_at=created_at))

    def record_skill_visit(self, *, skill_id: str, actor: str, event_id: UUID) -> None:
        """沿用详情页开放读取规则，按事件身份幂等记录访问。"""
        with self._write_session() as session:
            self._skill_row(session, skill_id)
            inserted = session.execute(
                pg_insert(SkillVisitEvent).values(event_id=event_id, skill_id=skill_id, actor=actor, visited_at=utc_now())
                .on_conflict_do_nothing(index_elements=[SkillVisitEvent.event_id]).returning(SkillVisitEvent.event_id)
            ).scalar_one_or_none()
            if inserted is None:
                existing = session.get(SkillVisitEvent, event_id)
                if existing.skill_id != skill_id or existing.actor != actor:
                    raise ConflictError("访问事件 ID 已用于其他访问。")

    def analytics_overview(self, *, start_date: date, end_date: date, granularity: Granularity) -> AnalyticsOverview:
        """聚合指标、趋势和热门榜，不逐个查询 Skill。"""
        now = utc_now()
        start, end = analytics_range(start_date, end_date, now)
        with self._read_session() as session:
            state = session.get(AnalyticsCollectionState, "default")
            visits_started = state.visits_started_at if state else now
            demo_started = state.demo_started_at if state else None
            collected_from = min(visits_started, demo_started) if demo_started else visits_started
            visit_filter = (SkillVisitEvent.visited_at >= start, SkillVisitEvent.visited_at < min(end, now))
            create_filter = (SkillCreationFact.created_at >= start, SkillCreationFact.created_at < min(end, now))
            counts = session.execute(select(func.count(), func.count(distinct(SkillVisitEvent.actor)),
                                            func.coalesce(func.bool_or(SkillVisitEvent.is_demo), False))
                                     .where(*visit_filter)).one()
            created = session.execute(select(func.count(), func.coalesce(func.bool_or(SkillCreationFact.is_demo), False))
                                      .where(*create_filter)).one()
            total = session.scalar(select(func.count()).select_from(orm.Skill))
            creation_bucket = func.date_trunc(granularity, func.timezone("Asia/Shanghai", SkillCreationFact.created_at))
            visit_bucket = func.date_trunc(granularity, func.timezone("Asia/Shanghai", SkillVisitEvent.visited_at))
            creations = {row[0].date(): row[1] for row in session.execute(
                select(creation_bucket, func.count()).where(*create_filter).group_by(creation_bucket))}
            visits = {row[0].date(): (row[1], row[2]) for row in session.execute(
                select(visit_bucket, func.count(), func.count(distinct(SkillVisitEvent.actor)))
                .where(*visit_filter).group_by(visit_bucket))}
            rank = (select(SkillVisitEvent.skill_id, func.count().label("pv"),
                           func.count(distinct(SkillVisitEvent.actor)).label("uv"))
                    .where(*visit_filter).group_by(SkillVisitEvent.skill_id).subquery())
            popular = session.execute(
                select(rank.c.skill_id, rank.c.pv, rank.c.uv,
                       func.coalesce(orm.Skill.display_name, orm.Skill.slug, SkillCreationFact.name, rank.c.skill_id).label("name"),
                       func.coalesce(orm.Skill.owner_ref, SkillCreationFact.owner_ref, "未知").label("owner_ref"),
                       orm.Skill.id.is_(None).label("deleted"))
                .outerjoin(orm.Skill, orm.Skill.id == rank.c.skill_id)
                .outerjoin(SkillCreationFact, SkillCreationFact.skill_id == rank.c.skill_id)
                .order_by(rank.c.pv.desc(), rank.c.uv.desc(), rank.c.skill_id).limit(10)
            ).mappings().all()
            overall_coverage = coverage(start, min(end, now), collected_from)
            trend = []
            for day in buckets(start_date, end_date, granularity):
                next_day = shift_month(day, 1) if granularity == "month" else day + timedelta(days=1)
                bucket_start = max(start, datetime.combine(day, time.min, SHANGHAI))
                bucket_end = min(end, now, datetime.combine(next_day, time.min, SHANGHAI))
                collected = coverage(bucket_start, bucket_end, collected_from)
                pv, uv = visits.get(day, (0, 0))
                trend.append(AnalyticsBucket(date=day, new_skills=creations.get(day, 0),
                                             pv=None if collected == "none" else pv,
                                             uv=None if collected == "none" else uv, coverage=collected))
            return AnalyticsOverview(
                start_date=start_date, end_date=end_date, granularity=granularity, generated_at=now,
                visits_started_at=visits_started, demo_started_at=demo_started,
                includes_demo=bool(demo_started or counts[2] or created[1]),
                creation_history_note=state.creation_history_note if state else "访问采集尚未初始化。",
                coverage=overall_coverage,
                metrics=AnalyticsMetrics(total_skills=total or 0, new_skills=created[0],
                                         pv=None if overall_coverage == "none" else counts[0],
                                         uv=None if overall_coverage == "none" else counts[1]),
                trend=trend, popular=[AnalyticsPopularSkill(**row) for row in popular],
            )
