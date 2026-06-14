from fastapi.testclient import TestClient

from skillhub.api.main import create_app
from tests.postgres_test_case import PostgresTestCase


class ApiCommandTestCase(PostgresTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = TestClient(create_app(self.engine))

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
        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill_id,
                "title": "PR: missing owner check",
                "input_text": "Project.findMany()",
                "expected_output": "Flag missing ownerId filter.",
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
    ):
        response = self.client.post(
            "/api/eval-runs",
            json={
                "skill_version_id": skill_version_id,
                "eval_set_id": eval_set_id,
                "environment_tags": environment_tags or [],
                "run_context": run_context or {},
                "results": {case_version_id: passed},
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
