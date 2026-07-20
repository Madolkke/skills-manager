# 验证与仓库约定

本文档记录当前主分支的提交前验证和仓库卫生约定。

## 推荐入口

本地需要安装 `just`、`uv`、Python 3.12、Node.js 22、npm 和 PostgreSQL。所有命令均从仓库根目录执行，并自动读取根目录 `.env`：

```bash
just setup
just dev
just check
```

单独启动 Worker 时必须指定唯一实例 ID；多个终端使用不同 ID：

```bash
just worker opencode-worker-1
just worker opencode-worker-2
```

`just check` 会在 PostgreSQL 测试数据库不可用时失败，不会静默跳过数据库用例。提交前执行完整 CI 等价检查：

```bash
just ci
```

`just ci` 会先将 `SKILLHUB_DATABASE_URL` 指向的数据库升级到 Alembic head，再检查 revision、migration drift 和全部前后端质量门禁。可通过 `just --list` 查看数据库、单项检查和独立服务命令。

## 底层验证命令

以下命令与 `justfile` 保持一致，适合未安装 `just` 或需要单独排障时使用。

API：

```bash
cd apps/backend
uv run python -m skillhub.models.schema.cli upgrade
uv run python -m skillhub.models.schema.cli check
uv run alembic check
uv run python -m compileall -q skillhub skillhub_worker
uv run ruff check skillhub skillhub_worker tests
uv run mypy skillhub/models/schema
uv run pytest
```

Web：

```bash
cd apps/frontend
npm run test
npm run lint
npm run build
```

## 仓库边界

- 运行时代码只放在 `apps/backend` 和 `apps/frontend`。
- 本地持久化数据只放在 `.data/`，该目录不提交。
- 依赖、构建产物和测试结果不提交。
- 数据库使用 Alembic migration；验证时必须执行 `alembic upgrade head`、`alembic check` 和真实 PostgreSQL 测试。
- 测试 fake 放在 `apps/backend/tests/fakes`，不放入 production application 层。

## 清理规则

- 新增脚本前先确认是否能复用 `scripts/dev.sh` 或 package scripts。
- 新增文档前先判断是否应补充 README、`docs/architecture.md`、`docs/api-contract.md`、`docs/ui-design.md` 或本文档。
- 临时 mockup、调试截图、导出包和本地数据库不得提交。
