# 流程说明映射

## 提取顺序

先整理事实，不要直接编写 JSON：

| 文档内容 | Bundle 目标 | 规则 |
| --- | --- | --- |
| 标题、目的、适用设备和版本 | `workflow.metadata` | 标题和说明不能为空；缺失字段保留空值并列入审阅报告。 |
| 运行前由操作者提供的值 | `workflow.inputs` | 使用稳定 ID 和机器可读 key；在 `schema.title`、`schema.description` 写展示语义。 |
| 不同设备或端点 | `deviceRoles` 和 `deviceRoleId` | 仅在文档明确区分角色时创建。 |
| 一个可执行检查或动作 | CollectionDefinition 与 Call | 抽取可复用的 Collection；同一动作可被多个步骤调用。 |
| 流程阶段 | Expression 或 Script Step | 只在文档提供脚本源码时创建 Script Step。 |
| 分支条件 | `topology` | 每条边使用目标节点 ID；无法类型化时只保留 `conditionText`。 |
| 结束状态、根因、建议 | Conclusion | 写入 `name`、`rootCause`、`repairRecommendation`。 |

## Collection 决策

为文档明确的 CLI 命令创建 `spec.collectionType: "cli"` 和单行 `commandTemplate`。命令参数必须对应 Collection 输入；输出字段必须具备 `id`、`key`、`required` 和合法 Schema。

当文档只说明“检查”“采集”或“执行恢复”，但缺少命令、输入或输出契约时，创建以下形式的占位 Collection：

```json
{
  "localId": "inspect-system-status",
  "key": "inspect_system_status",
  "metadata": {"name": "检查系统状态", "description": "待补充执行命令。", "tags": ["placeholder"]},
  "spec": {"collectionType": "cli", "commandTemplate": "", "outputSamples": []},
  "inputs": [],
  "outputs": []
}
```

不要发明命令、正则、SQL、输出 Schema 或固定值。若文档声明了输入或输出但未声明类型，优先将其列入审阅报告；不要以错误的 Schema 支撑表达式。占位 Collection 可以引用已确认的输入，但后续 Binding 只能引用同一步骤中更早、且已声明输出的 Call。

## 条件和命名空间

- 文档给出布尔输出和判断逻辑时，使用 `outputs.<callKey>.<outputKey>`；没有 `callKey` 时，只能在无冲突且输出已确认时使用 `outputs.<outputKey>`。
- 同一步骤的多次采集必须填写合法 `callKey`；不要用直接输出绕过该限制。
- 多个直接输出重名，或直接输出与 Workflow 输入重名时，保留条件文字并将冲突列入审阅报告。
- 为每个步骤指定一个 `isStart: true`，所有跳转目标必须引用当前 Bundle 中存在的节点 ID。

## 审阅报告

报告与 Bundle 同目录，至少包含：

1. 源文档和生成时间。
2. 已映射的步骤和 Collection。
3. 每个占位 Collection 的 `localId`、原因和需要补全的命令/输入/输出。
4. 未映射字段、无法类型化的条件、敏感数据删除情况和需要确认的业务决策。
5. 本地校验命令及结果。
