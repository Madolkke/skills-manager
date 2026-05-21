import { expect, test } from "@playwright/test";
import { SkillBundleFixture, SkillHubE2E } from "./helpers";

test("operator can complete the formal SkillHub core flow", async ({ page }, testInfo) => {
  const app = new SkillHubE2E(page);
  const bundle = new SkillBundleFixture(testInfo.outputPath("skill-bundle"));
  const skillSlug = `e2e-formal-reviewer-${Date.now()}`;
  const tag = `formal-${Date.now()}`;
  const caseTitle = "E2E: formal flow has clear primary action";

  const consoleMessages: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") consoleMessages.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => consoleMessages.push(`pageerror: ${error.message}`));

  bundle.write(skillSlug, tag, 1);
  await app.goto();
  await app.createSkill(tag, bundle.path);
  await app.expectOverview(skillSlug);

  bundle.write(skillSlug, tag, 2);
  await app.openTab("变体");
  await expect(page.getByRole("button", { name: "上传版本", exact: true })).toHaveCount(1);
  await app.uploadVariantVersion(bundle.path);
  await expect(page.locator(".variant-detail-panel .version-pill")).toHaveText("当前 v2");
  await expect(page.locator(".variant-detail-panel .version-current-summary")).toContainText("当前 v2");

  await app.openTab("测评集");
  await expect(page.getByRole("button", { name: "上传版本", exact: true })).toHaveCount(0);
  await page.getByLabel("Case 排序").selectOption("title");
  await expect(page.getByLabel("Case 排序")).toHaveValue("title");
  await app.addCase(caseTitle);
  await app.expectCurrentCaseVersion(1);
  await app.editCaseToVersion2();
  await app.expectCurrentCaseVersion(2);
  const versionTrack = page.locator(".case-version-track");
  await expect(versionTrack).toBeVisible();
  const versionSteps = versionTrack.locator(".case-version-step");
  await expect(versionSteps).toHaveCount(3);
  await expect(versionSteps.nth(0)).toContainText("v1");
  await expect(versionSteps.nth(1)).toHaveAttribute("aria-current", "step");
  await expect(versionSteps.nth(1)).toContainText("v2（当前）");
  await expect(versionSteps.nth(2)).toContainText("待创建");

  await app.openTab("测评");
  await expect(page.getByRole("button", { name: "上传版本", exact: true })).toHaveCount(0);
  await app.recordManualPass(caseTitle);

  await app.openTab("历史");
  await expect(page.getByRole("button", { name: "上传版本", exact: true })).toHaveCount(0);
  await app.expectHistoryEvidence(caseTitle);
  expect(consoleMessages).toEqual([]);
});
