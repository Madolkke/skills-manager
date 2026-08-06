# 执行器 Workflow 转换接口

## 1. 文档目的

本文定义写作侧 Workflow 到外部执行器 Workflow 的首版转换契约。它描述接口响应、字段映射、引用路径、ID 分配、转换失败和安全边界，供执行器、后端和后续扩展共同使用。

该接口只提供当前已保存 Workflow 的实时投影，不保存执行器副本，也不代表 Workflow 已通过领域校验或可以立即执行。

## 2. 接口

```http
GET /api/skills/{skill_id}/workflow/executor
```

- 请求不包含 body 或 query 参数；成功返回 `200 application/json`。
- `skill_id` 使用 SkillHub 内部 Skill ID，不使用可重命名 slug。
- 接口读取当前保存的 Workflow 文档和其中的精确 Collection 快照。
- 响应为扁平的 `ExecutorWorkflow` JSON 对象，不包含 envelope、源 revision、schema version、ETag 或其他元数据。
- 首版不要求 actor、权限或 API key。接口假设部署在执行器可以访问的受信网络中，网关或网络层负责访问控制。
- Skill 或 Workflow 不存在时沿用现有 `404` 响应语义。
- `/api/skills/{skill_id}/workflow/formatted` 保持原有行为，不使用本接口的模型或转换器。

## 3. 响应模型

所有字段均返回。没有内容时使用空字符串、空数组或 `null`，不省略字段。所有对象禁止未定义字段。

| 类型 | 字段 | JSON 类型 | 含义 |
| --- | --- | --- | --- |
| `ExecutorWorkflow` | `id` | `integer` | 固定为 `1`。 |
|  | `name` | `string` | 写作侧 `workflow.metadata.name`。 |
|  | `start_step_ids` | `integer[]` | 起始步骤的执行器 ID，保持写作侧节点顺序。 |
|  | `inputs` | `ExecutorValue[]` | Workflow 全局输入。 |
|  | `steps` | `ExecutorStep[]` | 执行步骤，保持写作侧节点顺序。 |
|  | `conclusions` | `ExecutorConclusion[]` | 结论节点，保持写作侧节点顺序。 |
| `ExecutorValue` | `name` | `string` | 参数或输出的写作侧 `key`。 |
|  | `description` | `string` | Schema 的 `description`。 |
|  | `value` | scalar 或 `null` | 运行时路径、JSON 标量字面量或未绑定值。 |
|  | `type` | `string` | `string`、`integer`、`number` 或 `boolean`。 |
| `ExecutorStep` | `id` | `integer` | 执行器步骤 ID。 |
|  | `name` | `string` | 写作侧步骤名称。 |
|  | `condition` | `string` | 写作侧步骤 `description`。 |
|  | `collections` | `ExecutorCollection[]` | 当前步骤的 CollectionCall 展开结果。 |
|  | `transitions` | `ExecutorTransition[]` | 当前步骤的跳转，保持原顺序。 |
| `ExecutorCollection` | `id` | `integer` | 当前 CollectionCall 的执行器 ID。 |
|  | `kind` | `"command"` | 当前 CLI Collection 统一映射为 `command`。 |
|  | `command` | `string` | Collection spec 的 `commandTemplate`。 |
|  | `example_outputs` | `array` | 首版固定为 `[]`。 |
|  | `inputs` | `ExecutorValue[]` | Collection 定义的输入和调用绑定。 |
|  | `outputs` | `ExecutorValue[]` | Collection 定义的输出。 |
| `ExecutorTransition` | `id` | `integer` | 执行器 Transition ID。 |
|  | `target_type` | `string` | `step` 或 `conclusion`，由目标节点类型决定。 |
|  | `target_id` | `integer` | 目标 Step 或 Conclusion ID。 |
|  | `condition` | `string` | `conditionExpression` 原文；空字符串表示无条件。 |
|  | `description` | `string` | `conditionText` 原文。 |
| `ExecutorConclusion` | `id` | `integer` | 执行器 Conclusion ID。 |
|  | `conclusion` | `string` | 写作侧 Conclusion 的 `name`。 |

`ExecutorValue.value` 只允许字符串、整数、浮点数、布尔值或 `null`。其中路径也是字符串；object 和 array 不是合法值。

## 4. 合法响应示例

下面是可直接解析的完整 JSON 示例。实际响应中不会包含省略号或注释。

