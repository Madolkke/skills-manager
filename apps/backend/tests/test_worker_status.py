from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import insert, update

from skillhub.models.entities import utc_now
from skillhub.models.schema import tables
from skillhub_worker.config import WorkerConfig
from skillhub_worker.main import run_once
from tests.api_command_test_case import ApiCommandTestCase
from tests.store_test_case import SqlStoreTestCase
from tests.test_worker_run_once import FakeLaminarClient, FakeOpencodeClient, FakeStore, _case_detail, _run_worker


class WorkerStatusStoreTest(SqlStoreTestCase):
    def test_worker_heartbeat_status_changes_from_online_to_offline_and_expires(self):
        self.store.record_worker_heartbeat(
            worker_id="worker-1",
            status="idle",
            metadata={
                "opencode_base_url": "http://opencode.test",
                "workdir_host": "/tmp/evals",
                "max_attempts": 2,
                "admin_key": "do-not-leak",
            },
        )

        overview = self.store.admin_worker_status_overview()

        self.assertEqual(overview["summary"]["total"], 1)
        self.assertEqual(overview["summary"]["online"], 1)
        self.assertEqual(overview["workers"][0]["status"], "idle")
        self.assertEqual(overview["workers"][0]["metadata"]["workdir_host"], "/tmp/evals")
        self.assertNotIn("admin_key", overview["workers"][0]["metadata"])

        with self.engine.begin() as connection:
            connection.execute(
                update(tables.worker_heartbeats)
                .where(tables.worker_heartbeats.c.worker_id == "worker-1")
                .values(last_seen_at=utc_now() - timedelta(seconds=45))
            )

        offline = self.store.admin_worker_status_overview()

        self.assertEqual(offline["summary"]["offline"], 1)
        self.assertEqual(offline["workers"][0]["status"], "offline")
        self.assertFalse(offline["workers"][0]["online"])

        with self.engine.begin() as connection:
            connection.execute(
                update(tables.worker_heartbeats)
                .where(tables.worker_heartbeats.c.worker_id == "worker-1")
                .values(last_seen_at=utc_now() - timedelta(hours=25))
            )

        expired = self.store.admin_worker_status_overview()

        self.assertEqual(expired["summary"]["total"], 0)
        self.assertEqual(expired["workers"], [])

    def test_worker_overview_summarizes_jobs_without_payload_content(self):
        skill = self.create_skill()
        case = self.store.create_eval_case(
            skill_id=skill.skill_id,
            title="Token logging",
            input_text="console.log(token)",
            expected_output="Flag token logging.",
            actor="tester",
        )
        self.store.enqueue_eval_case_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            case_version_id=case.eval_case_version_id,
            actor="tester",
            environment_tags=[],
            run_context={},
        )
        claimed = self.store.claim_next_eval_case_run_job(worker_id="worker-eval")
        with self.engine.begin() as connection:
            connection.execute(
                insert(tables.jobs).values(
                    id="job_builder_secret",
                    type="skill_builder_message",
                    status="queued",
                    payload={"session_id": "builder_1", "message_content": "do not leak prompt"},
                    attempts=0,
                    created_at=utc_now(),
                    created_by="tester",
                )
            )
        self.store.record_worker_heartbeat(
            worker_id="worker-eval",
            status="running",
            current_job_id=claimed["job"]["id"],
            current_job_type=claimed["job"]["type"],
            current_run_id=claimed["eval_case_run"]["id"],
        )
        with self.engine.begin() as connection:
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == claimed["job"]["id"])
                .values(last_heartbeat_at=utc_now() - timedelta(seconds=5))
            )

        with patch.dict(os.environ, {"WORKER_JOB_STALE_AFTER_SECONDS": "1"}):
            overview = self.store.admin_worker_status_overview()
        payload = json.dumps(overview, default=str)
        worker = overview["workers"][0]

        self.assertEqual(overview["summary"]["queued_eval_jobs"], 0)
        self.assertEqual(overview["summary"]["queued_builder_jobs"], 1)
        self.assertEqual(overview["summary"]["running_jobs"], 1)
        self.assertEqual(worker["status"], "running")
        self.assertEqual(worker["current_job"]["skill_id"], skill.skill_id)
        self.assertEqual(worker["current_job"]["skill_version_id"], skill.skill_version_id)
        self.assertTrue(worker["stalled"])
        self.assertGreaterEqual(worker["lease_age_seconds"], 5)
        self.assertIn("重启 Worker", worker["recovery_hint"])
        self.assertNotIn("do not leak prompt", payload)
        self.assertNotIn("message_content", payload)


