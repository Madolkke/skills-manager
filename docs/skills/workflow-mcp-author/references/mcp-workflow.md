# MCP 操作与恢复

## 工具选择

工具前缀随客户端连接名称变化，以下仅为逻辑工具名。检索使用 offset/limit，默认 20、最大 100，按需要继续翻页，不认为首页就是全目录。

| 目的 | 工具与注意事项 |
| --- | --- |
| 确定编辑对象 | search_workflows；名称不唯一时核对 slug、ID、网页入口 |
| 阅读现状 | get_workflow 的 outline/full/node；修改前读取相关完整结构 |
| 获取协议 | get_authoring_contract 的 overview/changes/collections/expressions |
| 系统规则 | search_system_commands(details=true)，仅启用系统命令；核对表达式、版本、完整 outputSchema |
| 共享采集 | search_collections；复用前检查 collectionType=cli、实际命令、输入、输出、精确 revision |
| 字段作用域 | get_expression_context，可附 changes 检查未保存候选 |
| 无写入预检 | validate_workflow_changes；检查 can_save、validation 和 collectionSnapshots |
| 新建外壳 | create_workflow；先确定真实标签，description 非空，slug 遵循实时输入约束 |
| 原子修改 | apply_workflow_changes；每批成功提交后才返回 saved |

只请求分析时不调用创建或保存工具。当前预检要求已有 skill_id，不能以创建空工作流来伪装无写入预览。必要时仅交付分析，明确尚未做服务端完整校验。

## 局部编辑规则

工具参数及操作定位用 snake_case，fields/definition 内作者字段沿用 camelCase。Binding.reference 的 input_id/call_id/output_id 等仍为 snake_case。不要直接提交网页完整文档替代 changes。

- 同批新增对象指定唯一 client_ref，后续操作可用 @名称；跨请求使用正式 ID。
- 预检 id_mappings 不是预留身份；不要跨批保存预检生成 ID。
- 默认先创建结构与采集草稿，再 get_workflow(full) 读回输入 ID，补绑定和表达式。明确且稳定的同批引用可以一批完成。
- 更新只传实际需要改变的字段；数组与 inputBindings 显式提供时按整体替换。局部绑定优先 binding.set/remove。
- 排序传当前列表全部成员；删除节点自动清入边，其他表达式原文仍须检查，不能假定自动重写。

## 来源与副本

| 操作 | 适用情况 |
| --- | --- |
| call.from_system | command_id + 必填具体 command_template；实例输入由实际占位符生成 |
| call.add | 引用已有 definition.id/revision，明确复用该版本 |
| call.create_collection | 创建独立 CLI；fields 是调用，definition 是采集定义 |
| call.set_command | 修改指定调用的具体命令，创建副本；系统来源保留，旧引用显式转换 |
| call.fork_collection | 创建独立副本并修改定义，解除来源 ID 和模式，仅重绑指定调用 |

只需改命令时不要误用 fork_collection 解除来源。系统实例的 Schema 如需独立修改，先说明并确认这属于用户已授权的独立副本范围。输出完整保留，不原地修改系统命令或共享定义。

## 预检与保存

每批先预检。strict 要求零错误，提醒不升级为错误；draft 允许未完成领域内容，但错误函数、未注册函数、不兼容绑定等硬限制仍拒绝。检查具体 code、severity 和 selection/位置，不仅检查 HTTP 成功。

预检失败后保留候选，不写入已知阻断批次。保存仍会重新校验；来源变化导致保存失败时重新读取来源与目标，不假定预检一直有效。合法但未完成草稿明确标为草稿。

一次 apply 的文档、Collection 和审计原子写入；多次 apply 及 create 之间不具有整段事务。部分完成时报告实际 ID、revision、最后成功批次及剩余缺口。

超时或断线可能发生在提交后：先通过已知 skill_id 或唯一 slug 搜索并读回，核对实际字段后再决定后续操作。状态无法判定时停止写入，报告不确定，不重复创建。当前无并发覆盖保护或请求幂等保证。

AUTH_REQUIRED/PERMISSION_DENIED 要求用户处理连接或权限；不索要 Cookie 正文，也不把 Cookie 当作工具参数。工具缺失、身份错误不通过其他接口绕过。
