# Workflow Agent 助手

## 定位

Workflow Agent 是写作工作台的服务端 AI 入口。首版提供：

- `workflow_assistant`：解释 Workflow、分析校验问题和给出写作建议。
- `debug_case_generator`：为当前 Step 的每个直接目标生成可编辑的单步调试例候选，最多 10 条。

Agent 不直接修改 Workflow、不创建调试例、不启动执行器。所有变更都先成为提案，由用户确认后通过既有领域校验和事务写入。

## 运行架构

SkillHub API 精确锁定 `agentscope==2.0.6`，在 API 进程内使用 `Agent`、`Toolkit` 和 `reply_stream()`。模型通过 OpenAI-compatible Provider 调用，前端不能选择 Provider 或模型。

每个 actor 与 Workflow 同时只有一个活动会话；一个会话同时只有一个活动运行。两个 Agent 使用独立 AgentScope session 和状态，共享可见时间线。跨 Agent 只传递近期用户输入和最终回答，不传递另一 Agent 的 thinking 或工具内部状态。

活动任务由 API 后台异步任务持有。SSE 断开不会取消任务；前端使用 `Last-Event-ID` 重连并从数据库补发事件。API 重启会把遗留的 `starting/running` 运行标记为 `interrupted`，不会恢复或重试。

## 数据边界

运行请求包含：

- 当前规范化本地 Workflow 草稿及服务端重算 digest；
- 当前选择位置和已保存 revision；
- 当前 Step、必要节点摘要和相关 Collection 定义；
- 相关 Collection 的原始回显示例；
- 当前确定性校验问题、当前 Step 已有调试例；
- 最近用户输入和各 Agent 的最终回答。

这些内容会发送给部署配置的外部 Provider。前端必须持续展示安全提示。AgentScope 原生 session/state/message 保存在 PostgreSQL `workflow_agent_scope` schema；SkillHub 在业务表 `workflow_agent_events` 中保存完整原生 Event，包括 thinking 和工具事件，用于断线补发和审计。

应用日志不得输出 Provider API key、上下文正文或原生 reasoning。永久删除会话会级联删除 SkillHub 会话、运行、事件、提案，并删除各 Agent 的 AgentScope session。

## 领域工具

首版工具均为只读且由服务端构建，没有通用工具入口：

- `read_workflow_context`
- `read_workflow_validation`
- `read_existing_debug_cases`

工具不能访问 Shell、任意 SQL、文件系统、外部网络或 Workflow 执行器。工具上下文是运行创建时的不可变快照，模型不能通过工具越过当前 Skill 或当前用户权限。

## API

所有端点要求 `skill.edit`：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/skills/{skill_id}/workflow/agents` | Agent 目录和配置状态 |
| `GET/POST` | `/api/skills/{skill_id}/workflow/agent-sessions` | 会话列表/取得活动会话 |
| `GET/POST` | `/api/workflow-agent-sessions/{session_id}/runs` | 运行历史/启动运行 |
| `GET` | `/api/workflow-agent-runs/{run_id}` | 运行和提案状态 |
| `GET` | `/api/workflow-agent-runs/{run_id}/events` | 原生 Event SSE |
| `POST` | `/api/workflow-agent-runs/{run_id}/cancel` | 请求取消 |
| `POST` | `/api/workflow-agent-sessions/{session_id}/archive` | 归档会话 |
| `DELETE` | `/api/workflow-agent-sessions/{session_id}` | 永久删除已归档会话 |
| `POST` | `/api/workflow-agent-proposals/{proposal_id}/apply` | 原子应用调试例候选 |

SSE data 结构：

```json
{
  "event_id": 17,
  "session_id": "workflow_agent_session_...",
  "run_id": "workflow_agent_run_...",
  "event": {
    "id": "native AgentScope event id",
    "type": "THINKING_BLOCK_DELTA",
    "delta": "..."
  }
}
```

`event` 不转换为 SkillHub 自定义事件。升级 AgentScope 前必须显式更新 Event 契约快照和兼容说明。

## 调试例提案

`debug_case_generator` 只能在选中且存在直接目标的 Step 上运行。结构化输出严格复用调试例字段：`step_id/name/description/expected_target_id/workflow_inputs/collection_fixtures`。

服务端要求候选覆盖所有直接目标，引用必须仍存在且总数不超过 10。用户可以编辑、取消勾选并确认。基于未保存草稿生成是允许的，但应用前必须先保存 Workflow；数据库中的当前 document digest 必须等于提案 `draft_digest`，否则提案标记为 `stale`。批量写入使用单事务，任一引用失效则全部拒绝。

前端时间线只展示提案摘要、候选数量和状态，不在助手栏内展开完整表单。点击摘要后进入独立候选工作区：左侧选择候选，右侧编辑当前候选，底部统一创建所选调试例。已应用和已过期提案仍可从原运行记录重新查看，但不能再次创建。

运行状态为 `starting`、`running`、`completed`、`failed`、`canceled`、`interrupted`。`starting/running` 是活动状态；Provider、配置、协议或超时错误写入 `failed`，用户取消写入 `canceled`，API 重启回收写入 `interrupted`。`response_text` 只保存最终回答，完整 thinking/tool 过程通过事件表保存。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WORKFLOW_AGENT_MODEL_BASE_URL` | 无 | OpenAI-compatible Base URL |
| `WORKFLOW_AGENT_MODEL_API_KEY` | 无 | Provider API key |
| `WORKFLOW_AGENT_MODEL` | 无 | 固定模型名称 |
| `WORKFLOW_AGENT_TIMEOUT_SECONDS` | `300` | 单次运行总超时 |
| `WORKFLOW_AGENT_REASONING_EFFORT` | 空 | 可选 reasoning effort |

专用 `WORKFLOW_AGENT_MODEL_*` 配置优先。为兼容已有本地环境，未设置专用变量时会依次使用 `DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY` 和 `OPENCODE_DEFAULT_MODEL`。

前三项任一缺失时目录仍可读取和管理历史，但启动运行返回 `503`。Provider 不支持 reasoning 参数时运行失败，错误保存在运行记录中；SkillHub 不自动降级参数或改用其他模型。

## 非目标

- API 重启后的任务恢复或自动重试。
- 文件附件、通用网络工具和执行器工具。
- Agent 直接编辑 Workflow 或自动启动调试。
- 前端选择 Provider、模型、Token 或推理轮次。
- 独立 AgentScope Agent Service 部署。
