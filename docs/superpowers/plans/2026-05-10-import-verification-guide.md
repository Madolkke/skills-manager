# 导入后验证引导 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 导入标准 Skill bundle 后，用一个轻量验证清单把“补 case -> 手工测评 -> 查看证据历史”串成连续产品路径。

**Architecture:** 不改后端；新增一个 focused React component 渲染概览页的验证清单。`DecisionWorkbench` 只传入当前 bundle/case/run 状态和导航回调；单条 case 创建成功后自动切到 `测评` tab。

**Tech Stack:** Next.js App Router、React client components、TypeScript、Playwright E2E、现有 FastAPI 后端。

---

### Task 1: 任务定义和红测

**Files:**
- Add: `.agent/tasks/TASK-009.json`
- Modify: `.agent/tasks.json`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: 添加 TASK-009 定义**

任务要求覆盖导入后清单、添加首条 case 自动进入测评、记录 run 后查看历史入口。

- [x] **Step 2: 写 Playwright 红测**

新增测试 `imported skill is guided into its first verification run`：

1. 导入标准 folder bundle。
2. 断言 `验证清单` 可见，且 `补齐评测集` 未完成。
3. 点击 `添加首批 case`。
4. 填写并提交第一条 case。
5. 断言 `测评` tab active、case 可见、记录按钮 disabled。
6. 标记 case 通过并记录 run。
7. 回到 `概览`，断言清单显示 `首轮测评完成`。
8. 点击 `查看证据历史`，断言进入历史页且有 1 条 run。

- [x] **Step 3: 运行红测**

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "first verification run"
```

预期：失败，因为目前没有 `验证清单`，创建 case 后也不会自动切到 `测评`。

### Task 2: 实现验证清单

**Files:**
- Add: `apps/web/components/eval-cases/verification-start-panel.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`

- [x] **Step 1: 新增 `VerificationStartPanel`**

组件 props：

```ts
type VerificationStartPanelProps = {
  bundleFileCount: number;
  caseCount: number;
  currentVersionNumber?: number;
  latestRun: EvalRunRecord | null;
  onAddCase: () => void;
  onOpenEvals: () => void;
  onOpenHistory: () => void;
};
```

组件渲染四个步骤，并根据 `caseCount` / `latestRun` 选择主按钮。

- [x] **Step 2: 接入 `OverviewPane`**

`OverviewPane` 新增 props：

```ts
caseCount: number;
onOpenEvals: () => void;
onOpenHistory: () => void;
```

在 `productHero` 和 metrics 后渲染 `VerificationStartPanel`。

- [x] **Step 3: 修改单条 case 提交后的落点**

`createCase` 在 API 成功后返回：

```ts
return {
  actionMode: "run",
  message: "测试用例已加入当前评测集。已切到手工测评。",
  mode: "evals",
};
```

这样用户从导入清单添加第一条 case 后，不会停留在概览页表单。

- [x] **Step 4: 添加样式**

新增 `.verificationStartPanel`、`.verificationStep`、`.verificationStepDone`、`.verificationGuideActions` 等样式。保持产品工作台风格：白底、细边框、信息密集、状态清晰，不做浮夸营销卡。

- [x] **Step 5: 运行局部 E2E**

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "first verification run"
```

预期：通过。

### Task 3: 文档、视觉和全量验证

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Add: `.agent/screenshots/TASK-009-1.png`

- [x] **Step 1: 更新文档**

README 增加导入后验证清单路径；UX review 记录外部实践和已解决摩擦；完成度审计增加 TASK-009 证据。

- [x] **Step 2: 截图验证**

用本地浏览器保存导入后验证清单截图，人工确认不空白、不重叠、移动端不溢出。

- [x] **Step 3: 全量验证**

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
git diff --check
```

- [x] **Step 4: 提交推送**

```bash
git add .
git commit -m "feat: guide first skill verification"
git push
```

## 自检

- 不把验证清单做成后端 workflow。
- 不阻断用户自由导航。
- 不引入新的本地持久化。
- 不复用跨版本 eval 草稿。
- 不扩大到 saved view / matrix / permissions。
