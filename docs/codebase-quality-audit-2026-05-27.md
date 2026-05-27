# 代码库质量审计 2026-05-27

## 结论

本轮清理把主分支收口为正式版 SkillHub 产品仓库。运行时代码只保留 `apps/api`、`apps/web-v4` 和必要脚本；过时 agent 任务体系、重复 skills、旧 demo/prototype 文档、历史截图和未实现的外部 eval import schema 已移除。

## 已删除

| 类型 | 路径 |
| --- | --- |
| Ralph 任务体系 | `.agent/`、`ralph.sh`、`scripts/lib/`、`RALPH.md` |
| 重复 agent 配置 | `.agents/`、`.codex/`、`.cursor/`、`.claude/` |
| 不可移植 MCP 配置 | `.mcp.json` |
| 旧计划和任务文档 | `docs/superpowers/` |
| 旧产品审计和截图 | `docs/product-ui-reference/`、`docs/product-*`、`docs/formal-web-v4-*` |
| 旧 MVP/demo 文档 | `docs/MVP_SPEC.md`、`docs/mvp-design-spec.md`、`docs/sqlite-schema-spike.md`、`docs/architecture-review-1.0.md` |
| 未实装外部导入样例 | `examples/`、`fixtures/`、`schemas/` |

## 权威文档

- `README.md`：当前产品闭环、启动、试用、验收和验证命令。
- `docs/api-contract.md`：正式 API 契约。
- `docs/formal-architecture-v0.1.md`：当前架构和不变量。
- `docs/formal-tech-stack.md`：当前技术栈和后续替换点。
- `docs/formal-ui-design.md`：Web V4 页面与组件契约。
- `docs/storage-adapter-contract.md`：Artifact adapter 边界。
- `docs/roadmap.md`：后续产品方向。

## 代码结构调整

- `skillhub.api.main` 只保留 app 创建、CORS、异常处理和路由注册。
- API schema 移到 `skillhub.api.schemas`。
- SQLite 启动和 repository dependency 移到 `skillhub.api.database`。
- 错误响应和字段校验文案移到 `skillhub.api.responses`。
- 路由按职责拆到 `routes_core.py`、`routes_history.py` 和 `routes_commands.py`。
- `SqlSkillRepository` 保留兼容入口，具体实现拆到 `repository_parts/`：
  - `skill_commands.py`：Skill 和 SkillVersion 写入。
  - `eval_case_commands.py`、`eval_run_commands.py`、`artifact_commands.py`：测评用例、运行记录和 artifact 写入。
  - `read_models.py`、`detail_queries.py`、`run_history_queries.py`、`case_history_queries.py`、`diff_queries.py`：页面读模型、历史和 diff 查询。
  - `roles.py`：角色、权限和审计事件。
  - `core_helpers.py`、`bundle_diff.py`：共享 SQL helper 和 bundle diff 计算。
- SQLAlchemy table metadata 的 index 注册拆到 `infrastructure.db.indexes`。
- in-memory domain 测试 workspace 拆到 `application.in_memory_workspace`。
- 过大的 API/repository 测试文件拆成共享测试基类和按职责命名的测试模块，单文件断言密度降低，测试语义不变。

## 保留的技术债

当前代码、文档和测试文件均已控制在 300 行以内。后续如果某个页面或测试模块继续增长，应按页面子组件、命令域或读模型职责拆分，而不是压缩断言或混合职责。

## 验收

本轮完成后应运行：

```bash
cd apps/api
uv run pytest
```

```bash
cd apps/web-v4
npm run test
npm run lint
npm run build
npm run e2e
npm run e2e:visual
```
