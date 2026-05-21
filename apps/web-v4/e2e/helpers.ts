import { expect, type Locator, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export class SkillHubE2E {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto("/skills", { waitUntil: "domcontentloaded" });
    await expect(this.page.getByRole("heading", { name: "SkillHub" })).toBeVisible();
  }

  async createSkill(tag: string, bundlePath: string): Promise<void> {
    await this.page.getByRole("button", { name: "新建 Skill", exact: true }).first().click();
    const dialog = this.dialog("新建 Skill");
    await expect(dialog).toBeVisible();
    await this.addTag(dialog, tag);
    await dialog.locator('input[name="folder_files"]').setInputFiles(bundlePath);
    await dialog.getByRole("button", { name: "创建 Skill", exact: true }).click();
    await expect(dialog).toBeHidden();
    await this.page.waitForURL(/skill=/);
  }

  async expectOverview(skillSlug: string): Promise<void> {
    await expect(this.page.getByRole("heading", { name: displaySkillName(skillSlug) })).toBeVisible();
    await expect(this.page.getByText("SKILL.md").first()).toBeVisible();
    await expect(this.page.getByText("checklist.md").first()).toBeVisible();
  }

  async uploadVariantVersion(bundlePath: string): Promise<void> {
    await this.page.getByRole("button", { name: "上传版本", exact: true }).first().click();
    await expect(this.page.getByRole("dialog", { name: "上传版本" })).toHaveCount(0);
    const panel = this.page.locator(".variant-upload-panel");
    await expect(panel.getByRole("heading", { name: "上传新版本" })).toBeVisible();
    await panel.locator('input[name="folder_files"]').setInputFiles(bundlePath);
    await panel.getByRole("button", { name: "确认上传", exact: true }).click();
    await expect(panel).toBeHidden();
  }

  async addCase(title: string): Promise<void> {
    await this.page.locator(".case-toolbar").getByRole("button", { name: "添加", exact: true }).click();
    const dialog = this.dialog("添加 case");
    await expect(dialog).toBeVisible();
    await dialog.locator("input").nth(0).fill(title);
    await dialog.locator("textarea").nth(0).fill("Open SkillHub and complete one formal workflow without mixing management and execution.");
    await dialog.locator("textarea").nth(1).fill("The UI exposes clear management, manual evaluation, and history evidence boundaries.");
    await dialog.locator("input").nth(1).fill("case v1 smoke");
    await dialog.getByRole("button", { name: "添加 case", exact: true }).click();
    await expect(dialog).toBeHidden();
  }

  async editCaseToVersion2(): Promise<void> {
    await this.page.getByRole("button", { name: "编辑为新版本", exact: true }).click();
    const dialog = this.dialog("编辑为新版本");
    await expect(dialog).toBeVisible();
    await dialog
      .locator("textarea")
      .nth(1)
      .fill("The UI exposes clear management, manual evaluation, and history evidence boundaries, with case v2 evidence.");
    await dialog.locator("input").nth(1).fill("case v2 evidence");
    await dialog.getByRole("button", { name: "保存新版本", exact: true }).click();
    await expect(dialog).toBeHidden();
  }

  async expectCurrentCaseVersion(version: number): Promise<void> {
    await expect(this.page.locator(".case-detail .tag-row").getByText(`case v${version}`, { exact: true })).toBeVisible();
  }

  async recordManualPass(caseTitle: string): Promise<void> {
    await expect(this.page.locator(".manual-case-detail").getByRole("heading", { name: caseTitle })).toBeVisible();
    await this.page.locator(".eval-action-bar .pass-button").click();
    await expect(this.page.getByText("1/1 已确认")).toBeVisible();
    await this.page.locator(".eval-action-bar .primary-button").click();
    await expect(this.page.getByText("测评结果已记录。")).toBeVisible();
  }

  async expectHistoryEvidence(caseTitle: string): Promise<void> {
    await expect(this.page.getByRole("heading", { name: "历史与证据链" })).toBeVisible();
    const evidence = this.page.locator(".evidence-panel");
    await expect(evidence.locator(".evidence-card").filter({ hasText: "VariantVersion" })).toBeVisible();
    await expect(evidence.locator(".evidence-card").filter({ hasText: "EvalSetVersion" })).toBeVisible();
    await expect(evidence.getByRole("heading", { name: "Case 结果" })).toBeVisible();
    const caseEvidence = evidence.locator(".case-evidence-row").filter({ hasText: caseTitle });
    await expect(caseEvidence).toBeVisible();
    await expect(caseEvidence.getByText(/case v2 · input [a-f0-9]{12} · expected [a-f0-9]{12}/)).toBeVisible();
    await expect(caseEvidence.getByText("通过", { exact: true })).toBeVisible();
  }

  async openTab(name: string): Promise<void> {
    await this.page.locator(".skill-tabs").getByRole("tab", { name, exact: true }).click();
  }

  private dialog(name: string): Locator {
    return this.page.getByRole("dialog", { name });
  }

  private async addTag(dialog: Locator, tag: string): Promise<void> {
    const input = dialog.locator(".tag-box input");
    await input.fill(tag);
    await input.press("Enter");
  }
}

export class SkillBundleFixture {
  readonly path: string;

  constructor(path: string) {
    this.path = path;
  }

  write(skillSlug: string, tag: string, version: number): void {
    mkdirSync(join(this.path, "references"), { recursive: true });
    writeFileSync(
      join(this.path, "SKILL.md"),
      `---\nname: ${skillSlug}\ndescription: Validates SkillHub formal UI flow version ${version}.\n---\n# ${displaySkillName(skillSlug)}\n\nVersion ${version} validates mature SkillHub workflows.\n`,
    );
    writeFileSync(
      join(this.path, "references", "checklist.md"),
      `# Formal workflow checklist\n\n- version: ${version}\n- tag: ${tag}\n- temp: ${tmpdir()}\n`,
    );
  }
}

export function displaySkillName(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}
