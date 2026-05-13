# 表单验证错误摘要 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 SkillHub 高频写入表单加入统一错误摘要、字段旁错误和首个错误聚焦，替换浏览器原生 required 气泡。

**Architecture:** 新增 `ValidatedForm` 作为轻量表单壳层，集中处理 submit-time required 校验、error summary focus 和 summary link focus。`WorkbenchField` 通过 context 获取当前字段错误，继续负责 `aria-invalid`、`aria-describedby` 和字段旁错误渲染。业务表单只把 `<form>` 换成 `<ValidatedForm onValidSubmit={...}>`，不改变现有 mutation 逻辑。

**Tech Stack:** React context/hooks、uncontrolled form + FormData、Vitest、Playwright E2E、Next.js typecheck/build。

---

### Task 1: 红灯测试

**Files:**
- Create: `apps/web/components/forms/form-validation.test.ts`
- Modify: `apps/web/e2e/accessibility-workbench.spec.ts`

- [x] **Step 1: 写 required 文案单元测试**

新增 `form-validation.test.ts`，覆盖：

```ts
expect(requiredFieldMessage("Skill ID", "text")).toBe("填写 Skill ID");
expect(requiredFieldMessage("Skill 文件夹", "file")).toBe("选择 Skill 文件夹");
expect(requiredFieldMessage("确认风险", "checkbox")).toBe("确认 确认风险");
```

- [x] **Step 2: 写 Launchpad 错误摘要 E2E**

在 `accessibility-workbench.spec.ts` 新增测试：清空 catalog，打开 `/skills`，切到 `新建 skill`，直接提交，断言 `.formErrorSummary` 可见且获得焦点，包含 `填写 Skill ID`，点击摘要链接后 `input[name="slug"]` 获得焦点，字段有 `aria-invalid="true"`。

- [x] **Step 3: 写 QuickAddCases 错误摘要 E2E**

导入 skill，进入 `测评`，直接点击 `快速加入`，断言 `.quickCaseGrid .formErrorSummary` 获得焦点，并包含 `填写 标题`、`填写 Input`、`填写 Expected output`。

- [x] **Step 4: 验证红灯**

Run:

```bash
cd apps/web
npm run test:unit
UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npx playwright test e2e/accessibility-workbench.spec.ts --project=chromium -g "error summary"
```

Expected: FAIL，因为 `form-validation.tsx` 和 `.formErrorSummary` 尚不存在。

### Task 2: 实现验证基础件

**Files:**
- Create: `apps/web/components/forms/form-validation.tsx`
- Modify: `apps/web/components/forms/workbench-field.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 实现 required 文案 helper**

导出：

```ts
export type RequiredControlKind = "checkbox" | "file" | "text";
export function requiredFieldMessage(label: string, kind: RequiredControlKind) {
  if (kind === "file") return `选择 ${label}`;
  if (kind === "checkbox") return `确认 ${label}`;
  return `填写 ${label}`;
}
```

- [x] **Step 2: 实现 `ValidatedForm`**

`ValidatedForm` 接收 `onValidSubmit`，内部 `preventDefault`，扫描 required fields。如果缺字段，设置 errors 并聚焦 summary；如果没有错误，清空 errors 并调用 `onValidSubmit(event)`。

- [x] **Step 3: 实现字段错误 context**

导出 `useFormFieldError(name)`，`WorkbenchField` 根据 `props.name` 读取 context error，并把它作为默认 `error`。

- [x] **Step 4: 添加 CSS**

新增 `.formErrorSummary`，使用红色左边框、浅红背景、清晰链接、`grid-column: 1 / -1`，并给 `:focus-visible` 足够明显的 ring。

- [x] **Step 5: 验证绿色单元测试**

Run:

```bash
cd apps/web
npm run test:unit
```

Expected: form validation 与 command menu unit tests 全部通过。

### Task 3: 接入高频表单

**Files:**
- Modify: `apps/web/components/skills/skill-launchpad.tsx`
- Modify: `apps/web/components/inspector/workbench-inspector.tsx`
- Modify: `apps/web/components/eval-cases/quick-add-cases.tsx`

- [x] **Step 1: 接入 `SkillLaunchpad`**

把导入和新建表单改为 `ValidatedForm`，分别保留 `onChange={onRefreshImportPreview}` 和 `onValidSubmit={onImportSkill/onCreateSkill}`。

- [x] **Step 2: 接入 `WorkbenchInspector`**

把所有 `.inspectorForm` 的写入 `<form>` 改为 `ValidatedForm`，保留 `key`、`onChange` 和现有 submit handler。

- [x] **Step 3: 接入 `QuickAddCases` 单条表单**

把 `.quickCaseGrid` 改为 `ValidatedForm`，保留现有 `submitSingle` 逻辑。批量模式保持现状，不在本轮做行级错误摘要。

- [x] **Step 4: 验证目标 E2E**

Run:

```bash
cd apps/web
UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npx playwright test e2e/accessibility-workbench.spec.ts --project=chromium -g "error summary"
```

Expected: 新增 error summary E2E 通过。

### Task 4: 文档、完整验证和提交

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Create: `.agent/tasks/TASK-050.json`
- Modify: `.agent/tasks.json`
- Modify: `.agent/logs/LOG.md`

- [x] **Step 1: 更新中文文档**

记录本轮完成 required 字段错误摘要、字段旁错误、summary focus 和 summary link focus；明确后端字段级错误映射、复杂格式校验、批量 case 行级错误仍在下一轮。

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
jq empty .agent/tasks.json .agent/tasks/TASK-050.json
wc -l apps/web/components/forms/form-validation.tsx apps/web/components/forms/workbench-field.tsx apps/web/components/skills/skill-launchpad.tsx apps/web/components/inspector/workbench-inspector.tsx apps/web/components/eval-cases/quick-add-cases.tsx
```

Expected: all pass，新增基础件和被改表单文件保持可维护大小。
