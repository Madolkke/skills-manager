from __future__ import annotations

from tests.api_command_test_case import ApiCommandTestCase


class SkillIdentityAndGlobalAdminTest(ApiCommandTestCase):
    def test_rename_creates_patch_version_and_preserves_internal_id(self):
        created = self.import_standard_skill_bundle("rename-source")

        response = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            json={
                "slug": "rename-target",
                "expected_slug": "rename-source",
                "owner_ref": "skillhub-lab",
            },
        )
        detail = self.client.get(f"/api/skills/{created['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], created["skill_id"])
        self.assertEqual(response.json()["slug"], "rename-target")
        self.assertEqual(len(detail["versions"]), 2)
        self.assertEqual(detail["summary"]["current_version"]["version"], "0.0.2")
        self.assertEqual(detail["summary"]["current_version"]["change_summary"], "Renamed Skill ID from rename-source to rename-target.")
        skill_file = next(item for item in detail["summary"]["current_version"]["bundle_files"] if item["path"] == "SKILL.md")
        checklist = next(item for item in detail["summary"]["current_version"]["bundle_files"] if item["path"] == "references/checklist.md")
        self.assertIn("name: rename-target", skill_file["content_text"])
        self.assertEqual(checklist["content_text"], "Check owner filters and secret logging.\n")
        self.assertIn("name: rename-source", detail["versions"][-1]["bundle_files"][0]["content_text"])

    def test_display_name_can_be_set_preserved_and_cleared_without_new_version(self):
        created = self.import_standard_skill_bundle("display-name-skill")
        base = {"slug": "display-name-skill", "owner_ref": "skillhub-lab"}

        set_response = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            json={**base, "display_name": "  中文名称  "},
        )
        listed = self.client.get("/api/skills").json()
        detail_after_set = self.client.get(f"/api/skills/{created['skill_id']}").json()
        preserved = self.client.patch(f"/api/skills/{created['skill_id']}", json=base)
        cleared = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            json={**base, "display_name": "   "},
        )
        detail = self.client.get(f"/api/skills/{created['skill_id']}").json()

        self.assertEqual(set_response.json()["display_name"], "中文名称")
        self.assertEqual(next(item for item in listed if item["skill"]["id"] == created["skill_id"])["skill"]["display_name"], "中文名称")
        self.assertEqual(detail_after_set["skill"]["display_name"], "中文名称")
        self.assertEqual(preserved.json()["display_name"], "中文名称")
        self.assertIsNone(cleared.json()["display_name"])
        self.assertEqual(len(detail["versions"]), 1)

        stale_display_name = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            json={**base, "expected_slug": "stale-skill-id", "display_name": "不应写入"},
        )
        self.assertEqual(stale_display_name.status_code, 409)
        self.assertIsNone(self.client.get(f"/api/skills/{created['skill_id']}").json()["skill"]["display_name"])

        too_long = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            json={**base, "display_name": f"  {'中' * 121}  "},
        )
        self.assertEqual(too_long.status_code, 422)

    def test_stale_expected_slug_and_non_artifact_bundle_reject_rename(self):
        artifact_skill = self.import_standard_skill_bundle("expected-source")
        stale = self.client.patch(
            f"/api/skills/{artifact_skill['skill_id']}",
            json={"slug": "expected-target", "expected_slug": "stale-source", "owner_ref": "skillhub-lab"},
        )
        memory_skill = self.create_skill("memory-source")
        unavailable = self.client.patch(
            f"/api/skills/{memory_skill['skill_id']}",
            json={"slug": "memory-target", "expected_slug": "memory-source", "owner_ref": "skillhub-lab"},
        )

        self.assertEqual(stale.status_code, 409)
        self.assertEqual(unavailable.status_code, 409)
        self.assertEqual(self.client.get(f"/api/skills/{artifact_skill['skill_id']}").json()["skill"]["slug"], "expected-source")
        self.assertEqual(self.client.get(f"/api/skills/{memory_skill['skill_id']}").json()["skill"]["slug"], "memory-source")

    def test_global_admin_applies_to_existing_and_future_skills_without_console_access(self):
        first = self.import_standard_skill_bundle("global-admin-first")
        assignment = self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={
                "subject_type": "user",
                "subject_id": "global-user",
                "resource_type": "global",
                "resource_id": "skills",
                "role": "admin",
            },
        )
        second = self.import_standard_skill_bundle("global-admin-second")

        first_capabilities = self.client.get(
            f"/api/skills/{first['skill_id']}/capabilities",
            headers={"X-SkillHub-Actor": "global-user"},
        ).json()
        second_capabilities = self.client.get(
            f"/api/skills/{second['skill_id']}/capabilities",
            headers={"X-SkillHub-Actor": "global-user"},
        ).json()
        denied_console = self.client.get(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Actor": "global-user"},
        )
        managed_role = self.client.post(
            f"/api/skills/{first['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "global-user"},
            json={"subject_type": "user", "subject_id": "viewer-user", "role": "viewer"},
        )
        renamed = self.client.patch(
            f"/api/skills/{first['skill_id']}",
            headers={"X-SkillHub-Actor": "global-user"},
            json={
                "slug": "global-admin-renamed",
                "expected_slug": "global-admin-first",
                "owner_ref": "skillhub-lab",
            },
        )
        deleted = self.client.request(
            "DELETE",
            f"/api/skills/{second['skill_id']}",
            headers={"X-SkillHub-Actor": "global-user"},
            json={"confirmation_slug": "global-admin-second"},
        )

        self.assertEqual(assignment.status_code, 200)
        self.assertIn("admin", first_capabilities["effective_roles"])
        self.assertTrue(first_capabilities["permissions"]["skill.delete"])
        self.assertIn("admin", second_capabilities["effective_roles"])
        self.assertEqual(denied_console.status_code, 403)
        self.assertEqual(managed_role.status_code, 200)
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["slug"], "global-admin-renamed")
        self.assertEqual(deleted.status_code, 200)

        revoked = self.client.delete(
            f"/api/admin/role-assignments/{assignment.json()['id']}",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
        )
        after = self.client.get(
            f"/api/skills/{first['skill_id']}/capabilities",
            headers={"X-SkillHub-Actor": "global-user"},
        ).json()
        self.assertEqual(revoked.status_code, 200)
        self.assertNotIn("admin", after["effective_roles"])

    def test_invalid_global_role_combination_is_rejected(self):
        response = self.client.post(
            "/api/admin/role-assignments",
            headers={"X-SkillHub-Admin-Key": "test-admin-key"},
            json={
                "subject_type": "group",
                "subject_id": "group-one",
                "resource_type": "global",
                "resource_id": "skills",
                "role": "owner",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_maintainer_can_rename_but_active_eval_blocks_it(self):
        created = self.import_standard_skill_bundle("maintainer-rename")
        assignment = self.client.post(
            f"/api/skills/{created['skill_id']}/role-assignments",
            json={"subject_type": "user", "subject_id": "maintainer-user", "role": "maintainer"},
        )
        self.assertEqual(assignment.status_code, 200)
        case = self.create_eval_case(created["skill_id"])
        self.enqueue_case_run(
            created["skill_version_id"],
            case["eval_set_id"],
            case["eval_case_version_id"],
        )

        blocked = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            headers={"X-SkillHub-Actor": "maintainer-user"},
            json={
                "slug": "maintainer-renamed",
                "expected_slug": "maintainer-rename",
                "owner_ref": "skillhub-lab",
            },
        )

        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(self.client.get(f"/api/skills/{created['skill_id']}").json()["skill"]["slug"], "maintainer-rename")

    def test_skill_admin_can_rename_while_viewer_cannot(self):
        created = self.import_standard_skill_bundle("skill-admin-source")
        for subject_id, role in (("skill-admin-user", "admin"), ("viewer-user", "viewer")):
            response = self.client.post(
                f"/api/skills/{created['skill_id']}/role-assignments",
                json={"subject_type": "user", "subject_id": subject_id, "role": role},
            )
            self.assertEqual(response.status_code, 200)

        denied = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            headers={"X-SkillHub-Actor": "viewer-user"},
            json={"slug": "viewer-target", "expected_slug": "skill-admin-source", "owner_ref": "skillhub-lab"},
        )
        renamed = self.client.patch(
            f"/api/skills/{created['skill_id']}",
            headers={"X-SkillHub-Actor": "skill-admin-user"},
            json={"slug": "skill-admin-target", "expected_slug": "skill-admin-source", "owner_ref": "skillhub-lab"},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["slug"], "skill-admin-target")

    def test_duplicate_slug_rolls_back_the_generated_version(self):
        source = self.import_standard_skill_bundle("duplicate-source")
        self.import_standard_skill_bundle("duplicate-target")

        response = self.client.patch(
            f"/api/skills/{source['skill_id']}",
            json={"slug": "duplicate-target", "expected_slug": "duplicate-source", "owner_ref": "skillhub-lab"},
        )
        detail = self.client.get(f"/api/skills/{source['skill_id']}").json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(detail["skill"]["slug"], "duplicate-source")
        self.assertEqual(len(detail["versions"]), 1)
