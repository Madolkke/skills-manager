from __future__ import annotations

from sqlalchemy import insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


class SkillDeletionApiTest(ApiCommandTestCase):
    def test_delete_requires_body_exact_slug_and_delete_permission(self):
        skill = self._create_as("delete-guard", "creator")
        skill_id = skill["skill_id"]

        missing = self.client.request("DELETE", f"/api/skills/{skill_id}", headers=self._actor("creator"))
        mismatch = self._delete(skill_id, "Delete-guard", "creator")

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(
            mismatch.json()["field_errors"],
            [
                {
                    "field": "confirmation_slug",
                    "message": "输入当前 Skill slug 以确认永久删除。",
                    "code": "skill.delete_confirmation_mismatch",
                }
            ],
        )
        self.assertEqual(self.client.get(f"/api/skills/{skill_id}").status_code, 200)

        for role in ("maintainer", "evaluator", "reviewer", "viewer"):
            assigned = self.client.post(
                f"/api/skills/{skill_id}/role-assignments",
                headers=self._actor("creator"),
                json={"subject_id": role, "subject_type": "user", "role": role},
            )
            self.assertEqual(assigned.status_code, 200)
            capabilities = self.client.get(
                f"/api/skills/{skill_id}/capabilities",
                headers=self._actor(role),
            )
            denied = self._delete(skill_id, "delete-guard", role)
            self.assertFalse(capabilities.json()["permissions"]["skill.delete"])
            self.assertEqual(denied.status_code, 403)

        owner = self.client.post(
            f"/api/skills/{skill_id}/role-assignments",
            headers=self._actor("creator"),
            json={"subject_id": "owner-user", "subject_type": "user", "role": "owner"},
        )
        self.assertEqual(owner.status_code, 200)
        self.assertTrue(
            self.client.get(f"/api/skills/{skill_id}/capabilities", headers=self._actor("owner-user"))
            .json()["permissions"]["skill.delete"]
        )
        self.assertEqual(self._delete(skill_id, "delete-guard", "owner-user").status_code, 200)

    def test_delete_blocks_active_eval_and_allows_terminal_job(self):
        skill = self.create_skill("delete-active-eval")
        case = self.create_eval_case(skill["skill_id"])
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        queued = self.enqueue_case_run(
            skill["skill_version_id"],
            detail["summary"]["primary_eval_set"]["id"],
            case["eval_case_version_id"],
        )

        blocked = self._delete(skill["skill_id"], "delete-active-eval")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.client.get(f"/api/skills/{skill['skill_id']}").status_code, 200)

        self.store.finalize_eval_case_run(
            eval_case_run_id=queued["eval_case_run_id"],
            passed=True,
            actual_output="done",
            actor="tester",
        )
        deleted = self._delete(skill["skill_id"], "delete-active-eval")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        with self.engine.connect() as connection:
            self.assertIsNone(
                connection.execute(select(tables.jobs.c.id).where(tables.jobs.c.id == queued["job_id"]))
                .scalar_one_or_none()
            )

    def test_delete_blocks_active_publish_record(self):
        skill = self.create_skill("delete-active-publish")
        review_id, publish_id = self._insert_review_publish(skill, status="queued")

        blocked = self._delete(skill["skill_id"], "delete-active-publish")
        self.assertEqual(blocked.status_code, 409)
        with self.engine.begin() as connection:
            self.assertIsNotNone(
                connection.execute(select(tables.publish_records.c.id).where(tables.publish_records.c.id == publish_id))
                .scalar_one_or_none()
            )
            connection.execute(
                update(tables.publish_records)
                .where(tables.publish_records.c.id == publish_id)
                .values(status="failed")
            )

        deleted = self._delete(skill["skill_id"], "delete-active-publish")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        with self.engine.connect() as connection:
            self.assertIsNone(
                connection.execute(select(tables.review_requests.c.id).where(tables.review_requests.c.id == review_id))
                .scalar_one_or_none()
            )

    def test_delete_cleans_owned_data_preserves_builder_and_shared_artifact(self):
        shared = self.store.create_text_artifact(
            kind="skill_bundle",
            namespace="shared",
            content="shared artifact",
            actor="tester",
        )
        exclusive = self.store.create_text_artifact(
            kind="skill_bundle",
            namespace="exclusive",
            content="exclusive artifact",
            actor="tester",
        )
        target = self._create_with_artifact("delete-populated", exclusive)
        survivor = self._create_with_artifact("delete-survivor", shared)
        target_id = target["skill_id"]
        target_version_id = target["skill_version_id"]
        now = utc_now()

        with self.engine.begin() as connection:
            connection.execute(
                update(tables.skill_versions)
                .where(tables.skill_versions.c.id == target_version_id)
                .values(
                    content_ref={"kind": "artifact", "locator": f"artifact:{shared['id']}", "digest": shared["digest"]},
                    content_digest=shared["digest"],
                )
            )
            second_version_id = new_id("skillver")
            connection.execute(
                insert(tables.skill_versions).values(
                    id=second_version_id,
                    skill_id=target_id,
                    version_number=2,
                    version="0.0.2",
                    display_name=None,
                    content_ref={"kind": "artifact", "locator": f"artifact:{exclusive['id']}", "digest": exclusive["digest"]},
                    content_digest=exclusive["digest"],
                    change_summary="Exclusive version.",
                    created_at=now,
                    created_by="local-user",
                )
            )
            session_id = new_id("builder")
            connection.execute(
                insert(tables.skill_builder_sessions).values(
                    id=session_id,
                    actor_ref="builder",
                    title="kept session",
                    status="created",
                    draft_files=[],
                    run_selection={},
                    created_skill_id=target_id,
                    created_skill_version_id=target_version_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            group_id = new_id("group")
            connection.execute(
                insert(tables.groups).values(
                    id=group_id,
                    scope_type="skill",
                    scope_id=target_id,
                    name="delete group",
                    description="",
                    created_by="local-user",
                    created_at=now,
                    updated_at=now,
                )
            )
            connection.execute(
                insert(tables.group_memberships).values(
                    group_id=group_id,
                    subject_type="user",
                    subject_id="member",
                    created_by="local-user",
                    created_at=now,
                )
            )
            connection.execute(
                insert(tables.saved_views).values(
                    id=new_id("view"),
                    skill_id=target_id,
                    name="delete view",
                    view_type="run_history",
                    config={},
                    created_by="local-user",
                    created_at=now,
                )
            )
            connection.execute(
                insert(tables.notifications).values(
                    id=new_id("notification"),
                    recipient_actor_id="local-user",
                    type="skill.notice",
                    title="delete",
                    body="",
                    resource_type="skill",
                    resource_id=target_id,
                    created_by="system",
                    created_at=now,
                )
            )

        deleted = self._delete(target_id, "delete-populated")
        self.assertEqual(deleted.status_code, 200, deleted.text)

        with self.engine.connect() as connection:
            builder = connection.execute(
                select(tables.skill_builder_sessions).where(tables.skill_builder_sessions.c.id == session_id)
            ).mappings().one()
            tombstones = connection.execute(
                select(tables.audit_events).where(tables.audit_events.c.resource_id == target_id)
            ).mappings().all()
            self.assertIsNone(builder["created_skill_id"])
            self.assertIsNone(builder["created_skill_version_id"])
            self.assertIsNotNone(connection.execute(select(tables.artifacts.c.id).where(tables.artifacts.c.id == shared["id"])).scalar_one_or_none())
            self.assertIsNone(connection.execute(select(tables.artifacts.c.id).where(tables.artifacts.c.id == exclusive["id"])).scalar_one_or_none())
            self.assertIsNotNone(connection.execute(select(tables.skills.c.id).where(tables.skills.c.id == survivor["skill_id"])).scalar_one_or_none())
            self.assertEqual(len(tombstones), 1)
            self.assertEqual(tombstones[0]["action"], "skill.deleted")
            self.assertEqual(set(tombstones[0]["payload"]), {"skill_id", "slug", "actor", "deleted_at"})

        recreated = self.create_skill("delete-populated")
        self.assertNotEqual(recreated["skill_id"], target_id)

    def _create_as(self, slug: str, actor: str) -> dict:
        response = self.client.post("/api/skills", headers=self._actor(actor), json=self.skill_payload(slug))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _create_with_artifact(self, slug: str, artifact: dict) -> dict:
        payload = self.skill_payload(slug, digest=artifact["digest"])
        payload["content_ref"] = {
            "kind": "artifact",
            "locator": f"artifact:{artifact['id']}",
            "digest": artifact["digest"],
        }
        response = self.client.post("/api/skills", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _delete(self, skill_id: str, slug: str, actor: str = "product-operator"):
        return self.client.request(
            "DELETE",
            f"/api/skills/{skill_id}",
            headers=self._actor(actor),
            json={"confirmation_slug": slug},
        )

    def _insert_review_publish(self, skill: dict, *, status: str) -> tuple[str, str]:
        now = utc_now()
        review_id = new_id("review")
        publish_id = new_id("publish")
        with self.engine.begin() as connection:
            target_id = connection.execute(select(tables.publish_targets.c.id).limit(1)).scalar_one()
            connection.execute(
                insert(tables.review_requests).values(
                    id=review_id,
                    skill_id=skill["skill_id"],
                    skill_version_id=skill["skill_version_id"],
                    status="open",
                    summary={},
                    created_by="local-user",
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
                    status=status,
                    check_snapshot=[],
                    metadata={},
                    created_by="local-user",
                    created_at=now,
                )
            )
        return review_id, publish_id

    def _actor(self, actor: str) -> dict[str, str]:
        return {"X-SkillHub-Actor": actor}
