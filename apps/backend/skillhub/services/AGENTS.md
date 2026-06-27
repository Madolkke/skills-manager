# services 目录约定

本目录是后端三层结构中的 Service 层，承载业务流程、权限校验、状态流转和跨 store 编排。修改 service 文件后，必须同步检查并更新本文档中的“文件语义”列表。

## 目录语义

- `__init__.py`：统一导出对 View 层开放的 service 类。
- `base.py`：提供 service 基类和共享 store 持有逻辑。
- `admin.py`：封装后台管理能力，包括用户组、Tag、授权、发布源和发布确认。
- `artifacts.py`：封装 artifact 下载和差异查询。
- `evaluations.py`：封装测评集、测试例、运行测评和聚合结果相关流程。
- `external.py`：封装外部 Skill zip upsert API 的创建和更新流程。
- `publish_release.py`：封装后台确认发布时调用的发布 hook。
- `reviews.py`：封装评审、评审回复、关闭评审、通知和发布单创建流程。
- `saved_views.py`：封装保存视图的创建和删除流程。
- `skills.py`：封装 Skill 创建、导入、更新、权限和列表详情查询流程。
- `versions.py`：封装 Skill 版本创建流程。

## 依赖方向

保持以下方向：

```text
views -> services -> models.store
views -> services -> models.rules
```

约束：

- service 可以依赖 `models.store`、`models.rules`、`models.entities` 和 `models.errors`。
- service 不 import FastAPI，不处理 HTTP request/response 对象。
- service 不直接 import `models.operations` 或 `models.schema`；需要数据能力时通过 `SkillHubStore` 暴露。
- 权限、状态流转和跨资源编排应放在 service，不放在 view。
- 纯计算规则优先放入 `models.rules`，service 只负责调用和编排。

## 修改规则

- 新增、删除或重命名 service 文件时，必须同步更新本文档的“目录语义”。
- 新增 service 方法时，优先保持输入为普通 Python 值或 dataclass，不传 FastAPI 类型。
- 如果 service 需要新的 store 方法，先在 `models.operations` 实现，再通过 `models.store.SkillHubStore` 暴露。
- 不恢复 `repository`、`application` 等旧命名。

## 验证建议

```powershell
cd apps/backend
uv run python -m compileall -q skillhub skillhub_worker
uv run pytest -q tests/test_architecture_layers.py
```

涉及业务流程变更时继续运行完整后端测试：

```powershell
cd apps/backend
uv run pytest -q
```
