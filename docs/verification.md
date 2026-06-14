# 验证与仓库约定

本文档记录当前主分支的提交前验证和仓库卫生约定。

## 必跑验证

API：

```bash
cd apps/api
uv run pytest
```

Web：

```bash
cd apps/web
npm run test
npm run lint
npm run build
```

## 仓库边界

- 运行时代码只放在 `apps/api` 和 `apps/web`。
- 本地持久化数据只放在 `.data/`，该目录不提交。
- 依赖、构建产物和测试结果不提交。
- 当前开发阶段不使用 Alembic migration 流程，数据库由启动时 schema 初始化管理。
- 测试 fake 放在 `apps/api/tests/fakes`，不放入 production application 层。

## 清理规则

- 新增脚本前先确认是否能复用 `scripts/dev.sh` 或 package scripts。
- 新增文档前先判断是否应补充 README、`docs/architecture.md`、`docs/api-contract.md`、`docs/ui-design.md` 或本文档。
- 临时 mockup、调试截图、导出包和本地数据库不得提交。
