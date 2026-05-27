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

## 保留的技术债

`apps/api/skillhub/infrastructure/db/repositories.py` 仍然过大，下一轮应按写入命令、读模型、权限、artifact/diff 拆分。当前清理只拆 API 边界，避免在删除历史噪音的同一轮引入 repository 行为风险。

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