```json
{
  "id": 1,
  "name": "PTN故障快排",
  "start_step_ids": [2],
  "inputs": [
    {
      "name": "slot-id",
      "description": "要检查的槽位号",
      "value": "inputs.slot-id",
      "type": "string"
    }
  ],
  "steps": [
    {
      "id": 2,
      "name": "准备环境",
      "condition": "",
      "collections": [
        {
          "id": 3,
          "kind": "command",
          "command": "screen-length 0 temporary",
          "example_outputs": [],
          "inputs": [
            {
              "name": "slot-id",
              "description": "要检查的槽位号",
              "value": "inputs.slot-id",
              "type": "string"
            }
          ],
          "outputs": [
            {
              "name": "memory_percentage",
              "description": "内存使用率",
              "value": "outputs.memory_percentage",
              "type": "number"
            }
          ]
        }
      ],
      "transitions": [
        {
          "id": 4,
          "target_type": "conclusion",
          "target_id": 5,
          "condition": "outputs.memory_percentage > 0.8",
          "description": "内存使用率超过80%"
        }
      ]
    }
  ],
  "conclusions": [
    {
      "id": 5,
      "conclusion": "无异常"
    }
  ]
}
```

## 5. 转换规则

### 5.1 节点和 ID

ID 使用单一、连续、无重复的整数命名空间：

1. Workflow 固定分配 `1`。
2. 按 `workflow.nodes` 顺序为所有 Step 分配 ID。
3. 按 Step 顺序、每个 Step 的 `collectionCalls` 顺序为可投影的 CLI CollectionCall 分配 ID；被忽略的 Log/Config Call 不占用 ID。
4. 按 Step 顺序、每个 Step 的 `topology` 顺序为 Transition 分配 ID。
5. 按节点顺序为 Conclusion 分配 ID。

转换器先建立写作侧 ID 到执行器 ID 的映射，再生成引用。跨 Step 的目标引用可以正确定位；同一定义的多次调用会得到不同的 Collection ID。重复或歧义的写作侧引用会导致转换失败。

同一个有序 Workflow 文档重复转换时，输出和所有整数 ID 完全相同。插入、删除或重排对象会改变其后续分配的 ID；ID 不保证跨 Workflow revision 或跨 Skill 永久稳定。

### 5.2 输入、输出和引用路径

- Workflow input 的 `name` 使用原始 `key`，`value` 固定为 `inputs.<key>`。
- `workflow_input` binding 转为被引用 Workflow input 的 `inputs.<key>`。
- `collection_output` binding 转为对应 CollectionCall 的输出路径。
- CollectionCall `key` 非空白时，输出路径为 `outputs.<callKey>.<outputKey>`；为空白时为 `outputs.<outputKey>`。
- 未绑定的 Collection input 输出 `value: null`，不会因为未绑定而调用领域校验。
- `literal` binding 保留原生 JSON 标量和 `null`；object、array 会拒绝转换。
- 路径中的原始 key 不 trim、不转义、不替换 `.` 或 `-`。只有判断 CollectionCall key 是否为空白时使用 `strip()`；执行器负责解释最终路径。

输入、输出和引用使用的 Schema 必须是 `string`、`integer`、`number` 或 `boolean`。object、array 和无法确定标量类型的 legacy loose Schema 不支持首版转换。

### 5.3 步骤、采集和跳转

- 只有 `expression` Step 可以转换；`script` Step 会拒绝整个 Workflow 转换。
- Step `condition` 取 `description`，不重新解析或生成表达式。
- 每个 CLI CollectionCall 都展开为一个 Collection，不能按 Definition 去重；同一定义被调用两次会得到两个执行器 Collection。
- CLI Collection 的 `kind` 固定为 `command`，命令来自 `spec.commandTemplate`。Log/Config CollectionCall 被静默忽略，不执行或投影日志 SQL、配置匹配，也不校验该 Call 的 Schema、binding、`deviceRoleId` 或 `sampleCount`。
- CLI CollectionCall 的非空 `deviceRoleId` 或 `sampleCount != 1` 无法由目标模型表达，会拒绝转换。
- 表达式或 CLI binding 对被忽略采集输出的 `outputs.*` 引用保持原样；转换器不分析、删除或改写这些引用，缺值语义由执行器处理。
- `example_outputs` 固定为 `[]`，忽略写作侧 `outputSamples`、stdout 和 inputValues。
- Transition 保持原数组顺序；`condition` 使用 `conditionExpression`，`description` 使用 `conditionText`。空表达式是无条件跳转。
- Transition 目标节点为 Step 时 `target_type` 为 `step`，目标为 Conclusion 时为 `conclusion`。
- Conclusion 的 `conclusion` 取 `name`；`rootCause` 和 `repairRecommendation` 首版不输出。

## 6. 忽略字段

首版明确不映射以下写作侧信息：

- Workflow revision、schema version，以及 metadata 中除 `name` 外的 `code`、`description`、`symptom`、`industry`、`device`、`versions`。
- Workflow 和 Collection 字段的 `required` 标记、Schema `title`、完整递归 JSON Schema 结构。
- DeviceRole 定义；被 CLI CollectionCall 使用时会因目标模型不支持设备路由而失败，被忽略的 Log/Config Call 不校验该字段。
- Collection metadata、tags、forkedFrom、定义 ID/revision 展示信息。
- CollectionCall 的 `name`；调用 `key` 仅用于输出路径。
- 原始 output samples、stdout、inputValues。
- Conclusion 的 `rootCause` 和 `repairRecommendation`。

