# backend 目录约定

本目录是 SkillHub 后端工作区，包含 FastAPI API、后台 worker、数据库 schema、业务规则和后端测试。修改本目录时，优先保持 `bootstrap / views / services / models` 三层结构清晰，不恢复旧的 `api/routes`、`application`、`domain`、`infrastructure` 或 `repository` 分层。

## 目录语义

- `skillhub/bootstrap/`：创建 FastAPI app、注册中间件、异常处理和启动期 schema 初始化。
- `skillhub/views/`：HTTP View 层，只处理请求解析、依赖注入、响应组织和路由注册。
- `skillhub/services/`：Service 层，承载业务流程、权限校验、状态流转和跨 store 编排。
- `skillhub/models/`：Model 层，包含实体、错误、纯业务规则、数据库结构和数据访问入口。
- `skillhub_worker/`：后台 worker，消费测评任务并调用 Opencode、Laminar 等执行侧能力。
- `tests/`：后端单元测试、API 测试、架构约束测试和 worker 测试。
- `migrations/`：保留迁移相关目录；当前项目仍以 schema sync 为主。

## 依赖方向

保持以下方向：

```text
bootstrap -> views
views -> services
services -> models.store
services -> models.rules
models.store -> models.operations
models.operations -> models.schema
worker -> models.store / models.rules
```

约束：

- View 层不直接访问 `models.operations` 或 `models.schema`。
- Service 层不 import FastAPI，不直接访问 `models.operations` 或 `models.schema`。
- Model 层不 import `views`、`services` 或 `bootstrap`。
- Worker 可以复用 Model 层和执行侧客户端，但不要调用 View 层。
- 新增或调整子目录职责时，同步更新对应子目录的 `AGENTS.md`。

## 修改规则

- 修改 `skillhub/views/` 时遵守 `skillhub/views/AGENTS.md`。
- 修改 `skillhub/services/` 时遵守 `skillhub/services/AGENTS.md`，并同步维护其中的文件语义列表。
- 修改 `skillhub/models/` 时遵守 `skillhub/models/AGENTS.md`。
- 修改 worker 行为时优先复用现有 `skillhub_worker` 客户端、workspace 和 trace helper。
- 后端 HTTP API contract 不应因内部重构改变；必要时同步更新 `views/schemas.py`、`views/responses.py` 和测试。

## 验证建议

常规后端改动至少运行：

```powershell
cd apps/backend
uv run python -m compileall -q skillhub skillhub_worker
uv run pytest -q tests/test_architecture_layers.py
```

涉及业务流程、schema、store、worker 或 API contract 时运行完整测试：

```powershell
cd apps/backend
uv run pytest -q
```
