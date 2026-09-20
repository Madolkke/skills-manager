"""真实 PostgreSQL 上验证分页边界、摘要和旧接口兼容。"""
from datetime import timedelta

from sqlalchemy import event, insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


class PaginationApiTests(ApiCommandTestCase):
    def test_skill_pages_filter_counts_and_bounded_queries(self):
        for index in range(43):
            self.create_skill(f"page-skill-{index:03}")
        statements = []

        def record(_connection, _cursor, statement, _params, _context, _many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", record)
        try:
            response = self.client.post("/api/skills/query", json={"page": 2, "page_size": 20, "sort": "name"})
        finally:
            event.remove(self.engine, "before_cursor_execute", record)
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total"], 43)
        self.assertEqual(len(payload["items"]), 20)
        self.assertEqual(payload["items"][0]["skill"]["slug"], "page-skill-020")
        self.assertEqual(payload["counts"]["all"], 43)
        self.assertLess(len(statements), 25)
        self.assertTrue(any("LIMIT" in query and "OFFSET" in query for query in statements))
        self.assertFalse(any("FROM artifacts" in query for query in statements))
        filtered = self.client.post("/api/skills/query", json={"query": "page-skill-042"}).json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["counts"]["all"], 43)
        self.assertEqual(self.client.post("/api/skills/query", json={"page_size": 101}).status_code, 422)
        self.assertEqual(self.client.post("/api/skills/query", json={"extra": 1}).status_code, 422)
        self.assertIsInstance(self.client.get("/api/skills").json(), list)

    def test_versions_core_and_cross_page_detail(self):
        skill = self.create_skill("versions")
        skill_id = skill["skill_id"]
        first = skill["skill_version_id"]
        for index in range(23):
            self.create_skill_version(skill_id, f"version-{index}")
        core = self.client.get(f"/api/skills/{skill_id}/core")
        self.assertEqual(core.status_code, 200, core.text)
        self.assertNotIn("versions", core.json())
        self.assertEqual(core.json()["version_count"], 24)
        self.assertEqual(core.json()["highest_version"]["version"], "0.0.24")
        page = self.client.get(f"/api/skills/{skill_id}/versions/page?page=2").json()
        self.assertEqual(len(page["items"]), 4)
        detail = self.client.get(f"/api/skill-versions/{first}/detail")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertIsNone(detail.json()["previous"])
        highest = core.json()["highest_version"]["id"]
        detail = self.client.get(f"/api/skill-versions/{highest}/detail").json()
        self.assertEqual(detail["previous"]["version"], "0.0.23")
        self.assertEqual(len(self.client.get(f"/api/skills/{skill_id}").json()["versions"]), 24)

    def test_reviews_runs_and_admin_pages(self):
        skill = self.create_skill("history")
        skill_id, version = skill["skill_id"], skill["skill_version_id"]
        detail = self.client.get(f"/api/skills/{skill_id}").json()
        eval_set = detail["summary"]["primary_eval_set"]["id"]
        started = utc_now() - timedelta(minutes=2)
        with self.engine.begin() as connection:
            for index in range(61):
                connection.execute(insert(tables.eval_runs).values(id=new_id("run"), skill_id=skill_id,
                    skill_version_id=version, eval_set_id=eval_set, status="finished", summary={},
                    run_context_hash=f"context-{index}", created_at=started + timedelta(seconds=index), created_by="tester"))
            for index in range(23):
                connection.execute(insert(tables.review_requests).values(id=new_id("review"), skill_id=skill_id,
                    skill_version_id=version, status="open" if index % 2 else "closed", summary={},
                    created_at=utc_now(), created_by="tester"))
        runs = self.client.get(f"/api/skills/{skill_id}/eval-runs/page?page=4").json()
        self.assertEqual(runs["total"], 61)
        self.assertEqual(len(runs["items"]), 1)
        guidance = self.client.get(f"/api/skills/{skill_id}/guidance").json()
        self.assertEqual(len(guidance["eval_runs"]), 1)
        self.assertEqual(guidance["eval_runs"][0]["run_context_hash"], "context-60")
        reviews = self.client.get(f"/api/skills/{skill_id}/reviews/page?page=2").json()
        self.assertEqual(reviews["total"], 23)
        self.assertEqual(len(reviews["items"]), 3)
        self.assertNotIn("responses", reviews["items"][0])
        self.assertEqual(reviews["counts"]["open"], 11)
        self.assertIn("responses", self.client.get(f'/api/reviews/{reviews["items"][0]["id"]}').json())
        self.assertEqual(self.client.get("/api/admin/overview").status_code, 403)
        headers = {"X-SkillHub-Admin-Key": "test-admin-key"}
        overview = self.client.get("/api/admin/overview", headers=headers)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["counts"]["skills"], 1)
        roles = self.client.get("/api/admin/role-assignments/page", headers=headers)
        self.assertEqual(roles.status_code, 200, roles.text)
        self.assertTrue(all("resource_label" in item for item in roles.json()["items"]))

    def test_tag_facets_preserve_same_group_or(self):
        one, two = self.create_tag_value("domain", "one"), self.create_tag_value("domain", "two")
        for index, tag in enumerate((one, two)):
            payload = self.skill_payload(f"tag-{index}")
            payload["tags"] = [tag]
            self.assertEqual(self.client.post("/api/skills", json=payload).status_code, 200)
        response = self.client.post("/api/skills/query", json={"tags": [one]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["tag_counts"]["domain\u0000two"], 2)

    def test_semver_previous_uses_full_history_and_prerelease_order(self):
        skill = self.create_skill("semver")
        versions = ["1.0.0-alpha", "1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0-beta-one", "1.0.0"]
        ids = [skill["skill_version_id"]]
        for index in range(4):
            ids.append(self.create_skill_version(skill["skill_id"], f"semver-{index}")["skill_version_id"])
        with self.engine.begin() as connection:
            for version_id, value in zip(ids, versions):
                connection.execute(update(tables.skill_versions).where(tables.skill_versions.c.id == version_id).values(version=value))
        for index, version_id in enumerate(ids):
            response = self.client.get(f"/api/skill-versions/{version_id}/detail?include_files=false")
            self.assertEqual(response.status_code, 200, response.text)
            previous = response.json()["previous"]
            self.assertEqual(previous["id"] if previous else None, ids[index - 1] if index else None)

    def test_cascade_filter_excludes_inactive_paths_and_role_search(self):
        parent = self.create_tag_value("parent", "on")
        child = self.create_tag_value("child", "leaf")
        other = self.create_tag_value("other", "extra")
        one, two = self.create_skill("active-path"), self.create_skill("inactive-path")
        with self.engine.begin() as connection:
            connection.execute(insert(tables.tag_group_cascades).values(child_tag_group_id="child", parent_tag_group_id="parent",
                parent_tag_value="on", activation_mode="parent_value", created_by="tester"))
            for skill, tags in ((one, [parent, child, other]), (two, [child])):
                for tag in tags:
                    connection.execute(insert(tables.skill_tags).values(skill_id=skill["skill_id"], tag_group_id=tag["group_id"],
                        tag_value=tag["value"], created_by="tester"))
        filtered = self.client.post("/api/skills/query", json={"tags": [child, other]}).json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["items"][0]["skill"]["id"], one["skill_id"])
        with self.engine.begin() as connection:
            connection.execute(insert(tables.role_assignments).values(id=new_id("role"), subject_type="user", subject_id="tester",
                resource_type="skill", resource_id=two["skill_id"], role="viewer", created_by="tester"))
        headers = {"X-SkillHub-Admin-Key": "test-admin-key"}
        diagnostic = self.client.post("/api/admin/skills/query", headers=headers,
            json={"diagnostic_group": "child", "diagnostic_kind": "orphaned"}).json()
        self.assertEqual(diagnostic["total"], 1)
        roles = self.client.get("/api/admin/role-assignments/page?resource=inactive-path&resource_type=skill&role=viewer", headers=headers).json()
        self.assertEqual(roles["total"], 1)
        self.assertEqual(roles["items"][0]["resource_label"], "inactive-path")
        self.assertFalse(roles["items"][0]["resource_missing"])
