from __future__ import annotations

from sqlalchemy import func, select

from skillhub.models.schema import tables
from tests import test_workflows as workflow_test_helpers
from tests.api_command_test_case import ApiCommandTestCase


class WorkflowSyncApiTest(ApiCommandTestCase):
    actor_headers = {"X-SkillHub-Actor": "workflow-owner"}

    def test_generator_catalog_has_exactly_one_three_file_default(self):
        response = self.client.get("/api/workflow-skill-generators", headers=self.actor_headers)

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        generators = payload["generators"]
        self.assertEqual(
            [(item["id"], item["version"]) for item in generators],
            [
                ("builtin.single-file", "workflow-skill-v4.1.1"),
                ("builtin.three-file", "2.1.1"),
                ("builtin.node-split", "2.1.1"),
            ],
        )
        defaults = [item for item in generators if item["default"]]
        self.assertEqual([item["id"] for item in defaults], ["builtin.three-file"])
        self.assertEqual(payload["default_generator_id"], "builtin.three-file")
        self.assertTrue(all(item["options_schema"]["additionalProperties"] is False for item in generators))

    def test_preview_contains_bundle_diff_and_action_without_writes(self):
        created, saved = self._create_valid_workflow("workflow-preview")
        before = self._write_counts()

        response = self._preview(
            created["skill_id"],
            revision=saved["revision"],
            generator_id="builtin.three-file",
        )

        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertEqual(preview["workflow_revision"], 2)
        self.assertEqual(preview["generator"]["id"], "builtin.three-file")
        self.assertEqual(preview["generator_options"], {})
        self.assertEqual(preview["action"]["mode"], "create")
        self.assertEqual(preview["action"]["next_version"], "0.0.2")
        self.assertEqual(
            {item["path"] for item in preview["files"]},
            {"SKILL.md", "references/workflow.md", "references/collections.md"},
        )
        self.assertTrue(all(item["content_text"] for item in preview["files"]))
        self.assertEqual(
            preview["diff"]["summary"],
            {"added": 2, "removed": 0, "changed": 1, "unchanged": 0, "binary": 0},
        )
        self.assertTrue(preview["diff"]["files"])
        self.assertEqual(len(preview["preview_digest"]), 64)
        self.assertEqual(self._write_counts(), before)

    def test_sync_rejects_tampered_digest_stale_revision_and_generator_version(self):
        created, saved = self._create_valid_workflow("workflow-stale-preview")
        skill_id = created["skill_id"]
        preview = self._preview(skill_id, revision=saved["revision"], generator_id="builtin.three-file").json()
        payload = self._sync_payload(preview, version="0.0.2")

        tampered = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers=self.actor_headers,
            json={**payload, "preview_digest": "0" * 64},
        )
        changed_generator = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers=self.actor_headers,
            json={**payload, "generator_version": "9.9.9"},
        )
        document = self.client.get(f"/api/skills/{skill_id}/workflow").json()["document"]
        document["workflow"]["metadata"]["code"] = "CHANGED-AFTER-PREVIEW"
        saved_again = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers=self.actor_headers,
            json={"document": document, "collection_changes": []},
        )
        stale = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync",
            headers=self.actor_headers,
            json=payload,
        )

        self.assertEqual(tampered.status_code, 409, tampered.text)
        self.assertEqual(changed_generator.status_code, 409, changed_generator.text)
        self.assertEqual(saved_again.status_code, 200, saved_again.text)
        self.assertEqual(saved_again.json()["revision"], 3)
        self.assertEqual(stale.status_code, 409, stale.text)
        with self.engine.connect() as connection:
            sync_count = connection.execute(select(func.count()).select_from(tables.workflow_syncs)).scalar_one()
            version_count = connection.execute(select(func.count()).select_from(tables.skill_versions)).scalar_one()
        self.assertEqual(sync_count, 0)
        self.assertEqual(version_count, 1)

    def test_preview_enforces_permission_and_strict_generator_options(self):
        created, saved = self._create_valid_workflow("workflow-preview-permission")
        skill_id = created["skill_id"]
        payload = {
            "expected_workflow_revision": saved["revision"],
            "generator_id": "builtin.three-file",
            "generator_options": {},
        }

        denied = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync-preview",
            headers={"X-SkillHub-Actor": "viewer"},
            json=payload,
        )
        invalid_options = self.client.post(
            f"/api/skills/{skill_id}/workflow/sync-preview",
            headers=self.actor_headers,
            json={**payload, "generator_options": {"template": "custom"}},
        )

        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertEqual(invalid_options.status_code, 400, invalid_options.text)

    def test_same_revision_generates_and_exactly_reuses_all_three_generators(self):
        created, saved = self._create_valid_workflow("workflow-three-generators")
        skill_id = created["skill_id"]
        generated_ids: dict[str, str] = {}

        for index, generator_id in enumerate(
            ("builtin.single-file", "builtin.three-file", "builtin.node-split"),
            start=2,
        ):
            preview_response = self._preview(skill_id, revision=saved["revision"], generator_id=generator_id)
            self.assertEqual(preview_response.status_code, 200, preview_response.text)
            preview = preview_response.json()
            self.assertEqual(preview["action"]["mode"], "create")
            synced = self.client.post(
                f"/api/skills/{skill_id}/workflow/sync",
                headers=self.actor_headers,
                json=self._sync_payload(preview, version=f"0.0.{index}"),
            )
            self.assertEqual(synced.status_code, 200, synced.text)
            self.assertEqual(synced.json()["mode"], "created")
            generated_ids[generator_id] = synced.json()["skill_version_id"]

            repeated_preview = self._preview(skill_id, revision=saved["revision"], generator_id=generator_id).json()
            self.assertEqual(repeated_preview["action"]["mode"], "already_current")
            repeated = self.client.post(
                f"/api/skills/{skill_id}/workflow/sync",
                headers=self.actor_headers,
                json=self._sync_payload(repeated_preview, version="9.9.9"),
            )
            self.assertEqual(repeated.status_code, 200, repeated.text)
            self.assertEqual(repeated.json()["mode"], "already_current")
            self.assertEqual(repeated.json()["skill_version_id"], generated_ids[generator_id])

        detail = self.client.get(f"/api/skills/{skill_id}").json()
        generated_versions = [item for item in detail["versions"] if item.get("workflow_sync")]
        self.assertEqual(len(detail["versions"]), 4)
        self.assertEqual(
            {item["workflow_sync"]["generator_id"] for item in generated_versions},
            set(generated_ids),
        )
        self.assertEqual({item["workflow_sync"]["workflow_revision"] for item in generated_versions}, {2})
        self.assertEqual(detail["workflow"]["status"], "in_sync")
        with self.engine.connect() as connection:
            audit_payloads = connection.execute(
                select(tables.audit_events.c.payload).where(tables.audit_events.c.action == "workflow.synced")
            ).scalars().all()
        self.assertEqual({payload["generator_id"] for payload in audit_payloads}, set(generated_ids))
        self.assertTrue(
            all(
                {"generator_version", "generator_options", "generator_options_digest", "preview_digest"} <= payload.keys()
                for payload in audit_payloads
            )
        )

    def _create_valid_workflow(self, slug: str) -> tuple[dict, dict]:
        helper = workflow_test_helpers.WorkflowApiTest
        created = helper._create_workflow(self, slug)
        skill_id = created["skill_id"]
        detail = self.client.get(f"/api/skills/{skill_id}/workflow").json()
        definition = helper._definition(self)
        document = helper._valid_document(self, detail["document"], definition)
        saved = self.client.put(
            f"/api/skills/{skill_id}/workflow",
            headers=self.actor_headers,
            json={
                "document": document,
                "collection_changes": [{"operation": "create", "definition": definition}],
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        return created, saved.json()

    def _preview(self, skill_id: str, *, revision: int, generator_id: str):
        return self.client.post(
            f"/api/skills/{skill_id}/workflow/sync-preview",
            headers=self.actor_headers,
            json={
                "expected_workflow_revision": revision,
                "generator_id": generator_id,
                "generator_options": {},
            },
        )

    def _sync_payload(self, preview: dict, *, version: str) -> dict:
        return {
            "version": version,
            "display_name": None,
            "change_summary": "同步 Workflow Generator。",
            "expected_workflow_revision": preview["workflow_revision"],
            "generator_id": preview["generator"]["id"],
            "generator_version": preview["generator"]["version"],
            "generator_options": preview["generator_options"],
            "preview_digest": preview["preview_digest"],
        }

    def _write_counts(self) -> tuple[int, int, int, int]:
        with self.engine.connect() as connection:
            return tuple(
                connection.execute(select(func.count()).select_from(table)).scalar_one()
                for table in (tables.artifacts, tables.skill_versions, tables.workflow_syncs, tables.audit_events)
            )
