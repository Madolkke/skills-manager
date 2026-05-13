# Command menu 第二阶段执行计划

> **给 agentic workers:** 必须使用 `superpowers:test-driven-development` 执行本计划。步骤使用 checkbox (`- [ ]`) 跟踪。

**目标:** 让 `Cmd/Ctrl+K` 支持最近使用排序、当前 selection 命令和命令 preview，使其成为 SkillHub 工作台的操作入口层。

**架构:** 保留 `DecisionWorkbench -> useWorkbenchCommands -> buildWorkbenchCommands -> CommandMenu` 的边界。`DecisionWorkbench` 只传入当前 selection 和 callback；命令元数据集中在 command config；最近使用排序放在独立纯函数；preview 拆成独立展示组件，避免 `command-menu.tsx` 继续膨胀。

**技术栈:** React hooks、TypeScript 纯函数、Vitest、Playwright E2E、Next.js typecheck/build。

---

### Task 1: 红灯测试

**Files:**
- Modify: `apps/web/components/command-menu/workbench-command-config.test.ts`
- Create: `apps/web/components/command-menu/command-menu-recents.test.ts`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: selection-aware 命令单元测试**

在 `workbench-command-config.test.ts` 增加：

- 选中 case 时，命令列表包含 `selected-case-history`，执行后调用 `onHistoryCase(caseId)`。
- 选中 run 时，命令列表包含 `selected-run-baseline` / `selected-run-candidate`，执行后调用 `onChooseComparisonRun(role, runId)`。
- selection-aware 命令包含 preview facts。

- [x] **Step 2: 最近命令纯函数测试**

新增 `command-menu-recents.test.ts`：

- `rememberRecentCommandId` 会把新命令放到最前、去重、最多保留 5 条。
- `rankCommandsForMenu` 在空 query 时按最近命令提前排序。
- `rankCommandsForMenu` 永远让 disabled 命令排在可用命令之后。

- [x] **Step 3: E2E 红灯**

在 `skills-workbench.spec.ts` 增加或扩展命令菜单测试：

- 执行 `添加 case` 后再次打开菜单，第一条 option 是 `添加 case`。
- 选中 case 后打开菜单，可以看到 preview 中的 case 标题；执行 `查看当前 case 历史` 后，case history panel 可见。

- [x] **Step 4: 验证红灯**

Run:

```bash
cd apps/web
npm run test:unit
UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npx playwright test e2e/skills-workbench.spec.ts --project=chromium -g "command menu"
```

Expected: FAIL，因为新 command ids、recents helper 和 preview DOM 尚不存在。

### Task 2: 实现命令元数据和最近排序

**Files:**
- Create: `apps/web/components/command-menu/command-menu-types.ts`
- Create: `apps/web/components/command-menu/command-menu-recents.ts`
- Modify: `apps/web/components/command-menu/workbench-command-config.ts`
- Modify: `apps/web/components/command-menu/use-workbench-commands.ts`

- [x] **Step 1: 抽出类型**

把 `CommandMenuItem` 移到 `command-menu-types.ts`，新增 `preview` 字段：

```ts
preview?: {
  title?: string;
  body: string;
  facts?: Array<{ label: string; value: string }>;
};
```

- [x] **Step 2: 最近命令 helper**

实现 `rememberRecentCommandId`、`normalizeRecentCommandIds`、`loadRecentCommandIds`、`saveRecentCommandIds`、`rankCommandsForMenu`。

- [x] **Step 3: selection-aware config**

扩展 `WorkbenchCommandOptions`，支持：

- `selection.selectedCase`
- `selection.selectedRun`
- `onHistoryCase`
- `onChooseComparisonRun`

新增 `selected-case-history`、`selected-run-baseline`、`selected-run-candidate`。mode priority 中让 `evals` 优先 case history，让 `history` 优先 selected run actions。

### Task 3: 接入 UI 和工作台 selection

**Files:**
- Create: `apps/web/components/command-menu/command-menu-preview.tsx`
- Modify: `apps/web/components/command-menu/command-menu.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 工作台传入 selection**

在 `DecisionWorkbench` 里从现有 `selectedCase`、`selectedRunId`、`runHistory` 派生 command selection，并传给 `useWorkbenchCommands`。

- [x] **Step 2: CommandMenu 记录最近命令**

执行可用命令时写入 localStorage，打开菜单时读取本地最近命令，并通过 `rankCommandsForMenu` 排序。

- [x] **Step 3: Preview 面板**

新增 `CommandMenuPreview`，在菜单右侧展示 active command 的 preview 或 fallback detail；移动端收成单列。

- [x] **Step 4: 绿色验证**

Run:

```bash
cd apps/web
npm run test:unit
UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npx playwright test e2e/skills-workbench.spec.ts --project=chromium -g "command menu"
```

Expected: unit 和 targeted E2E 全部通过。

### Task 4: 文档、完整验证和提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Create: `.agent/tasks/TASK-049.json`
- Modify: `.agent/tasks.json`
- Modify: `.agent/logs/LOG.md`

- [x] **Step 1: 更新中文产品文档**

记录 Command menu 第二阶段完成：最近使用、selection-aware case/run 命令、preview 面板；服务器端个性化和全局搜索留后续。

- [x] **Step 2: 完整验证**

Run:

```bash
cd apps/web && npm run test:unit
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && npm audit --omit=dev
cd apps/api && uv run pytest
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
jq empty .agent/tasks.json .agent/tasks/TASK-049.json
wc -l apps/web/components/command-menu/command-menu.tsx apps/web/components/command-menu/command-menu-recents.ts apps/web/components/command-menu/command-menu-preview.tsx apps/web/components/command-menu/workbench-command-config.ts
```

Expected: all pass，新增/修改文件保持可维护大小。
