from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import select, update

from skillhub.models.entities import utc_now
from skillhub.models.schema import tables
from tests.api_command_test_case import ApiCommandTestCase


class JobLeaseRecoveryTest(ApiCommandTestCase):
    admin_headers = {"X-SkillHub-Admin-Key": "test-admin-key"}

    def test_stale_eval_is_requeued_and_old_attempt_cannot_finish_it(self):
        queued = self._enqueue_eval("lease-requeue")
        first = self.store.claim_next_eval_case_run_job(worker_id="worker-1")
        self._expire_job(first["job"]["id"])

        recovered = self.store.recover_stale_jobs(stale_after_seconds=1, max_eval_attempts=2)
        second = self.store.claim_next_eval_case_run_job(worker_id="worker-2")
        self.store.finalize_eval_case_run(
            eval_case_run_id=queued["eval_case_run_id"],
            passed=False,
            actor="worker-1",
            **first["execution"],
        )

        with self.engine.connect() as connection:
            run = connection.execute(
                select(tables.eval_case_runs).where(tables.eval_case_runs.c.id == queued["eval_case_run_id"])
            ).mappings().one()
            job = connection.execute(select(tables.jobs).where(tables.jobs.c.id == first["job"]["id"])).mappings().one()

        self.assertEqual(recovered["eval_requeued"], 1)
        self.assertEqual(second["execution"]["attempt"], 2)
        self.assertEqual(run["status"], "running")
        self.assertEqual(job["locked_by"], "worker-2")

        self.store.finalize_eval_case_run(
            eval_case_run_id=queued["eval_case_run_id"],
            passed=True,
            actor="worker-2",
            **second["execution"],
        )
        self.assertEqual(self.store.eval_case_run_detail(queued["eval_case_run_id"])["eval_case_run"]["status"], "succeeded")

    def test_stale_eval_at_max_attempts_fails_job_and_case_run(self):
        queued = self._enqueue_eval("lease-fail")
        claimed = self.store.claim_next_eval_case_run_job(worker_id="worker-1")
        self._expire_job(claimed["job"]["id"])

        recovered = self.store.recover_stale_jobs(stale_after_seconds=1, max_eval_attempts=1)

        with self.engine.connect() as connection:
            run_status = connection.scalar(
                select(tables.eval_case_runs.c.status).where(tables.eval_case_runs.c.id == queued["eval_case_run_id"])
            )
            job_status = connection.scalar(select(tables.jobs.c.status).where(tables.jobs.c.id == claimed["job"]["id"]))
        self.assertEqual(recovered["eval_failed"], 1)
        self.assertEqual(run_status, "failed")
        self.assertEqual(job_status, "failed")

    def test_concurrent_reapers_recover_each_stale_eval_only_once(self):
        self._enqueue_eval("lease-concurrent")
        claimed = self.store.claim_next_eval_case_run_job(worker_id="worker-1")
        self._expire_job(claimed["job"]["id"])

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: self.store.recover_stale_jobs(stale_after_seconds=1, max_eval_attempts=2),
                    range(2),
                )
            )

        self.assertEqual(sum(result["eval_requeued"] for result in results), 1)

    def test_publish_stale_requires_manual_retry_with_stable_idempotency_key(self):
        record = self._create_pending_publish("publish-recovery")
        confirmed = self.client.post(
            f"/api/admin/publish-records/{record['id']}/confirm",
            headers=self.admin_headers,
        )
        claimed = self.store.claim_next_publish_release_job(worker_id="publish-worker-1")
        first_key = claimed["release_payload"]["idempotency_key"]
        self._expire_job(claimed["job"]["id"])

        recovered = self.store.recover_stale_jobs(stale_after_seconds=1, max_eval_attempts=2)
        self.store.complete_publish_release_job(
            publish_record_id=record["id"],
            release_result={"external_id": "late-result"},
            **claimed["execution"],
        )
        failed = self._publish_record(record["id"])
        retried = self.client.post(
            f"/api/admin/publish-records/{record['id']}/retry",
            headers=self.admin_headers,
        )
        second = self.store.claim_next_publish_release_job(worker_id="publish-worker-2")

        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "queued")
        self.assertEqual(recovered["publish_failed"], 1)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["metadata"]["external_state"], "unknown")
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["status"], "queued")
        self.assertEqual(second["release_payload"]["idempotency_key"], first_key)

        self.store.complete_publish_release_job(
            publish_record_id=record["id"],
            release_result={"external_id": "release-1"},
            **second["execution"],
        )
        released = self._publish_record(record["id"])
        self.assertEqual(released["status"], "released")
        self.assertNotIn("external_state", released["metadata"])

    def test_cancel_queued_cancels_job_and_releasing_returns_conflict(self):
        queued_record = self._create_pending_publish("publish-cancel-queued")
        self.client.post(f"/api/admin/publish-records/{queued_record['id']}/confirm", headers=self.admin_headers)

        cancelled = self.client.post(
            f"/api/admin/publish-records/{queued_record['id']}/cancel",
            headers=self.admin_headers,
        )
        with self.engine.connect() as connection:
            job_status = connection.scalar(
                select(tables.jobs.c.status)
                .where(tables.jobs.c.type == "publish_release")
                .where(tables.jobs.c.payload["publish_record_id"].as_string() == queued_record["id"])
            )

        releasing_record = self._create_pending_publish("publish-cancel-running")
        self.client.post(f"/api/admin/publish-records/{releasing_record['id']}/confirm", headers=self.admin_headers)
        self.store.claim_next_publish_release_job(worker_id="publish-worker")
        conflict = self.client.post(
            f"/api/admin/publish-records/{releasing_record['id']}/cancel",
            headers=self.admin_headers,
        )

        self.assertEqual(cancelled.json()["status"], "cancelled")
        self.assertEqual(job_status, "canceled")
        self.assertEqual(conflict.status_code, 409)

    def _enqueue_eval(self, slug: str) -> dict:
        skill = self.create_skill(slug)
        case = self.create_eval_case(skill["skill_id"])
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        return self.enqueue_case_run(
            skill["skill_version_id"],
            detail["summary"]["primary_eval_set"]["id"],
            case["eval_case_version_id"],
        )

    def _create_pending_publish(self, slug: str) -> dict:
        skill = self.create_skill(slug)
        target = self.client.get("/api/admin/publish-targets", headers=self.admin_headers).json()[0]
        self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_id": "reviewer-one", "role": "reviewer"},
        )
        review = self.client.post(
            f"/api/skills/{skill['skill_id']}/reviews",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={
                "skill_version_id": skill["skill_version_id"],
                "publish_targets": [{"publish_target_id": target["id"], "auto_submit_on_pass": False}],
            },
        ).json()
        self.client.post(
            f"/api/reviews/{review['id']}/responses",
            headers={"X-SkillHub-Actor": "reviewer-one"},
            json={"score": 1, "comment": "可以发布"},
        )
        self.client.post(f"/api/reviews/{review['id']}/close", headers={"X-SkillHub-Actor": "product-operator"})
        response = self.client.post(
            f"/api/skills/{skill['skill_id']}/publish-records",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={
                "skill_version_id": skill["skill_version_id"],
                "review_request_id": review["id"],
                "publish_target_id": target["id"],
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _expire_job(self, job_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job_id)
                .values(last_heartbeat_at=utc_now() - timedelta(seconds=10))
            )

    def _publish_record(self, record_id: str) -> dict:
        records = self.client.get("/api/admin/publish-records", headers=self.admin_headers).json()
        return next(record for record in records if record["id"] == record_id)
