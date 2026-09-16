"""面向工作流创作的分页目录和无写入候选投影。"""

from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, or_, select

from skillhub.models.errors import NotFoundError
from skillhub.models.operations.command_library import _source_to_collection
from skillhub.models.operations.workflows.authoring_prepare import prepare_authoring_document
from skillhub.models.rules.workflows import migrate_collection_definition
from skillhub.models.schema import orm


class WorkflowAuthoringMixin:
    def authoring_search_workflows(self, *, query: str = "", include_archived: bool = False,
                                   offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """批量读取工作流摘要，不生成详情访问事件或假定编辑权限。"""
        metadata = orm.Workflow.document["workflow"]["metadata"]
        statement = select(
            orm.Workflow.skill_id, orm.Workflow.id.label("workflow_id"), orm.Skill.slug,
            metadata["name"].astext.label("name"), metadata["description"].astext.label("description"),
            orm.Workflow.revision, orm.Skill.lifecycle_status, orm.Workflow.updated_at,
        ).join(orm.Skill, orm.Skill.id == orm.Workflow.skill_id)
        if not include_archived:
            statement = statement.where(orm.Skill.lifecycle_status != "archived")
        if query.strip():
            statement = statement.where(or_(
                orm.Skill.slug.icontains(query.strip(), autoescape=True),
                metadata["name"].astext.icontains(query.strip(), autoescape=True),
                metadata["description"].astext.icontains(query.strip(), autoescape=True),
            ))
        with self._read_session() as connection:
            total = connection.scalar(select(func.count()).select_from(statement.subquery()))
            rows = connection.execute(statement.order_by(orm.Workflow.updated_at.desc(), orm.Workflow.id)
                                      .offset(offset).limit(limit)).mappings().all()
            items = [{**dict(row), "archived": row["lifecycle_status"] == "archived"} for row in rows]
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def authoring_search_collections(self, *, query: str = "", definition_id: str | None = None,
                                     revision: int | None = None, offset: int = 0, limit: int = 20,
                                     details: bool = False) -> dict[str, Any]:
        """查询共享采集精确版本或当前版本，来源身份取自权威记录。"""
        definition = orm.WorkflowCollectionRevision.definition
        statement = select(
            orm.WorkflowCollectionRevision.document_schema_version, definition,
            orm.WorkflowCollectionDefinition.source_system_command_id,
        ).join(orm.WorkflowCollectionDefinition,
               orm.WorkflowCollectionDefinition.id == orm.WorkflowCollectionRevision.definition_id)
        if revision is None:
            statement = statement.where(orm.WorkflowCollectionRevision.revision == orm.WorkflowCollectionDefinition.latest_revision)
        else:
            statement = statement.where(orm.WorkflowCollectionRevision.revision == revision)
        if definition_id:
            statement = statement.where(orm.WorkflowCollectionDefinition.id == definition_id)
        if query.strip():
            statement = statement.where(or_(
                definition["key"].astext.icontains(query.strip(), autoescape=True),
                definition["metadata"]["name"].astext.icontains(query.strip(), autoescape=True),
                definition["metadata"]["description"].astext.icontains(query.strip(), autoescape=True),
            ))
        with self._read_session() as connection:
            total = connection.scalar(select(func.count()).select_from(statement.subquery()))
            rows = connection.execute(statement.order_by(orm.WorkflowCollectionDefinition.id)
                                      .offset(offset).limit(limit)).all()
            items = []
            for row in rows:
                item = migrate_collection_definition(row.document_schema_version, dict(row.definition))
                if row.source_system_command_id:
                    item["sourceSystemCommandId"] = row.source_system_command_id
                else:
                    item.pop("sourceSystemCommandId", None)
                    item.pop("sourceBindingMode", None)
                if not details:
                    item = {"id": item["id"], "revision": item["revision"], "key": item["key"],
                            "metadata": item["metadata"], "collectionType": item["spec"]["collectionType"],
                            "sourceSystemCommandId": row.source_system_command_id,
                            "forkedFrom": item.get("forkedFrom"), "sourceBindingMode": item.get("sourceBindingMode"),
                            "commandTemplate": item["spec"].get("commandTemplate"), "inputs": item["inputs"]}
                items.append(item)
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    def authoring_system_command(self, command_id: str, definition_id: str) -> dict[str, Any]:
        """只投影已启用的系统来源，完整复用命令转 Collection 规则。"""
        with self._read_session() as connection:
            source = connection.execute(select(orm.SystemCommandLibraryEntry).where(
                orm.SystemCommandLibraryEntry.id == command_id, orm.SystemCommandLibraryEntry.enabled.is_(True),
            )).scalar_one_or_none()
            if source is None:
                raise NotFoundError(f"Enabled system command does not exist: {command_id}")
            return _source_to_collection(source, definition_id=definition_id, revision=1, source_id=command_id)

    def authoring_system_command_details(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """从搜索行投影规则捕获参数，不将其误作实例输入，无逐命令查询。"""
        enriched = []
        for item in items:
            source = SimpleNamespace(
                id=item["id"], key=item["key"], name=item["name"], description=item["description"],
                expression=item["expression"], document=item.get("document") or {}, metadata_json=item.get("metadata") or {},
                captures=item.get("captureSchema") or {},
            )
            definition = _source_to_collection(source, definition_id="collection_command_preview", revision=1, source_id=item["id"])
            enriched.append({**item, "ruleInputs": definition["inputs"],
                             "inputNote": "规则捕获参数不是实例输入。请提供 command_template 并从预检 collectionSnapshots 或已保存定义读取 inputs。"})
        return enriched

    def authoring_validate_document(self, document) -> dict[str, Any]:
        """按实际读取文档提供完整诊断，不刷新来源或修改保存内容。"""
        return self._workflow_validation(document, include_expression_diagnostics=True)

    def authoring_prepare_document(self, document, collection_changes, *, include_expression_diagnostics: bool = False) -> dict[str, Any]:
        """只读预检；保存应传原始候选，以便重新验证最新来源。"""
        with self._read_session() as connection:
            result = prepare_authoring_document(self, connection, document=document, collection_changes=collection_changes,
                                                include_expression_diagnostics=include_expression_diagnostics)
            return {key: result[key] for key in ("document", "collection_changes", "validation")}
