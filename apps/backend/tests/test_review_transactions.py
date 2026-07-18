from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from skillhub.models.schema import orm
from skillhub.models.store import _StoreOperations
from tests.api_command_test_case import ApiCommandTestCase


class ReviewTransactionTest(ApiCommandTestCase):
    def test_review_creation_failure_rolls_back_all_related_records(self) -> None:
        skill = self.create_skill("review-atomic-rollback")
        target = self.client.get(
            "/api/admin/publish-targets",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
        ).json()[0]
        role = self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_id": "reviewer-one", "role": "reviewer"},
        )
        self.assertEqual(role.status_code, 200)

        with patch.object(_StoreOperations, "create_review_notifications", side_effect=RuntimeError("injected failure")):
            failed = self.client.post(
                f"/api/skills/{skill['skill_id']}/reviews",
                headers={"X-SkillHub-Actor": "product-operator"},
                json={
                    "skill_version_id": skill["skill_version_id"],
                    "publish_targets": [{"publish_target_id": target["id"], "auto_submit_on_pass": True}],
                },
            )

        self.assertEqual(failed.status_code, 500)

        with Session(self.engine) as session:
            self.assertEqual(self._count(session, orm.ReviewRequest, skill_id=skill["skill_id"]), 0)
            self.assertEqual(self._count(session, orm.ReviewRequestReviewer, skill_id=skill["skill_id"]), 0)
            self.assertEqual(self._count(session, orm.ReviewRequestPublishTarget, skill_id=skill["skill_id"]), 0)
            self.assertEqual(self._count(session, orm.Notification, resource_type="review"), 0)
            self.assertEqual(self._count(session, orm.AuditEvent, resource_id=skill["skill_id"], action="review.created"), 0)

    @staticmethod
    def _count(session: Session, entity: type, **filters: object) -> int:
        statement = select(func.count()).select_from(entity)
        for name, value in filters.items():
            statement = statement.where(getattr(entity, name) == value)
        return session.scalar(statement) or 0
