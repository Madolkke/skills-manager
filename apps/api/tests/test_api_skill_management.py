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
                        "assertion_template_id": "agent_output_contains",
                        "assertion_params": {"text": "ownerId"},
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
                        "assertion_template_id": "agent_output_contains",
                        "assertion_params": {"text": "Flag missing test coverage."},
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

    def test_eval_case_runner_config_can_be_saved(self):
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
                        "assertion_template_id": "agent_output_contains",
                        "assertion_params": {"text": "Find the answer."},
                    }
                ],
                "runner_config": {"model_provider_id": "deepseek", "model_id": "deepseek-v4-pro"},
            },
        )
        eval_set = self.client.get(f"/api/eval-sets/{response.json()['eval_set_id']}").json()
        case_version = eval_set["cases"][0]["case_version"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(case_version["steps"][0]["assertion_template_id"], "agent_output_contains")
        self.assertEqual(case_version["runner_config"]["model_provider_id"], "deepseek")
        self.assertEqual(case_version["runner_config"]["model_id"], "deepseek-v4-pro")

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
