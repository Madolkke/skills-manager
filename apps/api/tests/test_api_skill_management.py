from tests.api_command_test_case import ApiCommandTestCase
import base64


class ApiSkillManagementTest(ApiCommandTestCase):
    def test_read_flow_returns_hub_skill_eval_set_and_version_details(self):
        skill = self.create_skill("read-flow")
        case = self.create_eval_case(skill["skill_id"])

        hub = self.client.get("/api/skills").json()
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        eval_set = self.client.get(f"/api/eval-sets/{case['eval_set_id']}").json()

        self.assertEqual(hub[0]["summary"]["current_version"]["id"], skill["skill_version_id"])
        self.assertEqual(detail["summary"]["current_version"]["id"], skill["skill_version_id"])
        self.assertEqual(detail["versions"][0]["id"], skill["skill_version_id"])
        self.assertEqual(eval_set["cases"][0]["case_version"]["id"], case["eval_case_version_id"])

    def test_skill_versions_can_be_named_and_renamed(self):
        skill = self.create_skill("named-versions")

        skill_version = self.client.patch(
            f"/api/skill-versions/{skill['skill_version_id']}",
            json={"display_name": "stable baseline"},
        )
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()

        self.assertEqual(skill_version.status_code, 200)
        self.assertEqual(detail["summary"]["current_version"]["display_name"], "stable baseline")

    def test_eval_cases_update_current_eval_set(self):
        skill = self.create_skill("evalset-working-version")

        first_case = self.create_eval_case(skill["skill_id"])
        second_case = self.create_eval_case(skill["skill_id"])
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        eval_set_detail = self.client.get(f"/api/eval-sets/{second_case['eval_set_id']}").json()

        self.assertEqual(first_case["eval_set_id"], second_case["eval_set_id"])
        self.assertEqual(detail["summary"]["primary_eval_set"]["id"], second_case["eval_set_id"])
        self.assertEqual([item["case_version"]["id"] for item in eval_set_detail["cases"]], [first_case["eval_case_version_id"], second_case["eval_case_version_id"]])

    def test_eval_case_zip_attachment_can_be_saved_and_downloaded(self):
        skill = self.create_skill("case-attachment")
        zip_bytes = b"PK\x03\x04case archive"

        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill["skill_id"],
                "title": "Archive context",
                "input_text": "Review the attached archive.",
                "expected_output": "Flag missing test coverage.",
                "attachment_name": "context.zip",
                "attachment_base64": base64.b64encode(zip_bytes).decode("ascii"),
            },
        )
        eval_set = self.client.get(f"/api/eval-sets/{response.json()['eval_set_id']}").json()
        attachment = eval_set["cases"][0]["case_version"]["attachment_artifact"]
        downloaded = self.client.get(f"/api/artifacts/{attachment['id']}/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(attachment["media_type"], "application/zip")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, zip_bytes)

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

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["field"], "slug")

    def test_create_skill_rejects_invalid_slug_format(self):
        response = self.client.post("/api/skills", json=self.skill_payload("Invalid Slug"))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "slug")

    def test_request_actor_header_controls_created_owner(self):
        response = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "maintainer-one"},
            json=self.skill_payload("actor-owned-skill"),
        )
        assignments = self.client.get(f"/api/skills/{response.json()['skill_id']}/role-assignments").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(assignments[0]["subject_id"], "maintainer-one")
