"""面向 MCP 的工作流创作编排，共享作者模型与保存事务。"""
from typing import Any
from urllib.parse import urlencode

from skillhub.models.errors import InvariantError, NotFoundError, PermissionDeniedError
from skillhub.models.rules.workflows.authoring import build_authoring_candidate
from skillhub.models.rules.workflows.authoring_context import authoring_expression_context
from skillhub.models.rules.workflows.save_policy import blocking_workflow_errors
from skillhub.models.store import SkillHubStore
from skillhub.services.workflow_authoring_contract import authoring_contract
from skillhub.services.workflows import WorkflowService


class WorkflowAuthoringService:
    """由协议层注入事务绑定 Store，不持有 HTTP 请求或 Cookie。"""

    def __init__(self, store: SkillHubStore, web_base_url: str = 'http://127.0.0.1:3030'):
        self.store = store
        self.workflows = WorkflowService(store)
        self.web_base_url = web_base_url.rstrip('/')

    def search_workflows(self, query: str = '', include_archived: bool = False, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """分页读取摘要并给出网页入口，不记录页面访问。"""
        result = self.store.authoring_search_workflows(query=query, include_archived=include_archived, offset=offset, limit=limit)
        for item in result['items']:
            item['url'] = self._url(item['skill_id'])
        return result

    def get_workflow(self, skill_id: str, view: str = 'outline', node_id: str | None = None) -> dict[str, Any]:
        """匿名读取不返回以默认用户计算的编辑权限。"""
        detail = self.workflows.workflow_detail(skill_id=skill_id, actor='mcp-anonymous')
        detail['validation'] = self.store.authoring_validate_document(detail['document'])
        detail.pop('capabilities', None)
        detail['url'] = self._url(skill_id)
        document = detail.pop('document')
        if view == 'full':
            detail['document'] = document
        elif view == 'node':
            node = next((item for item in document['workflow']['nodes'] if item['id'] == node_id), None)
            if node is None:
                raise NotFoundError('工作流节点不存在。')
            refs = {(call['definition']['id'], call['definition']['revision']) for call in node.get('collectionCalls', [])}
            detail['node'] = node
            detail['collectionSnapshots'] = [item for item in document['collectionSnapshots'] if (item['id'], item['revision']) in refs]
        elif view == 'outline':
            workflow = document['workflow']
            detail['metadata'] = workflow['metadata']
            detail['inputs'] = workflow['inputs']
            detail['deviceRoles'] = workflow['deviceRoles']
            detail['nodes'] = [{key: node[key] for key in ('id', 'name', 'stepType', 'nodeType', 'isStart', 'parallelBranches') if key in node}
                               | {'calls': [{'id': call['id'], 'key': call['key'], 'definition': call['definition']} for call in node.get('collectionCalls', [])],
                                  'targets': [path['target']['id'] for path in node.get('topology', [])]}
                               for node in workflow['nodes']]
        else:
            raise InvariantError('工作流读取模式无效。')
        return detail

    def get_authoring_contract(self, topic: str = 'overview') -> dict[str, Any]:
        """读取作者结构与启用函数目录，不提供全局函数体。"""
        result = authoring_contract(topic, self.workflows)
        if topic == 'overview':
            result['tag_groups'] = self.store.list_tag_groups()
            result['tag_instructions'] = '创建时按标签组的必填与级联规则选择 tags；读取目录不修改标签。'
        return result

    def search_system_commands(self, query: str = '', target_version: str | None = None, details: bool = False,
                               offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """CLI 匹配复用已有规则，同时允许名称与 Key 检索。"""
        options = {'actor': 'mcp-anonymous', 'include_system': True, 'include_user': False, 'include_disabled': False, 'target_version': target_version}
        matched = self.store.search_command_library(query=query, **options)
        catalog = self.store.search_command_library(query='', **options) if query.strip() else []
        needle = query.strip().casefold()
        identities = {item['id'] for item in matched}
        matched.extend(item for item in catalog if item['id'] not in identities
                       and any(needle in str(item.get(key, '')).casefold() for key in ('key', 'name', 'description')))
        unique = list({item['id']: item for item in reversed(matched)}.values())[::-1]
        items = unique[offset:offset + limit]
        if details:
            items = self.store.authoring_system_command_details(items)
        else:
            items = [{key: item.get(key) for key in ('id', 'key', 'name', 'description', 'expression', 'metadata', 'source', 'captureSchema')} for item in items]
        return {'items': items, 'total': len(unique), 'offset': offset, 'limit': limit}

    def search_collections(self, query: str = '', definition_id: str | None = None, revision: int | None = None,
                           details: bool = False, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """读取共享定义版本；不通过用户命令库间接搜索。"""
        return self.store.authoring_search_collections(query=query, definition_id=definition_id, revision=revision,
                                                      details=details, offset=offset, limit=limit)

    def validate_workflow_changes(self, skill_id: str, changes: list[dict] | None = None, validation_policy: str = 'draft') -> dict[str, Any]:
        """预检只构建候选，不调用保存或写入回滚。"""
        candidate, prepared = self._prepare(skill_id, changes or [])
        blocking = blocking_workflow_errors(prepared['validation'], validation_policy=validation_policy,
                                            invalid_policy_message='保存校验策略无效。')
        return {'saved': False, 'can_save': not blocking,
                'validation': prepared['validation'], 'summary': candidate['summary'], 'id_mappings': candidate['id_mappings'],
                'collectionSnapshots': prepared['document']['collectionSnapshots'],
                'note': '预检 ID 未预留，正式保存会重新构造并校验。'}

    def get_expression_context(self, skill_id: str, selection: dict, changes: list[dict] | None = None) -> dict[str, Any]:
        """使用候选文档的真实字段作用域和 Schema 投影上下文。"""
        candidate, prepared = self._prepare(skill_id, changes or [])
        resolved = {key: candidate['id_mappings'].get(value[1:], value) if isinstance(value, str) and value.startswith('@') else value
                    for key, value in selection.items()}
        result = authoring_expression_context(prepared['document'], resolved)
        return {**result, 'functions': self.workflows.expression_contract()['functions'], 'id_mappings': candidate['id_mappings']}

    def create_workflow(self, slug: str, description: str, name: str | None = None, tags: list[dict] | None = None, *, actor: str) -> dict[str, Any]:
        """创建的 owner 来自解析身份，名称设置与创建位于同一事务。"""
        created = self.workflows.create_workflow_skill(slug=slug, owner_ref=actor, description=description, tags=tags or [], actor=actor)
        skill_id = created['skill_id']
        if name is not None:
            detail = self.workflows.workflow_detail(skill_id=skill_id, actor=actor)
            detail['document']['workflow']['metadata']['name'] = name
            self.store.save_workflow(skill_id=skill_id, document=detail['document'], collection_changes=[], actor=actor)
        detail = self.get_workflow(skill_id, 'outline')
        return {**detail, 'saved': True, 'changed': True, 'summary': '已创建工作流草稿，尚未同步或执行。'}

    def apply_workflow_changes(self, skill_id: str, changes: list[dict], validation_policy: str = 'draft', *, actor: str) -> dict[str, Any]:
        """在事务内一次保存；失败由外层回滚，不捕获后假装成功。"""
        capabilities = self.store.skill_capabilities(skill_id=skill_id, actor=actor)
        if not capabilities['permissions'].get('skill.edit'):
            raise PermissionDeniedError('当前用户没有此工作流的编辑权限。')
        candidate, _ = self._prepare(skill_id, changes)
        saved = self.store.save_workflow(skill_id=skill_id, document=candidate['document'], collection_changes=candidate['collection_changes'],
                                        actor=actor, validation_policy=validation_policy, include_expression_diagnostics=True)
        return {'skill_id': skill_id, 'revision': saved['revision'], 'saved': True, 'changed': saved['changed'],
                'validation': saved['validation'], 'id_mappings': candidate['id_mappings'], 'summary': candidate['summary'], 'url': self._url(skill_id)}

    def _prepare(self, skill_id: str, changes: list[dict]) -> tuple[dict, dict]:
        """候选生成和来源准备分别共享于无写入预检与最终保存。"""
        document = self.workflows.workflow_detail(skill_id=skill_id, actor='mcp-anonymous')['document']
        candidate = build_authoring_candidate(document, changes,
            resolve_system_command=lambda command_id, definition_id: self.store.authoring_system_command(command_id=command_id, definition_id=definition_id),
            resolve_collection=self._collection)
        prepared = self.store.authoring_prepare_document(candidate['document'], candidate['collection_changes'], include_expression_diagnostics=True)
        return candidate, prepared

    def _collection(self, definition_id: str, revision: int | None) -> dict:
        """按精确版本解析引用，禁止猜测不存在的采集定义。"""
        result = self.search_collections(definition_id=definition_id, revision=revision, details=True)
        if not result['items']:
            raise NotFoundError('采集定义版本不存在。')
        return result['items'][0]

    def _url(self, skill_id: str) -> str:
        """构造网页入口，不暴露调用 Cookie。"""
        return self.web_base_url + '/skills?' + urlencode({'section': 'workflows', 'skill': skill_id, 'tab': 'workflow'})
