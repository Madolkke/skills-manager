from __future__ import annotations

import json

from sqlalchemy import func, select, update

from skillhub.models.entities import ContentRef, digest_text
from skillhub.models.errors import ConflictError, FieldInvariantError
from skillhub.models.schema import tables
from tests.store_test_case import SqlStoreTestCase

EMPTY_OPTIONS_DIGEST = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


class WorkflowSyncStoreTest(SqlStoreTestCase):
    def test_generator_identity_reuse_and_sync_status_follow_current_version(self) -> None:
        created, source_text = self._create_workflow("generator-identity")
        skill_id = created["skill_id"]
        document_digest = digest_text(source_text)

        single_file = self._sync(
            skill_id=skill_id,
            source_text=source_text,
            document_digest=document_digest,
            generator_id="builtin.single-file",
            generator_version="workflow-skill-v3",
            version="0.0.2",
        )
        three_file = self._sync(
            skill_id=skill_id,
            source_text=source_text,
            document_digest=document_digest,
            generator_id="builtin.three-file",
            generator_version="1.0.0",
            version="0.0.3",
        )
        reactivated = self._sync(
            skill_id=skill_id,
            source_text=source_text,
            document_digest=document_digest,
            generator_id="builtin.single-file",
            generator_version="workflow-skill-v3",
            version="9.9.9",
        )

        assert single_file["mode"] == "created"
        assert three_file["mode"] == "created"
        assert reactivated["mode"] == "reactivated"
        assert reactivated["skill_version_id"] == single_file["skill_version_id"]
        assert self.store.workflow_detail(skill_id=skill_id, actor="owner")["sync"]["status"] == "in_sync"
        with self.engine.connect() as connection:
            count = connection.scalar(
                select(func.count()).select_from(tables.workflow_syncs).where(
                    tables.workflow_syncs.c.workflow_id == created["workflow_id"]
                )
            )
        assert count == 2
        legacy_preview_digest = digest_text("bundle:builtin.single-file")
        with self.engine.begin() as connection:
            connection.execute(
                update(tables.workflow_syncs)
                .where(tables.workflow_syncs.c.skill_version_id == single_file["skill_version_id"])
                .values(preview_digest=legacy_preview_digest)
            )

        manual = self.store.create_skill_version(
            skill_id=skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:manual", digest="manual-one"),
            change_summary="Manual edit.",
            actor="owner",
            make_current=True,
            version="0.0.4",
        )
        assert self.store.workflow_detail(skill_id=skill_id, actor="owner")["sync"]["status"] == "skill_changed"

        reactivated_again = self._sync(
            skill_id=skill_id,
            source_text=source_text,
            document_digest=document_digest,
            generator_id="builtin.single-file",
            generator_version="workflow-skill-v3",
            version="9.9.9",
        )
        assert reactivated_again["skill_version_id"] == single_file["skill_version_id"]
        assert reactivated_again["preview_digest"] == legacy_preview_digest
        detail = self.store.workflow_detail(skill_id=skill_id, actor="owner")
        changed_document = detail["document"]
        changed_document["workflow"]["metadata"]["description"] = "Changed after sync."
        saved = self.store.save_workflow(
            skill_id=skill_id,
            document=changed_document,
            collection_changes=[],
            actor="owner",
        )
        assert saved["revision"] == 2
        assert self.store.workflow_detail(skill_id=skill_id, actor="owner")["sync"]["status"] == "workflow_changed"

        self.store.create_skill_version(
            skill_id=skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:manual-two", digest="manual-two"),
            change_summary="Manual edit after Workflow edit.",
            actor="owner",
            make_current=True,
            version="0.0.5",
        )
        assert manual.skill_version_id
        assert self.store.workflow_detail(skill_id=skill_id, actor="owner")["sync"]["status"] == "diverged"

    def test_stale_preview_conflict_happens_before_any_sync_write(self) -> None:
        created, source_text = self._create_workflow("stale-preview")
        with self.engine.connect() as connection:
            artifact_count = connection.scalar(select(func.count()).select_from(tables.artifacts))

        with self.assertRaises(ConflictError):
            self._sync(
                skill_id=created["skill_id"],
                source_text=source_text,
                document_digest="stale-document-digest",
                generator_id="builtin.three-file",
                generator_version="1.0.0",
                version="0.0.2",
            )

        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(tables.artifacts)) == artifact_count
            assert connection.scalar(select(func.count()).select_from(tables.workflow_syncs)) == 0

    def test_generator_output_drift_conflicts_without_reactivating_existing_version(self) -> None:
        created, source_text = self._create_workflow("generator-output-drift")
        first = self._sync(
            skill_id=created["skill_id"],
            source_text=source_text,
            document_digest=digest_text(source_text),
            generator_id="builtin.three-file",
            generator_version="1.0.0",
            version="0.0.2",
            manifest_text="stable generated bundle",
        )
        self.store.create_skill_version(
            skill_id=created["skill_id"],
            content_ref=ContentRef(kind="skill_bundle", locator="memory:manual", digest="manual"),
            change_summary="Move current away from generated version.",
            actor="owner",
            make_current=True,
            version="0.0.3",
        )
        with self.engine.connect() as connection:
            artifact_count = connection.scalar(select(func.count()).select_from(tables.artifacts))
            audit_count = connection.scalar(select(func.count()).select_from(tables.audit_events))

        with self.assertRaises(ConflictError):
            self._sync(
                skill_id=created["skill_id"],
                source_text=source_text,
                document_digest=digest_text(source_text),
                generator_id="builtin.three-file",
                generator_version="1.0.0",
                version="9.9.9",
                manifest_text="drifted generated bundle",
            )

        detail = self.store.skill_detail(created["skill_id"], actor="owner")
        assert detail["skill"]["current_version_id"] != first["skill_version_id"]
        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(tables.artifacts)) == artifact_count
            assert connection.scalar(select(func.count()).select_from(tables.audit_events)) == audit_count
            assert connection.scalar(select(func.count()).select_from(tables.workflow_syncs)) == 1

    def test_version_conflict_rolls_back_artifacts_and_sync_record(self) -> None:
        created, source_text = self._create_workflow("sync-version-rollback")
        self.store.create_skill_version(
            skill_id=created["skill_id"],
            content_ref=ContentRef(kind="skill_bundle", locator="memory:existing", digest="existing"),
            change_summary="Reserve the sync version.",
            actor="owner",
            make_current=False,
            version="0.0.2",
        )
        with self.engine.connect() as connection:
            artifact_count = connection.scalar(select(func.count()).select_from(tables.artifacts))
            audit_count = connection.scalar(select(func.count()).select_from(tables.audit_events))

        with self.assertRaises(FieldInvariantError):
            self._sync(
                skill_id=created["skill_id"],
                source_text=source_text,
                document_digest=digest_text(source_text),
                generator_id="builtin.node-split",
                generator_version="1.0.0",
                version="0.0.2",
            )

        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(tables.artifacts)) == artifact_count
            assert connection.scalar(select(func.count()).select_from(tables.audit_events)) == audit_count
            assert connection.scalar(select(func.count()).select_from(tables.workflow_syncs)) == 0
        assert self.store.workflow_detail(skill_id=created["skill_id"], actor="owner")["sync"]["status"] == "never_synced"

    def test_skill_version_read_model_exposes_generator_evidence(self) -> None:
        created, source_text = self._create_workflow("generator-read-model")
        result = self._sync(
            skill_id=created["skill_id"],
            source_text=source_text,
            document_digest=digest_text(source_text),
            generator_id="builtin.node-split",
            generator_version="1.0.0",
            version="0.0.2",
        )

        detail = self.store.skill_detail(created["skill_id"], actor="owner")
        version = next(item for item in detail["versions"] if item["id"] == result["skill_version_id"])
        assert version["workflow_sync"] == {
            "workflow_id": created["workflow_id"],
            "workflow_revision": 1,
            "generator_id": "builtin.node-split",
            "generator_version": "1.0.0",
            "generator_options": {},
            "generator_options_digest": EMPTY_OPTIONS_DIGEST,
            "preview_digest": "preview-builtin.node-split",
            "created_at": version["workflow_sync"]["created_at"],
        }

    def _create_workflow(self, slug: str) -> tuple[dict, str]:
        document = {
            "documentType": "workflow_bundle",
            "workflow": {
                "id": f"workflow-{slug}",
                "revision": 1,
                "metadata": {
                    "name": slug,
                    "code": "",
                    "description": "Workflow store test.",
                    "symptom": "",
                    "industry": "",
                    "device": "",
                    "versions": [],
                },
                "inputs": [],
                "deviceRoles": [],
                "nodes": [],
            },
            "collectionSnapshots": [],
        }
        created = self.store.create_workflow_skill(
            slug=slug,
            owner_ref="owner",
            manifest_text="bootstrap bundle",
            document=document,
            tags=[],
            actor="owner",
        )
        detail = self.store.workflow_detail(skill_id=created["skill_id"], actor="owner")
        source_text = json.dumps(detail["document"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return created, source_text

    def _sync(
        self,
        *,
        skill_id: str,
        source_text: str,
        document_digest: str,
        generator_id: str,
        generator_version: str,
        version: str,
        manifest_text: str | None = None,
    ) -> dict:
        return self.store.sync_workflow(
            skill_id=skill_id,
            version=version,
            display_name=None,
            change_summary="Generated from Workflow.",
            manifest_text=manifest_text or f"bundle:{generator_id}",
            source_text=source_text,
            expected_workflow_revision=1,
            expected_document_digest=document_digest,
            generator_id=generator_id,
            generator_version=generator_version,
            generator_options={},
            generator_options_digest=EMPTY_OPTIONS_DIGEST,
            preview_digest=f"preview-{generator_id}",
            actor="owner",
        )
