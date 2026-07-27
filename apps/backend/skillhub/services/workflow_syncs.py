from __future__ import annotations

import json
from typing import Any

from skillhub.models.entities import digest_text
from skillhub.models.errors import ConflictError, FieldError, FieldInvariantError, InvariantError
from skillhub.models.rules.bundle_diffs import build_bundle_file_diff
from skillhub.models.rules.skill_imports import ParsedSkillBundle, parse_skill_import_source
from skillhub.models.rules.workflows import (
    WORKFLOW_SKILL_GENERATORS,
    generate_workflow_skill,
    list_workflow_skill_generators,
)
from skillhub.models.store import SkillHubStore


class WorkflowSyncServiceMixin:
    store: SkillHubStore

    def workflow_skill_generators(self) -> dict[str, Any]:
        """Expose the immutable built-in Generator catalog to API clients."""
        descriptors = list_workflow_skill_generators()
        default = next(descriptor for descriptor in descriptors if descriptor.default)
        return {
            "generators": [descriptor.to_payload() for descriptor in descriptors],
            "default_generator_id": default.id,
        }

    def preview_workflow_sync(
        self,
        *,
        skill_id: str,
        expected_workflow_revision: int,
        generator_id: str,
        generator_options: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        """Generate and diff a Workflow Skill Bundle without persisting any facts."""
        prepared = self._prepare_sync(
            skill_id=skill_id,
            expected_workflow_revision=expected_workflow_revision,
            generator_id=generator_id,
            generator_options=generator_options,
            actor=actor,
        )
        return self._preview_payload(prepared)

    def sync_workflow(
        self,
        *,
        skill_id: str,
        version: str,
        display_name: str | None,
        change_summary: str,
        expected_workflow_revision: int,
        generator_id: str,
        generator_version: str,
        generator_options: dict[str, Any],
        preview_digest: str,
        actor: str,
    ) -> dict[str, Any]:
        """Regenerate a confirmed preview and atomically create or reactivate its version."""
        try:
            descriptor = WORKFLOW_SKILL_GENERATORS.get(generator_id).descriptor
        except InvariantError as exc:
            raise ConflictError("Generator 已不可用，请重新生成预览并确认。") from exc
        if descriptor.version != generator_version:
            raise ConflictError("Generator 版本已在预览后变化，请重新生成预览并确认。")
        prepared = self._prepare_sync(
            skill_id=skill_id,
            expected_workflow_revision=expected_workflow_revision,
            generator_id=generator_id,
            generator_options=generator_options,
            actor=actor,
        )
        if prepared["preview_digest"] != preview_digest:
            raise ConflictError("Workflow Skill 生成结果已在预览后变化，请重新生成预览并确认。")
        result = self.store.sync_workflow(
            skill_id=skill_id,
            version=version,
            display_name=display_name,
            change_summary=change_summary,
            manifest_text=prepared["bundle"].manifest_text,
            source_text=prepared["source_text"],
            expected_workflow_revision=expected_workflow_revision,
            expected_document_digest=prepared["document_digest"],
            generator_id=generator_id,
            generator_version=descriptor.version,
            generator_options=prepared["generator_options"],
            generator_options_digest=prepared["generator_options_digest"],
            preview_digest=preview_digest,
            actor=actor,
        )
        return {
            **result,
            "bundle_digest": prepared["bundle"].digest,
            "generator": descriptor.to_payload(),
        }

    def _prepare_sync(
        self,
        *,
        skill_id: str,
        expected_workflow_revision: int,
        generator_id: str,
        generator_options: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        """Read a permission-checked snapshot and deterministically generate its Bundle."""
        version_snapshot = self.store.skill_version_create_snapshot(skill_id=skill_id, actor=actor)
        workflow_detail = self.store.workflow_detail(skill_id=skill_id, actor=actor)
        if int(workflow_detail["revision"]) != expected_workflow_revision:
            raise ConflictError("Workflow 已发生变化，请重新生成预览。")
        errors = workflow_detail["validation"]["errors"]
        if errors:
            raise FieldInvariantError(
                "Workflow contains validation errors and cannot be synced.",
                [
                    FieldError(
                        field="document",
                        message=f"Workflow 仍有 {len(errors)} 个错误，请修复后再同步。",
                        code="workflow.not_syncable",
                    )
                ],
            )
        skill_detail = self.store.skill_detail(skill_id, actor=actor)
        document = workflow_detail["document"]
        source_text = _canonical_json(document)
        document_digest = digest_text(source_text)
        generated = generate_workflow_skill(
            slug=skill_detail["skill"]["slug"],
            document=document,
            generator_id=generator_id,
            generator_options=generator_options,
        )
        bundle = parse_skill_import_source(generated.import_source(name=skill_detail["skill"]["slug"]))
        options_digest = digest_text(_canonical_json(generated.options))
        preview_digest = _preview_digest(
            workflow_id=str(workflow_detail["id"]),
            workflow_revision=expected_workflow_revision,
            document_digest=document_digest,
            generator_id=generated.descriptor.id,
            generator_version=generated.descriptor.version,
            generator_options=generated.options,
            bundle_digest=bundle.digest,
        )
        return {
            "workflow_detail": workflow_detail,
            "skill_detail": skill_detail,
            "version_snapshot": version_snapshot,
            "source_text": source_text,
            "document_digest": document_digest,
            "generated": generated,
            "generator_options": generated.options,
            "generator_options_digest": options_digest,
            "bundle": bundle,
            "files": _manifest_files(bundle),
            "preview_digest": preview_digest,
        }

    def _preview_payload(self, prepared: dict[str, Any]) -> dict[str, Any]:
        """Project generated content, current-version diff, and expected action for the UI."""
        workflow_detail = prepared["workflow_detail"]
        skill_detail = prepared["skill_detail"]
        generated = prepared["generated"]
        current_version = skill_detail["summary"]["current_version"]
        current_files = current_version.get("bundle_files", []) if current_version else []
        warnings = [dict(item) for item in workflow_detail["validation"]["warnings"]]
        warnings.extend(
            {
                "severity": "warning",
                "path": "generator",
                "code": "workflow.generator_warning",
                "message": message,
            }
            for message in generated.warnings
        )
        return {
            "workflow_id": workflow_detail["id"],
            "workflow_revision": workflow_detail["revision"],
            "workflow_document_digest": prepared["document_digest"],
            "generator": generated.descriptor.to_payload(),
            "generator_options": prepared["generator_options"],
            "generator_options_digest": prepared["generator_options_digest"],
            "files": prepared["files"],
            "bundle_digest": prepared["bundle"].digest,
            "diff": build_bundle_file_diff(current_files, prepared["files"]),
            "warnings": warnings,
            "action": _preview_action(
                skill_detail=skill_detail,
                version_snapshot=prepared["version_snapshot"],
                workflow_id=str(workflow_detail["id"]),
                workflow_revision=int(workflow_detail["revision"]),
                generator_id=generated.descriptor.id,
                generator_version=generated.descriptor.version,
                generator_options_digest=prepared["generator_options_digest"],
            ),
            "preview_digest": prepared["preview_digest"],
        }


def _preview_action(
    *,
    skill_detail: dict[str, Any],
    version_snapshot: dict[str, Any],
    workflow_id: str,
    workflow_revision: int,
    generator_id: str,
    generator_version: str,
    generator_options_digest: str,
) -> dict[str, Any]:
    """Resolve whether an exact generated result would be created or reused."""
    existing = next(
        (
            version
            for version in skill_detail["versions"]
            if _sync_matches(
                version.get("workflow_sync"),
                workflow_id=workflow_id,
                workflow_revision=workflow_revision,
                generator_id=generator_id,
                generator_version=generator_version,
                generator_options_digest=generator_options_digest,
            )
        ),
        None,
    )
    if existing is None:
        return {
            "mode": "create",
            "skill_version_id": None,
            "version": None,
            "version_number": None,
            "display_name": None,
            "next_version": version_snapshot["next_version"],
        }
    current_version_id = skill_detail["skill"]["current_version_id"]
    return {
        "mode": "already_current" if existing["id"] == current_version_id else "reactivate",
        "skill_version_id": existing["id"],
        "version": existing["version"],
        "version_number": existing["version_number"],
        "display_name": existing.get("display_name"),
        "next_version": None,
    }


def _sync_matches(sync: object, **expected: object) -> bool:
    """Compare a SkillVersion WorkflowSync read model with one exact Generator key."""
    return isinstance(sync, dict) and all(sync.get(key) == value for key, value in expected.items())


def _manifest_files(bundle: ParsedSkillBundle) -> list[dict[str, Any]]:
    """Read normalized file payloads from a parser-validated Bundle manifest."""
    files = json.loads(bundle.manifest_text)["files"]
    return [
        {
            **file,
            "binary": bool(file.get("binary", "content_base64" in file)),
            "content_text": file.get("content_text"),
            "content_base64": file.get("content_base64"),
        }
        for file in files
    ]


def _preview_digest(
    *,
    workflow_id: str,
    workflow_revision: int,
    document_digest: str,
    generator_id: str,
    generator_version: str,
    generator_options: dict[str, Any],
    bundle_digest: str,
) -> str:
    """Bind a preview confirmation to Workflow, Generator, options, and output facts."""
    return digest_text(
        _canonical_json(
            {
                "workflow_id": workflow_id,
                "workflow_revision": workflow_revision,
                "workflow_document_digest": document_digest,
                "generator_id": generator_id,
                "generator_version": generator_version,
                "generator_options": generator_options,
                "bundle_digest": bundle_digest,
            }
        )
    )


def _canonical_json(value: object) -> str:
    """Serialize digest evidence in one stable UTF-8 JSON representation."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
