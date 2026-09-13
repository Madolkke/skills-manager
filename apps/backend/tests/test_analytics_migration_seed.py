import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic import command
from sqlalchemy import func, insert, select, text
from sqlalchemy.orm import Session

from skillhub.models.schema import orm
from skillhub.models.schema.analytics import AnalyticsCollectionState, SkillCreationFact, SkillVisitEvent
from skillhub.models.schema.migrations import alembic_config, upgrade_database
from tests.postgres_test_case import PostgresTestCase


class AnalyticsMigrationSeedTest(PostgresTestCase):
    def test_backfill_existing_skills_and_seed_is_repeatable(self):
        """真实迁移保留创建日期，重复 seed 不改变业务数据或累计模拟次数。"""
        with self.engine.begin() as connection:
            config = alembic_config()
            config.attributes["connection"] = connection
            command.downgrade(config, "0007_command_library")
        created = datetime(2025, 5, 1, tzinfo=timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(insert(orm.Skill).values(id="existing", slug="existing", owner_ref="owner", created_at=created))
        upgrade_database(self.engine)
        with self.engine.connect() as connection:
            assert connection.scalar(select(SkillCreationFact.created_at).where(SkillCreationFact.skill_id == "existing")) == created
            assert connection.scalar(select(func.count()).select_from(SkillVisitEvent)) == 0
        scripts = Path(__file__).resolve().parents[3] / "scripts"
        sys.path.insert(0, str(scripts))
        try:
            spec = spec_from_file_location("analytics_seed_test", scripts / "seed-analytics-mocks.py")
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            now = datetime(2026, 9, 13, 9, tzinfo=timezone.utc)
            with Session(self.engine) as session, session.begin():
                first = module.seed_demo(session, now, 20260913)
                second = module.seed_demo(session, now, 20260913)
                assert first == second
                assert session.scalar(select(func.count()).select_from(SkillCreationFact)) == 61
                assert session.scalar(select(func.count()).select_from(SkillVisitEvent)) == 12000
                assert session.scalar(select(func.count(func.distinct(SkillVisitEvent.actor)))) == 30
                assert session.scalar(select(func.count()).select_from(SkillVisitEvent).where(SkillVisitEvent.visited_at > now)) == 0
                assert session.scalar(select(func.count()).select_from(SkillVisitEvent).join(
                    SkillCreationFact, SkillCreationFact.skill_id == SkillVisitEvent.skill_id
                ).where(SkillVisitEvent.visited_at < SkillCreationFact.created_at)) == 0
                assert session.get(AnalyticsCollectionState, "default").demo_started_at is not None
                assert session.scalar(text("select count(*) from skills where id = 'existing'")) == 1
        finally:
            sys.path.remove(str(scripts))
