# 验收者清单（不提供给被测 Agent）

被测 Agent 工作目录仅包含 Skill 入口、agents、references、场景文档和空 artifacts；本文件及预期数据不得放入其可读范围。

- 事件证明确实加载 workflow-mcp-author，模型为 deepseek/deepseek-v4-pro，业务写入实际调用 MCP。
- 创建结果为 3 个全局输入、1 个设备角色、2 个步骤、4 个结论、5 个调用；唯一起始步骤、互斥分支。
- 第一步 interfaces/routes；第二步 bgp/fabric/peer_check；所有调用均绑定设备角色。
- 四条系统来源保留来源关系；peer_check 创建独立 CLI，重复 peer_count 仅一个 integer 输入，绑定 len(outputs.bgp.peers)。
- interfaces、routes 使用全局输入；bgp 使用前一步 routes 第一条 vrf。fabric 固定零输入、sampleCount=3。
- 四条来源的输出 Schema 与目录一致；自定义 matched boolean、checked integer，均必填。保留对象数组、next_hops、families/prefixes 和 matrix[][]。
- 分支覆盖空列表、接口 up 与第一轮矩阵 healthy；每次索引前有必要的长度保护；不能将可选 value 当必达字段。
- 数据不足结论不引用仅第二步可见结果；健康模板含路由/邻居数量、healthy 与末轮 labels 数量。
- 最终 strict 保存真实零错误，提醒如实保留；快照来自最终读回而非人工组装。没有设备执行、解析、发布或同步。
- 编辑前后只改变 bgp 的定义引用和具体命令、健康 repairRecommendation 及相应 revision；同名输入 ID、类型、绑定与来源保留，原精确版本未变。
- 草稿空命令、空 outputs、无虚构阈值；实际 draft 可保存并明确列出未完成诊断，不能声称 strict 通过。
- 通过浏览器检查同一工作流的命令、Schema、绑定、模板和校验；保存一次测试说明后读回确认可继续编辑。
- 记录每项通过/失败/未验证、人工干预、会话 ID、耗时、token 信息。真实 Agent 失败不能由 SDK 成功替代。

单场景 20 分钟上限；连续三次相同无进展错误停止。修改 Skill 后最多追加两轮全新创建，不覆盖历史证据。只保留有效演示或明确标记的有效草稿；清理本次无效临时数据。
