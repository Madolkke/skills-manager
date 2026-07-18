# models 目录约定

本目录是后端三层结构中的 Model 层，承载领域对象、纯业务规则、数据库结构定义和事务内数据访问。修改本目录时，优先保持语义清晰和依赖方向简单，不引入新的架构概念。

## 目录语义

- `entities.py`：领域实体、读模型和跨层传递的数据对象。
- `errors.py`：领域错误和服务层可识别的业务异常。
- `rules/`：纯业务规则，不访问数据库、不依赖 FastAPI、不产生外部副作用。
- `schema/`：SQLAlchemy 2.x Declarative ORM 实体、relationship、Session 工厂和 Alembic revision 校验。
- `operations/`：按业务域组织的 Session + ORM 数据读写操作，包括 Skill、测评、评审、发布、Opencode Agent、Worker 心跳等持久化能力。
- `operations/skills/tag_catalog.py`、`tag_catalog_helpers.py`：Tag Group、Tag 候选值及删除引用保护。
- `operations/skills/list_read_models.py`：Skill 列表批量读模型装配，禁止逐 Skill 查询。
- `operations/skills/tag_cascades.py`：Tag 级联关系、活跃路径计算和历史数据诊断。
- `operations/shared/tagging.py`：所有 Skill 写入口共用的 Tag 清洗、自由值沉淀、条件必填和权限辅助逻辑。
- `operations/workflows/`：Workflow、WorkflowSync 和全局 Collection Catalog 的事务读写、同步状态与审计。
- `operations/workflows/imports.py`：Import Bundle 的原子导入、Collection 身份分配和引用重写。
- `operations/reviews/read_models.py`：评审详情、评审回复、发布目标和发布记录的查询辅助。
- `operations/reviews/reviewers.py`：评审人角色快照、用户组展开和通知写入辅助。
- `operations/reviews/publishing.py`：发布门禁计算和发布记录 upsert 辅助。
- `operations/reviews/publish_commands.py`：发布请求的 Store 命令 facade。
- `operations/reviews/notification_commands.py`：通知已读状态的 Store 命令 facade。
- `operations/reviews/publish_jobs.py`：发布任务的原子入队、并发领取和结果落库。
- `operations/shared/jobs.py`：跨领域复用的 Job 入队和状态更新辅助。
- `operations/reviews/helpers.py`：上述评审辅助能力的兼容组合入口。
- `rules/workflows/`：Workflow/Collection 严格结构、文档格式迁移、领域校验和确定性 Skill 转换。
- `store.py`：Model 层对 Service 层暴露的组合根，持有请求级 Session，并保留薄兼容 facade。

## 依赖方向

保持以下方向：

```text
services -> models.store
services -> models.rules
models.store -> models.operations
models.operations -> models.schema
```

约束：

- `rules/` 不能 import `models.store`、`models.operations`、`models.schema`。
- `schema/` 不能 import `models.store`、`models.operations` 或上层模块。
- `operations/` 可以 import `models.schema`、`models.entities`、`models.errors` 和 `models.rules`。
- `store.py` 只负责 Session 绑定和组合 operations，不通过多重继承承载业务能力。
- `models/` 不能 import `views`、`services` 或 `bootstrap`。
- 不恢复 `domain`、`repository`、`infrastructure`、`application` 等旧分层命名。

## 修改规则

- 新增纯计算、校验、策略判断时，放入 `rules/`。
- 新增表、索引或约束时，先修改 `schema/` Declarative 实体，再生成并审核 Alembic revision。
- 新增事务内读写方法时，放入对应业务域的 `operations/`，使用映射类和现有 Session；不得创建 Engine/Connection。
- Service 层需要新的数据能力时，通过 `SkillHubStore` 暴露，不直接 import `operations/`。
- 保持 HTTP 请求/响应 schema 在 `views/request_models/`，通过 `views/schemas.py` 兼容导出，不要放入 `models/`。
- 修改 import 后运行架构约束测试，避免破坏分层。

## 验证建议

涉及本目录代码变更时至少运行：

```powershell
cd apps/backend
uv run python -m compileall -q skillhub skillhub_worker
uv run ruff check skillhub skillhub_worker tests
uv run mypy skillhub/models/schema
uv run pytest -q tests/test_architecture_layers.py
```

涉及 schema、store 或 operations 行为时，继续运行完整后端测试：

```powershell
cd apps/backend
uv run pytest -q
```
