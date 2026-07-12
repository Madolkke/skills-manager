# SkillHub 正式版技术栈

本文档记录当前主分支的权威技术栈。目标是服务 `Skill -> SkillVersion -> EvalRun(context) + EvalSetVersion` 证据链，不再保留 Variant、demo 或 prototype 方案。

## 当前实现

| 层 | 选择 | 当前职责 |
| --- | --- | --- |
| API | FastAPI + Pydantic v2 | HTTP 契约、actor context、字段校验、错误映射。 |
| 数据层 | SQLAlchemy 2 | PostgreSQL-only schema 和 store。 |
| 本地数据库 | PostgreSQL | 通过 `SKILLHUB_DATABASE_URL` 注入连接串，启动时创建 schema。 |
| Web | Vue + Vite + TypeScript | Web 正式工作台，入口为 `apps/frontend`。 |
| Workflow 图谱 | Vue Flow + ELK.js | 只读拓扑投影和确定性分层布局。 |
| Workflow 结构校验 | Pydantic v2 + Zod | 后端持久化契约与前端即时校验镜像。 |
| Skill 生成 | PyYAML + 纯 Python renderer | 安全 frontmatter 和确定性单文件 `SKILL.md`。 |
| UI 组件 | 本地组件 + CSS 分层 | Hub、版本、测评集、测评、历史和 diff 页面。 |
| 测试 | pytest、Vitest、ESLint | API、Web 单元、lint 和 build。 |
| 内容存储 | 数据库内 artifact 记录 | 保存标准 Skill bundle、case input、expected output 和 actual output。 |

## 技术边界

- API 是事实源边界，Web 不直接读数据库。
- `SkillVersion`、`EvalCaseVersion`、`EvalSetVersion` 和 `EvalRun` 是不可变证据。
- 运行环境标签只属于 `EvalRun.environment_tags` 和 `EvalRun.run_context`。
- Bundle diff 只比较同一 Skill 下两个 `SkillVersion` 的不可变 bundle artifact。
- `AcceptedVerification` 按 `skill_id + skill_version_id + eval_set_version_id + run_context_hash` 收口。
- Workflow 与 Skill 永久一对一绑定，只能单向生成 SkillVersion；编辑器显式保存且不使用浏览器本地持久化。

## 本地优先原则

正式版默认应该在 macOS、Linux 和 Windows Git Bash 下通过 PostgreSQL 配置启动：

```bash
export SKILLHUB_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/skillhub
bash scripts/dev.sh
```

脚本不会生成本地数据库连接串；缺少 `SKILLHUB_DATABASE_URL` 时会直接退出，避免隐式落到错误数据源。

局域网共享时使用：

```bash
SKILLHUB_HOST=0.0.0.0 bash scripts/dev.sh
```

Web 默认根据浏览器当前 hostname 推导 API 地址，避免其他电脑访问时仍请求访问者自己的 `127.0.0.1`。API 默认 CORS 允许 localhost、127.0.0.1 和常见私有网段；自定义域名通过 `SKILLHUB_CORS_ALLOW_ORIGINS` 或 `SKILLHUB_CORS_ALLOW_ORIGIN_REGEX` 配置。

## 后续可替换点

| 能力 | 现在 | 后续方向 |
| --- | --- | --- |
| 数据库 | PostgreSQL 本地开发和部署 | 后续引入 Alembic 管理迁移。 |
| Artifact | 数据库记录内容和 digest | 文件系统、S3/R2/MinIO 或 Git-backed adapter。 |
| Eval strategy | 手工 pass/fail | 外部命令、脚本 runner、LLM judge、人工 review queue。 |
| UI 数据密度 | 本地组件和 CSS | 对表格密集视图引入 TanStack Table。 |
| 认证 | 本地 actor + 签名 cookie | OIDC 或团队账号。 |

## 不采用的旧方案

- 不恢复旧前端工作台、`apps/frontend-v3`、demo backend 或 prototype runtime。
- 不把运行环境标签重新放回内容版本。
- 不把 Git branch、fork 或 PR 作为核心领域对象。
- 不把历史 agent 任务和截图作为正式产品文档的一部分。
