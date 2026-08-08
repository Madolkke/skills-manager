from __future__ import annotations

import logging
from typing import Any

import yaml

from skillhub.models.entities import new_id
from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.rules.workflows import (
    format_workflow_document,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    workflow_log_schema_catalog,
)
from skillhub.models.rules.workflows.expression import expression_contract, validate_expression
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase
from skillhub.services.workflow_syncs import WorkflowSyncServiceMixin

logger = logging.getLogger(__name__)


class WorkflowService(WorkflowSyncServiceMixin, ServiceBase[SkillHubStore]):
    def log_schema(self) -> dict[str, Any]:
        """Return the fixed SQL table contract for log Collections."""
        return workflow_log_schema_catalog()

    def expression_contract(self) -> dict[str, Any]:
        """Return the public static-analysis contract for Workflow expressions."""
        return expression_contract()

    def validate_expression(self, *, source: str, environment: dict[str, Any]) -> dict[str, Any]:
        """Validate an expression without evaluating it or causing external effects."""
        return validate_expression(source, environment)

    def validate_expressions(self, *, expressions: list[dict[str, str]], environment: dict[str, Any]) -> dict[str, object]:
        """Validate an ordered expression batch against one shared type environment."""
        return {
            "validations": [
                {"id": item["id"], **validate_expression(item["source"], environment)}
                for item in expressions
            ]
        }

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
        bundle = parse_skill_import_source({"kind": "files", "name": slug, "files": [{"path": "SKILL.md", "content_text": f"---\n{frontmatter}\n---\n"}]})
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
        normalized_changes = [{"operation": item["operation"], "definition": item["definition"]} for item in collection_changes]
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
