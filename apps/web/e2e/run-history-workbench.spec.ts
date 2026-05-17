import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { addEvalCase, appendSkillBundleVersion, importSkillBundle } from "./helpers";

test("operator can review eval run history with filters", async ({ page }) => {
  const skillName = `history-reviewing-${Date.now()}`;
  await importSkillBundle(page, skillName);
  await addEvalCase(page, "PR: missing tenant scope");
  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: missing tenant scope" })
    .getByRole("button", { name: "通过", exact: true })
    .click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 1/1 通过。")).toBeVisible();
  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: missing tenant scope" })
    .getByRole("button", { name: "不通过", exact: true })
    .click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 0/1 通过。")).toBeVisible();

  await page.getByLabel("Workbench modes").getByRole("tab", { name: "历史" }).click();

  await expect(page.locator(".historyRunRow")).toHaveCount(2);
  await expect(page.locator(".historyRunRow").filter({ hasText: "0/1" })).toBeVisible();
  await page.getByLabel("Strategy filter").selectOption("manual_pass_fail");
  await expect(page.locator(".historyRunRow")).toHaveCount(2);
  await expect(page.locator(".historyCaseResults").getByText("PR: missing tenant scope")).toBeVisible();
});

test("operator can inspect run matrix across eval runs", async ({ page }) => {
  const skillName = `run-matrix-${Date.now()}`;
  await importSkillBundle(page, skillName);

  await page.getByRole("tab", { name: "测评", exact: true }).click();
  await page.getByRole("button", { name: "批量", exact: true }).click();
  await page.getByLabel("批量 case 文本").fill(
    [
      "PR: missing tenant scope | Project.all() | Flag missing tenant scope.",
      "PR: token logging | console.log(token) | Flag token logging.",
    ].join("\n"),
  );
  await page.getByRole("button", { name: "批量加入评测集" }).click();
  await page.locator(".caseReviewCard").filter({ hasText: "PR: missing tenant scope" }).getByRole("button", { name: "不通过", exact: true }).click();
  await page.locator(".caseReviewCard").filter({ hasText: "PR: token logging" }).getByRole("button", { name: "通过", exact: true }).click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 1/2 通过。")).toBeVisible();

  await addEvalCase(page, "PR: audit log leak");

  await appendSkillBundleVersion(page, skillName, { makeCurrent: false });
  await page.locator(".caseReviewCard").filter({ hasText: "PR: missing tenant scope" }).getByRole("button", { name: "通过", exact: true }).click();
  await page.locator(".caseReviewCard").filter({ hasText: "PR: token logging" }).getByRole("button", { name: "通过", exact: true }).click();
  await page.locator(".caseReviewCard").filter({ hasText: "PR: audit log leak" }).getByRole("button", { name: "通过", exact: true }).click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 3/3 通过。")).toBeVisible();

  await page.getByLabel("Workbench modes").getByRole("tab", { name: "历史" }).click();

  await expect(page.getByTestId("run-matrix-panel")).toBeVisible();
  const matrixTable = page.getByRole("table", { name: "Run matrix results" });
  await expect(matrixTable).toBeVisible();
  await expect(matrixTable).toHaveAttribute("aria-colcount", "5");
  await expect(matrixTable.getByRole("columnheader", { name: "Case" })).toBeVisible();
  await expect(matrixTable.getByRole("columnheader", { name: "Impact" })).toBeVisible();
  await expect(matrixTable.getByRole("columnheader", { name: "Summary" })).toBeVisible();
  await expect(page.locator(".runMatrixCaseHeader")).toHaveCSS("left", "0px");
  await expect(page.locator(".runMatrixRunHeader").first()).toHaveCSS("position", "sticky");
  await expect(page.locator(".runMatrixRunHeader").first()).toHaveCSS("top", "0px");
  await expect(page.locator(".runMatrixRunHeader")).toHaveCount(2);
  await expect(page.locator(".runMatrixCaseTitle", { hasText: "PR: missing tenant scope" })).toBeVisible();
  await expect(page.locator(".runMatrixCaseTitle", { hasText: "PR: token logging" })).toBeVisible();
  await expect(page.locator(".runMatrixCaseTitle", { hasText: "PR: audit log leak" })).toBeVisible();
  await expect(page.locator(".runMatrixCellFail")).toHaveCount(1);
  await expect(page.locator(".runMatrixCellPass")).toHaveCount(4);
  await expect(page.locator(".runMatrixCellMissing")).toHaveCount(1);
  await expect(matrixTable.getByRole("rowheader", { name: /PR: missing tenant scope/ })).toBeVisible();
  await expect(matrixTable.getByRole("cell", { name: /PR: missing tenant scope.*结果：不通过/ })).toBeVisible();
  await expect(matrixTable.getByRole("cell", { name: /PR: token logging.*结果：通过/ })).toHaveCount(2);
  await expect(matrixTable.getByRole("cell", { name: /PR: audit log leak.*结果：未覆盖/ })).toBeVisible();
  await expect(matrixTable.getByRole("cell", { name: /PR: audit log leak.*摘要：1\/2 通过.*1 未覆盖/ })).toBeVisible();

  const fullMatrixDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const fullMatrixCsv = await fullMatrixDownload;
  expect(fullMatrixCsv.suggestedFilename()).toMatch(new RegExp(`^run-matrix-${skillName}-.+\\.csv$`));
  const fullMatrixCsvPath = await fullMatrixCsv.path();
  expect(fullMatrixCsvPath).toBeTruthy();
  const fullMatrixCsvText = await readFile(fullMatrixCsvPath!, "utf8");
  expect(fullMatrixCsvText).toContain("Case,Versions,Impact,Summary");
  expect(fullMatrixCsvText).toContain("PR: missing tenant scope");
  expect(fullMatrixCsvText).toContain("PR: token logging");
  expect(fullMatrixCsvText).toContain("1/2 通过");
  expect(fullMatrixCsvText).toContain("不通过");
  expect(fullMatrixCsvText).toContain("通过");

  await expect(page.getByLabel("Impact column")).toBeChecked();
  await page.getByLabel("Impact column").uncheck();
  await expect(matrixTable).toHaveAttribute("aria-colcount", "4");
  await expect(matrixTable.getByRole("columnheader", { name: "Impact" })).toHaveCount(0);
  await expect(page.locator(".runMatrixImpactCell")).toHaveCount(0);
  await expect(matrixTable.getByRole("cell", { name: /PR: token logging.*结果：通过/ })).toHaveCount(2);
  const compactMatrixDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const compactMatrixCsv = await compactMatrixDownload;
  const compactMatrixCsvPath = await compactMatrixCsv.path();
  expect(compactMatrixCsvPath).toBeTruthy();
  const compactMatrixCsvText = await readFile(compactMatrixCsvPath!, "utf8");
  expect(compactMatrixCsvText.split("\n")[0]).not.toContain("Impact");
  await page.getByLabel("Impact column").check();
  await expect(matrixTable.getByRole("columnheader", { name: "Impact" })).toBeVisible();

  await expect(page.getByLabel("Summary column")).toBeChecked();
  await page.getByLabel("Summary column").uncheck();
  await expect(matrixTable).toHaveAttribute("aria-colcount", "4");
  await expect(matrixTable.getByRole("columnheader", { name: "Summary" })).toHaveCount(0);
  await expect(page.locator(".runMatrixSummaryCell")).toHaveCount(0);
  const noSummaryDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const noSummaryCsv = await noSummaryDownload;
  const noSummaryCsvPath = await noSummaryCsv.path();
  expect(noSummaryCsvPath).toBeTruthy();
  const noSummaryCsvText = await readFile(noSummaryCsvPath!, "utf8");
  expect(noSummaryCsvText.split("\n")[0]).not.toContain("Summary");
  await page.getByLabel("Summary column").check();
  await expect(matrixTable.getByRole("columnheader", { name: "Summary" })).toBeVisible();

  await page.locator(".historyRunRow").filter({ hasText: "1/2" }).getByRole("button", { name: "对照" }).click();
  await page.locator(".historyRunRow").filter({ hasText: "3/3" }).getByRole("button", { name: "候选" }).click();
  await expect(page.locator(".runMatrixImpactFixed")).toHaveCount(1);
  await expect(page.locator(".runMatrixImpactStablePass")).toHaveCount(1);
  await expect(page.locator(".runMatrixImpactMissing")).toHaveCount(1);
  await expect(matrixTable.getByRole("cell", { name: /PR: missing tenant scope.*影响：修复/ })).toBeVisible();
  await expect(matrixTable.getByRole("cell", { name: /PR: audit log leak.*影响：缺失/ })).toBeVisible();

  await page.getByLabel("Matrix group by").selectOption("impact");
  await expect(page.locator(".runMatrixGroupRow").filter({ hasText: "修复 · 1 case" })).toBeVisible();
  await expect(page.locator(".runMatrixGroupRow").filter({ hasText: "稳定通过 · 1 case" })).toBeVisible();
  await expect(page.locator(".runMatrixGroupRow").filter({ hasText: "缺失 · 1 case" })).toBeVisible();
  await page.getByLabel("Matrix impact filter").selectOption("fixed");
  await expect(page.locator(".runMatrixCaseTitle", { hasText: "PR: missing tenant scope" })).toBeVisible();
  await expect(page.locator(".runMatrixCaseTitle", { hasText: "PR: token logging" })).toHaveCount(0);
  await expect(page.locator(".runMatrixCaseTitle", { hasText: "PR: audit log leak" })).toHaveCount(0);
  const filteredMatrixDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const filteredMatrixCsv = await filteredMatrixDownload;
  const filteredMatrixCsvPath = await filteredMatrixCsv.path();
  expect(filteredMatrixCsvPath).toBeTruthy();
  const filteredMatrixCsvText = await readFile(filteredMatrixCsvPath!, "utf8");
  expect(filteredMatrixCsvText).toContain("修复");
  expect(filteredMatrixCsvText).toContain("PR: missing tenant scope");
  expect(filteredMatrixCsvText).not.toContain("PR: token logging");
  expect(filteredMatrixCsvText).not.toContain("PR: audit log leak");
});

