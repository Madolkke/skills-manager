# 局部操作示例与交付

示例中的 ID 均需替换为真实工具返回值，不能按名称猜测。完整协议从 changes 契约读取。

## 建立结构

已有新工作流外壳时，可以提交以下 changes；本例只展示协议，不替用户决定真实业务：

```json
[
  {"operation":"input.add","client_ref":"vrf","fields":{"key":"vrf","required":true,"schema":{"type":"string","title":"路由实例","description":"待查询路由实例"}}},
  {"operation":"node.add","client_ref":"inspect","fields":{"stepType":"expression","name":"读取路由","isStart":true,"parallelBranches":false}},
  {"operation":"node.add","client_ref":"done","fields":{"nodeType":"conclusion","name":"人工核对","rootCause":"等待采集结果核对。"}},
  {"operation":"transition.add","node_id":"@inspect","fields":{"target":{"id":"@done"},"conditionText":"采集后人工核对"}}
]
```

从真实系统规则添加调用：

```json
{"operation":"call.from_system","node_id":"实际步骤 ID","command_id":"实际系统命令 ID","command_template":"show routes <vrf>","fields":{"key":"routes","name":"路由采集"}}
```

先用 draft 预检及保存，再读取 collectionSnapshots.inputs 中 vrf 的真实 ID，binding.set 绑定到已保存全局输入；完成后再 strict 预检、保存。

## 独立 CLI

系统与共享目录无匹配，且原文已确认下列契约时：

```json
{"operation":"call.create_collection","node_id":"实际步骤 ID","fields":{"key":"marker","name":"标记采集"},"definition":{"key":"marker","metadata":{"name":"标记查询","description":"源文档明确提供的合成 CLI"},"spec":{"collectionType":"cli","commandParameterSyntax":"angle-v1","commandTemplate":"show marker","outputSamples":[]},"inputs":[],"outputs":[{"key":"status","required":true,"schema":{"type":"string","title":"状态","description":"明确声明的状态值"}}]}}
```

缺少契约时不要照抄本例 status，改为 outputs=[] 并报告缺口。缺少命令也不能套用 show marker。

## 局部修改

```json
{"operation":"call.set_command","node_id":"实际步骤 ID","call_id":"实际调用 ID","command_template":"show routes <vrf> detail"}
```

预检后检查同名输入和绑定保留，系统来源关系保留，只有指定调用重绑副本。固定命令不匹配或动态匹配不确定是提醒，不自行编造替换值消除提醒。

## 中文审阅报告

记录以下可核对事实，不需要机械复述工具调用全文：

- 来源文件、用户目标、目标身份与网页入口、最终 revision。
- 已确认业务事实、命令来源选择、参数和复杂 Schema、拓扑与绑定摘要。
- 修改已有流程时列明变更边界；来源副本、解除来源及未修改记录。
- 仍缺少的输入、命令、Schema 或判断规则；未映射的原文内容。
- 最终 saved/changed、策略、完整 errors/warnings、字段位置及契约来源。
- 创建但未完成、中断或写入结果不确定时的恢复信息。
- 未执行命令、未解析真实回显、未同步或发布，静态结果不能替代运行验收。

snapshot.json 保存最终 get_workflow(full) 实际读回结果或其明确标注的 document 部分。必须逐字段保留选定部分：不能将 collectionSnapshots 缩为 ID 列表、删除 outputs/outputSamples、简写 Schema 的 title/description 或用省略号替代。摘要只放 review.md；不要凭记忆重建快照。写入后读文件核对与最后一次工具返回一致；内容过长无法完整交付时明确报告未完成，不能将摘要标成完整快照。

validation.json 保留最后一次读回的完整 validation 对象（errors/warnings 中的 code、message、severity、selection、location 等字段按原返回保留），其他身份及策略可放外层说明，不手写“零错误”。MCP 不提供 Bundle 导出，此快照不作为可导入 Bundle。
