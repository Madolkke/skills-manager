# services 目录约定

本目录是后端三层结构中的 Service 层，承载业务流程、权限校验、状态流转和跨 store 编排。修改 service 文件后，必须同步检查并更新本文档中的“文件语义”列表。

## 目录语义

- `__init__.py`：统一导出对 View 层开放的 service 类。
- `base.py`：提供 service 基类和共享 store 持有逻辑。
- `admin.py`：后台管理兼容 facade，仅组合下列三个小型 service。
- `admin_catalog.py`：封装 Skill、Tag Catalog 和 Tag 级联管理。
- `admin_access.py`：封装用户组、成员和角色授权管理。
- `admin_runtime.py`：封装发布目标、发布记录、Worker 状态和 Opencode Agent 管理。
- `artifacts.py`：封装 artifact 下载和 bundle 差异查询。
- `evaluations.py`：封装测评集、测试例、运行测评和聚合结果相关流程。
- `evaluation_reads.py`：封装测评详情、历史和矩阵等只读用例。
- `external.py`：封装外部 Skill zip upsert API 的创建和更新流程。
- `opencode.py`：封装读取和脱敏 Opencode provider/model 配置，以及测评页可用 Opencode Agent 列表。
- `publish_release.py`：封装后台确认发布时调用的发布 hook。
- `reviews.py`：封装评审、评审回复、关闭评审、通知、发布单创建和评审通过后的自动发布流程。
- `saved_views.py`：封装保存视图的创建和删除流程。
- `skill_builder.py`：封装 AI 创建 Skill 会话、消息入队、工作区快照保存和最终创建 Skill 流程。
- `skills.py`：封装 Skill 创建、导入、更新、权限和列表详情查询流程。
- `versions.py`：封装 Skill 版本创建流程。
- `workflows.py`：封装 Workflow Skill 原子创建、显式保存、Import Bundle 导入、元信息更新、Catalog 读取和同步生成 SkillVersion。

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
- service 不持有或提交 SQLAlchemy `Session`；请求级事务由 View dependency 管理。
- service 方法不得使用直接 `Any` 返回标注；复杂写操作优先返回 dataclass/DTO。
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
