# 真实 Agent 测试提示词

## 首次创建（新会话）

使用 workflow-mcp-author Skill，读取 network-inspection.md，通过已连接的 SkillHub MCP 创建文档要求的在线工作流。自行查询真实契约、命令库和目标身份，完成预检、严格保存与读回；只修改本次 qa_mcp_skill_ 测试数据。交付网页链接、中文审阅报告、最终快照和校验 JSON 到 artifacts/。不执行设备命令，不使用 REST 或数据库替代 MCP。

## 局部修改（继续同一会话）

修改刚才创建的工作流：只把 bgp 调用的具体命令改为 `show bgp peers <vrf> detail`，保留 vrf 的原输入身份、类型及跨步骤绑定；保留系统来源关系，通过指定调用的副本完成。把“健康”结论的建议改为“保留巡检记录，本次共核对 N 个 BGP 邻居”，N 来自 bgp 邻居数组长度。其余内容不变。预检、严格保存、读回并交付更新后的报告、快照和校验 JSON，不覆盖首次创建产物。命令匹配提醒允许保留。

## 信息缺失（独立会话）

使用 workflow-mcp-author Skill，读取 draft-request.md，通过 SkillHub MCP 创建允许保存的草稿并读回。只修改本轮测试目标，不从其他示例借用命令、Schema 或阈值。交付实际诊断与中文补全清单到 artifacts/，明确草稿不等于完整有效。
