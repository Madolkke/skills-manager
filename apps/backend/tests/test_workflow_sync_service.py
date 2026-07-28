from __future__ import annotations

from copy import deepcopy

import pytest

from skillhub.models.errors import ConflictError, InvariantError, PermissionDeniedError
from skillhub.models.rules.workflows import normalize_workflow_document, validate_workflow_document
from skillhub.services import WorkflowService


def test_generator_catalog_declares_server_default() -> None:
    service = WorkflowService(_PreviewStore())  # type: ignore[arg-type]

    catalog = service.workflow_skill_generators()

    assert catalog["default_generator_id"] == "builtin.three-file"
    assert [item["id"] for item in catalog["generators"] if item["default"]] == ["builtin.three-file"]


def test_preview_is_read_only_and_returns_bundle_diff_and_create_action() -> None:
    store = _PreviewStore()
    service = WorkflowService(store)  # type: ignore[arg-type]

    preview = service.preview_workflow_sync(
        skill_id="skill_1",
        expected_workflow_revision=3,
        generator_id="builtin.three-file",
        generator_options={},
        actor="owner",
    )

    assert store.sync_calls == []
    assert [file["path"] for file in preview["files"]] == [
        "SKILL.md",
        "references/collections.md",
        "references/workflow.md",
    ]
    assert preview["action"] == {
        "mode": "create",
        "skill_version_id": None,
        "version": None,
        "version_number": None,
        "display_name": None,
        "next_version": "0.0.2",
    }
    assert preview["diff"]["summary"]["added"] == 2
    assert preview["diff"]["summary"]["changed"] == 1
    assert len(preview["preview_digest"]) == 64


def test_confirmed_preview_passes_complete_generator_evidence_to_store() -> None:
    store = _PreviewStore()
    service = WorkflowService(store)  # type: ignore[arg-type]
    preview = _preview(service)

    result = service.sync_workflow(
        skill_id="skill_1",
        version="0.0.2",
        display_name="Generated",
        change_summary="从 Workflow 生成。",
        expected_workflow_revision=3,
        generator_id="builtin.three-file",
        generator_version="2.0.0",
        generator_options={},
        preview_digest=preview["preview_digest"],
        actor="owner",
    )

    assert result["bundle_digest"] == preview["bundle_digest"]
    assert result["generator"]["id"] == "builtin.three-file"
    assert len(store.sync_calls) == 1
    write = store.sync_calls[0]
    assert write["expected_workflow_revision"] == 3
    assert write["expected_document_digest"] == preview["workflow_document_digest"]
    assert write["generator_options"] == {}
    assert write["generator_options_digest"] == preview["generator_options_digest"]
    assert write["preview_digest"] == preview["preview_digest"]


@pytest.mark.parametrize(
    ("revision", "generator_version", "preview_digest"),
    (
        (4, "2.0.0", "current"),
        (3, "1.0.0", "current"),
        (3, "2.0.0", "0" * 64),
    ),
)
def test_sync_rejects_stale_or_tampered_confirmation(
    revision: int,
    generator_version: str,
    preview_digest: str,
) -> None:
    store = _PreviewStore()
    service = WorkflowService(store)  # type: ignore[arg-type]
    preview = _preview(service)
    digest = preview["preview_digest"] if preview_digest == "current" else preview_digest

    with pytest.raises(ConflictError):
        service.sync_workflow(
            skill_id="skill_1",
            version="0.0.2",
            display_name=None,
            change_summary="sync",
            expected_workflow_revision=revision,
            generator_id="builtin.three-file",
            generator_version=generator_version,
            generator_options={},
            preview_digest=digest,
            actor="owner",
        )

    assert store.sync_calls == []


def test_preview_rejects_unknown_generator_options_and_missing_permission() -> None:
    store = _PreviewStore()
    service = WorkflowService(store)  # type: ignore[arg-type]

    with pytest.raises(InvariantError, match="does not support options"):
        service.preview_workflow_sync(
            skill_id="skill_1",
            expected_workflow_revision=3,
            generator_id="builtin.three-file",
            generator_options={"template": "custom"},
            actor="owner",
        )

    store.permission_denied = True
    with pytest.raises(PermissionDeniedError):
        _preview(service)


def _preview(service: WorkflowService) -> dict:
    return service.preview_workflow_sync(
        skill_id="skill_1",
        expected_workflow_revision=3,
        generator_id="builtin.three-file",
        generator_options={},
        actor="owner",
    )


class _PreviewStore:
    def __init__(self) -> None:
        self.document = _document()
        self.sync_calls: list[dict] = []
        self.permission_denied = False

    def skill_version_create_snapshot(self, **_kwargs) -> dict:
        if self.permission_denied:
            raise PermissionDeniedError("denied")
        return {"skill_id": "skill_1", "next_version_number": 2, "next_version": "0.0.2"}

    def workflow_detail(self, **_kwargs) -> dict:
        issues = validate_workflow_document(self.document)
        return {
            "id": "workflow_1",
            "revision": 3,
            "document": deepcopy(self.document),
            "validation": {
                "errors": [item for item in issues if item["severity"] == "error"],
                "warnings": [item for item in issues if item["severity"] == "warning"],
            },
        }

    def skill_detail(self, _skill_id: str, actor: str) -> dict:
        assert actor == "owner"
        return {
            "skill": {"id": "skill_1", "slug": "preview-skill", "current_version_id": "skillver_1"},
            "summary": {
                "current_version": {
                    "id": "skillver_1",
                    "bundle_files": [
                        {
                            "path": "SKILL.md",
                            "sha256": "old",
                            "size_bytes": 3,
                            "binary": False,
                            "content_text": "old",
                        }
                    ],
                }
            },
            "versions": [],
        }

    def sync_workflow(self, **kwargs) -> dict:
        self.sync_calls.append(kwargs)
        return {
            "mode": "created",
            "skill_id": "skill_1",
            "skill_version_id": "skillver_2",
            "workflow_revision": 3,
            "generator_id": kwargs["generator_id"],
            "generator_version": kwargs["generator_version"],
            "generator_options": kwargs["generator_options"],
            "generator_options_digest": kwargs["generator_options_digest"],
            "preview_digest": kwargs["preview_digest"],
        }


def _document() -> dict:
    return normalize_workflow_document(
        {
            "documentType": "workflow_bundle",
            "workflow": {
                "id": "workflow_1",
                "revision": 3,
                "metadata": {
                    "name": "Preview",
                    "code": "",
                    "description": "用于同步预览。",
                    "symptom": "",
                    "industry": "",
                    "device": "",
                    "versions": [],
                },
                "inputs": [],
                "deviceRoles": [],
                "nodes": [
                    {
                        "id": "step_1",
                        "name": "检查",
                        "description": "执行检查。",
                        "isStart": True,
                        "collectionCalls": [],
                        "topology": [
                            {
                                "id": "transition_1",
                                "target": {"id": "conclusion_1"},
                                "conditionText": "检查完成",
                                "conditionExpression": "true",
                            }
                        ],
                        "stepType": "expression",
                    },
                    {
                        "id": "conclusion_1",
                        "name": "完成",
                        "rootCause": "检查结束。",
                        "repairRecommendation": "记录结果。",
                        "nodeType": "conclusion",
                    },
                ],
            },
            "collectionSnapshots": [],
        }
    )
