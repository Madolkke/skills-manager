"""网页保存与 MCP 预检共享的只读候选构造。"""

from skillhub.models.errors import WorkflowValidationError
from skillhub.models.operations.command_source_sync import plan_system_sources
from skillhub.models.operations.workflows.catalog_plan import canonicalize_planned_snapshots, plan_collection_changes
from skillhub.models.rules.workflows import normalize_workflow_document
from skillhub.models.rules.workflows.save_policy import blocking_workflow_errors


def prepare_authoring_document(store, connection, *, document, collection_changes, include_expression_diagnostics=False):
    """规范化定义、权威快照和来源更新后校验，不执行任何写入。"""
    candidate = normalize_workflow_document(document)
    collections = plan_collection_changes(store, connection, collection_changes)
    candidate = canonicalize_planned_snapshots(store, connection, candidate, collections)
    sources = plan_system_sources(connection, document=candidate, pending_records=collections["records"])
    candidate = sources["document"]
    validation = store._workflow_validation(candidate, include_expression_diagnostics=include_expression_diagnostics)
    return {"document": candidate, "collection_changes": collections["changes"], "validation": validation,
            "collection_plan": collections, "source_plan": sources}


def require_writable_validation(validation, *, validation_policy):
    """严格模式拒绝全部错误；草稿沿用网页已有硬性写入限制。"""
    blocking = blocking_workflow_errors(validation, validation_policy=validation_policy)
    if blocking:
        prefix = "Workflow 校验失败：" if validation_policy == "strict" else "Workflow 函数调用无效："
        raise WorkflowValidationError(prefix + "; ".join(item["message"] for item in blocking), validation)
