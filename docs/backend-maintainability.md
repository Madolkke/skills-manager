# 后端维护指南

本文档记录 SkillHub 后端的维护边界，目标是让人工修改能够快速定位责任模块，并减少跨层耦合。

## 修改路径

后端保持以下依赖方向：

```text
bootstrap -> views -> services -> models.store -> models.operations -> models.schema
```

- HTTP 参数和响应结构放在 `apps/backend/skillhub/views/request_models/` 的资源域模块中。
- `apps/backend/skillhub/views/schemas.py` 只是兼容导出层。新增 schema 不应继续堆入该文件。
- 业务流程、权限和跨资源事务放在 `services/`，View 不直接调用 operations 或 SQLAlchemy。
- ORM 读写放在 `models/operations/` 对应业务域，通过请求级 `Session` 执行，并由 `SkillHubStore` 组合后暴露给 Service。
- Skill 列表使用 `skills/list_read_models.py` 批量装配，查询数必须通过 `test_session_lifecycle.py` 保持与 Skill 数量无关。
- 无副作用的校验和决策放在 `models/rules/`。

## 评审模块

评审 Store 的内部辅助能力按责任拆分：

- `reviews/read_models.py`：详情、列表和快照查询。
- `reviews/reviewers.py`：评审人角色展开、来源快照和通知写入。
- `reviews/publishing.py`：发布门禁和发布记录 upsert。
- `reviews/publish_commands.py`：创建发布请求的事务编排和兼容 Store facade。
- `reviews/notification_commands.py`：评审通知已读状态的事务操作。
- `reviews/publish_jobs.py`：发布任务原子入队、`FOR UPDATE SKIP LOCKED` 领取和结果落库。
- `reviews/helpers.py`：兼容组合入口，不在此处新增业务逻辑。
- `reviews/commands.py`：评审创建、回复、关闭和通知的事务编排；修改状态流转时优先保持一个事务内完成。

## Service 拆分

- `admin_catalog.py`、`admin_access.py`、`admin_runtime.py` 分别处理目录、权限和运行态管理，`admin.py` 仅保留兼容 facade。
- `evaluation_reads.py` 负责测评读模型；`artifacts.py` 只负责 bundle diff 和文件下载。

## Schema 变更

- `models/schema/` 中的 Declarative ORM 类是表、字段、约束和 relationship 的唯一代码定义。
- `migrations/versions/` 中的 Alembic revision 是数据库演进记录；禁止恢复启动期 schema patch。
- `models/schema/tables.py` 仅为迁移期间的旧 import 兼容出口，新 operations 不得依赖它。
- 新表或新约束需要修改 ORM 类、生成 Alembic revision，并运行 `alembic check` 和 migration 测试。

## 兼容与验证

重命名内部模块时，优先在旧路径保留薄兼容层，不要让所有 View 同时改动。完成修改后至少运行：

```powershell
cd apps/backend
uv run python -m compileall -q skillhub skillhub_worker
uv run ruff check skillhub skillhub_worker tests
uv run mypy skillhub/models/schema
uv run pytest -q
```

如果修改了 HTTP schema、Store 或 schema 定义，还应运行对应的架构、API 和数据库测试，并检查 `git diff --check`。
