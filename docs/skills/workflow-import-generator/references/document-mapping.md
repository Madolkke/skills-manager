# 流程说明到 CLI 工作流

## 事实与结构

| 源文档内容 | 目标与规则 |
| --- | --- |
| 名称、目的、适用设备及版本 | 写入 workflow.metadata；缺失信息报告待补全，不编造 |
| 操作者提供的值 | workflow.inputs；展示文字放 schema.title/description |
| 不同设备角色 | deviceRoles；设备字段 Schema 是 object，调用用 deviceRoleId |
| 具体命令及其契约 | CLI Collection；相同定义可复用，不同具体命令分别建定义 |
| 流程阶段 | Expression Step；只有明确脚本源码才创建 Script Step |
| 条件及路径 | topology；目标为节点稳定 ID，不以名称定位 |
| 根因与建议 | Conclusion 的 rootCause/repairRecommendation，可用已声明结果模板 |

节点、参数、Call、输出和跳转 ID 保持稳定；同一作用域不能重复。localId 在 Bundle 内唯一，每个 Call 必须引用存在的定义。完整生成结果恰有一个 isStart=true；这是本 Skill 的作者约束，产品后端本身允许多起点。

## 具体命令和参数

- `show routes vrf default detail`：固定命令，inputs=[]。
- `show routes vrf <vrf> detail`：只生成 vrf 输入。
- `show routes <vrf> compare <vrf>`：两个占位符共享一个输入 ID。
- `show routes [vrf <vrf>] [detail]` 若来源是命令库规则，不能直接当作实例；要求作者明确具体命令或保留草稿。不要全面禁止可能属于真实命令的方括号或竖线。

新 CLI 定义写 `commandParameterSyntax: "angle-v1"`。占位符名称按后端规则使用非关键字 Python 标识符；不能包含空格或未闭合尖括号。当前语法没有字面尖括号转义。

输入只来自实际占位符，默认 required=true、string；文档明确为 integer/number 等时采用原类型。调整现有生成文件时，同名输入保持 ID 和有效绑定；删除占位符清理对应输入与绑定，改名视为删除和新增。暂态非法命令保留草稿，不破坏性清理。校验器只报告错误，不替作者重写数据。

## 输出 Schema 与占位

每个输出使用 id/key/required/schema；标题、说明位于 Schema 内。对象包含 properties、required、additionalProperties=false，数组必须有 items，递归保留对象数组和二维数组。所有新字段提供中文 title/description。原契约不明确的类型列入报告，不以猜测填充。

缺少命令时生成占位 CLI：

```json
{
  "localId": "inspect-status",
  "key": "inspect_status",
  "metadata": {"name": "检查状态", "description": "缺少设备命令，待补全。"},
  "spec": {"collectionType": "cli", "commandParameterSyntax": "angle-v1", "commandTemplate": "", "outputSamples": []},
  "inputs": [],
  "outputs": []
}
```

已确认命令但缺少输出契约时保留命令，outputs=[]，不强行变成空命令。不要凭生产回显编造类型；示例仅可用明确许可的脱敏或合成内容。Bundle 不承载 TTP 执行逻辑。

禁止输出 Collection 的 id、revision、forkedFrom、sourceSystemCommandId、sourceBindingMode，以及 Workflow 的 id/revision。导入后它们是独立用户采集，不自动重建系统来源。

## 绑定与作用域

- 全局输入：`{"kind":"workflow_input","reference":{"input_id":"input-vrf"}}`。
- 前序输出整体绑定：`{"kind":"collection_output","reference":{"call_id":"call-routes","output_id":"output-routes"}}`，源目标递归 Schema 必须兼容。
- 嵌套输出：`{"kind":"expression","expression":"outputs.routes.routes[0].vrf"}`。不同时携带 value 或非空 reference。
- 设备参数使用 device_role_field 的 role_id 与 object-only 相对 path；条件和模板可使用 `topo.devices.device.address`。
- literal 使用 value，显式 null 与 Schema 不符时保留后端 warning，不宣称类型兼容。

示例统一用明确 Call Key。后续采集可引用同一步骤更早调用和图上传递前序步骤的输出；不能引用未来调用、不相关步骤或自身输出。不要仅凭 JSON 顺序推断跨步骤作用域，交给后端纯规则校验。

## 数组、模板和函数

- 单次采集对象数组：`outputs.interfaces.interfaces[0].counters.rx`。
- 嵌套对象数组：`outputs.routes.routes[0].next_hops[0].address`。
- 多次采集加二维业务数组：`outputs.fabric[0].matrix[0][0].value`。第一个下标选择采集结果，之后两个选择矩阵行列。
- 支持后端允许的负数和动态整数下标，例如 `outputs.fabric[-1].labels`、`outputs.interfaces.interfaces[inputs.index].name`；不假设未知业务数组长度。
- 条件说明示例：`接口 {{ outputs.interfaces.interfaces[0].name }} 已采集`。中文、花括号和下标不得丢失。
- 函数默认按仓库内置规则检查，如 len、sum、min/max。本地函数契约完全替代默认目录；不复制函数体，不假定某平台已启用函数。

分支默认互斥（parallelBranches=false）。文档明确要求所有满足条件的分支都执行时才设为 true；这不承诺并发调度或分支执行顺序，当前外部执行器投影仍忽略它。

## 中文审阅报告

包含源文件与生成时间、映射后的节点/命令/Collection、确认事实、占位原因及补全要求、未映射信息、敏感信息处理、分支决策和完整校验命令。

分别列出：导入硬性限制、领域错误、提醒、表达式位置诊断，以及所用函数契约和静态校验边界。未被调用的定义仍会被平台导入，必须报告。不得将“draft 退出码 0”写成“工作流完整通过”或“已经可执行”。
