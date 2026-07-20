from __future__ import annotations

import json
import logging
from typing import Any

import yaml

from skillhub.models.entities import new_id
from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.rules.workflows import (
    GENERATOR_VERSION,
    format_workflow_document,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    render_skill_markdown,
    validate_workflow_document,
)
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase

logger = logging.getLogger(__name__)


class WorkflowService(ServiceBase[SkillHubStore]):
    def create_workflow_skill(self, *, slug: str, owner_ref: str, description: str, tags: list[Any], actor: str) -> dict[str, Any]:
        workflow_id = new_id("workflow")
        clean_description = description.strip()
        if not clean_description:
            raise FieldInvariantError(
                "Workflow description is required.",
                [FieldError(field="description", message="请填写 Workflow 说明。", code="workflow.description_required")],
            )
        document = normalize_workflow_document(
            {
                "documentType": "workflow_bundle",
                "workflow": {
                    "id": workflow_id,
                    "revision": 1,
                    "metadata": {
                        "name": slug,
                        "code": "",
                        "description": clean_description,
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
        )
        frontmatter = yaml.safe_dump({"name": slug, "description": clean_description}, allow_unicode=True, sort_keys=False, width=1000).strip()
        bundle = parse_skill_import_source(
            {"kind": "files", "name": slug, "files": [{"path": "SKILL.md", "content_text": f"---\n{frontmatter}\n---\n"}]}
        )
        logger.info("creating workflow skill slug=%s actor=%s", slug, actor)
        return self.store.create_workflow_skill(
            slug=slug,
            owner_ref=owner_ref,
            manifest_text=bundle.manifest_text,
            document=document,
            tags=tags,
            actor=actor,
        )

    def workflow_detail(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        return self.store.workflow_detail(skill_id=skill_id, actor=actor)

    def formatted_workflow(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        detail = self.store.workflow_detail(skill_id=skill_id, actor=actor)
        return format_workflow_document(detail["document"])

    def list_collections(self, *, skill_id: str, actor: str) -> dict[str, Any]:
        return {"definitions": self.store.list_workflow_collections(skill_id=skill_id, actor=actor)}

    def save_workflow(self, *, skill_id: str, document: dict[str, Any], collection_changes: list[dict[str, Any]], actor: str) -> dict[str, Any]:
        normalized = normalize_workflow_document(document)
        normalized_changes = [
            {"operation": item["operation"], "definition": item["definition"]}
            for item in collection_changes
        ]
        self.store.save_workflow(skill_id=skill_id, document=normalized, collection_changes=normalized_changes, actor=actor)
        return self.store.workflow_detail(skill_id=skill_id, actor=actor)

    def import_workflow_bundle(self, *, skill_id: str, bundle: dict[str, Any], actor: str) -> dict[str, Any]:
        normalized = normalize_workflow_import_bundle(bundle)
        result = self.store.import_workflow_bundle(skill_id=skill_id, bundle=normalized, actor=actor)
        detail = self.store.workflow_detail(skill_id=skill_id, actor=actor)
        detail["import_result"] = {"collection_mappings": result["collection_mappings"]}
        logger.info(
            "workflow import completed skill_id=%s revision=%s collection_count=%s actor=%s",
            skill_id,
            detail["revision"],
            len(result["collection_mappings"]),
            actor,
        )
        return detail

    def update_metadata(self, *, skill_id: str, metadata: dict[str, Any], actor: str) -> dict[str, Any]:
        detail = self.store.workflow_detail(skill_id=skill_id, actor=actor)
        document = detail["document"]
        document["workflow"]["metadata"] = metadata
        return self.save_workflow(skill_id=skill_id, document=document, collection_changes=[], actor=actor)

    def sync_workflow(self, *, skill_id: str, version: str, display_name: str | None, change_summary: str, actor: str) -> dict[str, Any]:
        detail = self.store.workflow_detail(skill_id=skill_id, actor=actor)
        document = detail["document"]
        issues = validate_workflow_document(document)
        errors = [item for item in issues if item["severity"] == "error"]
        if errors:
            raise FieldInvariantError(
                "Workflow contains validation errors and cannot be synced.",
                [FieldError(field="document", message=f"Workflow 仍有 {len(errors)} 个错误，请修复后再同步。", code="workflow.not_syncable")],
            )
        slug = self._skill_slug(skill_id)
        markdown = render_skill_markdown(slug=slug, document=document)
        bundle = parse_skill_import_source(
            {"kind": "files", "name": slug, "files": [{"path": "SKILL.md", "content_text": markdown}]}
        )
        source_text = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        logger.info("syncing workflow skill_id=%s revision=%s actor=%s", skill_id, detail["revision"], actor)
        return self.store.sync_workflow(
            skill_id=skill_id,
            version=version,
            display_name=display_name,
            change_summary=change_summary,
            manifest_text=bundle.manifest_text,
            source_text=source_text,
            generator_version=GENERATOR_VERSION,
            actor=actor,
        )

    def _skill_slug(self, skill_id: str) -> str:
        return self.store.skill_detail(skill_id)["skill"]["slug"]
