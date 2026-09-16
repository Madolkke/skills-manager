# Workflow 创作 MCP

SkillHub 在 API 进程提供无状态 Streamable HTTP MCP，入口为 `/mcp`。工具与网页共享工作流模型、采集来源、静态校验和保存事务。读取不计入详情页面 PV/UV。

## 启动与连接

安装后端依赖并沿用现有服务启动方式：

```powershell
cd apps/backend
uv sync
```

本地可运行仓库的 `scripts/start-local-services.ps1`。API 使用 8003 端口时，MCP 地址为 `http://127.0.0.1:8003/mcp`；实际端口以环境配置为准。

在支持 Streamable HTTP 和自定义 Header 的 CodeAgent 中配置：

| 配置项 | 示例 |
| --- | --- |
| URL | `http://127.0.0.1:8003/mcp` |
| 传输 | Streamable HTTP |
| 写操作请求 Header | `Cookie: skillhub_sso=mock-demo` |

各客户端配置文件格式不同，上表是连接参数，不是所有客户端通用的 JSON 配置。Cookie 由客户端连接层提供，不放入工具参数或模型对话。读取、工具发现和无写入校验无需 Cookie。

部署到其他域名时，通过 `SKILLHUB_MCP_ALLOWED_HOSTS` 和 `SKILLHUB_MCP_ALLOWED_ORIGINS` 配置逗号分隔的允许地址；本地地址仍保留在允许列表。`SKILLHUB_WEB_BASE_URL` 配置工具返回的网页入口，默认使用本地 Web 端口。这些设置不会启用真实 SSO。

官方 Python SDK 示例：

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import httpx

