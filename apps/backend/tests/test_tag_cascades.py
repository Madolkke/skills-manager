from concurrent.futures import ThreadPoolExecutor

from skillhub.models.entities import ContentRef
from tests.api_command_test_case import ApiCommandTestCase


class TagCascadeApiTest(ApiCommandTestCase):
    admin_headers = {"X-SkillHub-Admin-Key": "test-admin-key"}

    def create_group(
        self,
        group_id: str,
        *,
        free_form: bool = False,
        required: bool = False,
        values: tuple[str, ...] = (),
    ) -> dict:
        response = self.client.post(
            "/api/admin/tag-groups",
            headers=self.admin_headers,
            json={
                "id": group_id,
                "display_name": group_id,
                "description": "",
                "free_form": free_form,
                "required": required if free_form else False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        group = response.json()
        for index, value in enumerate(values):
            group = self.client.post(
                f"/api/admin/tag-groups/{group_id}/values",
                headers=self.admin_headers,
                json={"value": value, "description": "", "sort_order": index},
            ).json()
        if required and not free_form:
            response = self.client.patch(
                f"/api/admin/tag-groups/{group_id}",
                headers=self.admin_headers,
                json={
                    "display_name": group_id,
                    "description": "",
                    "sort_order": 0,
                    "required": True,
                    "free_form": False,
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            group = response.json()
        return group

    def attach(self, parent_group_id: str, parent_value: str, child_group_id: str):
        return self.client.post(
            "/api/admin/tag-cascades",
            headers=self.admin_headers,
            json={
                "parent_group_id": parent_group_id,
                "parent_value": parent_value,
                "child_group_id": child_group_id,
            },
        )

    def test_free_form_values_are_trimmed_persisted_and_case_sensitive(self):
        self.create_group("keywords", free_form=True, required=True, values=("preset",))

        first = self.client.post(
            "/api/skills",
            json={
                **self.skill_payload("free-tag-first"),
                "tags": [{"group_id": "keywords", "value": "  Case Sensitive  "}],
            },
        )
        second = self.client.post(
            "/api/skills",
            json={
                **self.skill_payload("free-tag-second"),
                "tags": [{"group_id": "keywords", "value": "case sensitive"}],
            },
        )
        group = self.client.get("/api/tag-groups").json()[0]

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        first_detail = self.client.get(f"/api/skills/{first.json()['skill_id']}").json()
        self.assertEqual(first_detail["skill"]["tags"][0]["value"], "Case Sensitive")
        self.assertEqual([item["value"] for item in group["values"]], ["preset", "Case Sensitive", "case sensitive"])

    def test_enum_group_rejects_undefined_value(self):
        self.create_group("domain", values=("api",))

        response = self.client.post(
            "/api/skills",
            json={**self.skill_payload("undefined-enum-tag"), "tags": [{"group_id": "domain", "value": "web"}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["code"], "skill_tag.undefined")

    def test_concurrent_free_form_writes_share_one_candidate(self):
        self.create_group("keywords", free_form=True)

        def create(index: int):
            return self.store.create_skill(
                slug=f"concurrent-free-tag-{index}",
                owner_ref="skillhub-lab",
                content_ref=ContentRef(kind="skill_bundle", locator=f"memory:concurrent-{index}", digest=f"digest-{index}"),
                change_summary="Concurrent free Tag write.",
                actor=f"creator-{index}",
                tags=[{"group_id": "keywords", "value": "shared candidate"}],
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, [1, 2]))
        group = self.client.get("/api/tag-groups").json()[0]

        self.assertEqual(len(results), 2)
        self.assertEqual([item["value"] for item in group["values"]], ["shared candidate"])

    def test_failed_skill_tag_update_does_not_persist_free_candidate(self):
        free_group = self.create_group("keywords", free_form=True)
        protected = self.create_group("risk", values=("high",))
        skill = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "owner"},
            json={**self.skill_payload("free-tag-rollback"), "tags": [{"group_id": "risk", "value": "high"}]},
        ).json()
        self.client.post(
            f"/api/skills/{skill['skill_id']}/role-assignments",
            headers={"X-SkillHub-Actor": "owner"},
            json={"subject_type": "user", "subject_id": "maintainer", "role": "maintainer"},
        )
        self.client.post(
            "/api/admin/role-assignments",
            headers=self.admin_headers,
            json={
                "subject_type": "user",
                "subject_id": "auditor",
                "resource_type": "skill_tag",
                "resource_id": self.tag_resource_id("risk", "high"),
                "role": "evaluator",
            },
        )

        response = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            headers={"X-SkillHub-Actor": "maintainer"},
            json={"slug": "free-tag-rollback", "owner_ref": "skillhub-lab", "tags": [{"group_id": "keywords", "value": "must rollback"}]},
        )
        groups = self.client.get("/api/tag-groups").json()
        current_free_group = next(item for item in groups if item["id"] == free_group["id"])

        self.assertEqual(response.status_code, 403)
        self.assertEqual(current_free_group["values"], [])
        self.assertEqual(protected["values"][0]["value"], "high")

    def test_nested_required_groups_activate_only_on_selected_path(self):
        self.create_group("platform", values=("cloud", "desktop"))
        self.create_group("provider", required=True, values=("aws",))
        self.create_group("region", required=True, values=("cn",))
        self.assertEqual(self.attach("platform", "cloud", "provider").status_code, 200)
        self.assertEqual(self.attach("provider", "aws", "region").status_code, 200)

        root_only = self.client.post(
            "/api/skills",
            json={**self.skill_payload("cascade-root-only"), "tags": [{"group_id": "platform", "value": "cloud"}]},
        )
        missing_grandchild = self.client.post(
            "/api/skills",
            json={
                **self.skill_payload("cascade-missing-grandchild"),
                "tags": [
                    {"group_id": "platform", "value": "cloud"},
                    {"group_id": "provider", "value": "aws"},
                ],
            },
        )
        valid = self.client.post(
            "/api/skills",
            json={
                **self.skill_payload("cascade-valid"),
                "tags": [
                    {"group_id": "platform", "value": "cloud"},
                    {"group_id": "provider", "value": "aws"},
                    {"group_id": "region", "value": "cn"},
                ],
            },
        )
        inactive_branch = self.client.post(
            "/api/skills",
            json={**self.skill_payload("cascade-inactive"), "tags": [{"group_id": "platform", "value": "desktop"}]},
        )
        orphan = self.client.post(
            "/api/skills",
            json={**self.skill_payload("cascade-orphan"), "tags": [{"group_id": "provider", "value": "aws"}]},
        )

        self.assertEqual(root_only.status_code, 400)
        self.assertEqual(missing_grandchild.status_code, 400)
        self.assertEqual(valid.status_code, 200, valid.text)
        self.assertEqual(inactive_branch.status_code, 200, inactive_branch.text)
        self.assertEqual(orphan.status_code, 400)
        self.assertEqual(orphan.json()["field_errors"][0]["code"], "skill_tag.orphaned")

    def test_cascade_constraints_require_explicit_unbind(self):
        self.create_group("root", values=("one",))
        self.create_group("other", values=("two",))
        self.create_group("child", required=True, values=("leaf",))
        self.assertEqual(self.attach("root", "one", "child").status_code, 200)

        duplicate_parent = self.attach("other", "two", "child")
        cycle = self.attach("child", "leaf", "root")
        free_parent_update = self.client.patch(
            "/api/admin/tag-groups/root",
            headers=self.admin_headers,
            json={"display_name": "root", "description": "", "sort_order": 0, "required": False, "free_form": True},
        )
        required_unbind = self.client.delete("/api/admin/tag-cascades/child", headers=self.admin_headers)
        parent_value_delete = self.client.delete("/api/admin/tag-groups/root/values/one", headers=self.admin_headers)

        self.assertEqual(duplicate_parent.status_code, 400)
        self.assertEqual(cycle.status_code, 400)
        self.assertEqual(free_parent_update.status_code, 400)
        self.assertEqual(required_unbind.status_code, 400)
        self.assertEqual(parent_value_delete.status_code, 400)

        updated = self.client.patch(
            "/api/admin/tag-groups/child",
            headers=self.admin_headers,
            json={"display_name": "child", "description": "", "sort_order": 0, "required": False, "free_form": False},
        )
        unbound = self.client.delete("/api/admin/tag-cascades/child", headers=self.admin_headers)
        rebound = self.attach("other", "two", "child")

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(unbound.status_code, 200)
        self.assertEqual(rebound.status_code, 200)

    def test_reconfiguration_reports_orphans_and_revokes_tag_permission(self):
        self.create_group("root", values=("enabled",))
        self.create_group("child", values=("value",))
        skill = self.client.post(
            "/api/skills",
            json={**self.skill_payload("cascade-diagnostic"), "tags": [{"group_id": "child", "value": "value"}]},
        ).json()
        missing_required_skill = self.client.post(
            "/api/skills",
            json={**self.skill_payload("cascade-missing-required"), "tags": [{"group_id": "root", "value": "enabled"}]},
        ).json()
        self.client.post(
            "/api/admin/role-assignments",
            headers=self.admin_headers,
            json={
                "subject_type": "user",
                "subject_id": "tag-reviewer",
                "resource_type": "skill_tag",
                "resource_id": self.tag_resource_id("child", "value"),
                "role": "evaluator",
            },
        )
        before = self.client.get(
            f"/api/skills/{skill['skill_id']}/capabilities",
            headers={"X-SkillHub-Actor": "tag-reviewer"},
        ).json()

        self.assertTrue(before["permissions"]["eval.run"])
        self.assertEqual(self.attach("root", "enabled", "child").status_code, 200)
        required_update = self.client.patch(
            "/api/admin/tag-groups/child",
            headers=self.admin_headers,
            json={"display_name": "child", "description": "", "sort_order": 0, "required": True, "free_form": False},
        )
        self.assertEqual(required_update.status_code, 200)

        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        after = self.client.get(
            f"/api/skills/{skill['skill_id']}/capabilities",
            headers={"X-SkillHub-Actor": "tag-reviewer"},
        ).json()
        overview = self.client.get("/api/admin/tag-cascades", headers=self.admin_headers).json()
        diagnostic = next(item for item in overview["diagnostics"] if item["group_id"] == "child")

        self.assertFalse(detail["skill"]["tags"][0]["path_valid"])
        self.assertFalse(after["permissions"]["eval.run"])
        self.assertEqual(diagnostic["orphaned_skill_ids"], [skill["skill_id"]])
        self.assertEqual(diagnostic["missing_required_skill_ids"], [missing_required_skill["skill_id"]])

    def test_admin_cascade_api_requires_admin_key(self):
        denied = self.client.get("/api/admin/tag-cascades")

        self.assertEqual(denied.status_code, 403)
