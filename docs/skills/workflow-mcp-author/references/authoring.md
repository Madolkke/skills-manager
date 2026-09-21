# 流程说明与作者模型

## 事实映射

| 业务信息 | 作者模型 |
| --- | --- |
| 名称、描述、设备和适用版本 | workflow.metadata |
| 操作者提供的数据 | 全局 inputs，类型及中文 title/description 放 schema |
| 逻辑设备及管理字段 | deviceRoles，schema 为 object；调用使用 deviceRoleId |
| 阶段与路径 | 步骤、topology；目标按 ID 引用 |
| 根因及处置建议 | conclusion 的 rootCause/repairRecommendation |
| CLI 命令与明确契约 | Collection，调用按顺序放 collectionCalls |

新建完整工作流恰有一个起始步骤；这是本 Skill 的默认创作约束，产品可接受多个起点。编辑现有工作流时不为满足新建惯例重写无关结构。步骤默认 parallelBranches=false；只有业务明确要求执行所有满足条件分支时设 true。该字段不代表并行调度，当前执行器投影仍忽略它。

条件必须覆盖源文档规定的正常、异常和空数据路径。数组取值前按业务要求检查长度；Schema 不保证长度。没有定义的分支处置列入审阅，不能自行认定“正常”或补写修复动作。

## CLI 实例与 Schema

- `show routes default`：固定命令，零输入。
- `show routes <vrf>`：仅 vrf 输入。
- `show compare <vrf> with <vrf>`：同名占位符去重为一个输入。
- 系统规则 `show routes [vrf <vrf>] [detail]` 不可机械复制为实例；要求明确实际命令。不要全面禁止命令中的方括号、竖线等字符。

新 CLI 使用 angle-v1。参数为非关键字 Python 标识符，默认必填 string；原文明确其他类型才采用，检查绑定兼容性。保存输入 ID 由服务端分配；命令编辑同名参数保留身份与绑定，删除参数会清理绑定，改名视为删旧建新。

系统来源的名称、说明、回显 Schema 和示例由来源同步。若来源与文档契约冲突，不能改写只读来源或因搜索排序靠前就选中；报告冲突并请求明确选择。无兼容来源才依据确认契约创建自定义 CLI。

自定义输出按顶层属性拆为 outputs，每项携 key、required、schema；根 required 决定输出 required。内部 properties、items、required、additionalProperties 与标题说明完整保留。对象数组、二维数组不得降为字符串数组。原契约没有声明的约束不补造。

缺少命令时可创建 commandTemplate=""、inputs=[] 的独立 CLI 草稿；缺少输出契约时 outputs=[]。不要用空值调用必填 command_template 的 call.from_system。缺失输出只留自然语言说明，不构造依赖未知输出的表达式。草稿仍须符合平台硬限制。

## 表达式与模板

- 调用 Key 是表达式路径名称，和系统命令 Key、Collection Key、节点 ID 不同。
- 同一步骤内后续调用可见前序输出；跨步骤由拓扑传递决定。先构造拓扑，再查询相应字段上下文。
- 单次业务数组：`outputs.routes.routes[0].next_hops[0].address`。
- 三次采集加二维数组：`outputs.fabric[0].matrix[0][0].value`，第一个下标是采集结果。
- 支持契约允许的负数及动态整数下标；已知采集次数和未知业务长度分别处理。
- 模板形如 `接口 {{ outputs.interfaces.interfaces[0].name }}`，保留中文和花括号。
- 绑定形如 `{"kind":"expression","expression":"outputs.routes.routes[0].vrf"}`；全局输入引用为 `{"kind":"workflow_input","reference":{"input_id":"实际输入 ID"}}`。

函数必须来自实时启用声明，参数类型以服务端诊断为准，不复制函数体。读取上下文时 binding 需要 node_id/call_id/input_id，条件需要 node_id/transition_id；结论字段使用 rootCause 或 repairRecommendation。
