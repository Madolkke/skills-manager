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
        detail = self.client.get(f"/api/skills/{imported['skill_id']}").json()

        self.assertEqual(imported["slug"], "imported-reviewer")
        self.assertEqual(imported["entry_path"], "SKILL.md")
        self.assertEqual(detail["summary"]["current_version"]["content_ref"]["kind"], "artifact")
        self.assertEqual(detail["summary"]["current_version"]["bundle_artifact"]["id"], imported["bundle_artifact_id"])
        self.assertEqual(len(detail["summary"]["current_version"]["bundle_files"]), 2)
