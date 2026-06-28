from tests.api_command_test_case import ApiCommandTestCase
import base64
import httpx
from io import BytesIO
import json
from zipfile import ZipFile
from skillhub.services import opencode as opencode_service


class ApiSkillManagementTest(ApiCommandTestCase):
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

    def test_admin_delete_tag_value_removes_skill_tags_and_matching_tag_roles_only(self):
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

        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(first_detail["skill"]["tags"], [])
        self.assertEqual(second_detail["skill"]["tags"][0]["group_id"], "team")
        self.assertFalse(any(role["resource_id"] == self.tag_resource_id("domain", "shared") for role in roles))
        self.assertTrue(any(role["resource_id"] == self.tag_resource_id("team", "shared") for role in roles))

    def test_admin_delete_tag_group_removes_values_skill_tags_and_matching_roles(self):
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

        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(detail["skill"]["tags"], [])
        self.assertEqual(tag_groups, [])
        self.assertFalse(any(role["resource_type"] == "skill_tag" and role["resource_id"].startswith("cleanup:") for role in roles))

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
        self.assertEqual(other_owner.status_code, 200)

    def test_external_skill_zip_upsert_creates_and_updates_owner_scoped_skill(self):
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
        self.assertEqual(other_owner.status_code, 200)
        self.assertNotEqual(other_owner.json()["skill_id"], created.json()["skill_id"])

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

    def test_external_skill_zip_upsert_uses_actor_owner_scope_not_role_assignments(self):
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
