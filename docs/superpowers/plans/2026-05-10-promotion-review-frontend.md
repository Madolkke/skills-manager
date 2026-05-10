# Promotion Review Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在正式版 SkillHub 工作台里补齐“候选 VariantVersion 设为当前版本”前端闭环，让操作者能先看测评差异、文件 diff、风险结论，再完成 promote。

**Architecture:** 后端已经提供 `GET /api/variants/{variant_id}/promotion-review` 和 `POST /api/variants/promotions`。前端新增一个独立 Promotion Review 视图，由 `DecisionWorkbench` 负责加载和提交，具体展示拆到 `apps/web/components/promotion-review/*`，避免继续膨胀主工作台组件。

**Tech Stack:** Next.js App Router、React 19 client component、TypeScript、Playwright E2E、现有 Python FastAPI 后端。

---

## 文件结构

- Modify: `apps/web/lib/types.ts`
  - 增加 Promotion Review 响应类型、case comparison、readiness、promotion decision 类型。
- Create: `apps/web/components/promotion-review/promotion-review-pane.tsx`
  - 聚合上架评审页面：顶部结论、case impact、文件 diff、决策表单。
- Create: `apps/web/components/promotion-review/promotion-readiness-card.tsx`
  - 展示 ready/risky/unverified/blocked 状态、原因、通过项、风险项、阻塞项。
- Create: `apps/web/components/promotion-review/promotion-case-comparison-list.tsx`
  - 展示每个测试用例在 current 与 candidate 上的通过/不通过变化。
- Create: `apps/web/components/promotion-review/promotion-diff-viewer.tsx`
  - 复用后端 bundle diff 数据，展示文件列表与行级 diff。
- Modify: `apps/web/components/decision-workbench.tsx`
  - 新增 `promotion` mode、加载 review、提交 promote、刷新 skill。
  - 版本列表中每个非 current 版本提供“设为当前版本评审”入口。
  - 手工测评允许选择具体 VariantVersion，这样候选版本可以先被测评再 promote。
- Modify: `apps/web/e2e/helpers.ts`
  - `appendSkillBundleVersion` 支持 `makeCurrent` 参数，默认仍兼容原测试。
- Modify: `apps/web/e2e/skills-workbench.spec.ts`
  - 新增 promote happy path E2E：候选版本不立即设为 current，手工测评候选版本后进入评审并 promote。
- Modify: `apps/web/app/globals.css`
  - 增加 Promotion Review 的三栏/双栏布局和状态样式。

## 交互规格

页面上用户会看到：

1. 在“变体”页，每个 variant 卡片下面列出历史版本。current 版本显示 `Current`；非 current 版本显示一个小按钮 `设为当前版本评审`。
2. 点击候选版本后进入“评审”页。
3. 评审页左上角是结论卡：
   - `可设为当前版本`：候选版本完整测评，且没有 regression。
   - `有风险`：候选版本完整测评，但存在 regression 或仍失败的 case，需要填写决策说明。
   - `未验证`：候选版本还没在目标 EvalSetVersion 上跑过测评。
   - `无法设为当前版本`：数据不完整或文件快照不可审查。
4. 评审页中间显示 case 对比：
   - `修复`：current 不通过，candidate 通过。
   - `回退`：current 通过，candidate 不通过。
   - `稳定通过`：两边都通过。
   - `仍未通过`：两边都不通过。
   - `缺少对照` / `候选缺失`：某边没有测评结果。
5. 评审页右侧显示文件 diff：用户可以点文件看行级变化。
6. 底部决策区：
   - ready 时可直接点 `设为当前版本`。
   - risky 时必须填写说明，按钮文案为 `接受风险并设为当前版本`。
   - unverified/blocked 时按钮禁用，并提示先完成候选版本测评或修正阻塞项。

## Task 1: E2E Red Test

**Files:**
- Modify: `apps/web/e2e/helpers.ts`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [ ] **Step 1: 让 helper 支持追加候选版本但不设为 current**

将 helper 签名改成：

