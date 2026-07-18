import base64
import json
from datetime import timedelta
from io import BytesIO
from zipfile import ZipFile

import httpx
from sqlalchemy import insert, select, update

from skillhub.models.entities import utc_now
from skillhub.models.schema import tables
from skillhub.services import opencode as opencode_service
from tests.api_command_test_case import ApiCommandTestCase


class ApiSkillManagementTest(ApiCommandTestCase):
    def test_skill_builder_session_draft_and_create_skill_flow(self):
        session_response = self.client.post(
            "/api/skill-builder/sessions",
            headers={"X-SkillHub-Actor": "builder-user"},
            json={"title": "PR reviewer"},
        )
        self.assertEqual(session_response.status_code, 200)
        session_id = session_response.json()["id"]

        message_response = self.client.post(
            f"/api/skill-builder/sessions/{session_id}/messages",
            headers={"X-SkillHub-Actor": "builder-user"},
            json={
                "content": "帮我创建一个 PR 安全评审 Skill。",
                "intent": "chat",
                "provider_id": "deepseek",
                "model_id": "deepseek-v4",
            },
        )
        self.assertEqual(message_response.status_code, 200)
        self.assertEqual(message_response.json()["status"], "running")
        self.assertEqual(message_response.json()["messages"][0]["role"], "user")
        self.assertEqual(message_response.json()["run_progress"]["stage"], "queued")

        other_actor = self.client.get(f"/api/skill-builder/sessions/{session_id}", headers={"X-SkillHub-Actor": "other-user"})
        self.assertEqual(other_actor.status_code, 404)

        job_id = message_response.json()["messages"][0]["job_id"]
        now = utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job_id)
                .values(status="running", started_at=now, last_heartbeat_at=now, locked_by="test-worker")
            )
        self.store.update_skill_builder_job_progress(session_id=session_id, job_id=job_id, stage="sending_message")
        running_detail = self.client.get(f"/api/skill-builder/sessions/{session_id}", headers={"X-SkillHub-Actor": "builder-user"})
        self.assertEqual(running_detail.json()["run_progress"]["stage"], "sending_message")

        self.store.complete_skill_builder_job(
            session_id=session_id,
            job_id=job_id,
            assistant_content="已理解需求。",
            intent="chat",
            draft_files=[
                {
                    "path": "SKILL.md",
                    "content_text": (
                        "---\n"
                        "name: builder-pr-reviewer\n"
                        "description: Review pull requests for security and data access regressions.\n"
                        "---\n"
                        "\n"
                        "# PR Security Review\n"
                        "Flag missing authorization checks first.\n"
                    ),
                }
            ],
            opencode_session_id="session_1",
            workdir="/workspace/eval-runs/builder/workdir",
            metadata={},
        )

        workspace_response = self.client.patch(
            f"/api/skill-builder/sessions/{session_id}/workspace",
            headers={"X-SkillHub-Actor": "builder-user"},
            json={"files": [{"path": "notes/raw.md", "content_text": "用户手动补充的上下文。"}]},
        )
        create_response = self.client.post(
            f"/api/skill-builder/sessions/{session_id}/create-skill",
            headers={"X-SkillHub-Actor": "builder-user"},
            json={
                "version": "0.1.0",
                "tags": [],
                "files": [
                    {
                        "path": "SKILL.md",
                        "content_text": (
                            "---\n"
                            "name: builder-mapped-reviewer\n"
                            "description: Review pull requests for security and data access regressions.\n"
                            "---\n"
                            "\n"
                            "# PR Security Review\n"
                            "Flag missing authorization checks first.\n"
                        ),
                    },
                    {"path": "references/raw.md", "content_text": "用户手动补充的上下文。"},
                ],
            },
        )
        detail = self.client.get(f"/api/skill-builder/sessions/{session_id}", headers={"X-SkillHub-Actor": "builder-user"}).json()

        self.assertEqual(workspace_response.status_code, 200)
        self.assertEqual(workspace_response.json()["workspace_files"], [{"path": "notes/raw.md", "content_text": "用户手动补充的上下文。"}])
        self.assertEqual(workspace_response.json()["draft_files"], workspace_response.json()["workspace_files"])
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["slug"], "builder-mapped-reviewer")
        self.assertEqual(detail["status"], "created")
        self.assertEqual(detail["created_skill_id"], create_response.json()["skill_id"])

    def test_skill_builder_rejects_second_message_while_running(self):
        session = self.client.post("/api/skill-builder/sessions", json={}).json()
        first = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            json={"content": "创建 Skill", "intent": "chat"},
        )
        second = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            json={"content": "再发一条", "intent": "chat"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_skill_builder_create_session_replaces_existing_session(self):
        headers = {"X-SkillHub-Actor": "single-builder-user"}
        first = self.client.post("/api/skill-builder/sessions", headers=headers, json={"title": "旧会话"}).json()
        workspace = self.client.patch(
            f"/api/skill-builder/sessions/{first['id']}/workspace",
            headers=headers,
            json={"files": [{"path": "SKILL.md", "content_text": "---\nname: old\ndescription: Old.\n---\n"}]},
        )

        second = self.client.post("/api/skill-builder/sessions", headers=headers, json={"title": "新会话"})
        sessions = self.client.get("/api/skill-builder/sessions", headers=headers).json()
        old_detail = self.client.get(f"/api/skill-builder/sessions/{first['id']}", headers=headers)

        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(second.json()["id"], first["id"])
        self.assertEqual([item["id"] for item in sessions], [second.json()["id"]])
        self.assertEqual(old_detail.status_code, 404)

    def test_skill_builder_create_session_rejects_running_existing_session(self):
        headers = {"X-SkillHub-Actor": "running-builder-user"}
        session = self.client.post("/api/skill-builder/sessions", headers=headers, json={}).json()
        running = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            headers=headers,
            json={"content": "创建 Skill", "intent": "chat"},
        )

        replaced = self.client.post("/api/skill-builder/sessions", headers=headers, json={"title": "覆盖"})
        sessions = self.client.get("/api/skill-builder/sessions", headers=headers).json()

        self.assertEqual(running.status_code, 200)
        self.assertEqual(replaced.status_code, 409)
        self.assertEqual([item["id"] for item in sessions], [session["id"]])

    def test_skill_builder_recovers_stale_running_session(self):
        headers = {"X-SkillHub-Actor": "stale-builder-user"}
        session = self.client.post("/api/skill-builder/sessions", headers=headers, json={}).json()
        running = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            headers=headers,
            json={"content": "创建 Skill", "intent": "chat"},
        )
        job_id = running.json()["messages"][0]["job_id"]
        stale_at = utc_now() - timedelta(minutes=20)
        with self.engine.begin() as connection:
            connection.execute(
                update(tables.jobs)
                .where(tables.jobs.c.id == job_id)
                .values(created_at=stale_at, started_at=stale_at, last_heartbeat_at=stale_at)
            )
            connection.execute(
                update(tables.skill_builder_sessions)
                .where(tables.skill_builder_sessions.c.id == session["id"])
                .values(updated_at=stale_at)
            )

        detail = self.client.get(f"/api/skill-builder/sessions/{session['id']}", headers=headers)
        continued = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            headers=headers,
            json={"content": "继续创建", "intent": "chat"},
        )
        with self.engine.begin() as connection:
            old_job = connection.execute(select(tables.jobs).where(tables.jobs.c.id == job_id)).mappings().one()

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "failed")
        self.assertIn("长时间没有进展", detail.json()["last_error"])
        self.assertEqual(old_job["status"], "failed")
        self.assertEqual(continued.status_code, 200)
        self.assertEqual(continued.json()["status"], "running")

    def test_skill_builder_create_session_can_replace_running_session(self):
        headers = {"X-SkillHub-Actor": "replace-running-builder-user"}
        session = self.client.post("/api/skill-builder/sessions", headers=headers, json={}).json()
        running = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            headers=headers,
            json={"content": "创建 Skill", "intent": "chat"},
        )
        job_id = running.json()["messages"][0]["job_id"]

        replaced = self.client.post(
            "/api/skill-builder/sessions",
            headers=headers,
            json={"title": "新会话", "replace_running": True},
        )
        sessions = self.client.get("/api/skill-builder/sessions", headers=headers).json()
        old_detail = self.client.get(f"/api/skill-builder/sessions/{session['id']}", headers=headers)
        with self.engine.begin() as connection:
            old_job = connection.execute(select(tables.jobs).where(tables.jobs.c.id == job_id)).mappings().one()

        self.assertEqual(replaced.status_code, 200)
        self.assertNotEqual(replaced.json()["id"], session["id"])
        self.assertEqual([item["id"] for item in sessions], [replaced.json()["id"]])
        self.assertEqual(old_detail.status_code, 404)
        self.assertEqual(old_job["status"], "canceled")

    def test_skill_builder_cancel_running_session_allows_new_message_and_ignores_late_worker_result(self):
        headers = {"X-SkillHub-Actor": "cancel-builder-user"}
        session = self.client.post("/api/skill-builder/sessions", headers=headers, json={}).json()
        running = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            headers=headers,
            json={"content": "创建 Skill", "intent": "chat"},
        )
        job_id = running.json()["messages"][0]["job_id"]

        canceled = self.client.post(f"/api/skill-builder/sessions/{session['id']}/cancel", headers=headers)
        self.store.complete_skill_builder_job(
            session_id=session["id"],
            job_id=job_id,
            assistant_content="晚到的结果不应写入。",
            intent="chat",
            draft_files=[{"path": "SKILL.md", "content_text": "---\nname: late\ndescription: Late.\n---\n"}],
            opencode_session_id="late_session",
            workdir="/workspace/eval-runs/builder/late",
            metadata={},
        )
        continued = self.client.post(
            f"/api/skill-builder/sessions/{session['id']}/messages",
            headers=headers,
            json={"content": "重新开始", "intent": "chat"},
        )
        detail = self.client.get(f"/api/skill-builder/sessions/{session['id']}", headers=headers).json()
        with self.engine.begin() as connection:
            old_job = connection.execute(select(tables.jobs).where(tables.jobs.c.id == job_id)).mappings().one()

        self.assertEqual(canceled.status_code, 200)
        self.assertEqual(canceled.json()["status"], "failed")
        self.assertEqual(old_job["status"], "canceled")
        self.assertEqual(continued.status_code, 200)
        self.assertFalse(any(message["content"] == "晚到的结果不应写入。" for message in detail["messages"]))

    def test_skill_builder_create_session_cancels_old_queued_builder_jobs(self):
        headers = {"X-SkillHub-Actor": "queued-builder-user"}
        old = self.client.post("/api/skill-builder/sessions", headers=headers, json={}).json()
        now = utc_now()
        with self.engine.begin() as connection:
            connection.execute(
                insert(tables.jobs).values(
                    id="job_builder_old",
                    type="skill_builder_message",
                    status="queued",
                    payload={"runner": "opencode_skill_builder", "session_id": old["id"], "message_id": "buildermsg_old"},
                    result_ref=None,
                    attempts=0,
                    locked_by=None,
                    last_heartbeat_at=None,
                    created_at=now,
                    started_at=None,
                    finished_at=None,
                    created_by="queued-builder-user",
                    error=None,
                )
            )

        created = self.client.post("/api/skill-builder/sessions", headers=headers, json={})
        with self.engine.begin() as connection:
            job = connection.execute(select(tables.jobs).where(tables.jobs.c.id == "job_builder_old")).mappings().one()

        self.assertEqual(created.status_code, 200)
        self.assertEqual(job["status"], "canceled")
        self.assertEqual(job["error"], "Skill Builder session was replaced by a new session.")

    def test_opencode_provider_proxy_returns_sanitized_catalog(self):
        def fake_get(*_args, **_kwargs):
            return httpx.Response(
                200,
                json={
                    "default": {"deepseek": "deepseek-v4-pro"},
                    "providers": [
                        {
                            "id": "deepseek",
                            "name": "DeepSeek",
                            "source": "env",
                            "env": ["DEEPSEEK_API_KEY"],
                            "key": "secret",
                            "models": {
                                "deepseek-v4-pro": {
                                    "id": "deepseek-v4-pro",
                                    "name": "DeepSeek V4 Pro",
                                    "api": {"url": "https://api.deepseek.com"},
                                    "headers": {"authorization": "secret"},
                                    "status": "active",
                                }
                            },
                        }
                    ],
                },
                request=httpx.Request("GET", "http://opencode.test/config/providers"),
            )

        original_get = opencode_service.httpx.get
        opencode_service.httpx.get = fake_get
        try:
            response = self.client.get("/api/opencode/providers")
        finally:
            opencode_service.httpx.get = original_get

        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["providers"][0]["default_model_id"], "deepseek-v4-pro")
        self.assertEqual(payload["providers"][0]["models"][0]["id"], "deepseek-v4-pro")
        self.assertNotIn("secret", str(payload))
        self.assertNotIn("DEEPSEEK_API_KEY", str(payload))
        self.assertNotIn("api.deepseek.com", str(payload))

    def test_read_flow_returns_hub_skill_eval_set_and_version_details(self):
        skill = self.create_skill("read-flow")
        case = self.create_eval_case(skill["skill_id"])

        hub = self.client.get("/api/skills").json()
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        eval_set = self.client.get(f"/api/eval-sets/{case['eval_set_id']}").json()

        self.assertEqual(hub[0]["summary"]["current_version"]["id"], skill["skill_version_id"])
        self.assertEqual(hub[0]["summary"]["current_version"]["version"], "0.0.1")
        self.assertEqual(detail["summary"]["current_version"]["id"], skill["skill_version_id"])
        self.assertEqual(detail["summary"]["current_version"]["version"], "0.0.1")
        self.assertEqual(detail["versions"][0]["id"], skill["skill_version_id"])
        self.assertEqual(eval_set["cases"][0]["case_version"]["id"], case["eval_case_version_id"])

    def test_create_skill_accepts_initial_semver(self):
        response = self.client.post(
            "/api/skills",
            json={**self.skill_payload("initial-semver-api"), "version": "0.2.0"},
        )
        detail = self.client.get(f"/api/skills/{response.json()['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "0.2.0")
        self.assertEqual(detail["summary"]["current_version"]["version"], "0.2.0")

    def test_skill_version_create_accepts_semver(self):
        skill = self.create_skill("semver-api")

        response = self.client.post(
            "/api/skill-versions",
            json={
                "skill_id": skill["skill_id"],
                "content_ref": {"kind": "skill_bundle", "locator": "memory:semver-v2", "digest": "digest-semver-v2"},
                "change_summary": "Major version.",
                "version": "2.0.0",
                "make_current": True,
            },
        )
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], "2.0.0")
        self.assertEqual(detail["summary"]["current_version"]["version"], "2.0.0")

    def test_skill_version_create_rejects_invalid_semver(self):
        skill = self.create_skill("invalid-semver-api")

        response = self.client.post(
            "/api/skill-versions",
            json={
                "skill_id": skill["skill_id"],
                "content_ref": {"kind": "skill_bundle", "locator": "memory:bad-semver", "digest": "digest-bad-semver"},
                "change_summary": "Bad version.",
                "version": "v2",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "version")

    def test_skill_versions_can_be_named_and_renamed(self):
        skill = self.create_skill("named-versions")

        skill_version = self.client.patch(
            f"/api/skill-versions/{skill['skill_version_id']}",
            json={"display_name": "stable baseline"},
        )
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()

        self.assertEqual(skill_version.status_code, 200)
        self.assertEqual(detail["summary"]["current_version"]["display_name"], "stable baseline")

    def test_skill_create_ignores_initial_version_display_name(self):
        payload = self.skill_payload("initial-name-ignored")
        payload["display_name"] = "should not be stored"

        response = self.client.post("/api/skills", json=payload)
        detail = self.client.get(f"/api/skills/{response.json()['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(detail["summary"]["current_version"]["display_name"])

    def test_skill_import_ignores_initial_version_display_name(self):
        response = self.client.post(
            "/api/skill-imports",
            json={
                "owner_ref": "skillhub-lab",
                "source": self.bundle_source("import-name-ignored"),
                "display_name": "should not be stored",
            },
        )
        detail = self.client.get(f"/api/skills/{response.json()['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(detail["summary"]["current_version"]["display_name"])

    def test_eval_cases_update_current_eval_set(self):
        skill = self.create_skill("evalset-working-version")

        first_case = self.create_eval_case(skill["skill_id"])
        second_case = self.create_eval_case(skill["skill_id"])
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        eval_set_detail = self.client.get(f"/api/eval-sets/{second_case['eval_set_id']}").json()

        self.assertEqual(first_case["eval_set_id"], second_case["eval_set_id"])
        self.assertEqual(detail["summary"]["primary_eval_set"]["id"], second_case["eval_set_id"])
        self.assertEqual([item["case_version"]["id"] for item in eval_set_detail["cases"]], [first_case["eval_case_version_id"], second_case["eval_case_version_id"]])

    def test_skill_supports_multiple_eval_sets_and_existing_case_membership(self):
        skill = self.create_skill("multi-eval-set")
        first_case = self.create_eval_case(skill["skill_id"])
        secondary = self.client.post(
            f"/api/skills/{skill['skill_id']}/eval-sets",
            json={"name": "Extended", "description": "扩展回归场景"},
        )

        library = self.client.get(
            f"/api/skills/{skill['skill_id']}/eval-cases",
            params={"exclude_eval_set_id": secondary.json()["id"]},
        )
        added = self.client.post(
            f"/api/eval-sets/{secondary.json()['id']}/cases",
            json={"case_id": first_case["eval_case_id"]},
        )
        secondary_detail = self.client.get(f"/api/eval-sets/{secondary.json()['id']}").json()

        self.assertEqual(secondary.status_code, 200)
        self.assertEqual(library.status_code, 200)
        self.assertEqual([item["case"]["id"] for item in library.json()], [first_case["eval_case_id"]])
        self.assertEqual(added.status_code, 200)
        self.assertEqual(secondary_detail["cases"][0]["case"]["id"], first_case["eval_case_id"])
        self.assertEqual(secondary_detail["cases"][0]["case_version"]["id"], first_case["eval_case_version_id"])

    def test_editing_shared_eval_case_updates_all_eval_sets_to_latest_version(self):
        skill = self.create_skill("shared-case-version")
        case = self.create_eval_case(skill["skill_id"])
        secondary = self.client.post(f"/api/skills/{skill['skill_id']}/eval-sets", json={"name": "Secondary"}).json()
        self.client.post(f"/api/eval-sets/{secondary['id']}/cases", json={"case_id": case["eval_case_id"]})

        updated = self.client.patch(
            f"/api/eval-cases/{case['eval_case_id']}",
            json={
                "case_id": case["eval_case_id"],
                "eval_set_id": case["eval_set_id"],
                "title": "Updated shared case",
                "steps": [
                    {
                        "title": "更新后的步骤",
                        "input": "Project.findMany({ where: {} })",
                        "assertions": [
                            {
                                "assertion_template_id": "agent_output_contains",
                                "assertion_params": {"text": "ownerId"},
                            }
                        ],
                    }
                ],
                "make_current": True,
            },
        )
        primary_detail = self.client.get(f"/api/eval-sets/{case['eval_set_id']}").json()
        secondary_detail = self.client.get(f"/api/eval-sets/{secondary['id']}").json()

        self.assertEqual(updated.status_code, 200)
        self.assertNotEqual(updated.json()["eval_case_version_id"], case["eval_case_version_id"])
        self.assertEqual(primary_detail["cases"][0]["case_version"]["id"], updated.json()["eval_case_version_id"])
        self.assertEqual(secondary_detail["cases"][0]["case_version"]["id"], updated.json()["eval_case_version_id"])
        self.assertEqual(primary_detail["cases"][0]["case"]["title"], "Updated shared case")

    def test_eval_case_update_ignores_legacy_model_runner_config(self):
        skill = self.create_skill("case-title-rollback")
        case = self.create_eval_case(skill["skill_id"])

        response = self.client.patch(
            f"/api/eval-cases/{case['eval_case_id']}",
            json={
                "case_id": case["eval_case_id"],
                "eval_set_id": case["eval_set_id"],
                "title": "Half saved title",
                "steps": [
                    {
                        "title": "忽略旧模型配置",
                        "input": "输出 helloworld",
                        "assertions": [
                            {
                                "assertion_template_id": "agent_output_contains",
                                "assertion_params": {"text": "helloworld"},
                            }
                        ],
                    }
                ],
                "runner_config": {"model_provider_id": "deepseek"},
                "make_current": True,
            },
        )
        detail = self.client.get(f"/api/eval-sets/{case['eval_set_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(detail["cases"][0]["case"]["title"], "Half saved title")
        self.assertEqual(detail["cases"][0]["case_version"]["id"], response.json()["eval_case_version_id"])
        self.assertNotIn("model_provider_id", detail["cases"][0]["case_version"]["runner_config"])

    def test_eval_set_membership_rejects_cross_skill_case_and_reorders(self):
        first = self.create_skill("membership-first")
        second = self.create_skill("membership-second")
        first_case = self.create_eval_case(first["skill_id"])
        second_case = self.create_eval_case(second["skill_id"])
        extra_case = self.create_eval_case(first["skill_id"])
        secondary = self.client.post(f"/api/skills/{first['skill_id']}/eval-sets", json={"name": "Ordering"}).json()
        self.client.post(f"/api/eval-sets/{secondary['id']}/cases", json={"case_id": first_case["eval_case_id"]})
        self.client.post(f"/api/eval-sets/{secondary['id']}/cases", json={"case_id": extra_case["eval_case_id"]})

        cross_skill = self.client.post(
            f"/api/eval-sets/{secondary['id']}/cases",
            json={"case_id": second_case["eval_case_id"]},
        )
        reordered = self.client.patch(
            f"/api/eval-sets/{secondary['id']}/cases/order",
            json={"case_ids": [extra_case["eval_case_id"], first_case["eval_case_id"]]},
        )

        self.assertEqual(cross_skill.status_code, 400)
        self.assertEqual(reordered.status_code, 200)
        self.assertEqual([item["case"]["id"] for item in reordered.json()["cases"]], [extra_case["eval_case_id"], first_case["eval_case_id"]])

    def test_eval_case_workspace_zip_can_be_saved_and_downloaded(self):
        skill = self.create_skill("case-attachment")
        zip_bytes = b"PK\x03\x04case archive"

        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill["skill_id"],
                "eval_set_id": skill["eval_set_id"],
                "title": "Archive context",
                "steps": [
                    {
                        "title": "读取工作目录",
                        "input": "Review the attached archive.",
                        "assertions": [
                            {
                                "assertion_template_id": "agent_output_contains",
                                "assertion_params": {"text": "Flag missing test coverage."},
                            }
                        ],
                    }
                ],
                "workspace_name": "context.zip",
                "workspace_base64": base64.b64encode(zip_bytes).decode("ascii"),
            },
        )
        eval_set = self.client.get(f"/api/eval-sets/{response.json()['eval_set_id']}").json()
        workspace = eval_set["cases"][0]["case_version"]["workspace_artifact"]
        downloaded = self.client.get(f"/api/artifacts/{workspace['id']}/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(workspace["media_type"], "application/zip")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, zip_bytes)

    def test_eval_case_runner_config_ignores_legacy_model_fields(self):
        skill = self.create_skill("case-runner-config")

        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill["skill_id"],
                "eval_set_id": skill["eval_set_id"],
                "title": "Runner config",
                "steps": [
                    {
                        "title": "读取工作目录",
                        "input": "Read workspace files.",
                        "assertions": [
                            {
                                "assertion_template_id": "agent_output_contains",
                                "assertion_params": {"text": "Find the answer."},
                            }
                        ],
                    }
                ],
                "runner_config": {"model_provider_id": "deepseek", "model_id": "deepseek-v4-pro"},
            },
        )
        eval_set = self.client.get(f"/api/eval-sets/{response.json()['eval_set_id']}").json()
        case_version = eval_set["cases"][0]["case_version"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(case_version["steps"][0]["assertions"][0]["assertion_template_id"], "agent_output_contains")
        self.assertNotIn("model_provider_id", case_version["runner_config"])
        self.assertNotIn("model_id", case_version["runner_config"])

    def test_eval_case_step_supports_multiple_assertions(self):
        skill = self.create_skill("case-multi-assertions")

        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill["skill_id"],
                "eval_set_id": skill["eval_set_id"],
                "title": "Multi assertion case",
                "steps": [
                    {
                        "title": "生成并检查输出",
                        "input": "请输出 helloworld，并创建 done.txt",
                        "assertions": [
                            {
                                "assertion_template_id": "agent_output_contains",
                                "assertion_params": {"text": "helloworld"},
                            },
                            {
                                "assertion_template_id": "file_created",
                                "assertion_params": {"directory": ".", "filename": "done.txt"},
                            },
                        ],
                    }
                ],
            },
        )
        eval_set = self.client.get(f"/api/eval-sets/{response.json()['eval_set_id']}").json()
        step = eval_set["cases"][0]["case_version"]["steps"][0]

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("assertion_template_id", step)
        self.assertEqual([item["id"] for item in step["assertions"]], ["assertion-1", "assertion-2"])
        self.assertEqual([item["assertion_template_id"] for item in step["assertions"]], ["agent_output_contains", "file_created"])

    def test_eval_assertion_templates_endpoint_returns_builtin_templates(self):
        response = self.client.get("/api/eval-assertion-templates")

        self.assertEqual(response.status_code, 200)
        self.assertIn("agent_output_contains", [item["id"] for item in response.json()])

    def test_eval_case_change_updates_same_eval_set_after_run_history_exists(self):
        skill = self.create_skill("evalset-locked-version")
        first_case = self.create_eval_case(skill["skill_id"])
        self.record_run(skill["skill_version_id"], first_case["eval_set_id"], first_case["eval_case_version_id"], True)

        second_case = self.create_eval_case(skill["skill_id"])
        eval_set_detail = self.client.get(f"/api/eval-sets/{second_case['eval_set_id']}").json()

        self.assertEqual(second_case["eval_set_id"], first_case["eval_set_id"])
        self.assertEqual(len(eval_set_detail["cases"]), 2)

    def test_skill_capabilities_do_not_expose_variant_promote(self):
        skill = self.create_skill("capability-contract")

        response = self.client.get(f"/api/skills/{skill['skill_id']}/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("variant.promote", response.json()["permissions"])
        self.assertTrue(response.json()["permissions"]["verification.accept"])
        self.assertIn("admin", response.json()["effective_roles"])

    def test_all_actors_can_read_skill_but_unassigned_actor_cannot_write(self):
        skill = self.create_skill("public-read-permission")

        listed = self.client.get("/api/skills", headers={"X-SkillHub-Actor": "guest-user"})
        detail = self.client.get(f"/api/skills/{skill['skill_id']}", headers={"X-SkillHub-Actor": "guest-user"})
        update = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            headers={"X-SkillHub-Actor": "guest-user"},
            json={"slug": "public-read-permission-v2", "owner_ref": "skillhub-lab"},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(update.status_code, 403)

    def test_group_and_tag_roles_are_combined_for_effective_permissions(self):
        tag = self.create_tag_value("domain", "安全 组 🔐")
        skill = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator"},
            json={**self.skill_payload("group-tag-permission"), "tags": [tag]},
        ).json()
        self.client.post("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"name": "qa-team"})
        groups = self.client.get("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()
        group_id = groups[0]["id"]
        self.client.post(f"/api/admin/groups/{group_id}/members", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"subject_id": "qa-user"})
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "group", "subject_id": group_id, "resource_type": "skill_tag", "resource_id": self.tag_resource_id("domain", "安全 组 🔐"), "role": "evaluator"},
        )

        capabilities = self.client.get(f"/api/skills/{skill['skill_id']}/capabilities", headers={"X-SkillHub-Actor": "qa-user"}).json()

        self.assertIn(group_id, capabilities["groups"])
        self.assertIn("evaluator", capabilities["effective_roles"])
        self.assertTrue(capabilities["permissions"]["eval.run"])

    def test_skill_scoped_groups_can_be_managed_from_skill_settings(self):
        first = self.create_skill("skill-group-first")
        second = self.create_skill("skill-group-second")

        created = self.client.post(
            f"/api/skills/{first['skill_id']}/groups",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"name": "reviewers", "description": "Skill local reviewers"},
        )
        duplicate_other_skill = self.client.post(
            f"/api/skills/{second['skill_id']}/groups",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"name": "reviewers"},
        )
        group_id = created.json()["id"]
        member = self.client.post(
            f"/api/skills/{first['skill_id']}/groups/{group_id}/members",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_id": "qa-user"},
        )
        assigned = self.client.post(
            f"/api/skills/{first['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_type": "group", "subject_id": group_id, "role": "evaluator"},
        )
        first_capabilities = self.client.get(f"/api/skills/{first['skill_id']}/capabilities", headers={"X-SkillHub-Actor": "qa-user"}).json()
        second_capabilities = self.client.get(f"/api/skills/{second['skill_id']}/capabilities", headers={"X-SkillHub-Actor": "qa-user"}).json()

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["scope_type"], "skill")
        self.assertEqual(created.json()["scope_id"], first["skill_id"])
        self.assertEqual(duplicate_other_skill.status_code, 200)
        self.assertEqual(member.status_code, 200)
        self.assertEqual(assigned.status_code, 200)
        self.assertIn(group_id, first_capabilities["groups"])
        self.assertTrue(first_capabilities["permissions"]["eval.run"])
        self.assertFalse(second_capabilities["permissions"]["eval.run"])

    def test_skill_scoped_groups_cannot_be_assigned_cross_skill(self):
        first = self.create_skill("skill-group-scope-first")
        second = self.create_skill("skill-group-scope-second")
        group = self.client.post(
            f"/api/skills/{first['skill_id']}/groups",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"name": "local reviewers"},
        ).json()

        response = self.client.post(
            f"/api/skills/{second['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_type": "group", "subject_id": group["id"], "role": "evaluator"},
        )

        self.assertEqual(response.status_code, 403)

    def test_skill_tags_accept_long_arbitrary_value_and_update_response_includes_tags(self):
        skill = self.create_skill("arbitrary-tags")
        long_tag = "任意 Tag / 允许空格、符号和 emoji 🔐 " + ("x" * 80)
        tag = self.create_tag_value("free_form", long_tag)

        response = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"slug": "arbitrary-tags", "owner_ref": "skillhub-lab", "tags": [tag]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tags"][0]["group_id"], "free_form")
        self.assertEqual(response.json()["tags"][0]["value"], long_tag)

    def test_required_tag_group_is_enforced_on_skill_create_and_tag_update(self):
        required_tag = self.create_tag_value("domain", "api", display_name="API")
        group = self.client.get("/api/admin/tag-groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()[0]
        updated_group = self.client.patch(
            "/api/admin/tag-groups/domain",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"display_name": group["display_name"], "description": group["description"], "sort_order": group["sort_order"], "required": True},
        )

        missing_create = self.client.post("/api/skills", json=self.skill_payload("missing-required-tag"))
        created = self.client.post("/api/skills", json={**self.skill_payload("has-required-tag"), "tags": [required_tag]})
        missing_update = self.client.patch(
            f"/api/skills/{created.json()['skill_id']}",
            json={"slug": "has-required-tag", "owner_ref": "skillhub-lab", "tags": []},
        )
        identity_only = self.client.patch(
            f"/api/skills/{created.json()['skill_id']}",
            json={"slug": "has-required-tag", "owner_ref": "new-owner"},
        )

        self.assertEqual(updated_group.status_code, 200)
        self.assertTrue(updated_group.json()["required"])
        self.assertEqual(missing_create.status_code, 400)
        self.assertEqual(missing_create.json()["field_errors"][0]["field"], "tags")
        self.assertEqual(created.status_code, 200)
        self.assertEqual(missing_update.status_code, 400)
        self.assertEqual(missing_update.json()["field_errors"][0]["field"], "tags")
        self.assertEqual(identity_only.status_code, 200)
        self.assertEqual(identity_only.json()["owner_ref"], "new-owner")

    def test_empty_tag_group_cannot_be_marked_required(self):
        created = self.client.post(
            "/api/admin/tag-groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"id": "empty_required", "display_name": "空组", "description": "", "required": True},
        )
        self.client.post(
            "/api/admin/tag-groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"id": "empty_optional", "display_name": "空可选组", "description": ""},
        )
        updated = self.client.patch(
            "/api/admin/tag-groups/empty_optional",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"display_name": "空可选组", "description": "", "sort_order": 0, "required": True},
        )

        self.assertEqual(created.status_code, 400)
        self.assertIn("必选 Tag Group", created.json()["detail"])
        self.assertEqual(updated.status_code, 400)
        self.assertIn("必选 Tag Group", updated.json()["detail"])

    def test_required_tag_group_keeps_at_least_one_value(self):
        self.create_tag_value("domain", "api")
        group = self.client.get("/api/admin/tag-groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()[0]
        self.client.patch(
            "/api/admin/tag-groups/domain",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"display_name": group["display_name"], "description": group["description"], "sort_order": group["sort_order"], "required": True},
        )

        deleted = self.client.delete("/api/admin/tag-groups/domain/values/api", headers={"X-SkillHub-Admin-Key": "test-admin-key"})

        self.assertEqual(deleted.status_code, 400)
        self.assertIn("必选 Tag Group", deleted.json()["detail"])

    def test_protected_tag_changes_require_admin_role(self):
        tag = self.create_tag_value("risk", "protected tag")
        skill = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator"},
            json={**self.skill_payload("protected-tag-skill"), "tags": [tag]},
        ).json()
        self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "creator"},
            json={"subject_id": "maintainer-one", "role": "maintainer"},
        )
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "user", "subject_id": "qa", "resource_type": "skill_tag", "resource_id": self.tag_resource_id("risk", "protected tag"), "role": "evaluator"},
        )

        denied = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            headers={"X-SkillHub-Actor": "maintainer-one"},
            json={"slug": "protected-tag-skill", "owner_ref": "skillhub-lab", "tags": []},
        )
        allowed = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            headers={"X-SkillHub-Actor": "creator"},
            json={"slug": "protected-tag-skill", "owner_ref": "skillhub-lab", "tags": []},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["tags"], [])

    def test_creating_skill_with_protected_tag_requires_tag_admin_role(self):
        tag = self.create_tag_value("risk", "protected create")
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "user", "subject_id": "tag-admin", "resource_type": "skill_tag", "resource_id": self.tag_resource_id("risk", "protected create"), "role": "admin"},
        )

        denied = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "ordinary-user"},
            json={**self.skill_payload("ordinary-protected-create"), "tags": [tag]},
        )
        allowed = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "tag-admin"},
            json={**self.skill_payload("admin-protected-create"), "tags": [tag]},
        )

        self.assertEqual(denied.status_code, 400)
        self.assertEqual(allowed.status_code, 200)

    def test_same_tag_value_in_different_groups_does_not_share_permissions(self):
        self.create_tag_value("domain", "shared")
        self.create_tag_value("team", "shared")
        first = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator-one"},
            json={**self.skill_payload("tag-scope-domain"), "tags": [{"group_id": "domain", "value": "shared"}]},
        ).json()
        second = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator-two"},
            json={**self.skill_payload("tag-scope-team"), "tags": [{"group_id": "team", "value": "shared"}]},
        ).json()
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "user", "subject_id": "scoped-user", "resource_type": "skill_tag", "resource_id": self.tag_resource_id("domain", "shared"), "role": "evaluator"},
        )

        first_capabilities = self.client.get(f"/api/skills/{first['skill_id']}/capabilities", headers={"X-SkillHub-Actor": "scoped-user"}).json()
        second_capabilities = self.client.get(f"/api/skills/{second['skill_id']}/capabilities", headers={"X-SkillHub-Actor": "scoped-user"}).json()

        self.assertTrue(first_capabilities["permissions"]["eval.run"])
        self.assertFalse(second_capabilities["permissions"]["eval.run"])

    def test_admin_delete_group_removes_memberships_and_group_roles(self):
        skill = self.create_skill("delete-group-scope")
        self.client.post("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"name": "cleanup-team"})
        group_id = self.client.get("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()[0]["id"]
        self.client.post(f"/api/admin/groups/{group_id}/members", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"subject_id": "cleanup-user"})
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "group", "subject_id": group_id, "resource_type": "skill", "resource_id": skill["skill_id"], "role": "evaluator"},
        )

        deleted = self.client.delete(f"/api/admin/groups/{group_id}", headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        groups = self.client.get("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()
        roles = self.client.get("/api/admin/role-assignments", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()

        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(groups, [])
        self.assertFalse(any(role["subject_type"] == "group" and role["subject_id"] == group_id for role in roles))

    def test_admin_delete_tag_value_rejects_skill_and_role_references(self):
        self.create_tag_value("domain", "shared")
        self.create_tag_value("team", "shared")
        first = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator-one"},
            json={**self.skill_payload("delete-tag-value-domain"), "tags": [{"group_id": "domain", "value": "shared"}]},
        ).json()
        second = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator-two"},
            json={**self.skill_payload("delete-tag-value-team"), "tags": [{"group_id": "team", "value": "shared"}]},
        ).json()
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "user", "subject_id": "domain-user", "resource_type": "skill_tag", "resource_id": self.tag_resource_id("domain", "shared"), "role": "evaluator"},
        )
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "user", "subject_id": "team-user", "resource_type": "skill_tag", "resource_id": self.tag_resource_id("team", "shared"), "role": "evaluator"},
        )

        deleted = self.client.delete("/api/admin/tag-groups/domain/values/shared", headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        first_detail = self.client.get(f"/api/skills/{first['skill_id']}").json()
        second_detail = self.client.get(f"/api/skills/{second['skill_id']}").json()
        roles = self.client.get("/api/admin/role-assignments", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()

        self.assertEqual(deleted.status_code, 400)
        self.assertIn("Tag 值仍被引用", deleted.json()["detail"])
        self.assertEqual(first_detail["skill"]["tags"][0]["group_id"], "domain")
        self.assertEqual(second_detail["skill"]["tags"][0]["group_id"], "team")
        self.assertTrue(any(role["resource_id"] == self.tag_resource_id("domain", "shared") for role in roles))
        self.assertTrue(any(role["resource_id"] == self.tag_resource_id("team", "shared") for role in roles))

    def test_admin_delete_tag_group_rejects_skill_and_role_references(self):
        tag = self.create_tag_value("cleanup", "one")
        self.create_tag_value("cleanup", "two")
        skill = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "creator"},
            json={**self.skill_payload("delete-tag-group"), "tags": [tag]},
        ).json()
        self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"subject_type": "user", "subject_id": "cleanup-user", "resource_type": "skill_tag", "resource_id": self.tag_resource_id("cleanup", "one"), "role": "evaluator"},
        )

        deleted = self.client.delete("/api/admin/tag-groups/cleanup", headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        tag_groups = self.client.get("/api/admin/tag-groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()
        roles = self.client.get("/api/admin/role-assignments", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()

        self.assertEqual(deleted.status_code, 400)
        self.assertIn("Tag Group 仍被引用", deleted.json()["detail"])
        self.assertEqual(detail["skill"]["tags"][0]["group_id"], "cleanup")
        self.assertEqual([group["id"] for group in tag_groups], ["cleanup"])
        self.assertTrue(any(role["resource_type"] == "skill_tag" and role["resource_id"].startswith("cleanup:") for role in roles))

    def test_admin_api_requires_configured_key(self):
        denied = self.client.get("/api/admin/skills", headers={"X-SkillHub-Admin-Key": "wrong"})
        allowed = self.client.get("/api/admin/skills", headers={"X-SkillHub-Admin-Key": "test-admin-key"})

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)

    def test_admin_duplicate_group_returns_domain_error(self):
        first = self.client.post("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"name": "qa-team"})
        duplicate = self.client.post("/api/admin/groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"name": "qa-team"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("Group already exists", duplicate.json()["detail"])

    def test_admin_opencode_agent_crud_soft_delete_and_enabled_catalog(self):
        payload = {
            "id": "strict-reviewer",
            "name": "严格评审",
            "description": "严格检查输出。",
            "prompt": "你是严格的评审 Agent。",
            "enabled": True,
            "permission": {"read": True, "grep": True},
            "provider_id": "deepseek",
            "model_id": "deepseek-v4",
            "temperature": 0.2,
            "steps": ["检查输入", "给出结论"],
        }
        created = self.client.post("/api/admin/opencode-agents", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json=payload)
        duplicate = self.client.post("/api/admin/opencode-agents", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json=payload)
        public_catalog = self.client.get("/api/opencode/agents")
        disabled = self.client.patch(
            "/api/admin/opencode-agents/strict-reviewer",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={**payload, "name": "严格评审 v2", "enabled": False},
        )
        public_after_disable = self.client.get("/api/opencode/agents")
        deleted = self.client.delete("/api/admin/opencode-agents/strict-reviewer", headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        admin_after_delete = self.client.get("/api/admin/opencode-agents", headers={"X-SkillHub-Admin-Key": "test-admin-key"})

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["id"], "strict-reviewer")
        self.assertEqual(created.json()["permission"]["read"], True)
        self.assertEqual(created.json()["permission"]["bash"], False)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("already exists", duplicate.json()["detail"])
        self.assertEqual([agent["id"] for agent in public_catalog.json()["agents"]], ["strict-reviewer"])
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(public_after_disable.json()["agents"], [])
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(admin_after_delete.json(), [])

    def test_admin_opencode_agent_rejects_unknown_permission_key(self):
        response = self.client.post(
            "/api/admin/opencode-agents",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={
                "id": "bad-agent",
                "name": "Bad Agent",
                "prompt": "Do work.",
                "permission": {"read": True, "network": True},
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_admin_publish_target_auto_publish_closes_review_to_released_record(self):
        from types import SimpleNamespace

        from skillhub_worker.publish_runner import run_publish_once

        skill = self.create_skill("auto-publish-api")
        targets = self.client.get("/api/admin/publish-targets", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()
        target = next(item for item in targets if item["target_key"] == "yunxi")
        updated_target = self.client.patch(
            f"/api/admin/publish-targets/{target['id']}",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"enabled": True, "auto_publish_enabled": True, "gate_expression": target["gate_expression"]},
        )
        self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_id": "reviewer-one", "role": "reviewer"},
        )
        review = self.client.post(
            f"/api/skills/{skill['skill_id']}/reviews",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"skill_version_id": skill["skill_version_id"], "publish_targets": [{"publish_target_id": target["id"], "auto_submit_on_pass": True}]},
        ).json()
        self.client.post(
            f"/api/reviews/{review['id']}/responses",
            headers={"X-SkillHub-Actor": "reviewer-one"},
            json={"score": 1, "comment": "可以发布"},
        )

        closed = self.client.post(f"/api/reviews/{review['id']}/close", headers={"X-SkillHub-Actor": "product-operator"})
        processed = run_publish_once(
            self.store,
            config=SimpleNamespace(
                worker_id="publish-worker",
                opencode_base_url="http://opencode.test",
                workdir_host="/tmp",
                max_attempts=1,
            ),
        )
        records = self.client.get("/api/admin/publish-records", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()

        self.assertEqual(updated_target.status_code, 200)
        self.assertTrue(updated_target.json()["auto_publish_enabled"])
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["publish_records"][0]["status"], "pending_confirmation")
        self.assertTrue(processed)
        self.assertEqual(records[0]["status"], "released")
        self.assertEqual(records[0]["confirmed_by"], "publish-worker")
        self.assertEqual(records[0]["metadata"]["auto_publish"], True)

    def test_review_can_snapshot_explicit_group_and_user_reviewers(self):
        skill = self.create_skill("explicit-review-groups")
        group = self.client.post(
            "/api/admin/groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"name": "backend-reviewers", "description": "Backend review pool"},
        ).json()
        self.client.post(f"/api/admin/groups/{group['id']}/members", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"subject_id": "alice"})
        self.client.post(f"/api/admin/groups/{group['id']}/members", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"subject_id": "bob"})
        self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_id": "auto-reviewer", "role": "reviewer"},
        )

        review = self.client.post(
            f"/api/skills/{skill['skill_id']}/reviews",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={
                "skill_version_id": skill["skill_version_id"],
                "publish_targets": [],
                "reviewer_sources": [
                    {"subject_type": "group", "subject_id": group["id"]},
                    {"subject_type": "user", "subject_id": "bob"},
                    {"subject_type": "user", "subject_id": "carol"},
                ],
            },
        )

        self.assertEqual(review.status_code, 200)
        reviewers = {item["reviewer_actor"]: item for item in review.json()["reviewers"]}
        self.assertEqual(set(reviewers), {"alice", "bob", "carol"})
        self.assertEqual(reviewers["alice"]["source_subject_type"], "group")
        self.assertEqual(reviewers["alice"]["source_subject_id"], group["id"])
        self.assertEqual(reviewers["bob"]["source_subject_type"], "user")
        self.assertEqual(reviewers["carol"]["source_subject_type"], "user")
        self.assertNotIn("auto-reviewer", reviewers)

        notifications = self.client.get("/api/me/notifications", headers={"X-SkillHub-Actor": "bob"}).json()
        self.assertEqual(len(notifications), 1)

    def test_review_with_no_explicit_reviewers_keeps_role_snapshot(self):
        skill = self.create_skill("auto-reviewer-fallback")
        self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"subject_id": "role-reviewer", "role": "reviewer"},
        )

        review = self.client.post(
            f"/api/skills/{skill['skill_id']}/reviews",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={"skill_version_id": skill["skill_version_id"], "publish_targets": []},
        )

        self.assertEqual(review.status_code, 200)
        self.assertEqual([item["reviewer_actor"] for item in review.json()["reviewers"]], ["role-reviewer"])

    def test_review_rejects_empty_explicit_group(self):
        skill = self.create_skill("empty-review-group")
        group = self.client.post(
            "/api/admin/groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"name": "empty-reviewers"},
        ).json()

        review = self.client.post(
            f"/api/skills/{skill['skill_id']}/reviews",
            headers={"X-SkillHub-Actor": "product-operator"},
            json={
                "skill_version_id": skill["skill_version_id"],
                "publish_targets": [],
                "reviewer_sources": [{"subject_type": "group", "subject_id": group["id"]}],
            },
        )

        self.assertEqual(review.status_code, 409)
        self.assertIn("No reviewers", review.json()["detail"])

    def test_reviewer_candidates_require_review_manage_permission(self):
        skill = self.create_skill("reviewer-candidates")
        group = self.client.post(
            "/api/admin/groups",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"name": "candidate-reviewers"},
        ).json()
        self.client.post(f"/api/admin/groups/{group['id']}/members", headers={"X-SkillHub-Admin-Key": "test-admin-key"}, json={"subject_id": "candidate-user"})

        denied = self.client.get(f"/api/skills/{skill['skill_id']}/reviewer-candidates", headers={"X-SkillHub-Actor": "viewer"})
        allowed = self.client.get(f"/api/skills/{skill['skill_id']}/reviewer-candidates", headers={"X-SkillHub-Actor": "product-operator"})

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        candidate = next(item for item in allowed.json()["groups"] if item["id"] == group["id"])
        self.assertEqual(candidate["scope_type"], "global")
        self.assertEqual(candidate["member_count"], 1)
        self.assertEqual(candidate["members"][0]["subject_id"], "candidate-user")

    def test_saved_run_view_endpoints_create_list_and_delete_view(self):
        skill = self.create_skill("saved-view-api")

        created = self.client.post(
            "/api/saved-views",
            json={
                "skill_id": skill["skill_id"],
                "name": "Windows failures",
                "config": {"skill_version_id": skill["skill_version_id"], "status": "finished", "unknown": "ignored"},
            },
        )
        listed = self.client.get(f"/api/skills/{skill['skill_id']}/saved-views")
        deleted = self.client.delete(f"/api/saved-views/{created.json()['id']}")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["config"], {"skill_version_id": skill["skill_version_id"], "status": "finished"})
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(deleted.json(), {"ok": True})

    def test_update_skill_changes_identity_only(self):
        skill = self.create_skill("settings-api")

        response = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            json={"slug": "settings-api-v2", "owner_ref": "platform-team"},
        )
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "settings-api-v2")
        self.assertEqual(detail["skill"]["owner_ref"], "platform-team")
        self.assertNotIn("default_variant_id", detail["skill"])

    def test_create_skill_duplicate_slug_returns_slug_field_error(self):
        self.create_skill("duplicate-skill")

        response = self.client.post("/api/skills", json=self.skill_payload("duplicate-skill"))
        other_owner = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "other-owner"},
            json={**self.skill_payload("duplicate-skill"), "owner_ref": "other-owner"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["field"], "slug")
        self.assertEqual(other_owner.status_code, 400)
        self.assertEqual(other_owner.json()["field_errors"][0]["field"], "slug")

    def test_external_skill_zip_upsert_creates_updates_and_rejects_cross_owner_slug(self):
        first_tag = self.create_tag_value("domain", "api")
        second_tag = self.create_tag_value("domain", "worker")

        created = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-user", "tags": json.dumps([first_tag])},
            files={"file": ("skill.zip", self.skill_zip("external-reviewer"), "application/zip")},
        )
        updated = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-user", "tags": json.dumps([second_tag])},
            files={"file": ("skill.zip", self.skill_zip("external-reviewer", body="Updated guidance."), "application/zip")},
        )
        other_owner = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "another-user", "tags": json.dumps([first_tag])},
            files={"file": ("skill.zip", self.skill_zip("external-reviewer"), "application/zip")},
        )
        updated_detail = self.client.get(f"/api/skills/{updated.json()['skill_id']}").json()

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["operation"], "created")
        self.assertEqual(created.json()["version"], "0.0.1")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["operation"], "updated")
        self.assertEqual(updated.json()["skill_id"], created.json()["skill_id"])
        self.assertEqual(updated.json()["version"], "0.0.2")
        self.assertEqual(updated_detail["skill"]["tags"][0]["value"], "worker")
        self.assertEqual(other_owner.status_code, 400)
        self.assertEqual(other_owner.json()["field_errors"][0]["field"], "slug")

    def test_external_skill_zip_upsert_rejects_existing_version_and_unknown_tag(self):
        tag = self.create_tag_value("domain", "external")
        created = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-version-user", "tags": json.dumps([tag]), "version": "1.0.0"},
            files={"file": ("skill.zip", self.skill_zip("external-version"), "application/zip")},
        )

        duplicate_version = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-version-user", "tags": json.dumps([tag]), "version": "1.0.0"},
            files={"file": ("skill.zip", self.skill_zip("external-version"), "application/zip")},
        )
        unknown_tag = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-version-user", "tags": json.dumps([{"group_id": "domain", "value": "missing"}])},
            files={"file": ("skill.zip", self.skill_zip("external-version"), "application/zip")},
        )
        detail = self.client.get(f"/api/skills/{created.json()['skill_id']}").json()

        self.assertEqual(created.status_code, 200)
        self.assertEqual(duplicate_version.status_code, 400)
        self.assertEqual(duplicate_version.json()["field_errors"][0]["field"], "version")
        self.assertEqual(unknown_tag.status_code, 400)
        self.assertEqual(unknown_tag.json()["field_errors"][0]["field"], "tags")
        self.assertEqual(len(detail["versions"]), 1)

    def test_external_skill_zip_upsert_requires_required_tag_group(self):
        required_tag = self.create_tag_value("domain", "required-external")
        group = self.client.get("/api/admin/tag-groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"}).json()[0]
        self.client.patch(
            "/api/admin/tag-groups/domain",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={"display_name": group["display_name"], "description": group["description"], "sort_order": group["sort_order"], "required": True},
        )

        missing = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-required-user", "tags": json.dumps([])},
            files={"file": ("skill.zip", self.skill_zip("external-required"), "application/zip")},
        )
        created = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-required-user", "tags": json.dumps([required_tag])},
            files={"file": ("skill.zip", self.skill_zip("external-required"), "application/zip")},
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["field_errors"][0]["field"], "tags")
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["operation"], "created")

    def test_external_skill_zip_upsert_uses_actor_owner_for_existing_global_skill_update(self):
        tag = self.create_tag_value("domain", "external-owner")
        created = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-owner", "tags": json.dumps([tag])},
            files={"file": ("skill.zip", self.skill_zip("external-owner-skill"), "application/zip")},
        )

        updated = self.client.post(
            "/api/external/skills/upsert-zip",
            data={"actor_id": "external-owner", "tags": json.dumps([tag])},
            files={"file": ("skill.zip", self.skill_zip("external-owner-skill", body="Updated without role."), "application/zip")},
        )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["operation"], "updated")
        self.assertEqual(updated.json()["skill_id"], created.json()["skill_id"])

    def test_create_skill_rejects_invalid_slug_format(self):
        response = self.client.post("/api/skills", json=self.skill_payload("Invalid Slug"))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "slug")

    def test_request_actor_header_controls_created_admin(self):
        response = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "maintainer-one"},
            json=self.skill_payload("actor-owned-skill"),
        )
        assignments = self.client.get(f"/api/skills/{response.json()['skill_id']}/role-assignments").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(assignments[0]["subject_id"], "maintainer-one")
        self.assertEqual(assignments[0]["role"], "admin")

    def skill_zip(self, slug: str, body: str = "Review backend changes.") -> bytes:
        archive = BytesIO()
        with ZipFile(archive, "w") as zip_file:
            zip_file.writestr(
                f"{slug}/SKILL.md",
                (
                    "---\n"
                    f"name: {slug}\n"
                    "description: Review pull requests for auth and data access regressions.\n"
                    "---\n"
                    "# Reviewer\n"
                    f"{body}\n"
                ),
            )
            zip_file.writestr(f"{slug}/references/checklist.md", "Check owner filters.\n")
        return archive.getvalue()
