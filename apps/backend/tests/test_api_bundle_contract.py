from io import BytesIO
from pathlib import Path
from shutil import rmtree
from zipfile import ZipFile

from sqlalchemy.orm import Session

from skillhub.models.schema import orm
from skillhub.services.artifacts import QUICK_PUBLISH_DIRECTORY
from tests.api_command_test_case import ApiCommandTestCase


class ApiBundleContractTest(ApiCommandTestCase):
    def test_old_variant_payloads_are_not_part_of_the_contract(self):
        response = self.client.post("/api/eval-runs", json={"variant_version_id": "legacy"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.post("/api/variants", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/variant-versions", json={}).status_code, 404)

    def test_eval_case_run_payload_rejects_legacy_strategy(self):
        skill = self.create_skill("no-strategy-contract")
        case = self.create_eval_case(skill["skill_id"])

        response = self.client.post(
            "/api/eval-case-runs",
            json={
                "skill_version_id": skill["skill_version_id"],
                "eval_set_id": case["eval_set_id"],
                "case_version_id": case["eval_case_version_id"],
                "strategy": "manual_pass_fail",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "strategy")

    def test_eval_case_payload_rejects_legacy_single_input_fields(self):
        skill = self.create_skill("new-case-contract")

        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill["skill_id"],
                "eval_set_id": skill["eval_set_id"],
                "title": "Legacy case",
                "input_text": "old input",
                "expected_output": "old output",
            },
        )

        self.assertEqual(response.status_code, 422)
        fields = {item["field"] for item in response.json()["field_errors"]}
        self.assertIn("steps", fields)
        self.assertIn("input_text", fields)

    def test_eval_case_step_validation_points_to_nested_field(self):
        skill = self.create_skill("step-contract")

        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill["skill_id"],
                "eval_set_id": skill["eval_set_id"],
                "title": "Invalid step",
                "steps": [{"title": "Missing input", "assertions": [{"assertion_template_id": "agent_output_contains"}]}],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "steps[0].input")

    def test_skill_version_from_bundle_source_can_be_diffed(self):
        imported = self.import_standard_skill_bundle("bundle-diff")
        first_version_id = imported["skill_version_id"]
        second = self.client.post(
            "/api/skill-versions",
            json={
                "skill_id": imported["skill_id"],
                "source": self.bundle_source(
                    "bundle-diff",
                    skill_md_body="Flag auth regressions and tenant leaks first.",
                    checklist="Check owner filters, tenant filters, and secret logging.",
                ),
                "change_summary": "Add tenant guidance.",
                "make_current": True,
            },
        )
        self.assertEqual(second.status_code, 200)

        diff = self.client.get(
            "/api/artifacts/diff",
            params={
                "left_skill_version_id": first_version_id,
                "right_skill_version_id": second.json()["skill_version_id"],
            },
        )

        self.assertEqual(diff.status_code, 200)
        self.assertEqual(diff.json()["summary"]["changed"], 2)
        self.assertEqual(diff.json()["left"]["skill_version_id"], first_version_id)

    def test_skill_version_bundle_can_be_downloaded_and_quick_published(self):
        imported = self.import_standard_skill_bundle("bundle-export")
        version_id = imported["skill_version_id"]
        destination = QUICK_PUBLISH_DIRECTORY / version_id

        try:
            download = self.client.get(f"/api/skill-versions/{version_id}/download")

            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.headers["content-type"], "application/zip")
            with ZipFile(BytesIO(download.content)) as archive:
                self.assertEqual(archive.namelist(), ["SKILL.md", "references/checklist.md"])
                self.assertIn("name: bundle-export", archive.read("SKILL.md").decode("utf-8"))

            published = self.client.post(f"/api/skill-versions/{version_id}/quick-publish")

            self.assertEqual(published.status_code, 200)
            self.assertEqual(Path(published.json()["destination"]), destination)
            self.assertEqual(published.json()["file_count"], 2)
            self.assertIn("name: bundle-export", (destination / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual((destination / "references" / "checklist.md").read_text(encoding="utf-8"), "Check owner filters and secret logging.\n")
        finally:
            if destination.exists():
                rmtree(destination)

    def test_bundle_diff_rejects_cross_skill_versions(self):
        first = self.import_standard_skill_bundle("first-diff")
        second = self.import_standard_skill_bundle("second-diff")

        response = self.client.get(
            "/api/artifacts/diff",
            params={
                "left_skill_version_id": first["skill_version_id"],
                "right_skill_version_id": second["skill_version_id"],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("same skill", response.json()["detail"])

    def test_import_skill_from_file_tree_uses_skill_md_frontmatter(self):
        imported = self.import_standard_skill_bundle("imported-reviewer")
        hub = self.client.get("/api/skills").json()
        detail = self.client.get(f"/api/skills/{imported['skill_id']}").json()
        expected_description = "Review pull requests for auth and data access regressions."

        self.assertEqual(imported["slug"], "imported-reviewer")
        self.assertEqual(imported["entry_path"], "SKILL.md")
        self.assertEqual(hub[0]["summary"]["current_version"]["description"], expected_description)
        self.assertEqual(detail["summary"]["current_version"]["description"], expected_description)
        self.assertEqual(detail["versions"][0]["description"], expected_description)
        self.assertNotEqual(detail["summary"]["current_version"]["description"], detail["summary"]["current_version"]["change_summary"])
        self.assertEqual(detail["summary"]["current_version"]["content_ref"]["kind"], "artifact")
        self.assertEqual(detail["summary"]["current_version"]["bundle_artifact"]["id"], imported["bundle_artifact_id"])
        self.assertEqual(len(detail["summary"]["current_version"]["bundle_files"]), 2)

    def test_invalid_bundle_manifest_does_not_break_skill_reads(self):
        imported = self.import_standard_skill_bundle("invalid-description-manifest")
        with Session(self.engine) as session, session.begin():
            artifact = session.get(orm.Artifact, imported["bundle_artifact_id"])
            self.assertIsNotNone(artifact)
            artifact.content_text = "{not-json"

        hub = self.client.get("/api/skills")
        detail = self.client.get(f"/api/skills/{imported['skill_id']}")

        self.assertEqual(hub.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertIsNone(hub.json()[0]["summary"]["current_version"]["description"])
        self.assertIsNone(detail.json()["summary"]["current_version"]["description"])
        self.assertIsNone(detail.json()["versions"][0]["description"])
