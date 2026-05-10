# 上下文命令菜单实现计划

> **给 agentic worker:** 必须按任务逐步执行；步骤使用 checkbox (`- [x]`) 记录状态。

**目标:** 为 SkillHub 工作台加入上下文命令菜单，让高频动作可通过 `Cmd/Ctrl+K` 搜索执行。

**架构:** 新增独立 `CommandMenu` 客户端组件处理过滤、键盘导航和执行；`DecisionWorkbench` 只提供当前上下文命令列表；`AppShell` 顶部按钮通过全局 DOM event 触发菜单打开。

**技术栈:** Next.js App Router、React 19 client components、TypeScript、Playwright E2E、现有全局 CSS。

---

### Task 1: 红测覆盖命令菜单主路径

**文件:**
- 修改: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 写失败测试**

新增测试：

```ts
test("operator can open command menu and jump to add case", async ({ page }) => {
  await importSkillBundle(page, `command-menu-${Date.now()}`);

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.getByRole("dialog", { name: "Command menu" })).toBeVisible();
  await page.getByPlaceholder("搜索命令、页面或动作").fill("添加 case");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "添加测试用例" })).toBeVisible();

  await page.getByRole("button", { name: "Open command menu" }).click();
  await expect(page.getByRole("dialog", { name: "Command menu" })).toBeVisible();
});
```

- [x] **Step 2: 运行红测**

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "operator can open command menu"
```

预期：失败，因为现在顶部按钮没有行为，也没有 command menu dialog。

### Task 2: 实现命令菜单组件

**文件:**
- 新增: `apps/web/components/command-menu/command-menu.tsx`
- 新增: `apps/web/components/command-menu/global-command-button.tsx`
- 修改: `apps/web/components/chrome.tsx`
- 修改: `apps/web/app/globals.css`

- [x] **Step 1: 新增 `CommandMenu` 类型和组件**

组件导出：

```ts
export type CommandMenuItem = {
  id: string;
  title: string;
  group: string;
  detail: string;
  shortcut?: string;
  disabled?: boolean;
  disabledReason?: string;
  run: () => void;
};
```

行为：

- 监听 `Meta/Ctrl+K` 和 `skillhub:open-command-menu`。
- 打开后 focus input。
- 按标题、分组、说明过滤。
- `ArrowUp/ArrowDown` 移动高亮。
- `Enter` 执行第一个可用命令。
- `Esc` 关闭。

- [x] **Step 2: 让顶部按钮可触发菜单**

`GlobalCommandButton` dispatch：

```ts
window.dispatchEvent(new Event("skillhub:open-command-menu"));
```

`AppShell` 用该组件替换静态 `Cmd K` 按钮。

- [x] **Step 3: 样式**

新增 `.commandMenuBackdrop`、`.commandMenuPanel`、`.commandMenuSearch`、`.commandMenuItem` 等类，视觉方向为“高密度操作控制台”：暗色顶部、白色内容、分组小标签、清晰选中态。

### Task 3: 接入 SkillHub 工作台上下文命令

**文件:**
- 修改: `apps/web/components/decision-workbench.tsx`

- [x] **Step 1: 构造命令列表**

在 `DecisionWorkbench` 中用 `useMemo<CommandMenuItem[]>` 提供：

- 打开概览、变体、测评、差异、历史。
- 导入 bundle、新建 skill、新建 variant、追加版本、添加 case。
- 记录本次测评。
- 比较版本。

- [x] **Step 2: 渲染菜单**

在工作台根节点渲染：

```tsx
<CommandMenu commands={commandItems} scopeLabel={selectedDetail.skill.slug} />
```

### Task 4: 验证、文档、提交

**文件:**
- 修改: `README.md`
- 修改: `docs/product-ux-review.md`
- 修改: `docs/product-completion-audit-2026-05-08.md`

- [x] **Step 1: 文档补充**

说明命令菜单借鉴 Linear / GitHub，支持 `Cmd/Ctrl+K` 和顶部按钮。

- [x] **Step 2: 全量验证**

```bash
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
cd apps/api && uv run pytest
git diff --check
```

- [ ] **Step 3: 提交推送**

```bash
git add .
git commit -m "feat: add contextual command menu"
git push
```

## 自检

- 规格覆盖：快捷键、顶部按钮、搜索、执行命令、禁用态、测试、文档。
- 范围控制：没有做跨页面搜索、最近命令、批量操作或新后端。
- 腐化控制：命令菜单 UI 独立文件，workbench 只提供命令元数据。
