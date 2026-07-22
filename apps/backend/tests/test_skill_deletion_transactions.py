from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import func, insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.operations.skills.deletion import SkillDeletionMixin
from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


class SkillDeletionTransactionTest(ApiCommandTestCase):
    def test_delete_uses_current_slug_after_concurrent_rename(self):
        skill = self.create_skill("delete-old-slug")
        updated = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            json={"slug": "delete-new-slug", "owner_ref": "skillhub-lab", "tags": []},
        )
        stale = self.client.request(
            "DELETE",
            f"/api/skills/{skill['skill_id']}",
            json={"confirmation_slug": "delete-old-slug"},
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(stale.status_code, 400)
        self.assertEqual(self.client.get(f"/api/skills/{skill['skill_id']}").status_code, 200)

    def test_unexpected_failure_rolls_back_all_deletion_changes(self):
        skill = self.create_skill("delete-rollback")
        skill_id = skill["skill_id"]
        with self.engine.connect() as connection:
            original_audits = connection.execute(
                select(func.count()).select_from(tables.audit_events).where(tables.audit_events.c.resource_id == skill_id)
            ).scalar_one()

        with patch.object(
            SkillDeletionMixin,
            "_delete_unreferenced_artifacts",
            side_effect=RuntimeError("injected deletion failure"),
        ):
            response = self.client.request(
                "DELETE",
                f"/api/skills/{skill_id}",
                json={"confirmation_slug": "delete-rollback"},
            )
            self.assertEqual(response.status_code, 500)

        with self.engine.connect() as connection:
            self.assertIsNotNone(
                connection.execute(select(tables.skills.c.id).where(tables.skills.c.id == skill_id)).scalar_one_or_none()
            )
            self.assertEqual(
                connection.execute(
                    select(func.count()).select_from(tables.audit_events).where(tables.audit_events.c.resource_id == skill_id)
                ).scalar_one(),
                original_audits,
            )

    def test_related_active_job_blocks_even_when_publish_record_is_pending(self):
        skill = self.create_skill("delete-active-job")
        review_id = new_id("review")
        publish_id = new_id("publish")
        job_id = new_id("job")
        now = utc_now()
        with self.engine.begin() as connection:
            target_id = connection.execute(select(tables.publish_targets.c.id).limit(1)).scalar_one()
            connection.execute(
                insert(tables.review_requests).values(
                    id=review_id,
                    skill_id=skill["skill_id"],
                    skill_version_id=skill["skill_version_id"],
                    status="open",
                    summary={},
                    created_by="product-operator",
                    created_at=now,
                )
            )
            connection.execute(
                insert(tables.publish_records).values(
                    id=publish_id,
                    skill_id=skill["skill_id"],
                    skill_version_id=skill["skill_version_id"],
                    review_request_id=review_id,
                    publish_target_id=target_id,
                    status="pending_confirmation",
                    check_snapshot=[],
                    metadata={},
                    created_by="product-operator",
                    created_at=now,
                )
            )
            connection.execute(
                insert(tables.jobs).values(
                    id=job_id,
                    type="publish_release",
                    status="queued",
                    payload={"schema_version": 1, "publish_record_id": publish_id, "idempotency_key": f"publish_release:{publish_id}"},
                    attempts=0,
                    created_by="product-operator",
                    created_at=now,
                )
            )
            connection.execute(
                insert(tables.worker_heartbeats).values(
                    worker_id="delete-test-worker",
                    status="running",
                    current_job_id=job_id,
                    current_job_type="publish_release",
                    last_seen_at=now,
                    started_at=now,
                    metadata={},
                )
            )

        blocked = self.client.request(
            "DELETE",
            f"/api/skills/{skill['skill_id']}",
            json={"confirmation_slug": "delete-active-job"},
        )
        self.assertEqual(blocked.status_code, 409)

        with self.engine.begin() as connection:
            connection.execute(update(tables.jobs).where(tables.jobs.c.id == job_id).values(status="canceled"))
        deleted = self.client.request(
            "DELETE",
            f"/api/skills/{skill['skill_id']}",
            json={"confirmation_slug": "delete-active-job"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        with self.engine.connect() as connection:
            heartbeat = connection.execute(
                select(tables.worker_heartbeats).where(tables.worker_heartbeats.c.worker_id == "delete-test-worker")
            ).mappings().one()
            self.assertEqual(heartbeat["status"], "idle")
            self.assertIsNone(heartbeat["current_job_id"])

    def test_workflow_skill_can_be_deleted_without_touching_collection_catalog(self):
        created = self.client.post(
            "/api/workflows",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={
                "slug": "delete-workflow",
                "owner_ref": "workflow-owner",
                "description": "Disposable workflow.",
                "tags": [],
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        skill_id = created.json()["skill_id"]
        with self.engine.connect() as connection:
            catalog_count = connection.execute(
                select(func.count()).select_from(tables.workflow_collection_definitions)
            ).scalar_one()

        deleted = self.client.request(
            "DELETE",
            f"/api/skills/{skill_id}",
            headers={"X-SkillHub-Actor": "workflow-owner"},
            json={"confirmation_slug": "delete-workflow"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.text)
        with self.engine.connect() as connection:
            self.assertIsNone(
                connection.execute(select(tables.workflows.c.id).where(tables.workflows.c.skill_id == skill_id)).scalar_one_or_none()
            )
            self.assertEqual(
                connection.execute(select(func.count()).select_from(tables.workflow_collection_definitions)).scalar_one(),
                catalog_count,
            )
