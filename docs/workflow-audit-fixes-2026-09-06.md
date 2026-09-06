# 近期代码审计修复记录

审计范围：2026 年 8 月 16 日至 29 日，基线 `d6c3955`。本轮修复 9 项问题，不扩展自定义函数、全局替换或运行时表达式求值。

## 修复与回归对应

| 问题 | 修复 | 回归测试（测试目录内） |
| --- | --- | --- |
| 1. 系统命令局部更新丢字段 | PUT/PATCH 未传和 null 保留，空数组/空串清空 | 后端 `test_command_library_updates.py`、`test_command_source_transactions.py` |
| 2. 样例 ID 冲突 | 随机 ID；加载修复重复及缺失 ID，保留样例内容 | 前端 `AdminSystemCommandsTab.test.ts` |
| 3. 来源同步遗漏引用 | 比较所有表达式入口的路径、类型、新增诊断及可见输出冲突 | 后端 `test_command_source_diagnostics.py` |
| 4. 重复调用同步读旧版本 | 先构建候选快照、全部校验，再统一写入版本 | 后端 `test_command_source_sync.py`、`test_command_source_transactions.py` |
| 5. 批量校验取消后漏检 | 未完成条目重新入队，失败不占成功缓存，过滤过期响应 | 前端 `workflow-expression-validation.test.ts`、`workflow-expression-validation-lifecycle.test.ts` |
| 6. 跨步骤绑定未贯通 | 执行器按调用顺序及图前序解析；常规模板使用完整调用索引 | 后端 `test_workflow_cross_step_bindings.py` |
| 7. 可选对象被误拒 | 内部类型区分属性存在性和值类型，公开响应保持兼容 | 后端 `test_expression_binding_regressions.py`、`test_command_source_binding_types.py` |
| 8. split/and/or 推导错误 | 具体数组项类型及操作数返回类型联合 | 后端 `test_expression_binding_regressions.py`、`test_command_source_binding_types.py` |
| 9. 模板分隔符解析错误 | 引号、转义、三引号及括号状态机；前后端统一 UTF16 诊断位置 | 后端 `test_expression_binding_regressions.py`；前端 `workflow-template.test.ts` |

新增回归先在旧实现上确认失败，再修复；使用已有 fixture、API TestClient 和 Vue Test Utils。管理端添加/删除/保存、工作流保存/导入导出/执行器转换/四种 Skill 生成通过自动化流程验证。

## 验证环境与结果

- 前端完整测试：277 项通过；ESLint、类型检查和生产构建通过。构建仍提示大于 500 kB 的产物，本轮不调整打包策略。
- 后端 compileall、Ruff、Schema mypy、架构测试通过。
- PostgreSQL 使用本次创建的隔离 Docker 实例，测试库为 `skillhub_audit_test`，强制 `SKILLHUB_REQUIRE_POSTGRES_TESTS=1`，不操作现有业务数据库。
- 系统命令重复调用只新增一个版本；破坏结论模板的来源同步返回 400，工作流文档及版本数量保持不变。事务回归通过，无数据库不可用跳过。
- 后端最终完整测试：656 项通过、2 项基线失败、1 项跳过，另有 2 个子测试通过。跳过项为 Windows 环境不能创建符号链接的既有测试，不涉及数据库。完整测试收集后补充的传递前序及文档顺序回归另行运行，跨步骤绑定测试共 10 项通过。

## 基线遗留问题

`test_skill_list_statuses.py` 的两个测试预期 `open` / `unreviewed`，实际为 `closed`。已将原始 `git archive HEAD` 展开到临时目录，使用独立 `skillhub_audit_baseline` 数据库重复运行，两项失败完全一致。

测试夹具 `_insert_publish` 会创建更晚的 closed ReviewRequest，而列表读模型按创建时间选择最新评审。该测试最后修改于 2026 年 8 月 13 日，早于本次审计范围；本轮不修改该业务或夹具。因此后端完整质量门禁仍有基线失败，不能宣称全库测试全部通过。

另外修正 `test_workflow_sync_api.py` 的陈旧目录断言，使其包含 8 月 24 日已加入的 `builtin.cli-workflow`，与领域测试及现有接口一致。

## 兼容与交付

- 无数据库迁移、新 HTTP 端点或 Workflow Schema 版本变更。
- 未闭合空模板只报告 `TEMPLATE_UNCLOSED`；`{{}}` 只报告 `TEMPLATE_EMPTY_EXPRESSION`。
- 保存草稿时保留既有诊断；系统来源自动更新新增的不兼容必须阻断整个事务。
- 新模块按本次责任抽取，未全面重构命令库，也未修改用户原有未跟踪资料。

修复提交：`4ef9025`（部分更新及样例 ID）、`dbcaf37`（表达式与模板）、`f94f4fd`（来源同步）、`867e255`（跨步骤绑定）。提交保留在本地，未推送。