未来若需要保留这些信息，应扩展独立执行器 DTO 或新增版本化接口，不应把作者侧字段直接塞入本响应。

## 7. 转换错误

转换失败返回 HTTP `400`，错误响应沿用 API 的 `field_errors` 结构：

```json
{
  "detail": "Workflow 无法转换为执行器定义。",
  "field_errors": [
    {
      "field": "workflow.nodes[0].stepType",
      "message": "执行器 Workflow 暂不支持 script Step。",
      "code": "executor_workflow.unsupported_step_type"
    }
  ]
}
```

服务端聚合所有可以检测的问题，并按写作侧文档顺序返回：

| code | 触发条件 |
| --- | --- |
| `executor_workflow.unsupported_step_type` | Step 为 `script` 或其他未支持类型。 |
| `executor_workflow.unsupported_device_role` | CollectionCall 使用非空 `deviceRoleId`。 |
| `executor_workflow.unsupported_sample_count` | CollectionCall 的 `sampleCount` 不为 `1`。 |
| `executor_workflow.unsupported_schema` | 使用 object、array 或无法确定标量类型的 Schema。 |
| `executor_workflow.unsupported_literal` | literal binding 的值为 object 或 array。 |
| `executor_workflow.unresolvable_reference` | Definition、Workflow input、CollectionCall、output 或 Transition target 引用不存在。 |
| `executor_workflow.ambiguous_reference` | 引用匹配到多个写作侧对象。 |

`field_errors[].field` 使用写作侧文档路径，例如 `workflow.inputs[0].schema`、`workflow.nodes[0].collectionCalls[0].sampleCount`。

本接口不调用 Workflow 领域校验器。无起始步骤、空表达式、缺失 binding 等仍可机械转换的草稿不会因此返回 `400`；只有目标模型无法表示或转换器无法解析的内容才会失败。

## 8. 安全与生命周期

- 该接口无认证、无授权、无租户隔离，只能部署在受信网络内。响应可能包含命令模板、输入输出名称和表达式，不应直接暴露到公网。
- 每次请求都读取当前 Workflow 并实时转换；首版不缓存、不持久化执行器定义，也不创建审计事件。
- 当前接口没有 revision 或 ETag，执行器不能仅凭响应元数据判断两次结果是否来自同一作者 revision。
- 本接口不执行命令、不解释 Transition 表达式，也不提供运行状态、重试、并发、设备调度或 secrets 管理能力。
- 执行器负责解释未经转义的 dot-path，并自行保证获取、缓存和执行过程中的版本一致性。
- 新增兼容字段应优先扩展独立 `ExecutorWorkflow` 模型；破坏性变化应设计新的版本化端点。

## 9. 集成测试 Workflow

仓库提供一份可直接提交给 Workflow Import API 的完整数据：

- [executor-integration-workflow-import.json](examples/executor-integration-workflow-import.json)
- 包含 4 种标量 Workflow input、3 个 Step、4 个 CLI Collection、3 种 binding、5 个 Transition 和 3 个 Conclusion。
- 写作侧结构校验、引用校验和领域校验均通过；其中 output samples 会在执行器转换时被忽略。

从仓库根目录启动后端后，可在 PowerShell 中执行：

```powershell
$api = "http://localhost:8000"
$headers = @{ "X-SkillHub-Actor" = "integration-tester" }
$createBody = @{
  slug = "ptn-executor-integration"
  owner_ref = "integration-tester"
  description = "验证外部执行器 Workflow 转换。"
  tags = @()
} | ConvertTo-Json

$created = Invoke-RestMethod -Method Post -Uri "$api/api/workflows" `
  -Headers $headers -ContentType "application/json" -Body $createBody
$bundle = Get-Content -Raw "docs/examples/executor-integration-workflow-import.json"
Invoke-RestMethod -Method Post -Uri "$api/api/skills/$($created.skill_id)/workflow/import" `
  -Headers $headers -ContentType "application/json" -Body $bundle
$executor = Invoke-RestMethod -Method Get `
  -Uri "$api/api/skills/$($created.skill_id)/workflow/executor"
$executor | ConvertTo-Json -Depth 20
```

关键预期：

- 顶层 `id` 为 `1`，`start_step_ids` 为 `[2]`。
- Step ID 为 `2..4`，Collection ID 为 `5..8`，Transition ID 为 `9..13`，Conclusion ID 为 `14..16`。
- `usage` binding 转换为 `outputs.memory.usage_percentage`。
- `slot-id` binding 保留为 `inputs.slot-id`；`mode`、`dry_run`、`baseline` 分别保留 string、boolean、integer literal。
- 未绑定的可选 `note` 返回 `null`，所有 `example_outputs` 返回 `[]`。

Import API 不幂等；重复运行时应使用新的 `slug`，或复用已创建 Skill 但只执行一次导入。
