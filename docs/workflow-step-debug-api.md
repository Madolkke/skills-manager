# Workflow 单步调试

## 1. 功能边界

Workflow 单步调试用于用一组预置输入和采集回显运行某个已保存 Step，并判断执行器是否到达该 Step 的一个直接下游节点。

SkillHub 负责保存调试例和运行历史、生成执行器投影、调用外部执行器、自动处理暂停以及计算命中结果。浏览器只访问 SkillHub，不直接访问执行器。

调试基于启动瞬间的当前已保存 Workflow revision。编辑器存在未保存修改时仍可维护调试例和查看历史，但不能启动新运行。该能力不提供取消、批量运行、版本化调试例或业务层 payload 大小限制。

## 2. 权限与安全

全部调试接口都要求当前 actor 对 Skill 具有 `skill.edit`。调试例的读取、写入和运行不复用无认证的 executor GET 权限。

SkillHub 调用执行器时不发送认证信息，并禁用代理环境变量。执行器和无认证的 `GET /api/skills/{skill_id}/workflow/executor` 都只能部署在受信网络内，不能直接暴露到公网。

## 3. 调试例

调试例绑定一个写作侧 Step，保存以下内容：

| 字段 | 含义 |
| --- | --- |
| `id` | SkillHub 生成的稳定调试例 ID。 |
| `skill_id` | 所属 Skill。 |
| `step_id` | 写作侧 Step ID。 |
| `name` | 调试例名称。 |
| `description` | 可选说明，空值保存为 `""`。 |
| `expected_target_id` | 当前 Step topology 中一个直接目标的写作侧节点 ID。 |
| `workflow_inputs` | 以写作侧 Workflow input ID 为 key 的值对象。 |
| `collection_fixtures` | 以写作侧 CollectionCall ID 为 key 的采集 fixture。 |

`workflow_inputs` 缺少某个 key 表示“未提供”；key 存在且值为 `null` 表示显式提供 `null`。二者在暂停参数恢复时具有不同语义。

每个 Collection fixture 包含 `raw_output` 字符串数组和 `outputs` 对象。`outputs` 以写作侧 Collection output ID 为 key。调试例可以保存不完整数据；只有执行器暂停并实际请求缺失值时，当前运行才失败。

调试例不保留版本。`PATCH` 使用最后写入覆盖。删除调试例会级联删除历史运行，但存在活动运行时返回 `409`。保存 Workflow 并删除 Step 后，该 Step 的调试例和历史会在同一事务中删除。

