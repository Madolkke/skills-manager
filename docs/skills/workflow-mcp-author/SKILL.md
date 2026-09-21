---
name: workflow-mcp-author
description: "通过已连接的 SkillHub MCP，将流程说明转换为在线工作流，或局部编辑已有工作流。仅创作 CLI 采集，支持命令库复用、复杂 Schema、表达式绑定、模板、预检和保存，并交付中文审阅报告。"
---

# MCP 工作流创作

根据用户提供的业务事实，通过 SkillHub MCP 创建或修改在线工作流。仅使用 CLI 采集；保存作者文档不会执行命令或同步、发布 Skill。

## 使用顺序

1. 发现当前连接的 MCP 工具，按实际前缀调用。新任务读取 `get_authoring_contract` 的 overview、changes；涉及采集和表达式时分别读取 collections、expressions。协议以实时声明为准。
2. 提取源文档中的命令、契约、流程和缺口，参考 [流程映射](references/authoring.md)。查找目标工作流并确认身份，编辑前读取最新文档；新建前核对 overview 中实际标签要求。
3. 搜索合适的系统命令或 CLI Collection；使用具体命令，核对来源 Schema。无适合来源时，依据用户确认的契约创建独立 CLI。检索流程及编辑语义见 [MCP 操作](references/mcp-workflow.md)。
4. 形成局部修改批次，使用预检检查候选。默认先保存结构和采集草稿，再读回真实输入 ID，补齐绑定、条件与结果模板。完整内容 strict 保存；明确缺失的内容按 draft 保存并报告缺口。
5. 每批检查 `saved/changed/validation`，最后 `get_workflow(view="full")` 读回核对。按 [交付与示例](references/examples.md) 输出身份、网页入口、快照、诊断及中文审阅报告。

## 必须保留的语义

- 根据当前用户授权决定是否写入。仅分析、查询或预览时不创建外壳；明确要求创建或修改时直接完成授权范围，不额外设置固定审批环节。
- MCP 未连接、权限不足或工具缺失时说明阻塞，不通过 REST、数据库、模拟 actor 或自行配置 Cookie 绕过。Cookie 只由连接层提供，不出现在工具参数和交付文件中。
- 只新增或修改 CLI 采集；已有非 CLI 采集保持原样。仅承接源文档明确提供的 Script Step 源码，静态检查但不执行。
- `command_template`/`commandTemplate` 是具体命令。系统检索规则和 `ruleInputs` 不等于实例命令或输入。固定命令零输入，重复 `<参数>` 只对应一个输入。
- 不根据回显示例推测输出类型。不虚构缺失的命令、Schema、判断阈值或故障结论；保留平台允许的占位及自然语言说明，避免引用未知输出。
- 函数以当前 MCP 返回的启用声明为准，空目录不回退；通过 `get_expression_context` 检查字段位置的可见变量，不凭 JSON 排列推断跨步骤作用域。
- 修改保留无关字段、节点和绑定。排序要提供完整成员；数组显式更新会整体替换。来源副本与解除来源是不同操作。
- 没有并发覆盖保护，不同时从网页和 Agent 修改。写入超时先查询实际状态，不自动重放创建或整批写入。
- 当前 MCP 非空 Cookie 映射 `product-operator`，真实 SSO 未实现。静态通过不证明命令可执行或流程运行正确。

## 文档与交付

支持 Markdown、文本和已可靠提取的文档内容；无法读取时指出缺失，不臆测。交付 `<源名>.workflow-mcp.review.md`、`.workflow-mcp.snapshot.json`、`.workflow-mcp.validation.json`；默认当前工作目录，遇同名文件使用新后缀。

快照来自最终 MCP 读回，不是可导入 Bundle。未保存时不伪造正式 ID、revision 或成功结果。新建外壳和多个批次不是整体事务；中断时交付已创建身份和最后确认状态，便于恢复。
