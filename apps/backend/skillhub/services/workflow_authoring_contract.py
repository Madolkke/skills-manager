"""MCP 创作说明；动态函数目录由 WorkflowService 注入。"""
from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows.schema import CollectionDefinition, WorkflowBundle


def authoring_contract(topic: str, workflows) -> dict[str, Any]:
    """按主题返回必要声明，避免每个调用携带全量 Schema。"""
    common = {'document_schema_version': 5, 'topic': topic}
    if topic == 'overview':
        return {**common, 'summary': 'Workflow 与 Skill 一对一；保存作者文档不会同步 Skill 或执行命令。',
                'schema': WorkflowBundle.model_json_schema(by_alias=True),
                'workflow': ['search_workflows → get_workflow', 'search_system_commands → validate_workflow_changes',
                             'create_workflow → apply_workflow_changes → get_workflow'],
                'editing': '使用稳定 ID 或同批 @client_ref 引用；工具外壳 snake_case，作者字段 camelCase。',
                'limitations': ['没有并发覆盖保护；写请求超时后先读取状态，不自动重试创建。',
                                'parallelBranches 仅保存写作意图，当前执行器投影忽略此字段。']}
    if topic == 'changes':
        return {**common, 'summary': '局部操作先构建候选，再原子保存；预检不产生写入。',
                'references': '新增对象携 client_ref，后续操作用 @名称 引用；返回 id_mappings。预检 ID 不是预留身份。',
                'updates': 'fields 仅覆盖显式字段；数组整体替换；排序 ids 必须包含目标列表全部成员。',
                'validation_policies': {'draft': '沿用网页硬性限制，返回尚未完成的诊断。', 'strict': '仅允许零错误，提醒不阻止保存。'},
                'collections': '定义修改采用 fork，仅重绑指定调用；不修改系统命令和共享定义。',
                'deletion': '删除节点清除入边；其他表达式和绑定保留原文并报告问题。'}
    if topic == 'collections':
        return {**common, 'summary': '支持 cli/function/log/config；函数体及 SQL 仅保存、静态检查。',
                'schema': CollectionDefinition.model_json_schema(by_alias=True),
                'sources': 'call.from_system 使用已启用系统命令；先 search_system_commands(details=true)，将 inputs[].id 用作 inputBindings 键；call.add 引用精确 Collection 版本。'}
    if topic == 'expressions':
        return {**common, **workflows.expression_contract()}
    if topic == 'logs':
        return {**common, **workflows.log_schema()}
    raise InvariantError('未知的创作契约主题。')
