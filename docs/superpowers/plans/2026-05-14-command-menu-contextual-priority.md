# Command menu 上下文化排序执行计划

> **给 agentic workers:** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐项执行本计划。步骤使用 checkbox (`- [ ]`) 跟踪。

**目标:** 让 `Cmd/Ctrl+K` 在不同 workbench mode 下优先展示当前最相关的动作，而不是永远按静态全局顺序展示。

**架构:** 在 `buildWorkbenchCommands` 中保留现有命令 catalog，再新增稳定排序函数，根据 `currentMode` 和空 skill 状态提前相关命令。`CommandMenu` 的 ARIA、搜索、Tab trap 和 disabled 下沉逻辑不改动。

**技术栈:** React hooks、纯 TypeScript command config、Vitest、Playwright E2E、Next.js typecheck/build。

---

### Task 1: 写上下文化排序红灯测试

**Files:**
- Modify: `apps/web/components/command-menu/workbench-command-config.test.ts`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 新增 Vitest 排序断言**

在 `buildWorkbenchCommands` describe 内新增三个测试：

```ts
it("prioritizes eval actions when the current mode is evals", () => {
  const { commands } = createCommands({ currentMode: "evals" });

  expect(commands.slice(0, 4).map((command) => command.id)).toEqual([
    "record-run",
    "new-case",
    "batch-case",
    "nav-history",
  ]);
});

it("prioritizes variant maintenance when the current mode is variants", () => {
  const { commands } = createCommands({ currentMode: "variants" });

  expect(commands.slice(0, 4).map((command) => command.id)).toEqual([
    "new-variant",
    "new-version",
    "compare-version",
    "nav-evals",
  ]);
});

it("prioritizes creation entry points before a skill exists", () => {
  const { commands } = createCommands({
    canCompareVersions: false,
    casesCount: 0,
    currentMode: "overview",
    hasPersistedSkill: false,
  });

  expect(commands.slice(0, 3).map((command) => command.id)).toEqual([
    "import-skill",
    "new-skill",
    "nav-overview",
  ]);
});
```

- [x] **Step 2: 新增 E2E 用户可见排序断言**

在 `skills-workbench.spec.ts` 增加一个测试：导入 skill、添加 case、进入 `测评` 页、打开 command menu，不输入搜索时第一条 option 应该是 `记录本次测评`。

- [x] **Step 3: 验证红灯**

Run:

```bash
cd apps/web
npm run test:unit -- --runInBand
```

Expected: FAIL because `currentMode` does not exist and command order is still static.

### Task 2: 实现 mode priority 排序

**Files:**
- Modify: `apps/web/components/command-menu/workbench-command-config.ts`
- Modify: `apps/web/components/command-menu/use-workbench-commands.ts`
- Modify: `apps/web/components/decision-workbench.tsx`

- [x] **Step 1: 扩展 options**

给 `WorkbenchCommandOptions` 增加 `currentMode: WorkbenchMode`，并从 `DecisionWorkbench` 调用 `useWorkbenchCommands` 时传入当前 `mode`。

- [x] **Step 2: 添加稳定排序函数**

在 `workbench-command-config.ts` 添加 `modePriority` 和 `prioritizeCommands`。规则：空 skill 优先 `import-skill/new-skill/nav-overview`；否则按 `currentMode` 的 command id list 提前相关命令，未列出的命令保持原相对顺序。

- [x] **Step 3: 保持现有行为边界**

不改变 command id、title、group、shortcut、disabledReason、run callback；不修改 `CommandMenu`。

- [x] **Step 4: 验证绿色**

Run:

```bash
cd apps/web
npm run test:unit
UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npx playwright test e2e/skills-workbench.spec.ts --project=chromium -g "command menu prioritizes"
```

Expected: unit tests pass and targeted E2E passes.

### Task 3: 文档和完整验证

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Create: `.agent/tasks/TASK-045.json`
- Modify: `.agent/tasks.json`
- Modify: `.agent/logs/LOG.md`

- [x] **Step 1: 更新产品文档**

记录 command menu 已完成上下文化排序第一阶段：空 skill、测评、变体、历史、差异、审计各有优先命令；最近使用/个性化排序留给后续。

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
jq empty .agent/tasks.json .agent/tasks/TASK-045.json
```

Expected: all pass.