## 4. SkillHub API

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/api/skills/{skill_id}/workflow/debug-cases` | 列出 Skill 的调试例；可用 `step_id` 筛选。 |
| `POST` | `/api/skills/{skill_id}/workflow/debug-cases` | 创建调试例。 |
| `GET` | `/api/workflow-debug-cases/{case_id}` | 读取调试例。 |
| `PATCH` | `/api/workflow-debug-cases/{case_id}` | 更新调试例。 |
| `DELETE` | `/api/workflow-debug-cases/{case_id}` | 删除调试例及历史。 |
| `POST` | `/api/workflow-debug-cases/{case_id}/runs` | 启动运行；存在活动运行时返回该运行。 |
| `GET` | `/api/workflow-debug-cases/{case_id}/runs` | 按时间倒序读取运行历史。 |
| `GET` | `/api/workflow-debug-runs/{run_id}` | 只读获取当前持久化状态。 |
| `POST` | `/api/workflow-debug-runs/{run_id}/advance` | 向执行器推进一次状态。 |

案例列表的可选 `step_id` 查询参数使用写作侧 Step ID。历史查询使用不透明 `cursor`，`limit` 默认为 `10`，最大为 `100`。响应中的 `next_cursor` 为空表示没有下一页。

同一调试例最多存在一个活动运行。重复调用启动接口不会创建第二个外部运行，而是返回已有记录并标记复用。活动状态包括 `starting`、`running`、`paused` 和 `external_state_unknown`。

## 5. 运行快照

运行记录保存启动时的调试例快照、Workflow revision 和 digest、`task_id`、执行器 `run_id`、最近一次原始执行器状态、错误、已恢复暂停标识及时间信息。

记录只保存解释运行所需的最小映射：源 Step、预期目标、Workflow input key、CollectionCall 整数 ID 和 output key。完整 `workflow_data` 不写入数据库。

状态含义：

| `status` | 含义 |
| --- | --- |
| `starting` | 已创建记录，正在启动外部运行。 |
| `running` | 执行器处于 pending/running，或暂停已恢复。 |
| `paused` | 执行器暂停，等待或重试自动恢复。 |
| `completed` | 已完成命中判定。 |
| `failed` | 配置、数据或执行器契约错误导致无法继续。 |
| `external_state_unknown` | 启动请求超时，无法确认执行器是否已创建运行。 |

`passed` 为三态：命中预期目标时为 `true`；执行器终态但未命中时为 `false`；无法完成判定时为 `null`。

## 6. Executor Workflow 一致性

启动运行和 executor GET 使用同一个纯投影入口。在同一数据库快照中，SkillHub 同时得到严格的 `ExecutorWorkflow` 和内部 ID 映射。

发送给执行器的 `workflow_data` 必须与同一已保存 revision 的下列接口响应深度相等：

```http
GET /api/skills/{skill_id}/workflow/executor
```

外部启动请求只包含三个字段：

```json
{
  "task_id": "2d60b42c-6603-4b49-8739-6b8657f99f61",
  "workflow_data": {
    "id": 1,
    "name": "PTN故障快排",
    "start_step_ids": [],
    "inputs": [],
    "steps": [],
    "conclusions": []
  },
  "step_id": 2
}
```

`workflow_data` 中不得出现 revision、digest、调试例、运行信息或内部 ID 映射。`step_id` 使用该投影中写作侧源 Step 对应的执行器整数 ID。执行器启动响应必须严格为：

```json
{ "run_id": "db225efd-b2f8-4d91-a02f-cb5cb64f020e" }
```

调试沿用现有 Executor Workflow 限制：只支持四种标量 Schema；object、array、script Step、设备角色和其他无法投影的结构会在启动前失败。

## 7. 推进与判定

前端轮询时调用 `/advance`，每次请求最多查询一次执行器运行状态。

判定顺序如下：

1. 预期目标为 Step，且其 `StepRunStatus.status` 变为 `success` 或 `failure`，立即完成并设 `passed=true`。
2. 预期目标为 Conclusion，且其整数 ID 出现在 `conclusion_ids`，立即完成并设 `passed=true`。
3. 执行器整体进入 `success` 或 `failure`，但目标未命中，完成并设 `passed=false`。
4. pending/running 保持活动；paused 进入自动恢复流程。

目标命中后不等待其他 Step 或整个执行器进入终态。其他节点的状态不影响当前目标判定。

临时网络错误和执行器 `5xx` 会保留活动运行，允许后续 `/advance` 重试。执行器 `4xx`、无效 JSON 或不符合契约的响应会立即失败。运行超过 `WORKFLOW_DEBUG_MAX_DURATION_SECONDS` 后失败且 `passed=null`。

启动请求超时不会自动重试，因为 SkillHub 无法确认外部服务是否已创建运行；记录进入 `external_state_unknown`。

## 8. 暂停恢复

执行器状态为 paused 时，SkillHub 使用 `paused_flow_run_id` 调用 paused-schema。Schema 的 `properties` 含 `value` 时视为采集回显暂停，否则视为参数输入暂停。

参数输入恢复规则：

1. 优先按运行快照中的 input ID/key 映射读取调试例值。
2. 调试例没有提供时使用 paused-schema 中的 `default`。
3. required 字段仍缺失时运行失败。

采集回显恢复以 `properties.value.default` 的 CollectionResult 数组为模板。SkillHub 保留模板中的 `command`、`inputs`、`device_name` 和其他字段，仅按 `collection_id` 覆盖对应 fixture 的 `raw_output` 与按 output key 转换后的 `outputs`。执行器请求的 Collection 缺少 fixture 时运行失败。

每次成功恢复会记录 `paused_flow_run_id + paused_key`。执行器重复返回同一暂停时不会重复调用 resume。

## 9. 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WORKFLOW_EXECUTOR_BASE_URL` | 无 | 外部执行器 Base URL；未配置时启动接口返回 `503`。 |
| `WORKFLOW_EXECUTOR_REQUEST_TIMEOUT_SECONDS` | `10` | 单个外部 HTTP 请求超时秒数。 |
| `WORKFLOW_DEBUG_POLL_INTERVAL_SECONDS` | `2` | 前端推进运行的建议轮询间隔。 |
| `WORKFLOW_DEBUG_MAX_DURATION_SECONDS` | `300` | 单次运行最大活动时长。 |

外部执行器接口和完整 Executor Workflow 字段见[执行器 Workflow 转换接口](executor-workflow-api.md)。

运行响应会返回当前配置对应的 `poll_interval_seconds`，前端以此安排下一次 `/advance`；该值只影响浏览器推进频率，不进入执行器请求或 `workflow_data`。

## 10. 错误语义

调试例字段或引用不正确时返回 `400` 和 `field_errors`；无 `skill.edit` 返回 `403`；Skill、Workflow、调试例或运行不存在时返回 `404`；活动运行期间删除案例返回 `409`；未配置执行器时启动运行返回 `503`。

运行过程中的失败写入运行记录的 `error`：本地配置、暂停输入缺失、执行器 `4xx` 或协议错误进入 `failed`；轮询阶段的网络错误和 `5xx` 标记为可重试并保持活动；启动请求结果无法确认时进入 `external_state_unknown`。错误码使用 `workflow_debug.*` 前缀，调用方应以 `status`、`passed` 和 `error.retryable` 决定展示与后续动作。

## 11. 后续扩展

首版明确不包含取消、批量执行、调试例版本、执行器认证、持久化完整 `workflow_data` 或破坏性契约的版本协商。新增这些能力时应保持现有运行事实可解释，并为破坏性外部契约设计版本化接口。