class WorkerStatusApiTest(ApiCommandTestCase):
    def test_admin_workers_requires_admin_key_and_omits_job_payload(self):
        with self.engine.begin() as connection:
            connection.execute(
                insert(tables.jobs).values(
                    id="job_builder_api_secret",
                    type="skill_builder_message",
                    status="running",
                    payload={"session_id": "builder_api", "content": "secret builder message"},
                    attempts=1,
                    locked_by="worker-api",
                    started_at=utc_now(),
                    last_heartbeat_at=utc_now(),
                    created_at=utc_now(),
                    created_by="tester",
                )
            )
        self.store.record_worker_heartbeat(
            worker_id="worker-api",
            status="running",
            current_job_id="job_builder_api_secret",
            current_job_type="skill_builder_message",
            current_session_id="builder_api",
        )

        denied = self.client.get("/api/admin/workers")
        allowed = self.client.get("/api/admin/workers", headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        payload = json.dumps(allowed.json(), ensure_ascii=False)

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["workers"][0]["worker_id"], "worker-api")
        self.assertNotIn("secret builder message", payload)
        self.assertNotIn("content", payload)


def test_run_once_records_idle_when_no_jobs(tmp_path: Path):
    store = FakeStore(None)
    did_work = _run_worker(tmp_path, store=store, client=FakeOpencodeClient(), laminar=FakeLaminarClient())

    assert did_work is False
    assert [item["status"] for item in store.heartbeats] == ["idle"]


def test_run_once_records_eval_running_and_idle(tmp_path: Path):
    store = FakeStore(_case_detail())
    did_work = _run_worker(tmp_path, store=store, client=FakeOpencodeClient(), laminar=FakeLaminarClient())

    assert did_work is True
    assert [item["status"] for item in store.heartbeats] == ["idle", "running", "idle"]
    assert store.heartbeats[1]["current_run_id"] == "evalcase_1"
    assert store.heartbeats[1]["current_job_type"] == "eval_case_run"


def test_run_once_records_builder_running_and_idle(tmp_path: Path):
    store = FakeStore(None)
    store.builder_detail = {
        "session": {
            "id": "builder_1",
            "opencode_session_id": None,
            "workspace_files": [{"path": "SKILL.md", "content_text": "---\nname: writer\ndescription: Write docs.\n---\nBody"}],
        },
        "message": {"id": "buildermsg_1", "content": "请继续完善 SKILL.md", "intent": "chat"},
        "job": {"id": "job_builder_1", "type": "skill_builder_message", "payload": {"provider_id": "deepseek", "model_id": "deepseek-v4"}},
    }

    did_work = run_once(store, FakeOpencodeClient(), FakeLaminarClient(), config=_worker_config(tmp_path))

    assert did_work is True
    assert [item["status"] for item in store.heartbeats] == ["idle", "running", "idle"]
    assert store.heartbeats[1]["current_session_id"] == "builder_1"
    assert store.heartbeats[1]["current_job_type"] == "skill_builder_message"


def _worker_config(tmp_path: Path) -> WorkerConfig:
    return WorkerConfig(
        opencode_base_url="http://opencode.test",
        laminar_base_url="http://laminar.test",
        laminar_http_port=8000,
        laminar_project_api_key="key",
        workdir_host=tmp_path,
        workdir_container="/workspace/eval-runs",
        poll_interval_seconds=0.1,
        timeout_seconds=30,
        max_attempts=1,
        worker_id="test-worker",
    )