```ts
export async function appendSkillBundleVersion(
  page: Page,
  skillName: string,
  options: { makeCurrent?: boolean } = {},
) {
  // ...
  const makeCurrent = options.makeCurrent ?? true;
  if (!makeCurrent) {
    await page.locator('input[name="make_current"]').uncheck();
  }
  await page.getByRole("button", { name: "保存版本" }).click();
}
```

- [ ] **Step 2: 写失败测试**

在 `apps/web/e2e/skills-workbench.spec.ts` 添加：

```ts
test("operator can review a candidate version before promoting it", async ({ page }) => {
  const skillName = `promotion-reviewing-${Date.now()}`;
  await importSkillBundle(page, skillName);
  await addEvalCase(page, "PR: missing tenant scope");

  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: missing tenant scope" })
    .getByRole("button", { name: "不通过", exact: true })
    .click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 0/1 通过。")).toBeVisible();

  await appendSkillBundleVersion(page, skillName, { makeCurrent: false });

  await page.getByRole("button", { name: "测评", exact: true }).click();
  await page.getByLabel("测评目标版本").selectOption({ label: /v2/ });
  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: missing tenant scope" })
    .getByRole("button", { name: "通过", exact: true })
    .click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 1/1 通过。")).toBeVisible();

  await page.getByRole("button", { name: "变体", exact: true }).click();
  await page.locator(".variantVersionRow").filter({ hasText: "v2" }).getByRole("button", { name: "设为当前版本评审" }).click();

  await expect(page.getByRole("heading", { name: "设为当前版本评审" })).toBeVisible();
  await expect(page.getByText("可设为当前版本")).toBeVisible();
  await expect(page.getByText("修复")).toBeVisible();
  await expect(page.getByText("SKILL.md")).toBeVisible();

  await page.getByRole("button", { name: "设为当前版本", exact: true }).click();
  await expect(page.getByText("已设为当前版本。")).toBeVisible();
  await expect(page.locator(".variantVersionRow").filter({ hasText: "v2" }).getByText("Current")).toBeVisible();
});
```

- [ ] **Step 3: 运行红灯测试**

Run:

```bash
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e -- --grep "operator can review a candidate version before promoting it"
```

Expected: FAIL，因为当前 UI 没有 `测评目标版本`、`设为当前版本评审`、promotion review 页面。

## Task 2: Types And Promotion Components

**Files:**
- Modify: `apps/web/lib/types.ts`
- Create: `apps/web/components/promotion-review/promotion-readiness-card.tsx`
- Create: `apps/web/components/promotion-review/promotion-case-comparison-list.tsx`
- Create: `apps/web/components/promotion-review/promotion-diff-viewer.tsx`
- Create: `apps/web/components/promotion-review/promotion-review-pane.tsx`

- [ ] **Step 1: 添加类型**

新增类型：

```ts
export type PromotionReadiness = {
  status: "ready" | "risky" | "unverified" | "blocked";
  label: string;
  reason: string;
  requires_note: boolean;
  risk_items: string[];
  blocking_items: string[];
  passing_items: string[];
};

export type PromotionCaseComparison = {
  case_id: string;
  case_title: string;
  case_version_id: string;
  change: "fixed" | "regressed" | "stable_pass" | "stable_fail" | "missing_baseline" | "missing_candidate";
  change_label: string;
  current_passed: boolean | null;
  candidate_passed: boolean | null;
  input_text: string | null;
  expected_output_text: string | null;
};

export type PromotionReview = {
  skill: SkillSummary["skill"];
  variant: Omit<VariantDetail, "current_version" | "versions"> & { tags: string[] };
  current_version: VariantVersion | null;
  candidate_version: VariantVersion;
  eval_set: Omit<EvalSetSummary, "current_version" | "versions">;
  eval_set_version: EvalSetVersion;
  candidate_run: EvalRunRecord | null;
  current_run: EvalRunRecord | null;
  readiness: PromotionReadiness;
  comparison_summary: Record<PromotionCaseComparison["change"], number>;
  case_comparisons: PromotionCaseComparison[];
  bundle_diff: BundleDiff | null;
};

export type PromotionDecision = {
  id: string;
  skill_id: string;
  variant_id: string;
  from_version_id: string | null;
  to_version_id: string;
  eval_set_version_id: string;
  evidence_eval_run_id: string;
  baseline_eval_run_id: string | null;
  readiness_status: PromotionReadiness["status"];
  decision_note: string | null;
  accepted_risk: boolean;
  created_at?: string;
  created_by: string;
};
```

