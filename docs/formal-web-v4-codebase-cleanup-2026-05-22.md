# Web V4 代码清理审计

日期：2026-05-22

结论：主分支后续只保留正式 SkillHub 运行时代码：`apps/api`、`apps/web-v4`、正式启动脚本、正式测试和正式文档。旧工作台、早期 demo 和 prototype 已从主分支移除，避免后续开发继续在多套 UI / API 原型之间分叉。

## 清理范围

已移除：

- `apps/web`：旧 Next.js 工作台，包含权限、治理、审计、promotion review、run matrix 等不属于 Web V4 主流程的历史界面。
- `demo`：早期 Vite 前端 demo。
- `demo-backend`：早期 demo API 和外部 runner。
- `prototype`：早期静态 prototype。
- `scripts/dev-legacy-web.sh`：旧工作台启动入口。

已调整：

- `scripts/dev.sh`：不再支持 `SKILLHUB_WEB_FLAVOR=legacy`，只分发到 `scripts/dev-v4.sh`。
- `.github/workflows/ci.yml`：移除早期 demo 后端和 demo 前端 job；正式 API job 改为跑 `pytest apps/api/tests`；正式 Web job 改为 `apps/web-v4` 的 lint、unit 和 build。
- `README.md`：移除旧工作台、早期原型和 demo runner 使用说明，明确后续产品开发以 `apps/api` 和 `apps/web-v4` 为准。

## 保留范围

- `docs/` 中的历史审计、计划和设计记录保留。它们是项目决策记录，不再作为可运行代码入口。
- `examples/evaluators/`、`fixtures/`、`schemas/` 保留，用于正式 API 和后续集成参考。
- `.agent`、`.agents`、`.codex`、`.claude`、`.cursor` 保留为本项目的本地 agent/技能配置。

## 后续规则

1. 新产品功能默认进入 `apps/api` 和 `apps/web-v4`。
2. 不再新增旧 `apps/web`、`demo`、`demo-backend` 或 `prototype` 运行时代码。
3. 如果必须恢复历史原型，只能另开独立分支或独立 PR，不能混进正式版主流程。
4. CI 必须验证正式 API 和正式 Web，不再用早期 demo 作为健康信号。