async def main():
    async with httpx.AsyncClient(headers={"Cookie": "skillhub_sso=mock-demo"}) as client:
        async with streamable_http_client("http://127.0.0.1:8003/mcp", http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_workflows", {"query": "接口"})
                print(result.structuredContent)

asyncio.run(main())
```

## 工具

| 工具 | 用途 |
| --- | --- |
| `search_workflows` | 按名称、slug、说明查询，默认排除归档项 |
| `get_workflow` | `outline` 大纲、`full` 完整文档或 `node` 指定节点 |
| `get_authoring_contract` | 按 `overview/changes/collections/expressions/logs` 获取规范与 Schema |
| `search_system_commands` | 搜索启用的系统命令，`details=true` 返回完整输出 Schema 及可直接用于绑定的输入参数 ID |
| `search_collections` | 搜索共享采集；指定 definition_id/revision 可读取精确版本 |
| `get_expression_context` | 依据真实字段位置提供可见变量、路径、类型和函数声明 |
| `validate_workflow_changes` | 无写入构建候选并返回完整诊断 |
| `create_workflow` | 以当前身份为 owner 创建 Workflow Skill 草稿 |
| `apply_workflow_changes` | 按顺序原子应用一批局部修改 |

目录分页默认 20 条，最多 100 条。命令搜索仅使用系统命令库；共享 Collection 是独立的复用资产目录。匿名读取不返回假定为默认用户的编辑权限。

## 创作顺序

1. 查询工作流并读取需要的节点；创建前读取 `overview` 契约的 `tag_groups`，按必选与级联规则选择标签，再调用 `create_workflow`。
2. 读取所需创作契约，搜索系统命令或共享采集。
3. 使用局部操作构建候选；按字段位置读取表达式上下文。
4. 无写入预检并修正错误，然后调用 `apply_workflow_changes`。
5. 检查 `saved/changed/validation`，通过返回的网页入口继续编辑。

外壳参数使用 snake_case，`fields` 和 `definition` 中的作者字段沿用 camelCase。已有对象以稳定 ID 定位；新对象可以指定请求内唯一的 `client_ref`，同批后续操作使用 `@引用名`。正式 ID 由服务端生成并返回 `id_mappings`。预检 ID 不会被预留，保存时以正式响应为准。

绑定的 `reference` 是既有作者协议中的特殊结构，使用 `input_id`、`call_id`、`output_id` 等 snake_case 键，不是 `inputId`。例如绑定同批全局输入：`{"kind":"workflow_input","reference":{"input_id":"@vrf"}}`；绑定前序表达式：`{"kind":"expression","expression":"outputs.routes.routes[0].vrf"}`。`search_system_commands(details=true)` 的 `inputs` 提供转换后的 `id`、`key`、`required` 和 `schema`，可直接作为 `inputBindings` 的键或 `binding.set` 的 `input_id`，无需猜测 ID；`outputSchema` 保留完整业务数组层级，`captureSchema` 是命令匹配捕获规则。

例如命令 `show routes <vrf>` 的详情返回 `inputs: [{"id":"input_vrf","key":"vrf","required":true,"schema":{"type":"string",...}}]`，添加采集时可传 `"inputBindings":{"input_vrf":{"kind":"workflow_input","reference":{"input_id":"@vrf"}}}`。输入 ID 投影与正式 `call.from_system` 复用相同规则；若管理员随后改变系统命令参数，应重新读取详情再构造绑定。

`create_workflow` 接收 `slug`、`description`、可选 `name` 与 `tags`。标签格式为 `[{"group_id":"实际标签组 ID","value":"实际标签值"}]`；未配置必选标签组时可以省略。创建沿用网页的标签约束，未填激活的必选组会返回错误，不留下部分 Skill。

创建工作流后，添加步骤和结论的示例：

```json
{
  "skill_id": "替换为创建结果",
  "validation_policy": "strict",
  "changes": [
    {"operation":"node.add","client_ref":"check","fields":{"stepType":"expression","name":"检查接口","isStart":true}},
    {"operation":"node.add","client_ref":"done","fields":{"nodeType":"conclusion","name":"检查完成","rootCause":"未发现异常。"}},
    {"operation":"transition.add","node_id":"@check","fields":{"target":{"id":"@done"},"conditionText":"检查结束"}}
  ]
}
```

`get_authoring_contract(topic="changes")` 返回当前操作联合 Schema。支持元信息、输入、角色、节点、调用、绑定、跳转的局部编辑和排序。数组字段显式提供时整体替换；排序需列出目标列表全部成员。删除节点同时清除入边，其他绑定和表达式保持原文并产生诊断，不自动猜测替换文本。

新增采集优先用 `call.from_system`；复用已有版本用 `call.add`。新自定义定义用 `call.create_collection`。修改定义用 `call.fork_collection`，仅重绑定指定调用，保留 `forkedFrom`，移除系统自动同步身份，原共享定义和系统命令不变。全部修改成功时才持久化，失败不会留下半成品 Collection。

表达式上下文例子：

```json
{
  "skill_id": "...",
  "selection": {"node_id":"...","field":"binding","call_id":"...","input_id":"input_vrf"}
}
```

条件字段还需 `transition_id`；结论字段使用 `rootCause` 或 `repairRecommendation`。可附加 `changes` 检查未保存候选，并用 `@client_ref` 定位新节点。绑定仅看到前序可用采集；条件和结论按拓扑确定作用域。输出路径中的 `[]` 表示业务数组，采集多次时另有最外层 `[0]`。

## 校验、事务与边界

- 默认 `validation_policy="draft"` 与网页一致，允许未完成草稿；非法结构、错误函数、未注册函数和不兼容绑定仍拒绝保存。
- `strict` 要求零错误，提醒允许存在。保存草稿成功不等于校验通过；始终检查 `validation.errors`。
- MCP 的读取、预检和保存均补全表达式字段诊断，附带 `selection` 及字段内 UTF-16 `start/end`。严重度沿用既有规则：例如条件中的未知属性、语法或已知采集下标越界可能为 warning，严格保存也允许；绑定类型不兼容、错误函数调用属于硬性限制。
- 预检不写数据库，保存会重新构造候选、投影实际系统来源并校验。预检不是预约提交。
- 服务端按一次调用提交 Workflow、Collection 和审计，失败全部回滚；提交成功才返回成功结果。
- 本期没有并发覆盖保护、请求去重或新的历史版本管理。不要同时从网页与 Agent 修改；写入超时先读取实际状态，不自动重试创建。
- 不提供导入导出、同步 Skill、发布、删除整个工作流或执行工具。函数体、脚本、SQL 和命令文本仅用于写作；静态校验通过不证明运行结果正确。
- `parallelBranches` 保留写作意图，当前执行器投影仍忽略该字段。

## 模拟身份及后续 SSO 接入

**当前身份接口 A 的 HTTP 调用和 SSO 有效性尚未实现。** 创建和保存只检查 Cookie 非空，随后固定使用 `product-operator`；业务层仍检查该用户对目标工作流的编辑权限。`X-SkillHub-Actor` 不能改变 MCP 身份，工具参数不能指定 actor 或 owner。

环境变量 `SKILLHUB_MCP_USERINFO_URL` 默认空。即使配置 URL，本轮也不会发送 HTTP 请求；身份解析器中保留注释掉的调用示例，模拟模式不受 URL 可用性影响。

后续接入需修改 `services/mcp_identity.py`：取消模拟返回，将请求 Cookie 发到配置 URL，5 秒超时，根据接口 A 的实际协议解析稳定用户 ID。示例假定 GET 返回 `{"user_id":"..."}`，这是适配约定，不代表真实 SSO 接口已经确认。会话失效、超时、异常响应应返回失败，不能回退到模拟身份。

Cookie 只存在于请求上下文，不进入工具返回、日志、数据库或审计。读取与预检无需身份请求；模拟认证仅应用于 MCP，现有网页和 REST 的身份方式保持原状。