test("operator can save and reapply an eval run history view", async ({ page }) => {
  const skillName = `saved-run-view-${Date.now()}`;
  await importSkillBundle(page, skillName);
  await addEvalCase(page, "PR: missing tenant scope");

  await page.locator(".caseReviewCard").filter({ hasText: "PR: missing tenant scope" }).getByRole("button", { name: "不通过", exact: true }).click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 0/1 通过。")).toBeVisible();

  await appendSkillBundleVersion(page, skillName, { makeCurrent: false });
  await page.locator(".caseReviewCard").filter({ hasText: "PR: missing tenant scope" }).getByRole("button", { name: "通过", exact: true }).click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 1/1 通过。")).toBeVisible();

  await page.getByLabel("Workbench modes").getByRole("tab", { name: "历史" }).click();
  await expect(page.locator(".historyRunRow")).toHaveCount(2);
  const baselineRunRow = page.locator(".historyRunRow").filter({ hasText: "0/1" });
  const candidateRunRow = page.locator(".historyRunRow").filter({ hasText: "1/1" });
  await baselineRunRow.getByRole("button", { name: "对照" }).click();
  await candidateRunRow.getByRole("button", { name: "候选" }).click();
  await expect(page.getByTestId("run-comparison-panel").getByText("+100%", { exact: true })).toBeVisible();

  await page.getByLabel("Matrix group by").selectOption("impact");
  await page.getByLabel("Show matrix score").uncheck();
  await page.getByLabel("Summary column").uncheck();

  await page.getByLabel("保存视图名称").fill("候选对照复盘");
  await page.getByRole("button", { name: "保存当前视图" }).click();
  await expect(page.getByLabel("Saved run view")).toContainText("候选对照复盘");

  await candidateRunRow.getByRole("button", { name: "对照" }).click();
  await baselineRunRow.getByRole("button", { name: "候选" }).click();
  await page.getByLabel("Matrix group by").selectOption("none");
  await page.getByLabel("Show matrix score").check();
  await page.getByLabel("Summary column").check();
  await expect(page.getByLabel("Saved run view")).toHaveValue("adhoc");
  await expect(page.locator(".historyRunRow")).toHaveCount(2);
  await page.getByLabel("Saved run view").selectOption({ label: "候选对照复盘" });
  await expect(baselineRunRow.getByRole("button", { name: "对照" })).toHaveClass(/historyCompareActive/);
  await expect(candidateRunRow.getByRole("button", { name: "候选" })).toHaveClass(/historyCompareActive/);
  await expect(page.getByTestId("run-comparison-panel").getByText("+100%", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Matrix group by")).toHaveValue("impact");
  await expect(page.getByLabel("Show matrix score")).not.toBeChecked();
  await expect(page.getByLabel("Summary column")).not.toBeChecked();

  await page.getByRole("button", { name: "删除视图" }).click();
  await expect(page.getByLabel("Saved run view")).not.toContainText("候选对照复盘");
});

test("operator can compare eval runs and accept a verification pointer", async ({ page }) => {
  await importSkillBundle(page, `run-compare-${Date.now()}`);
  await addEvalCase(page, "PR: missing tenant scope");
  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: missing tenant scope" })
    .getByRole("button", { name: "不通过", exact: true })
    .click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 0/1 通过。")).toBeVisible();
  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: missing tenant scope" })
    .getByRole("button", { name: "通过", exact: true })
    .click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 1/1 通过。")).toBeVisible();

  await page.getByLabel("Workbench modes").getByRole("tab", { name: "历史" }).click();
  await page.locator(".historyRunRow").filter({ hasText: "0/1" }).getByRole("button", { name: "对照" }).click();
  await page.locator(".historyRunRow").filter({ hasText: "1/1" }).getByRole("button", { name: "候选" }).click();

  await expect(page.getByTestId("run-comparison-panel")).toBeVisible();
  await expect(page.getByTestId("run-comparison-panel").getByText("+100%", { exact: true })).toBeVisible();
  await expect(page.getByTestId("run-comparison-panel").getByText("修复 1")).toBeVisible();

  await page.getByLabel("Accepted verification note").fill("Accepted as Primary verification.");
  await page.getByRole("button", { name: "接受为验证依据" }).click();
  await expect(page.getByText("候选 run 已接受为验证依据。")).toBeVisible();
  await expect(page.locator(".historyRunRow").filter({ hasText: "1/1" }).getByText("Accepted")).toBeVisible();
});

test("operator can inspect eval case version history", async ({ page }) => {
  await importSkillBundle(page, `case-history-${Date.now()}`);
  await addEvalCase(page, "PR: stale case wording");
  await page.getByLabel("Inspector").getByRole("button", { name: "编辑 case" }).click();
  await page.getByPlaceholder("新标题").fill("PR: edited case wording");
  await page.getByPlaceholder("新的 input").fill("diff --git a/service.py b/service.py\n+return Project.find_many({})");
  await page.getByPlaceholder("新的 expected output").fill("Must flag missing tenant scope.");
  await page.getByPlaceholder("为什么更新").fill("Clarified tenant-scope expected result.");
  await page.getByRole("button", { name: "保存 case version" }).click();

  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: edited case wording" })
    .getByRole("button", { name: "历史" })
    .click();

  await expect(page.getByText("Case version history")).toBeVisible();
  await expect(page.locator(".caseHistoryVersion")).toHaveCount(2);
  await expect(page.locator(".caseHistoryVersion").filter({ hasText: "Clarified tenant-scope expected result." })).toBeVisible();
  await expect(page.locator(".caseHistoryVersion").filter({ hasText: "Must flag missing tenant scope." })).toBeVisible();

  await page.locator(".evalCaseDetailPanel").getByRole("button", { name: "查看当前" }).click();
  await expect(page.locator(".evalCaseDetailPanel")).toContainText("diff --git a/service.py b/service.py");
  await expect(page.locator(".evalCaseDetailPanel")).toContainText("Must flag missing tenant scope.");
});

test("operator can restore an older eval case version", async ({ page }) => {
  await importSkillBundle(page, `case-restore-${Date.now()}`);
  await addEvalCase(page, "PR: restore case wording");
  await page.getByLabel("Inspector").getByRole("button", { name: "编辑 case" }).click();
  await page.getByPlaceholder("新标题").fill("PR: restore case wording");
  await page.getByPlaceholder("新的 input").fill("diff --git a/service.py b/service.py\n+return Project.find_many({})");
  await page.getByPlaceholder("新的 expected output").fill("Bad edited expectation.");
  await page.getByPlaceholder("为什么更新").fill("Accidental edit.");
  await page.getByRole("button", { name: "保存 case version" }).click();

  await page
    .locator(".caseReviewCard")
    .filter({ hasText: "PR: restore case wording" })
    .getByRole("button", { name: "历史" })
    .click();
  await expect(page.locator(".caseHistoryVersion")).toHaveCount(2);
  await page
    .locator(".caseHistoryVersion")
    .filter({ hasText: "Must flag missing owner_id filter as a P1 issue." })
    .getByRole("button", { name: "恢复此版本" })
    .click();

  await expect(page.getByText("已从 case v1 恢复为新版本。")).toBeVisible();
  await expect(page.locator(".caseHistoryVersion")).toHaveCount(3);
  await expect(page.locator(".caseHistoryVersion").first()).toContainText("Must flag missing owner_id filter as a P1 issue.");
  const currentVersion = page.locator(".caseHistoryVersion").filter({ hasText: "当前版本" });
  await expect(currentVersion).toHaveCount(1);
  await expect(currentVersion).toContainText("Must flag missing owner_id filter as a P1 issue.");
});
