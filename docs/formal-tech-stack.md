# SkillHub 正式版技术栈

本文档记录当前主分支的权威技术栈。目标是服务 `Skill -> SkillVersion -> EvalRun(context) + EvalSetVersion` 证据链，不再保留 Variant、demo 或 prototype 方案。

## 当前实现

| 层 | 选择 | 当前职责 |
| --- | --- | --- |
| API | FastAPI + Pydantic v2 | HTTP 契约、actor context、字段校验、错误映射。 |
| 数据层 | SQLAlchemy 2 + Alembic | SQLite/PostgreSQL 兼容 schema、迁移和 repository。 |
| 本地数据库 | 文件型 SQLite | 默认写入 `.data/skillhub.sqlite3`，干净 clone 后自动建库。 |
| Web | React + Vite + TypeScript | Web V4 正式工作台，入口为 `apps/web-v4`。 |
| UI 组件 | 本地组件 + CSS 分层 | Hub、版本、测评集、测评、历史和 diff 页面。 |
| 测试 | pytest、Vitest、ESLint、Playwright | API、Web 单元、lint、build、E2E、视觉和小窗口冒烟。 |
| 内容存储 | 数据库内 artifact 记录 | 保存标准 Skill bundle、case input、expected output 和 actual output。 |

## 技术边界

- API 是事实源边界，Web 不直接读数据库。
- `SkillVersion`、`EvalCaseVersion`、`EvalSetVersion` 和 `EvalRun` 是不可变证据。
- 运行环境标签只属于 `EvalRun.environment_tags` 和 `EvalRun.run_context`。
- Bundle diff 只比较同一 Skill 下两个 `SkillVersion` 的不可变 bundle artifact。
- `AcceptedVerification` 按 `skill_id + skill_version_id + eval_set_version_id + run_context_hash` 收口。

## 本地优先原则

正式版默认应该在 macOS、Linux 和 Windows Git Bash 下可直接启动：

```bash
bash scripts/dev.sh
```

脚本默认只设置 `SKILLHUB_DATA_DIR`，不设置 `SKILLHUB_DATABASE_URL`。API 通过该目录生成文件型 SQLite URL，避免 Windows 路径被误判后回退到 `sqlite:///:memory:`。

## 后续可替换点

| 能力 | 现在 | 后续方向 |
| --- | --- | --- |
| 数据库 | SQLite 本地开发 | PostgreSQL 部署。 |
| Artifact | 数据库记录内容和 digest | 文件系统、S3/R2/MinIO 或 Git-backed adapter。 |
| Eval strategy | 手工 pass/fail | 外部命令、脚本 runner、LLM judge、人工 review queue。 |
| UI 数据密度 | 本地组件和 CSS | 对表格密集视图引入 TanStack Table。 |
| 认证 | 本地 actor + 签名 cookie | OIDC 或团队账号。 |

## 不采用的旧方案

- 不恢复 `apps/web`、`apps/web-v3`、demo backend 或 prototype runtime。
- 不把运行环境标签重新放回内容版本。
- 不把 Git branch、fork 或 PR 作为核心领域对象。
- 不把历史 agent 任务和截图作为正式产品文档的一部分。