- [ ] **Step 2: 实现展示组件**

组件只接收 typed props，不自己 fetch。`PromotionReviewPane` 负责：

```tsx
<PromotionReadinessCard readiness={review.readiness} />
<PromotionCaseComparisonList cases={review.case_comparisons} summary={review.comparison_summary} />
<PromotionDiffViewer diff={review.bundle_diff} />
```

并根据 `readiness.status` 控制 promote 按钮是否可用。

## Task 3: Workbench Integration

**Files:**
- Modify: `apps/web/components/decision-workbench.tsx`

- [ ] **Step 1: 新增 mode 和 state**

```ts
type Mode = "overview" | "variants" | "evals" | "diff" | "history" | "promotion";

const [evalTargetVersionId, setEvalTargetVersionId] = useState<string | null>(null);
const [promotionReview, setPromotionReview] = useState<PromotionReview | null>(null);
const [promotionLoading, setPromotionLoading] = useState(false);
```

- [ ] **Step 2: 手工测评绑定选中版本**

`recordEvalRun` 使用：

```ts
const targetVersion = variantVersionsForSelectedSkill.find((version) => version.id === evalTargetVersionId)
  ?? defaultVariant?.current_version
  ?? null;
```

payload 的 `variant_version_id` 改为 `targetVersion.id`。

- [ ] **Step 3: 进入 promotion review**

新增：

```ts
async function openPromotionReview(variantId: string, candidateVersionId: string) {
  setMode("promotion");
  setPromotionLoading(true);
  setPromotionReview(null);
  try {
    const params = new URLSearchParams({ candidate_version_id: candidateVersionId });
    if (currentEvalSetVersion?.id) params.set("eval_set_version_id", currentEvalSetVersion.id);
    setPromotionReview(await apiGet<PromotionReview>(`/api/variants/${variantId}/promotion-review?${params}`));
  } finally {
    setPromotionLoading(false);
  }
}
```

- [ ] **Step 4: 提交 promote**

新增：

```ts
async function promoteFromReview(note: string) {
  if (!promotionReview?.candidate_run) return;
  await runCommand("已设为当前版本。", async () => {
    const result = await apiSend<{ ok: boolean; promotion_decision: PromotionDecision }>("/api/variants/promotions", {
      method: "POST",
      body: {
        variant_id: promotionReview.variant.id,
        version_id: promotionReview.candidate_version.id,
        evidence_eval_run_id: promotionReview.candidate_run.id,
        eval_set_version_id: promotionReview.eval_set_version.id,
        decision_note: note,
        accept_risk: promotionReview.readiness.status === "risky",
        actor: ACTOR,
      },
    });
    setPromotionReview(null);
    setMode("variants");
    return "已设为当前版本。";
  });
}
```

## Task 4: Styling And Verification

**Files:**
- Modify: `apps/web/app/globals.css`

- [ ] **Step 1: 增加 Promotion Review 样式**

保持当前 Linear-like 产品方向，但做成更像“评审控制台”：

- 顶部：结论卡 + exact binding。
- 主体：左侧 case impact list，右侧 file diff。
- 底部：sticky decision bar。

- [ ] **Step 2: 跑全量验证**

Run:

```bash
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache npm run e2e
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest
```

Expected:

- TypeScript passes.
- Next build passes.
- Playwright all tests pass.
- API pytest all tests pass.

## 自检

- 规格覆盖：候选版本可独立测评、可打开评审、可看 case 对比、可看 diff、可 promote、promote 后 current 指针刷新。
- 设计边界：promotion 展示组件不 fetch；workbench 只负责状态和命令。
- YAGNI：不做权限、PR、自动优化、多维表格；只做用户已经确认的 promote 前审查闭环。
