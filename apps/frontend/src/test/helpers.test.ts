import { describe, expect, it } from "vitest";
import { buildBundleTree } from "../lib/bundle";
import { actionBarStatusText, emptyActualOutputText, modelLabel, promptSourceLabel, runnerState, stepTimelineRows, summarizeOpencodeRuns, summarizeRunnerBoard } from "../features/evaluation/lib/evalRunner";
import { cleanCaseForm } from "../features/evaluation/lib/evalCaseManagement";
import { scoreKind, scoreLabel } from "../lib/format";
import { compactDigest, resolveSelectedRunId, runScoreText } from "../lib/history";
import { summarizeBundleDiff } from "../lib/bundle-diff";
import { ApiError, apiErrorMessage, resolveApiBaseUrl } from "../lib/api";
import { bumpVersion, nextPatchVersion } from "../lib/semver";

describe("skill evidence helpers", () => {
  it("distinguishes untested cards from verified cards", () => {
    expect(scoreKind(null)).toBe("empty");
    expect(scoreLabel(null)).toBe("未测");
    expect(scoreKind({ summary: { passed: 1, failed: 0, total: 1 } } as never)).toBe("verified");
  });

  it("summarizes runner board states", () => {
    const cases = [
      { case_version: { id: "case-v1" } },
      { case_version: { id: "case-v2" } },
      { case_version: { id: "case-v3" } },
    ] as never;
    const runs = {
      "case-v1": { eval_case_run: { status: "queued" } },
      "case-v2": { eval_case_run: { status: "succeeded", passed: true } },
      "case-v3": { eval_case_run: { status: "succeeded", passed: false } },
    } as never;

    expect(summarizeRunnerBoard(cases, runs)).toEqual([
      { kind: "not-run", label: "未运行", count: 0 },
      { kind: "queued", label: "排队中", count: 1 },
      { kind: "running", label: "运行中", count: 0 },
      { kind: "passed", label: "通过", count: 1 },
      { kind: "rejected", label: "不通过", count: 1 },
      { kind: "failed", label: "执行失败", count: 0 },
    ]);
  });

  it("describes runner state and case config in Chinese", () => {
    expect(runnerState(null).label).toBe("未运行");
    expect(runnerState({ eval_case_run: { status: "running" }, job: { status: "running" } } as never).label).toBe("运行中");
    expect(runnerState({ eval_case_run: { status: "failed", error: "worker failed" } } as never).helper).toBe("worker failed");
    expect(modelLabel({ case_version: { runner_config: {} } } as never)).toBe("Opencode 外部配置");
    expect(modelLabel(null, { eval_case_run: { run_context: { opencode: { provider_id: "deepseek", model_id: "v4" } } } } as never)).toBe("deepseek/v4");
    expect(promptSourceLabel({ case_version: { steps: [{ id: "s1" }, { id: "s2" }] } } as never)).toBe("2 个步骤");
  });

  it("describes active runner feedback without inventing progress", () => {
    const cases = [
      { case_version: { id: "case-v1" } },
      { case_version: { id: "case-v2" } },
    ] as never;
    const summary = summarizeOpencodeRuns(cases, {
      "case-v1": { eval_case_run: { status: "running" }, job: { status: "running" } },
      "case-v2": { eval_case_run: { status: "queued" }, job: { status: "queued" } },
    } as never);

    expect(summary.runningRuns).toBe(1);
    expect(summary.queuedRuns).toBe(1);
    expect(actionBarStatusText(summary, 2, 5)).toBe("正在运行 1 个测试例，页面每 5 秒自动刷新。");
    expect(emptyActualOutputText(runnerState({ eval_case_run: { status: "running" } } as never))).toBe("等待步骤执行结果...");
  });

  it("merges configured steps with current runner progress", () => {
    const item = {
      case_version: {
        steps: [
          {
            id: "s1",
            title: "第一步",
            input: "生成 README",
            assertions: [{ id: "assertion-1", assertion_template_id: "agent_output_contains", assertion_params: { text: "README" } }],
          },
          {
            id: "s2",
            title: "第二步",
            input: "检查文件",
            assertions: [{ id: "assertion-1", assertion_template_id: "file_exists", assertion_params: { path: "README.md" } }],
          },
        ],
      },
    } as never;
    const detail = {
      eval_case_run: {
        runner_metadata: {
          current_stage_label: "第 2/2 步判定中",
          current_step: { id: "s2", index: 2, stage: "asserting" },
          step_results: [{ step_id: "s1", status: "passed", reason: "输出包含指定文本。", actual: "README" }],
        },
      },
    } as never;

    expect(stepTimelineRows(item, detail).map((step) => `${step.id}:${step.label}`)).toEqual(["s1:通过", "s2:判定中"]);
    expect(stepTimelineRows(item, detail)[1].reason).toBe("第 2/2 步判定中");
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

  it("summarizes bundle file diff against the previous skill version", () => {
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

  it("derives the API URL from the current browser host for LAN users", () => {
    expect(resolveApiBaseUrl({
      location: { protocol: "http:", hostname: "192.168.1.20" },
      configuredPort: "18000",
    })).toBe("http://192.168.1.20:18000");
  });

  it("keeps an explicit API URL when one is configured", () => {
    expect(resolveApiBaseUrl({
      configuredUrl: "http://api.skillhub.test:9000/",
      location: { protocol: "http:", hostname: "192.168.1.20" },
    })).toBe("http://api.skillhub.test:9000");
  });

  it("prefers concrete API field errors over generic request messages", () => {
    expect(apiErrorMessage(new ApiError("请求字段不完整或格式不正确。", 422, { title: "填写标题。" }))).toBe("填写标题。");
  });

  it("only sends preserve_workspace when updating an existing eval case", () => {
    const form = {
      title: "新增文件测试",
      steps: [
        {
          id: "",
          title: "步骤 1",
          input: "请创建 done.txt",
          assertions: [
            {
              id: "assertion-1",
              assertion_template_id: "file_created",
              assertion_params: { directory: ".", filename: "done.txt" },
            },
          ],
        },
      ],
      runner_config: {},
      notes: "",
    };

    expect(cleanCaseForm(form)).not.toHaveProperty("preserve_workspace");
    expect(cleanCaseForm(form, { includePreserveWorkspace: true })).toHaveProperty("preserve_workspace", true);
  });

  it("calculates semantic version bumps", () => {
    expect(bumpVersion("0.0.1", "major")).toBe("1.0.0");
    expect(bumpVersion("0.0.1", "minor")).toBe("0.1.0");
    expect(bumpVersion("0.0.1", "patch")).toBe("0.0.2");
    expect(nextPatchVersion([])).toBe("0.0.1");
  });
});
