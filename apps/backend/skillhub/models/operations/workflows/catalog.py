from __future__ import annotations

from typing import Any

from skillhub.models.operations.workflows.catalog_plan import (
    canonicalize_planned_snapshots,
    persist_collection_plan,
    plan_collection_changes,
)


class WorkflowCatalogMixin:
    def _apply_collection_changes(self, connection, *, changes, actor: str, created_at):
        """兼容既有入口，统一使用只读计划后执行写入。"""
        plan = plan_collection_changes(self, connection, changes)
        persist_collection_plan(self, connection, plan, actor=actor, created_at=created_at)
        return plan["mappings"], plan["applied"]

    def _canonicalize_collection_snapshots(self, connection, document: dict[str, Any], mappings) -> dict[str, Any]:
        """使用已保存的精确版本替换传入快照。"""
        return canonicalize_planned_snapshots(self, connection, document, {"mappings": mappings, "definitions": {}})
