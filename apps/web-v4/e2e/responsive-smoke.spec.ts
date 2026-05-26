import { expect, test, type Page } from "@playwright/test";
import { VisualSeed } from "./visual-seed";

test("formal pages keep key content inside a 320px viewport", async ({ page, request }) => {
  const dataset = await new VisualSeed(request).createProductDataset();
  await page.setViewportSize({ width: 320, height: 820 });

  await openAndCheck(page, "/skills");
  await openAndCheck(page, `/skills?skill=${dataset.primarySkillId}`);
  await openAndCheck(page, `/skills?skill=${dataset.primarySkillId}&tab=evalsets`);
  await openAndCheck(page, `/skills?skill=${dataset.primarySkillId}&tab=evaluate`);
  await openAndCheck(page, `/skills?skill=${dataset.primarySkillId}&tab=history`);

  await page.goto(`/skills?skill=${dataset.primarySkillId}&tab=versions`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "版本", exact: true })).toBeVisible();
  const diffResponse = page.waitForResponse((response) => response.url().includes("/api/artifacts/diff") && response.ok());
  await page.getByRole("button", { name: "Bundle diff" }).click();
  await diffResponse;
  await expectNoDocumentOverflow(page);
});

async function openAndCheck(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await expect(page.locator(".app-shell")).toBeVisible();
  await expectNoDocumentOverflow(page);
}

async function expectNoDocumentOverflow(page: Page): Promise<void> {
  const width = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(width.document, JSON.stringify(width)).toBeLessThanOrEqual(width.viewport + 1);
  expect(width.body, JSON.stringify(width)).toBeLessThanOrEqual(width.viewport + 1);
}
