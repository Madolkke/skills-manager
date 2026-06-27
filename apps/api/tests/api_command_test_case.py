from fastapi.testclient import TestClient
import os

from skillhub.bootstrap.app import create_app
from skillhub.models.store import SkillHubStore
from tests.postgres_test_case import PostgresTestCase


class ApiCommandTestCase(PostgresTestCase):
    def setUp(self) -> None:
        super().setUp()
        os.environ["SKILLHUB_ADMIN_CONSOLE_KEY"] = "test-admin-key"
        self.client = TestClient(create_app(self.engine))
        self.store = SkillHubStore(self.engine)

    def skill_payload(self, slug: str, digest: str | None = None):
        return {
            "slug": slug,
            "owner_ref": "skillhub-lab",
            "content_ref": {
                "kind": "skill_bundle",
                "locator": f"memory:{slug}",
                "digest": digest or f"digest-{slug}",
            },
            "change_summary": "Initial version.",
        }

    def create_skill(self, slug: str):
        response = self.client.post("/api/skills", json=self.skill_payload(slug))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_tag_value(
        self,
        group_id: str = "domain",
        value: str = "security",
        display_name: str | None = None,
    ):
        groups = self.client.get("/api/admin/tag-groups", headers={"X-SkillHub-Admin-Key": "test-admin-key"})
        self.assertEqual(groups.status_code, 200)
        existing_group = next((item for item in groups.json() if item["id"] == group_id), None)
        if existing_group is None:
            group = self.client.post(
                "/api/admin/tag-groups",
                headers={"X-SkillHub-Admin-Key": "test-admin-key"},
                json={"id": group_id, "display_name": group_id, "description": ""},
            )
            self.assertEqual(group.status_code, 200)
            existing_group = group.json()
        if not any(item["value"] == value for item in existing_group.get("values", [])):
            created = self.client.post(
                f"/api/admin/tag-groups/{group_id}/values",
                headers={"X-SkillHub-Admin-Key": "test-admin-key"},
                json={"value": value, "display_name": display_name, "description": ""},
            )
            self.assertEqual(created.status_code, 200)
        return {"group_id": group_id, "value": value}

    def tag_resource_id(self, group_id: str, value: str) -> str:
        encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
        return f"{group_id}:{encoded}"

    def create_skill_version(self, skill_id: str, slug: str):
        response = self.client.post(
            "/api/skill-versions",
            json={
                "skill_id": skill_id,
                "content_ref": {
                    "kind": "skill_bundle",
                    "locator": f"memory:{slug}",
                    "digest": f"digest-{slug}",
                },
                "change_summary": f"Create {slug}.",
                "make_current": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_eval_case(self, skill_id: str):
        skill = self.client.get(f"/api/skills/{skill_id}").json()
        eval_set_id = skill["summary"]["primary_eval_set"]["id"]
        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill_id,
                "eval_set_id": eval_set_id,
                "title": "PR: missing owner check",
                "steps": [
                    {
                        "title": "检查 owner 过滤",
                        "input": "Project.findMany()",
                        "assertions": [
                            {
                                "assertion_template_id": "agent_output_contains",
                                "assertion_params": {"text": "Flag missing ownerId filter."},
                            }
                        ],
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def record_run(
        self,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        passed: bool,
        environment_tags: list[str] | None = None,
        run_context: dict[str, str] | None = None,
        actual_output: str = "",
    ):
        context = run_context or {}
        tags = environment_tags or []
        queued = self.client.post(
            "/api/eval-case-runs",
            json={
                "skill_version_id": skill_version_id,
                "eval_set_id": eval_set_id,
                "case_version_id": case_version_id,
                "environment_tags": tags,
                "run_context": context,
            },
        )
        self.assertEqual(queued.status_code, 200)
        self.store.finalize_eval_case_run(
            eval_case_run_id=queued.json()["eval_case_run_id"],
            passed=passed,
            actual_output=actual_output,
            actor="tester",
        )
        response = self.client.post(
            "/api/eval-runs/aggregations",
            json={
                "skill_version_id": skill_version_id,
                "eval_set_id": eval_set_id,
                "environment_tags": tags,
                "run_context": context,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def enqueue_case_run(
        self,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        environment_tags: list[str] | None = None,
        run_context: dict[str, str] | None = None,
    ):
        response = self.client.post(
            "/api/eval-case-runs",
            json={
                "skill_version_id": skill_version_id,
                "eval_set_id": eval_set_id,
                "case_version_id": case_version_id,
                "environment_tags": environment_tags or [],
                "run_context": run_context or {},
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def import_standard_skill_bundle(self, slug: str):
        response = self.client.post(
            "/api/skill-imports",
            json={
                "owner_ref": "skillhub-lab",
                "source": self.bundle_source(slug),
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def bundle_source(
        self,
        slug: str,
        skill_md_body: str = "Flag auth regressions first.",
        checklist: str = "Check owner filters and secret logging.",
    ):
        return {
            "kind": "files",
            "name": slug,
            "files": [
                {
                    "path": f"{slug}/SKILL.md",
                    "content_text": (
                        "---\n"
                        f"name: {slug}\n"
                        "description: Review pull requests for auth and data access regressions.\n"
                        "---\n"
                        "# Security Reviewing\n"
                        f"{skill_md_body}\n"
                    ),
                },
                {
                    "path": f"{slug}/references/checklist.md",
                    "content_text": f"{checklist}\n",
                },
            ],
        }
