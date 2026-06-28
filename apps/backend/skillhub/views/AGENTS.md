# views 目录约定

本目录是后端三层结构中的 View 层，只处理 HTTP 边界：路由注册、依赖注入、请求解析、响应组织和认证头解析。业务流程、权限判定和状态流转应下放到 `services/`。

## 目录语义

- `__init__.py`：集中注册所有 FastAPI routes。
- `auth.py`：解析普通 actor、后台密钥等 HTTP 身份输入。
- `dependencies.py`：创建数据库 engine、store 和 service 依赖。
- `opencode.py`：提供 Opencode provider/model 配置的脱敏代理接口。
- `schemas.py`：HTTP request/response schema，保持 API contract 稳定。
- `responses.py`：把领域对象和 service 返回值转换成 HTTP 响应结构。
- 其他业务文件：按资源组织 endpoint，例如 `skills.py`、`evaluations.py`、`reviews.py`。

## 依赖方向

保持以下方向：

```text
views -> services
views -> models.entities/errors/rules
```

约束：

- endpoint 函数只做 HTTP 相关工作，不直接写业务流程。
- 除 `dependencies.py` 外，不直接创建或持有 `SkillHubStore`。
- 不 import `models.operations` 或 `models.schema`。
- 不在 view 中访问 SQLAlchemy table、engine transaction 或底层数据访问方法。
- 新增 API 时优先新增 service 方法，再由 view 调用。

## 修改规则

- 修改请求体或响应体时，同步更新 `schemas.py`、`responses.py` 和相关测试。
- 新增路由文件后，在 `__init__.py` 注册。
- 保持错误返回通过统一异常处理和现有响应格式，不在 endpoint 中临时拼不同格式。
- 不恢复 `api/routes` 旧目录。

## 验证建议

```powershell
cd apps/backend
uv run python -m compileall -q skillhub skillhub_worker
uv run pytest -q tests/test_architecture_layers.py
```
