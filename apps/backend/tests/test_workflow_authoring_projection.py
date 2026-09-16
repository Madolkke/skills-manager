"""创作预检的权威快照、只读保证和正式保存一致性。"""

from contextlib import contextmanager
from copy import deepcopy

import pytest
from sqlalchemy import event, func, select, update

from skillhub.models.errors import InvariantError, NotFoundError, WorkflowValidationError
from skillhub.models.schema import orm
from tests import test_workflows as workflow_fixtures
from tests.api_command_test_case import ApiCommandTestCase


class WorkflowAuthoringProjectionTest(ApiCommandTestCase):
    _create_workflow = workflow_fixtures.WorkflowApiTest._create_workflow
    _definition = workflow_fixtures.WorkflowApiTest._definition
    _valid_document = workflow_fixtures.WorkflowApiTest._valid_document

    @contextmanager
    def _read_only_statements(self):
        """收集实际 SQL，禁止通过执行写入后回滚伪装预检。"""
        statements = []

        def observe(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lstrip().split()[0].upper())

        event.listen(self.engine, "before_cursor_execute", observe)
        try:
            yield
        finally:
            event.remove(self.engine, "before_cursor_execute", observe)
        assert statements
        assert not {"INSERT", "UPDATE", "DELETE"}.intersection(statements), statements

    def _candidate(self, slug="authoring-test", definition=None):
        """创建空白工作流并构造包含一个采集的有效候选。"""
        skill_id = self._create_workflow(slug)["skill_id"]
        document = self.store.executor_workflow_source(skill_id=skill_id)
        definition = definition or self._definition()
        return skill_id, self._valid_document(document, definition), [{"operation": "create", "definition": definition}]

    def _source(self):
        """创建带二维对象数组的来源以核对 Schema 投影。"""
        return self.store.create_system_command(
            key="authoring_interfaces", name="接口来源", expression="show interfaces", actor="workflow-owner",
            document={"outputSchema": {"type": "object", "properties": {
                "state": {"type": "string", "title": "状态", "description": "接口状态"},
                "matrix": {"type": "array", "items": {"type": "array", "items": {
                    "type": "object", "properties": {"healthy": {"type": "boolean"}}, "required": ["healthy"],
                }}},
            }, "required": ["state", "matrix"]}},
        )

    def test_pending_definitions_prepare_without_any_database_writes(self):
        """尚未保存的定义可预检，预检与正式保存候选完全一致。"""
        skill_id, document, changes = self._candidate()
        original = deepcopy(document)
        with self._read_only_statements():
            prepared = self.store.authoring_prepare_document(document, changes)
        assert document == original
        assert prepared["validation"]["errors"] == []
        assert self.store.authoring_search_collections()["total"] == 0
        saved = self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes,
                                        actor="workflow-owner", validation_policy="strict")
        prepared["document"]["workflow"]["revision"] = saved["revision"]
        assert saved["document"] == prepared["document"]

    def test_saved_snapshot_is_authoritative_and_missing_revision_is_rejected(self):
        """已有定义的伪快照不影响预检，未知精确版本明确拒绝。"""
        skill_id, document, changes = self._candidate()
        saved = self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes, actor="workflow-owner")
        tampered = deepcopy(saved["document"])
        tampered["collectionSnapshots"][0]["outputs"][0]["schema"]["type"] = "integer"
        with self._read_only_statements():
            prepared = self.store.authoring_prepare_document(tampered, [])
        assert prepared["document"] == saved["document"]
        tampered["workflow"]["nodes"][0]["collectionCalls"][0]["definition"]["revision"] = 99
        with pytest.raises(InvariantError, match="revision does not exist"):
            self.store.authoring_prepare_document(tampered, [])

    def test_source_refresh_is_read_only_and_matches_save(self):
        """现存来源更新的预检不产生新版本，正式保存才应用相同计划。"""
        source = self._source()
        definition = self.store.authoring_system_command(source["id"], "authoring-source")
        matrix = next(output for output in definition["outputs"] if output["key"] == "matrix")
        assert matrix["schema"]["items"]["items"]["properties"]["healthy"]["type"] == "boolean"
        skill_id, document, changes = self._candidate(definition=definition)
        saved = self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes, actor="workflow-owner")
        self.store.update_system_command(command_id=source["id"], name="来源已更新", actor="admin")
        with self._read_only_statements():
            prepared = self.store.authoring_prepare_document(saved["document"], [])
        assert prepared["document"]["collectionSnapshots"][0]["metadata"]["name"] == "来源已更新"
        assert prepared["document"]["collectionSnapshots"][0]["revision"] == 2
        assert self.store.authoring_search_collections(definition_id=definition["id"], details=True)["items"][0]["revision"] == 1
        refreshed = self.store.save_workflow(skill_id=skill_id, document=saved["document"], collection_changes=[],
                                            actor="workflow-owner", validation_policy="strict")
        prepared["document"]["workflow"]["revision"] = refreshed["revision"]
        assert prepared["document"] == refreshed["document"]

    def test_pending_source_refresh_and_incompatible_updates_never_write_during_prepare(self):
        """新来源草稿同样使用最新权威来源，并阻止不兼容投影。"""
        source = self._source()
        definition = self.store.authoring_system_command(source["id"], "pending-source")
        _skill_id, document, changes = self._candidate(definition=definition)
        document["workflow"]["nodes"][0]["topology"][0]["conditionExpression"] = "outputs.interface.state != ''"
        self.store.update_system_command(command_id=source["id"], name="最新名称", actor="admin")
        with self._read_only_statements():
            prepared = self.store.authoring_prepare_document(document, changes)
        assert prepared["document"]["collectionSnapshots"][0]["metadata"]["name"] == "最新名称"
        assert self.store.authoring_search_collections()["total"] == 0
        modified = deepcopy(source["document"])
        modified["outputSchema"]["properties"].pop("state")
        modified["outputSchema"]["required"].remove("state")
        self.store.update_system_command(command_id=source["id"], document=modified, actor="admin")
        with self._read_only_statements(), pytest.raises(InvariantError):
            self.store.authoring_prepare_document(document, changes)
        assert self.store.authoring_search_collections()["total"] == 0

    def test_strict_save_rejects_errors_before_collection_or_audit_writes(self):
        """严格保存返回全部诊断，拒绝时没有部分 Collection 或审计。"""
        skill_id, document, changes = self._candidate()
        document["workflow"]["metadata"]["name"] = ""
        with self.engine.connect() as connection:
            before = connection.scalar(select(func.count()).select_from(orm.AuditEvent))
        with self._read_only_statements(), pytest.raises(WorkflowValidationError) as error:
            self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes,
                                     actor="workflow-owner", validation_policy="strict")
        assert error.value.validation["errors"]
        assert self.store.authoring_search_collections()["total"] == 0
        assert self.store.workflow_detail(skill_id=skill_id, actor="workflow-owner")["revision"] == 1
        with self.engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(orm.AuditEvent)) == before
        draft = self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes, actor="workflow-owner")
        assert draft["validation"]["errors"]
        assert draft["revision"] == 2

    def test_catalog_pagination_archive_filter_and_precise_revisions(self):
        """分页按精确过滤计数，归档默认隐藏，采集详情保留精确版本。"""
        skill_id, document, changes = self._candidate(slug="authoring-first")
        self._create_workflow("authoring-second")
        self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes, actor="workflow-owner")
        with self.engine.begin() as connection:
            connection.execute(update(orm.Skill).where(orm.Skill.id == skill_id).values(lifecycle_status="archived"))
        active = self.store.authoring_search_workflows(query="authoring", limit=1)
        assert active["total"] == 1
        assert active["items"][0]["slug"] == "authoring-second"
        archived = self.store.authoring_search_workflows(query="接口状态排查", include_archived=True)
        assert archived["total"] == 1 and archived["items"][0]["archived"]
        assert self.store.authoring_search_workflows(query="authoring", include_archived=True, offset=1, limit=1)["total"] == 2
        assert self.store.authoring_search_workflows(query="%_")["items"] == []
        summary = self.store.authoring_search_collections(query="接口")
        assert summary["total"] == 1 and "inputs" not in summary["items"][0]
        detail = self.store.authoring_search_collections(definition_id=changes[0]["definition"]["id"], revision=1, details=True)
        assert detail["items"][0]["outputs"][0]["schema"]["type"] == "string"
        assert self.store.authoring_search_collections(revision=99)["items"] == []

    def test_disabled_source_cannot_be_projected(self):
        """仅已启用的系统命令可用于新采集。"""
        source = self._source()
        self.store.update_system_command(command_id=source["id"], enabled=False, actor="admin")
        with pytest.raises(NotFoundError, match="Enabled system command"):
            self.store.authoring_system_command(source["id"], "disabled-source")

    def test_same_batch_create_then_fork_is_read_only_before_save(self):
        """复制同批先前创建的定义时，预检使用候选版本并按依赖顺序保存。"""
        skill_id, document, changes = self._candidate(slug="authoring-chain")
        source = deepcopy(changes[0]["definition"])
        fork = deepcopy(source)
        fork["id"] = "collection-authoring-fork"
        fork["forkedFrom"] = {"id": source["id"], "revision": 1}
        fork["metadata"]["description"] = "来自本批新建定义"
        document["workflow"]["nodes"][0]["collectionCalls"][0]["definition"] = {"id": fork["id"], "revision": 1}
        changes.append({"operation": "fork", "definition": fork})
        with self._read_only_statements():
            prepared = self.store.authoring_prepare_document(document, changes)
        assert self.store.authoring_search_collections()["total"] == 0
        assert [item["id"] for item in prepared["document"]["collectionSnapshots"]] == [fork["id"]]
        saved = self.store.save_workflow(skill_id=skill_id, document=document, collection_changes=changes,
                                         actor="workflow-owner", validation_policy="strict")
        assert self.store.authoring_search_collections()["total"] == 2
        assert saved["document"]["collectionSnapshots"][0]["forkedFrom"] == {"id": source["id"], "revision": 1}
