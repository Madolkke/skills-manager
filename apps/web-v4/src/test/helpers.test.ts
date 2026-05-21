import { describe, expect, it } from "vitest";
import { buildBundleTree } from "../lib/bundle";
import { manualRecordHint, manualResultLabel, nextPendingCaseVersionId, summarizeManualEval } from "../lib/eval";
import { sameTags, scoreKind, scoreLabel } from "../lib/format";
import { compactDigest, resolveSelectedRunId, runScoreText } from "../lib/history";
import { summarizeBundleDiff } from "../lib/variant-diff";

describe("skill evidence helpers", () => {
  it("distinguishes untested cards from verified cards", () => {
    expect(scoreKind(null)).toBe("empty");
    expect(scoreLabel(null)).toBe("未测");
    expect(scoreKind({ summary: { passed: 1, failed: 0, total: 1 } } as never)).toBe("verified");
  });

  it("matches variants by tag set instead of input order", () => {
    expect(sameTags(["codex", "gpt5.4"], ["gpt5.4", "codex"])).toBe(true);
    expect(sameTags(["codex"], ["codex", "gpt5.4"])).toBe(false);
  });

  it("summarizes manual evaluation progress", () => {
    expect(summarizeManualEval(3, { a: true, b: false })).toEqual({
      confirmed: 2,
      passed: 1,
      failed: 1,
      pending: 1,
      coverage: 67,
    });
  });

  it("finds the next pending case version for keyboard evaluation flow", () => {
    const cases = [
      { case_version: { id: "case-v1" } },
      { case_version: { id: "case-v2" } },
      { case_version: { id: "case-v3" } },
    ] as never;

    expect(nextPendingCaseVersionId(cases, { "case-v1": true })).toBe("case-v2");
    expect(nextPendingCaseVersionId(cases, { "case-v1": true, "case-v2": false, "case-v3": true })).toBeNull();
  });

  it("moves to the next pending case after the active case before wrapping", () => {
    const cases = [
      { case_version: { id: "case-v1" } },
      { case_version: { id: "case-v2" } },
      { case_version: { id: "case-v3" } },
      { case_version: { id: "case-v4" } },
    ] as never;

    expect(nextPendingCaseVersionId(cases, { "case-v2": true }, "case-v2")).toBe("case-v3");
    expect(
      nextPendingCaseVersionId(cases, { "case-v2": true, "case-v3": true, "case-v4": true }, "case-v4"),
    ).toBe("case-v1");
  });

  it("describes manual evaluation status in Chinese", () => {
    expect(manualResultLabel(true)).toBe("通过");
    expect(manualResultLabel(false)).toBe("不通过");
    expect(manualResultLabel()).toBe("待评估");
    expect(manualRecordHint(3, 1)).toBe("需确认剩余 1 个 case 后才能记录。");
  });

  it("formats evidence chain summaries for history", () => {
    expect(runScoreText({ passed: 3, failed: 1, total: 4 })).toBe("3/4 通过");
    expect(runScoreText({ total: 0 })).toBe("未测");
    expect(compactDigest("sha256:1234567890abcdef")).toBe("sha256:1234567890ab");
    expect(compactDigest("1234567890abcdef")).toBe("1234567890ab");
  });

  it("selects the latest run when route does not specify a valid run", () => {
    const runs = [
      { eval_run: { id: "run-latest" } },
      { eval_run: { id: "run-older" } },
    ] as never;

    expect(resolveSelectedRunId(runs, null)).toBe("run-latest");
    expect(resolveSelectedRunId(runs, "run-older")).toBe("run-older");
    expect(resolveSelectedRunId(runs, "missing-run")).toBe("run-latest");
    expect(resolveSelectedRunId([], null)).toBeNull();
  });

  it("builds a nested bundle tree from root-prefixed file paths", () => {
    const tree = buildBundleTree([
      { path: "code-reviewer/SKILL.md", size_bytes: 412 },
      { path: "code-reviewer/examples/pr.diff", size_bytes: 75 },
      { path: "code-reviewer/tests/cases.md", size_bytes: 48 },
    ] as never, "code-reviewer");

    expect(tree.name).toBe("code-reviewer");
    expect(tree.children.map((node) => node.name)).toEqual(["SKILL.md", "examples", "tests"]);
    expect(tree.children[1]).toMatchObject({ type: "folder", path: "code-reviewer/examples" });
    const examples = tree.children[1];
    expect(examples?.type).toBe("folder");
    if (examples?.type !== "folder") throw new Error("examples should be a folder node");
    expect(examples.children[0]).toMatchObject({ type: "file", name: "pr.diff", path: "code-reviewer/examples/pr.diff" });
  });

  it("summarizes bundle file diff against the previous variant version", () => {
    const diff = summarizeBundleDiff(
      [
        { path: "code-reviewer/SKILL.md", sha256: "new-skill", size_bytes: 420 },
        { path: "code-reviewer/prompts/review.md", sha256: "same-prompt", size_bytes: 80 },
        { path: "code-reviewer/rules/security.md", sha256: "new-rule", size_bytes: 120 },
      ],
      [
        { path: "code-reviewer/SKILL.md", sha256: "old-skill", size_bytes: 410 },
        { path: "code-reviewer/prompts/review.md", sha256: "same-prompt", size_bytes: 80 },
        { path: "code-reviewer/tests/legacy.md", sha256: "old-test", size_bytes: 90 },
      ],
    );

    expect(diff.summary).toEqual({ added: 1, changed: 1, removed: 1, unchanged: 1, total: 4 });
    expect(diff.files.map((file) => `${file.status}:${file.path}`)).toEqual([
      "changed:code-reviewer/SKILL.md",
      "added:code-reviewer/rules/security.md",
      "removed:code-reviewer/tests/legacy.md",
      "unchanged:code-reviewer/prompts/review.md",
    ]);
  });
});
