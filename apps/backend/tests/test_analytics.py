from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import event, func, insert, select, update

from skillhub.models.entities import ContentRef
from skillhub.models.schema.analytics import AnalyticsCollectionState, SkillCreationFact, SkillVisitEvent
from tests.api_command_test_case import ApiCommandTestCase
from tests.test_workflow_import_export import workflow_document

ADMIN = {"X-SkillHub-Admin-Key": "test-admin-key"}


class AnalyticsTest(ApiCommandTestCase):
    def setUp(self) -> None:
        """初始化真实 PostgreSQL 测试库和固定采集起点。"""
        super().setUp()
        with self.engine.begin() as connection:
            connection.execute(insert(AnalyticsCollectionState).values(
                id="default", visits_started_at=datetime(2025, 1, 1, tzinfo=timezone.utc), creation_history_note="测试历史覆盖"))

    def overview(self, start="2026-01-01", end="2026-02-28", granularity="month"):
        """使用真实后台接口读取统计。"""
        return self.client.get("/api/admin/analytics/overview", headers=ADMIN,
                               params={"start_date": start, "end_date": end, "granularity": granularity})

    def test_visits_require_existing_skill_and_are_idempotent_by_actor(self):
        """仅同一访问可以重复提交，普通详情读取本身不计数。"""
        skill = self.create_skill("visits")["skill_id"]
        path = f"/api/skills/{skill}/visits"
        payload = {"event_id": str(uuid4())}
        assert self.client.get(f"/api/skills/{skill}").status_code == 200
        for _ in range(2):
            assert self.client.post(path, json=payload, headers={"X-SkillHub-Actor": "alice"}).status_code == 200
        assert self.client.post(path, json=payload, headers={"X-SkillHub-Actor": "bob"}).status_code == 409
        other = self.create_skill("other-visits")["skill_id"]
        assert self.client.post(f"/api/skills/{other}/visits", json=payload, headers={"X-SkillHub-Actor": "alice"}).status_code == 409
        assert self.client.post("/api/skills/missing/visits", json={"event_id": str(uuid4())}).status_code == 404
        assert self.client.post(path, json={"event_id": "invalid"}).status_code == 422
        assert self.client.post(path, json={**payload, "actor": "spoof"}).status_code == 422
        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(SkillVisitEvent)) == 1

    def test_monthly_uv_boundaries_rank_and_deleted_history(self):
        """UTC 边界转换为北京时间；删除后历史和排名仍保留。"""
        skill = self.create_skill("historical")["skill_id"]
        january = datetime(2026, 1, 31, 15, 59, tzinfo=timezone.utc)
        february = datetime(2026, 1, 31, 16, 0, tzinfo=timezone.utc)
        with self.engine.begin() as connection:
            connection.execute(update(SkillCreationFact).where(SkillCreationFact.skill_id == skill).values(created_at=january))
            connection.execute(insert(SkillVisitEvent), [
                {"event_id": uuid4(), "skill_id": skill, "actor": actor, "visited_at": when}
                for actor, when in [("alice", january), ("alice", february), ("bob", february)]
            ])
        result = self.overview().json()
        assert result["metrics"] == {"total_skills": 1, "new_skills": 1, "pv": 3, "uv": 2}
        assert [(row["pv"], row["uv"], row["new_skills"]) for row in result["trend"]] == [(1, 1, 1), (2, 2, 0)]
        assert result["popular"][0]["skill_id"] == skill
        daily = self.overview("2026-02-01", "2026-02-03", "day").json()
        assert [row["pv"] for row in daily["trend"]] == [2, 0, 0]
        self.store.delete_skill(skill_id=skill, confirmation_slug="historical", actor="product-operator")
        deleted = self.overview().json()
        assert deleted["metrics"] == {"total_skills": 0, "new_skills": 1, "pv": 3, "uv": 2}
        assert deleted["popular"][0]["deleted"] is True
        assert deleted["popular"][0]["name"] == "historical"

    def test_coverage_dates_admin_auth_and_fixed_query_count(self):
        """未采集不是零，查询数量不随 Skill 数增长。"""
        assert self.client.get("/api/admin/analytics/overview", params={"start_date": "2026-01-01", "end_date": "2026-01-02"}).status_code == 403
        for start, end in [("2026-02-01", "2026-01-01"), ("2020-01-01", "2026-01-01"), ("2026-01-01", "2099-01-01")]:
            assert self.overview(start, end).status_code == 400
        assert self.overview(granularity="hour").status_code == 422
        before = self.overview("2024-11-01", "2024-12-31").json()
        assert before["metrics"]["pv"] is None
        assert all(row["coverage"] == "none" for row in before["trend"])
        with self.engine.begin() as connection:
            connection.execute(update(AnalyticsCollectionState).values(visits_started_at=datetime(2026, 1, 15, tzinfo=timezone.utc)))
        statements = []

        def count_sql(_conn, _cursor, statement, _parameters, _context, _many):
            """只捕获聚合接口实际执行的 SQL。"""
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", count_sql)
        try:
            response = self.overview()
        finally:
            event.remove(self.engine, "before_cursor_execute", count_sql)
        assert response.status_code == 200
        assert len(statements) <= 8
        assert response.json()["trend"][0]["coverage"] == "partial"

    def test_all_creation_paths_versions_and_rollback(self):
        """三个创建入口均只写一个事实，失败事务不遗留事实。"""
        skill = self.create_skill("ordinary")["skill_id"]
        self.create_skill_version(skill, "ordinary-v2")
        document = workflow_document()
        document["workflow"]["nodes"] = []
        document["collectionSnapshots"] = []
        self.store.create_workflow_skill(slug="workflow", owner_ref="owner", manifest_text="{}", document=document, tags=[], actor="product-operator")
        for version, digest in [("0.0.1", "first"), ("0.0.2", "second")]:
            self.store.upsert_skill_bundle_for_owner(owner_ref="owner", slug="external", actor="product-operator", bundle_digest=digest,
                                                     bundle_manifest_text="{}", file_count=1, entry_path="SKILL.md", tags=[], version=version)
        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(SkillCreationFact)) == 3
        try:
            with self.store.transaction() as transactional:
                transactional.insert_skill_with_initial_version(slug="rollback", owner_ref="owner", actor="product-operator", tags=[],
                                                                 content_ref=ContentRef(kind="skill_bundle", locator="memory:x", digest="x"),
                                                                 change_summary="", version="0.0.1", creator_role_reason="test")
                raise RuntimeError("rollback")
        except RuntimeError:
            pass
        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(SkillCreationFact)) == 3

    def test_actor_month_uv_is_not_sum_of_daily_uv(self):
        """同一 actor 跨天跨设备访问在月度只算一个。"""
        skill = self.create_skill("monthly")["skill_id"]
        with self.engine.begin() as connection:
            connection.execute(insert(SkillVisitEvent), [
                {"event_id": uuid4(), "skill_id": skill, "actor": "shared", "visited_at": datetime(2026, 1, day, tzinfo=timezone.utc)}
                for day in [1, 2, 3]
            ])
        assert self.overview().json()["metrics"]["uv"] == 1
        assert sum(row["uv"] for row in self.overview("2026-01-01", "2026-01-03", "day").json()["trend"]) == 3

    def test_ranking_ties_and_demo_label_outside_event_period(self):
        """排名按 PV、UV、ID 稳定排序，空时间段仍说明总量包含演示内容。"""
        skills = sorted(self.create_skill(f"rank-{index}")["skill_id"] for index in range(3))
        with self.engine.begin() as connection:
            connection.execute(update(AnalyticsCollectionState).values(demo_started_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
            connection.execute(insert(SkillVisitEvent), [
                {"event_id": uuid4(), "skill_id": skill, "actor": actor, "visited_at": datetime(2026, 1, 2, tzinfo=timezone.utc), "is_demo": True}
                for skill, actors in [(skills[0], ["a", "a"]), (skills[1], ["a", "b"]), (skills[2], ["a", "b"])]
                for actor in actors
            ])
        result = self.overview().json()
        assert [row["skill_id"] for row in result["popular"]] == [skills[1], skills[2], skills[0]]
        empty = self.overview("2024-11-01", "2024-12-31").json()
        assert empty["includes_demo"] is True
        assert empty["metrics"]["pv"] is None
