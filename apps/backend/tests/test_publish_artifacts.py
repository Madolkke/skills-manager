from __future__ import annotations

import json

from skillhub.models.entities import ContentRef
from skillhub.models.errors import InvariantError, NotFoundError
from tests.store_test_case import SqlStoreTestCase


class PublishArtifactReadModelTest(SqlStoreTestCase):
    def test_publish_artifact_contains_sorted_text_and_binary_files(self):
        manifest = {
            "files": [
                {
                    "path": "references/data.bin",
                    "sha256": "binary-digest",
                    "size_bytes": 2,
                    "content_base64": "AAE=",
                    "binary": True,
                },
                {
                    "path": "SKILL.md",
                    "sha256": "text-digest",
                    "size_bytes": 4,
                    "content_text": "test",
                },
            ]
        }
        version_id, artifact = self._create_artifact_version("publish-artifact-valid", json.dumps(manifest))

        result = self.store.publish_release_artifact(skill_version_id=version_id)

        self.assertEqual(result["id"], artifact["id"])
        self.assertEqual(result["digest"], artifact["digest"])
        self.assertEqual([file["path"] for file in result["files"]], ["SKILL.md", "references/data.bin"])
        self.assertEqual(result["files"][0]["content_text"], "test")
        self.assertFalse(result["files"][0]["binary"])
        self.assertEqual(result["files"][1]["content_base64"], "AAE=")
        self.assertTrue(result["files"][1]["binary"])

    def test_publish_artifact_requires_artifact_content_ref(self):
        skill = self.store.create_skill(
            slug="publish-artifact-memory",
            owner_ref="skillhub-lab",
            content_ref=ContentRef(kind="skill_bundle", locator="memory:bundle", digest="memory-digest"),
            change_summary="Initial version.",
            actor="tester",
        )

        with self.assertRaisesRegex(InvariantError, "has no skill_bundle artifact"):
            self.store.publish_release_artifact(skill_version_id=skill.skill_version_id)

    def test_publish_artifact_requires_existing_artifact(self):
        skill = self.store.create_skill(
            slug="publish-artifact-missing",
            owner_ref="skillhub-lab",
            content_ref=ContentRef(kind="artifact", locator="artifact:missing", digest="missing-digest"),
            change_summary="Initial version.",
            actor="tester",
        )

        with self.assertRaisesRegex(NotFoundError, "Artifact not found"):
            self.store.publish_release_artifact(skill_version_id=skill.skill_version_id)

    def test_publish_artifact_requires_skill_bundle_kind(self):
        version_id, _artifact = self._create_artifact_version(
            "publish-artifact-wrong-kind",
            json.dumps({"files": [self._text_file()]}),
            kind="workflow_source",
        )

        with self.assertRaisesRegex(InvariantError, "is not a skill_bundle"):
            self.store.publish_release_artifact(skill_version_id=version_id)

    def test_publish_artifact_requires_matching_digest(self):
        content = json.dumps({"files": [self._text_file()]})
        artifact = self.store.create_text_artifact(
            kind="skill_bundle",
            namespace="test:publish-artifact-digest",
            content=content,
            actor="tester",
        )
        skill = self.store.create_skill(
            slug="publish-artifact-digest",
            owner_ref="skillhub-lab",
            content_ref=ContentRef(kind="artifact", locator=f"artifact:{artifact['id']}", digest="wrong-digest"),
            change_summary="Initial version.",
            actor="tester",
        )

        with self.assertRaisesRegex(InvariantError, "digest does not match"):
            self.store.publish_release_artifact(skill_version_id=skill.skill_version_id)

    def test_publish_artifact_requires_readable_manifest_with_files(self):
        for index, content in enumerate(["not-json", json.dumps({"files": []})], start=1):
            with self.subTest(content=content):
                version_id, _artifact = self._create_artifact_version(f"publish-artifact-invalid-{index}", content)

                with self.assertRaisesRegex(InvariantError, "has no readable files"):
                    self.store.publish_release_artifact(skill_version_id=version_id)

    def _create_artifact_version(self, slug: str, content: str, *, kind: str = "skill_bundle"):
        artifact = self.store.create_text_artifact(
            kind=kind,
            namespace=f"test:{slug}",
            content=content,
            actor="tester",
        )
        skill = self.store.create_skill(
            slug=slug,
            owner_ref="skillhub-lab",
            content_ref=ContentRef(
                kind="artifact",
                locator=f"artifact:{artifact['id']}",
                digest=artifact["digest"],
            ),
            change_summary="Initial version.",
            actor="tester",
        )
        return skill.skill_version_id, artifact

    def _text_file(self) -> dict:
        return {
            "path": "SKILL.md",
            "sha256": "text-digest",
            "size_bytes": 4,
            "content_text": "test",
        }
