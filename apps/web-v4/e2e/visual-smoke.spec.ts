import { expect, test, type Page } from "@playwright/test";
import { VisualSeed } from "./visual-seed";

test("captures the five formal product reference pages", async ({ page, request }) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") consoleMessages.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => consoleMessages.push(`pageerror: ${error.message}`));

  const dataset = await new VisualSeed(request).createProductDataset();

  await open(page, "/skills");
  await expect(page.getByRole("heading", { name: "SkillHub" })).toBeVisible();
  await expect(page.locator(".skill-card").first()).toContainText("维护者 product-operator");
  await expect(page.locator(".recent-row").first()).toContainText(/Primary v\d+/);
  await expect(page.locator(".recent-row").first()).toContainText("操作者 product-operator");
  await expect(page.locator(".recent-list")).toHaveAttribute("aria-label", "最近测评，显示 6 / 7 条");
  await expect(page.locator(".recent-row")).toHaveCount(6);
  await page.getByRole("button", { name: "查看全部最近测评" }).click();
  await expect(page.locator(".recent-list")).toHaveAttribute("aria-label", "最近测评，显示 7 / 7 条");
  await expect(page.locator(".recent-row")).toHaveCount(7);
  await page.getByRole("button", { name: "收起最近测评" }).click();
  await expect(page.locator(".recent-list")).toHaveAttribute("aria-label", "最近测评，显示 6 / 7 条");
  await expect(page.locator(".recent-row")).toHaveCount(6);
  await capture(page, "01-hub-home.png");

  await open(page, `/skills?skill=${dataset.primarySkillId}`);
  await expect(page.getByRole("heading", { name: "Code Reviewer" })).toBeVisible();
  await expect(page.locator(".skill-identity-card")).toContainText("根目录");
  await expect(page.locator(".skill-identity-card")).toContainText("code-reviewer/");
  await expect(page.locator(".skill-identity-card")).toContainText("维护者");
  await expect(page.locator(".skill-identity-card")).toContainText("product-operator");
  await expect(page.locator(".bundle-tree-node.branch").filter({ hasText: "code-reviewer/" })).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".bundle-tree-node.branch").filter({ hasText: "examples/" })).toBeVisible();
  await expect(page.locator(".bundle-tree-node.leaf").filter({ hasText: "pr.diff" })).toBeVisible();
  await capture(page, "02-skill-overview.png");

  await open(page, `/skills?skill=${dataset.primarySkillId}&tab=evalsets`);
  await expect(page.getByRole("heading", { name: "PR: missing owner filter" })).toBeVisible();
  const firstCaseRow = page.locator(".case-row").first();
  await expect(firstCaseRow.locator(".case-position-mark")).toHaveText("#1");
  await expect(firstCaseRow.locator(".case-row-metadata")).toContainText("case v2");
  await expect(firstCaseRow.locator(".case-current-chip")).toContainText("当前");
  await expect(firstCaseRow.locator(".case-status-chip")).toContainText("活跃");
  await capture(page, "03-eval-set-management.png");

  await open(page, `/skills?skill=${dataset.primarySkillId}&tab=evaluate`);
  await expect(page.getByRole("heading", { name: "PR: missing owner filter" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看变体版本详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看测评集版本详情" })).toBeVisible();
  await page.getByRole("button", { name: "查看变体版本详情" }).click();
  await expect(page.locator(".manual-version-detail-panel")).toContainText("VariantVersion");
  await expect(page.locator(".manual-version-detail-panel")).toContainText("内容 digest");
  await page.getByRole("button", { name: "查看测评集版本详情" }).click();
  await expect(page.locator(".manual-version-detail-panel")).toContainText("EvalSetVersion");
  await expect(page.locator(".manual-version-detail-panel")).toContainText("8 个 case");
  await page.getByRole("button", { name: "关闭版本详情" }).click();
  await page.locator(".eval-action-bar .pass-button").click();
  await expect(page.locator(".progress-summary-card")).toContainText("1/8 已确认");
  await expect(page.locator(".progress-summary-card .progress-total-label")).toHaveText("共 8 个 case");
  await expect(page.locator(".progress-track-card")).toContainText("结果分布");
  const manualRows = page.locator(".manual-case-row");
  await expect(manualRows.nth(0).locator(".manual-case-index")).toHaveText("#1");
  await expect(manualRows.nth(0).locator(".manual-status-dot.passed")).toBeVisible();
  await expect(manualRows.nth(0).locator(".manual-shortcut-chip")).toHaveText("1");
  await expect(manualRows.nth(1).locator(".manual-case-index")).toHaveText("#2");
  await capture(page, "04-manual-evaluation.png");

  await open(page, `/skills?skill=${dataset.primarySkillId}&tab=variants`);
  await expect(page.getByRole("heading", { name: "变体" })).toBeVisible();
  await expect(page.locator(".variant-detail-panel .inspector-version-track")).toBeVisible();
  await expect(page.locator(".variant-detail-panel .version-track-step.current")).toContainText("当前");
  await expect(page.locator(".variant-detail-panel .version-current-summary")).toContainText(/当前 v\d+/);
  await expect(page.locator(".variant-detail-panel .timeline-item")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Bundle diff" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看该版本详情" })).toBeVisible();
  await page.getByRole("button", { name: "Bundle diff" }).click();
  await expect(page.locator(".variant-inspector-detail-panel")).toContainText("Bundle diff");
  await expect(page.locator(".variant-inspector-detail-panel")).toContainText("变更文件");
  await page.getByRole("button", { name: "查看该版本详情" }).click();
  await expect(page.locator(".variant-inspector-detail-panel")).toContainText("VariantVersion 详情");
  await expect(page.locator(".variant-inspector-detail-panel")).toContainText("内容 digest");
  await page.getByRole("button", { name: "查看该版本详情" }).click();
  await expect(page.locator(".variant-inspector-detail-panel")).toHaveCount(0);
  await page.getByRole("button", { name: "上传版本", exact: true }).click();
  await expect(page.locator(".variant-upload-panel").getByRole("heading", { name: "上传新版本" })).toBeVisible();
  await capture(page, "05-variant-management.png");

  expect(consoleMessages).toEqual([]);
});

async function open(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
    `,
  });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function capture(page: Page, name: string): Promise<void> {
  await expect(page).toHaveScreenshot(name, {
    animations: "disabled",
    caret: "hide",
    mask: dynamicMasks(page),
    maskColor: "#f8fafc",
  });
}

function dynamicMasks(page: Page) {
  return [
    page.locator(".recent-row small"),
    page.locator(".summary-metric small"),
    page.locator(".reliability-panel dl div:nth-child(4) dd"),
    page.locator(".evalset-card .mini-grid span:nth-child(3) b"),
    page.locator(".case-version-card span"),
    page.locator(".timeline-item small"),
    page.locator(".run-row small"),
    page.locator(".version-row small"),
    page.locator(".evidence-meta-row"),
  ];
}
