# services 目录约定

本目录是后端三层结构中的 Service 层，承载业务流程、权限校验、状态流转和跨 store 编排。修改 service 文件后，必须同步检查并更新本文档中的“文件语义”列表。

## 目录语义

- `workflow_authoring.py`、`workflow_authoring_contract.py`：MCP 工作流分页查询、字段上下文、局部编辑批次与只读预检，通过 `models.rules.workflows.save_policy` 与正式保存共用策略及阻断诊断规则；读取、预检及保存通过 Store 返回完整表达式诊断和 UTF-16 字段位置。
- `mcp_identity.py`：仅 MCP 写工具使用的 Cookie 非空检查和模拟用户解析；身份接口 URL 为预留配置，本期不发 HTTP。

- `pagination.py`：独立分页与轻量详情用例，保留旧列表 API 及身份规则。

- `command_parsing.py`、`ttp_worker.py`：系统命令只读选择、TTP 独立子进程解析、超时回收与结果校验；不执行设备命令。

- `expression_functions.py`：封装后台全局表达式函数 CRUD。

- `analytics.py`：提供运营统计读取及按 actor 记录页面访问。

- `__init__.py`：统一导出对 View 层开放的 service 类。
- `base.py`：提供 service 基类和共享 store 持有逻辑。
- `admin.py`：后台管理兼容 facade，仅组合下列三个小型 service。
- `admin_catalog.py`：封装 Skill、Tag Catalog 和 Tag 级联管理。
- `admin_access.py`：封装用户组、成员和角色授权管理。
- `admin_runtime.py`：封装发布目标、发布记录、Worker 状态和 Opencode Agent 管理。
- `command_library.py`：封装系统/用户 CLI 命令库搜索、具体命令只读预览、版本过滤和管理员 CRUD；局部更新保留未传及 null 字段，允许显式空值清空内容。
- `artifacts.py`：封装 artifact 下载和 bundle 差异查询。
- `evaluations.py`：封装测评集、测试例、运行测评和聚合结果相关流程。
- `executor_workflows.py`：读取当前 Workflow 文档并转换为外部执行器 DTO。
- `evaluation_reads.py`：封装测评详情、历史和矩阵等只读用例。
- `external.py`：封装外部 Skill zip upsert API 的创建和更新流程。
- `opencode.py`：封装读取和脱敏 Opencode provider/model 配置，以及测评页可用 Opencode Agent 列表。
- `publish_release.py`：封装后台确认发布时调用的发布 hook。
- `reviews.py`：封装评审、评审回复、关闭评审、通知、发布单创建和评审通过后的自动发布流程。
- `saved_views.py`：封装保存视图的创建和删除流程。
- `skill_builder.py`：封装 AI 创建 Skill 会话、消息入队、工作区快照保存和最终创建 Skill 流程。
- `skills.py`：封装 Skill 创建、导入、更新、权限和列表详情查询流程。
- `versions.py`：封装 Skill 版本创建流程。
- `workflows.py`：封装 Workflow Skill 原子创建、显式保存、Import Bundle 导入导出、元信息更新、Collection Catalog 和固定日志 SQL 列目录读取，以及表达式/绑定目标 Schema 的静态批量校验。
- `workflow_executor_client.py`：封装外部执行器的单步运行、状态查询、暂停输入结构读取和恢复调用，并校验其协议响应。
- `workflow_debug.py`：组合 Workflow 单步调试案例和运行编排能力。
- `workflow_debug_cases.py`：封装调试例 CRUD、字段清洗和当前 Workflow 引用检查。
- `workflow_debug_runs.py`：编排调试运行启动、轮询、暂停恢复、目标判定和持久化状态流转。
- `workflow_debug_runtime.py`：解析执行器运行配置，并提供调试历史游标和公共响应投影。
- `workflow_syncs.py`：编排 Workflow Generator 目录、无副作用同步预览、确认摘要校验和 SkillVersion 同步。

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

- 系统命令创作：搜索仅返回规则捕获；预检提供实际输入快照，`call.set_command` 保留来源并创建当前调用副本。
