# 旧 apps/web 工作树审计

日期：2026-05-22

结论：本文件记录的是 `redesign/formal-skillhub-ui` 开发工作树在 2026-05-22 出现的旧 `apps/web` 历史 redesign 脏改动和未跟踪文件。它们没有被纳入 Web V4 正式版证据，也不应在正式版发布分支中混入。默认启动入口已经指向 `apps/web-v4`；旧工作台只通过 legacy 入口保留用于对照。

## 当前入口归属

- 默认正式入口：`bash scripts/dev.sh` 会执行 `scripts/dev-v4.sh`，启动 `apps/api` 和 `apps/web-v4`。
- 旧工作台入口：`bash scripts/dev-legacy-web.sh` 或 `SKILLHUB_WEB_FLAVOR=legacy bash scripts/dev.sh`，启动 `apps/web`。
- 本审计不证明旧 `apps/web` 可发布，也不证明旧工作台符合 5 张正式版参考图。

## 原开发工作树脏改动概览

当时的 `git status --short` 显示旧 `apps/web` 包含以下范围：

- 修改：`apps/web/app/globals.css`、`apps/web/app/skills/page.tsx`、多个 `apps/web/components/*` 面板、`apps/web/package.json` 和 `apps/web/package-lock.json`。
- 删除：`apps/web/components/empty-state.tsx`、`apps/web/components/sidebar.tsx`。
- 未跟踪：`apps/web/app/styles/*`、`apps/web/components/app-rail.tsx`、`apps/web/components/hub-home.tsx`、`apps/web/components/ui/*`。

当时的 `git diff --stat -- apps/web` 规模为 14 个已跟踪文件，约 1023 行新增、971 行删除；这还不包含未跟踪的新样式和 UI 组件。

## 变更性质

- `apps/web/app/globals.css` 从旧的 700 多行样式大文件大幅缩小，并拆出未跟踪的 `apps/web/app/styles/base.css`、`forms.css`、`hub.css`、`responsive.css`、`shell.css`、`skill.css` 和 `ui.css`。
- `apps/web/package.json` 新增了 Radix、`clsx`、`lucide-react` 等 UI 依赖，`package-lock.json` 因此出现大规模依赖变化。
- 旧 `Sidebar` / `EmptyState` 被移除，新增 `AppRail` 和 `HubHome`，说明这批改动来自旧前端的一次独立外壳 redesign。
- 多个旧面板开始改用本地 `Button`、`Dialog`、`SelectField` 等未跟踪 UI 组件。
- `apps/web/components/app-rail.tsx` 中仍存在没有业务处理器的 `设置` 图标按钮，旧工作台还没有完成正式版要求的“只暴露有真实行为的入口”约束。

## 风险

1. 这批改动不在默认正式入口中运行，但会持续让 `git status` 显示脏工作树，容易误导发布、审计和提交范围判断。
2. 旧 `apps/web` 与正式 `apps/web-v4` 有相似的 UI 目标，但结构、运行时和证据链不同，不能直接互相替代。
3. 如果把旧工作台脏改动混入 Web V4 正式版提交，会增加依赖和 UI 行为的不确定性。
4. 如果未来确实需要保留旧 redesign，应先隔离到单独分支或单独提交，再独立验证 legacy 启动和旧页面行为。

## 建议处理方式

优先级从高到低：

1. **归档保留**：如果这批旧 redesign 有参考价值，把当前 `apps/web` 状态提交到单独 legacy 分支，不进入 Web V4 正式分支。
2. **选择性迁移**：只把确实优于 Web V4 的设计或组件思想迁移到 `apps/web-v4`，迁移前必须先写独立验收点并跑 Web V4 验证。
3. **明确丢弃**：如果确认旧 redesign 不再需要，再由用户明确授权后丢弃；不要在没有授权时执行回退或删除。

## 当前操作原则

- 正式版提交继续只点名 stage `apps/web-v4`、`apps/api`、`docs`、`README.md` 和相关脚本。
- 不使用 `git add .`。
- 不对旧 `apps/web` 执行 `git checkout --`、`git restore`、`git reset --hard` 或批量删除。
- 最终 PR/发布记录中需要说明：旧 `apps/web` 脏改动仍是未归档历史工作台状态，不是 Web V4 正式版的一部分。

## 本轮验证

本审计写入后已重新运行 Web V4 正式版验证，并确认默认入口仍进入 `apps/web-v4`：

- `cd apps/web-v4 && npm run lint`
- `cd apps/web-v4 && npm run build`
- `cd apps/web-v4 && npm run test`
- `cd apps/web-v4 && npm run e2e`
- `cd apps/web-v4 && npm run e2e:visual`
- `cd apps/api && uv run pytest`
- `git diff --check -- README.md docs apps/web-v4`
- `SKILLHUB_API_PORT=18113 SKILLHUB_WEB_PORT=13113 SKILLHUB_DATA_DIR=/tmp/skillhub-legacy-audit-smoke-data bash scripts/dev.sh`
- `npx agent-browser open http://127.0.0.1:13113/skills`
- `npx agent-browser snapshot -i`

结果：Web lint、build、unit、E2E、视觉 smoke、API pytest 和 whitespace check 均通过；agent-browser snapshot 显示 Web V4 Hub 的 `SkillHub`、`新建 Skill`、筛选和排序控件，并在点击 `新建 Skill` 后显示新建 Skill 对话框。原开发工作树里的旧 `apps/web` 没有被 stage、提交、回退或删除；本正式版发布分支也不包含旧 `apps/web` redesign 改造。
