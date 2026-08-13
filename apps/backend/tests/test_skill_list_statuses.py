from __future__ import annotations

from sqlalchemy import insert

from skillhub.models.entities import new_id, utc_now
from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


class SkillListStatusTest(ApiCommandTestCase):
    def test_list_projects_only_current_version_review_and_publish_statuses(self) -> None:
        created = self.create_skill("list-statuses")
        skill_id = created["skill_id"]
        current_version_id = created["skill_version_id"]
        historical_version_id = self.create_skill_version(skill_id, "list-statuses-history")["skill_version_id"]
        targets = self.client.get("/api/admin/publish-targets", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()

        self._insert_review(skill_id, historical_version_id, "closed")
        self._insert_review(skill_id, current_version_id, "open")
        self._insert_publish(skill_id, historical_version_id, targets[0]["id"], "released")
        self._insert_publish(skill_id, current_version_id, targets[0]["id"], "releasing")

        item = next(row for row in self.client.get("/api/skills").json() if row["skill"]["id"] == skill_id)

        self.assertEqual(item["summary"]["review_status"], "open")
        self.assertEqual(item["summary"]["publish_status"], "releasing")

    def test_list_prefers_released_when_current_version_has_multiple_targets(self) -> None:
        created = self.create_skill("list-release-precedence")
        skill_id = created["skill_id"]
        version_id = created["skill_version_id"]
        targets = self.client.get("/api/admin/publish-targets", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()

        self._insert_publish(skill_id, version_id, targets[0]["id"], "failed")
        self._insert_publish(skill_id, version_id, targets[1]["id"], "released")

        item = next(row for row in self.client.get("/api/skills").json() if row["skill"]["id"] == skill_id)

        self.assertEqual(item["summary"]["review_status"], "unreviewed")
        self.assertEqual(item["summary"]["publish_status"], "released")

    def test_tag_group_sort_order_rejects_fractional_values(self) -> None:
        response = self.client.post(
            "/api/admin/tag-groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"id": "fractional-order", "display_name": "排序", "sort_order": 1.5},
        )

        self.assertEqual(response.status_code, 422)

    def _insert_review(self, skill_id: str, version_id: str, status: str) -> str:
        review_id = new_id("review")
        with self.engine.begin() as connection:
            connection.execute(
                insert(tables.review_requests).values(
                    id=review_id,
                    skill_id=skill_id,
                    skill_version_id=version_id,
                    status=status,
                    summary={},
                    created_at=utc_now(),
                    created_by="tester",
                )
            )
        return review_id

    def _insert_publish(self, skill_id: str, version_id: str, target_id: str, status: str) -> None:
        review_id = self._insert_review(skill_id, version_id, "closed")
        with self.engine.begin() as connection:
            connection.execute(
                insert(tables.publish_records).values(
                    id=new_id("publish"),
                    skill_id=skill_id,
                    skill_version_id=version_id,
                    review_request_id=review_id,
                    publish_target_id=target_id,
                    status=status,
                    check_snapshot=[],
                    metadata={},
                    created_at=utc_now(),
                    created_by="tester",
                )
            )
