# Web V4 正式版发布范围

日期：2026-05-22

结论：正式版主分支只承载 Web V4 需要的 API、前端、脚本和文档；旧 `apps/web`、早期 `demo`、`demo-backend` 和 `prototype` 运行时代码已经在后续清理中移出主分支。

## 纳入范围

- `apps/api`：正式 Web V4 依赖的 API 行为和对应测试。
- `apps/web-v4`：正式版前端、E2E、视觉 smoke、固定基线截图和测试 fixture。
- `scripts/dev.sh`：默认启动正式 Web V4。
- `scripts/dev-v4.sh`：直接启动正式 Web V4。
- `README.md`：中文一键启动、核心流程、验证命令和正式版边界。
- `docs/product-ui-reference/`：5 张正式版目标参考图。
- `docs/formal-web-v4-reference-diff-2026-05-22.md`：参考图差异与取舍。
- `docs/formal-web-v4-completion-audit-2026-05-21.md`：正式版完成度审计。
- `docs/formal-web-v4-codebase-cleanup-2026-05-22.md`：旧运行时代码清理记录。

## 明确排除

- `apps/web` 旧 Next.js 工作台。
- `demo` 早期 Vite demo。
- `demo-backend` 早期 demo API。
- `prototype` 静态 prototype。
- `apps/web-v2`、`apps/web-v3` 历史前端实验。
- `.agent` 任务变更和与 Web V4 正式版无关的历史计划。
- 旧工作台 redesign 中新增的 Radix/lucide/本地 UI 组件。

## 发布判断

- 默认运行入口必须是 `apps/web-v4`。
- 主分支不再提供 legacy 工作台启动入口。
- 正式 PR review 时应重点检查 Web V4 的核心闭环、API 契约、README 一键启动和验证记录。
- 如果后续需要恢复旧工作台或 demo，应另开独立分支或 PR，不与正式版主流程混合。

## 当前 PR 状态

- PR：`https://github.com/xunx911/skills-manager/pull/1`
- Head：`release/formal-skillhub-v4`
- Base：`main`
- 状态：已通过 squash merge 合并到 `main`
- Merge commit：`add9620af4d43cd8544dff0fe50f741c9c164f83`
- 合并前 CI：`Backend tests`、`Formal API domain tests`、`Demo frontend build`、`Formal web build` 均为 `SUCCESS`
- 合并后本地回归：Web lint/build/unit/E2E/视觉 smoke、API pytest、agent-browser 默认入口 smoke 均通过。
- 后续清理：`apps/web`、`demo`、`demo-backend`、`prototype` 和 legacy 启动脚本已在清理 PR 中移出主分支；正式 CI 只保留 `apps/api` 与 `apps/web-v4`。
