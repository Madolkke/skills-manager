# 本地 Session 退出控制实现计划

> **给执行代理：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按步骤执行本计划。步骤使用 checkbox（`- [ ]`）追踪。

**目标：** 给本地 Local login 面板补退出登录入口，清除 actor cookie 后回到默认 actor，并刷新当前权限状态。

**架构：** 复用后端已有 `DELETE /api/session`。前端 `LocalSessionPanel` 增加 `onClearSession`，`DecisionWorkbench` 调用 session delete 后通过现有 `runCommand -> loadSkills` 刷新 skill detail 和 capabilities。

**技术栈：** FastAPI、React、Next.js、Playwright。

---

### 任务 1：退出登录红绿路径

**文件：**
- 修改：`apps/web/e2e/skills-workbench.spec.ts`
- 修改：`apps/web/components/session/local-session-panel.tsx`
- 修改：`apps/web/components/decision-workbench.tsx`
- 修改：`apps/web/app/globals.css`

- [x] **Step 1: 写 E2E 红测**
  - 新增测试 `operator can clear the local session actor`。
  - 清空 catalog 后打开 `/skills`。
  - 登录 `release-manager`，填写 `skillhub-dev`，断言面板显示 `release-manager`。
  - 点击 `退出登录`。
  - 断言面板显示 `product-operator`，`退出登录` disabled。
  - 导入一个 skill，断言访问控制 owner 行显示 `product-operator`。

- [x] **Step 2: 跑 E2E 红灯**
  - 运行：`cd apps/web && npm run e2e -- skills-workbench.spec.ts -g "clear the local session"`
  - 预期：失败，因为当前页面没有 `退出登录` 按钮。

- [x] **Step 3: 实现前端退出**
  - `LocalSessionPanelProps` 增加 `onClearSession: () => void | Promise<void>`。
  - `LocalSessionPanel` 渲染 `.localSessionActions`，包含 `登录 actor` 和 `退出登录`。
  - 当前 actor 为 `product-operator` 时禁用 `退出登录`。
  - `DecisionWorkbench` 新增 `clearSession()`，调用 `apiSend<SessionResponse>("/api/session", { method: "DELETE" })`，设置返回 actor。
  - `DecisionWorkbench` 把 `clearSession` 传给 `LocalSessionPanel`。

- [x] **Step 4: 补 CSS**
  - `.localSessionActions` 两列布局。
  - `.localSessionSecondaryButton` 使用中性边框按钮，不和登录主按钮抢层级。

- [x] **Step 5: 跑 E2E 绿灯**
  - 运行：`cd apps/web && npm run e2e -- skills-workbench.spec.ts -g "clear the local session"`
  - 预期：通过。

### 任务 2：视觉基线和文档

**文件：**
- 修改：`apps/web/e2e/visual-workbench.spec.ts-snapshots/local-session-panel-chromium-darwin.png`
- 新建：`.agent/tasks/TASK-068.json`
- 修改：`.agent/tasks.json`
- 修改：`.agent/logs/LOG.md`
- 修改：`README.md`
- 修改：`docs/product-ux-review.md`
- 修改：`docs/product-ux-friction-audit-2026-05-14.md`
- 修改：`docs/product-completion-audit-2026-05-08.md`

- [x] **Step 1: 更新 local session 视觉基线**
  - 运行：`cd apps/web && npm run e2e -- visual-workbench.spec.ts -g "local session panel" --update-snapshots`
  - 预期：通过，基线包含 `退出登录` 按钮。

- [x] **Step 2: 更新中文文档和任务记录**
  - 记录本地 session 现在可以退出到默认 actor。
  - 明确这仍然不是正式认证，只是开发期 session 控制补全。

- [x] **Step 3: 完整验证**
  - `cd apps/api && UV_NO_CACHE=1 uv run pytest`
  - `cd apps/web && npm run test:unit`
  - `cd apps/web && npm run typecheck`
  - `cd apps/web && npm run build`
  - `cd apps/web && npm audit --omit=dev`
  - `cd apps/web && npm run e2e`
  - `git diff --check`
  - `jq empty .agent/tasks.json .agent/tasks/TASK-068.json`
