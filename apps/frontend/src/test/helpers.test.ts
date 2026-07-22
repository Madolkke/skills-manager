import { describe, expect, it, vi } from "vitest";
import { buildBundleTree } from "../lib/bundle";
import { actionBarStatusText, agentLabel, emptyActualOutputText, modelLabel, promptSourceLabel, runnerInsightRows, runnerState, stepTimelineRows, summarizeOpencodeRuns, summarizeRunnerBoard } from "../features/evaluation/lib/evalRunner";
import { currentRunContext, runContextHash } from "../features/evaluation/composables/useOpencodeEvaluation";
import { buildEvalCaseValidationSummary, validateStep } from "../features/evaluation/lib/evalCaseForm";
import { buildCopiedEvalCasePayload, cleanCaseForm, copyEvalCaseTitle } from "../features/evaluation/lib/evalCaseManagement";
import { GENERATED_WORKSPACE_NAME, validateWorkspaceFiles, workspaceFilesToBase64 } from "../features/evaluation/lib/workspaceDraft";
import { pendingPublishRecords, selectedPendingRecords, summarizeBatchResults } from "../lib/batchPublish";
import { evalRunReason, formalEvalReason, publishRequestReason } from "../lib/disabledReasons";
import { runWaitHint } from "../lib/evalWaitHints";
import { scoreKind, scoreLabel } from "../lib/format";
import { compactDigest, resolveSelectedRunId, runScoreText } from "../lib/history";
import { appBasePath, stripAppBase, withAppBase } from "../lib/navigation";
import { buildSkillSuggestions, buildVersionFlowItems } from "../lib/skillGuidance";
import {
  builderSubmitMappingsFromFiles,
  builderSubmitPayloadFiles,
  builderWorkspaceFilesFromSession,
  builderRunningElapsedLabel,
  builderProgressStageText,
  builderProgressSteps,
  builderRecoveryNotice,
  renderMarkdown,
  validateBuilderSubmitMappings,
  validateBuilderWorkspaceFiles,
} from "../features/skill-builder/lib/builderUi";
import {
  buildBundleSourceFromDraftFiles,
  bundleFilesToDraftFiles,
  createBlankSkillSource,
  validateBlankSkillDraft,
  validateBundleDraftFiles,
  validateBundlePath,
} from "../lib/skillBundleDraft";
import { missingRequiredTagGroups, requiredTagMissingMessage, sortTagGroupsForPicker } from "../lib/skillTags";
import { activeTagGroups, buildTagCascadeTreeRows, orphanedTags, pruneInactiveTags, withCascadeParents } from "../lib/tagCascades";
import { filterSkills, tagUsageCounts } from "../pages/hub/hubFilters";
import { buildTaskCenterGroups, taskCenterBadgeCount } from "../lib/taskCenter";
import { summarizeBundleDiff } from "../lib/bundle-diff";
import { api, ApiError, apiErrorMessage, resolveApiBaseUrl } from "../lib/api";
import { bumpVersion, nextPatchVersion } from "../lib/semver";
import { durationText, queuedWorkerJobs, workerCurrentJobText, workerJobTypeText, workerStatusText, workerStatusTone } from "../lib/workerStatus";
import { buildReviewerSources, reviewerSourceText, reviewerUserIds, selectedReviewerCount } from "../lib/reviewerSelection";
import type { EvalSetCase, ReviewerCandidateOverview, SkillSummary, TagGroup, WorkerStatusOverview } from "../types";

describe("skill builder UI helpers", () => {
  it("renders common markdown and safe external links", () => {
    const html = renderMarkdown("# 标题\n\n- A\n- B\n\n```py\nprint('hi')\n```\n\n[站点](https://example.com)");

    expect(html).toContain("<h1>标题</h1>");
    expect(html).toContain("<li>A</li>");
    expect(html).toContain("language-py");
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it("does not emit executable markdown html", () => {
    const html = renderMarkdown("<script>alert(1)</script>\n\n[bad](javascript:alert(1))");

    expect(html).not.toContain("<script");
    expect(html).not.toContain("href=\"javascript:");
  });

  it("formats builder running elapsed time", () => {
    const now = Date.parse("2026-07-05T12:00:00.000Z");

    expect(builderRunningElapsedLabel(null, now)).toBe("正在等待模型返回");
    expect(builderRunningElapsedLabel("2026-07-05T11:59:58.000Z", now)).toBe("刚刚开始");
    expect(builderRunningElapsedLabel("2026-07-05T11:59:42.000Z", now)).toBe("已等待 18 秒");
    expect(builderRunningElapsedLabel("2026-07-05T11:57:50.000Z", now)).toBe("已等待 2 分 10 秒");
  });

  it("builds builder recovery notices", () => {
    expect(builderRecoveryNotice(null)).toBeNull();
    expect(builderRecoveryNotice({ status: "running", messages: [], draft_files: [], run_selection: {} } as never)).toEqual({
      title: "Agent 运行中",
      message: "排队中",
      tone: "running",
    });
    expect(builderRecoveryNotice({ status: "failed", last_error: "AI 创建任务长时间没有进展。", messages: [], draft_files: [], run_selection: {} } as never)).toEqual({
      title: "上次运行未完成",
      message: "AI 创建任务长时间没有进展。",
      tone: "failed",
    });
  });

  it("maps builder progress stages for display", () => {
    expect(builderProgressStageText("sending_message")).toBe("等待模型返回");
    expect(builderProgressStageText("unknown")).toBe("处理中");
    const steps = builderProgressSteps({
      status: "running",
      run_progress: { job_id: "job_1", status: "running", stage: "sending_message" },
      messages: [],
      draft_files: [],
      run_selection: {},
    } as never);

    expect(steps.find((item) => item.stage === "preparing_workspace")?.state).toBe("done");
    expect(steps.find((item) => item.stage === "sending_message")?.state).toBe("active");
    expect(steps.find((item) => item.stage === "saving_result")?.state).toBe("pending");
  });

  it("uses workspace files from Builder sessions before legacy draft files", () => {
    const files = builderWorkspaceFilesFromSession({
      draft_files: [{ path: "legacy.md", content_text: "legacy" }],
      workspace_files: [{ path: "SKILL.md", content_text: "---\nname: writer\ndescription: Write.\n---\n" }],
      run_selection: {},
      messages: [],
    } as never);

    expect(files.map((file) => file.path)).toEqual(["SKILL.md"]);
    expect(validateBuilderWorkspaceFiles([{ id: "file-1", path: "notes.md", binary: false, content_text: "" }]).valid).toBe(true);
  });

  it("builds mapped Builder submit files and validates final bundle paths", () => {
    const mappings = builderSubmitMappingsFromFiles([
      { id: "file-1", path: "workspace/skill.md", binary: false, content_text: "---\nname: writer\ndescription: Write.\n---\n" },
      { id: "file-2", path: "notes.md", binary: false, content_text: "Notes" },
    ]);
    mappings[0].targetPath = "SKILL.md";
    mappings[1].targetPath = "references/notes.md";

    expect(validateBuilderSubmitMappings(mappings).valid).toBe(true);
    expect(builderSubmitPayloadFiles(mappings)).toEqual([
      { path: "SKILL.md", content_text: "---\nname: writer\ndescription: Write.\n---\n" },
      { path: "references/notes.md", content_text: "Notes" },
    ]);
    mappings[1].targetPath = "SKILL.md";
    expect(validateBuilderSubmitMappings(mappings).valid).toBe(false);
  });
});

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
    expect(agentLabel({ eval_case_run: { run_context: { opencode: { agent_id: "strict-reviewer" } } } } as never)).toBe("strict-reviewer");
    expect(promptSourceLabel({ case_version: { steps: [{ id: "s1" }, { id: "s2" }] } } as never)).toBe("2 个步骤");
  });

  it("builds opencode run context with optional agent and model", () => {
    expect(currentRunContext(null)).toEqual({});
    expect(currentRunContext({ agent_id: "strict-reviewer" })).toEqual({ opencode: { agent_id: "strict-reviewer" } });
    expect(currentRunContext({ agent_id: "strict-reviewer", provider_id: "deepseek", model_id: "v4" })).toEqual({
      opencode: { agent_id: "strict-reviewer", provider_id: "deepseek", model_id: "v4" },
    });
    expect(runContextHash({ agent_id: "a", provider_id: "p", model_id: "m" })).toBe("agent:a|model:p/m");
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
    expect(emptyActualOutputText(runnerState({ eval_case_run: { status: "running" } } as never))).toBe("仍在等待后台进程或 Opencode 返回步骤结果。");
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

  it("summarizes runner insights from metadata", () => {
    const rows = runnerInsightRows({
      eval_case_run: {
        status: "running",
        run_context: { opencode: { provider_id: "deepseek", model_id: "v4" } },
        runner_metadata: {
          current_stage_label: "第 1 步执行中",
          current_step: { id: "s1", index: 1, stage: "running" },
          opencode_agent: { agent_id: "strict-reviewer", name: "严格评审" },
          skill_installation: { skill_slug: "writer", version: "0.0.2", mode: "project_isolated" },
        },
      },
    } as never);

    expect(rows.map((row) => `${row.label}:${row.value}`)).toContain("Skill 安装:writer · 0.0.2 · project_isolated");
    expect(rows.map((row) => `${row.label}:${row.value}`)).toContain("运行配置:严格评审 · deepseek/v4");
    expect(rows[0].help).toContain("第 1 步");
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

  it("builds a minimal blank Skill bundle source", () => {
    const source = createBlankSkillSource({ slug: "code-reviewer", description: "Review code changes." });

    expect(source).toEqual({
      kind: "files",
      name: "code-reviewer",
      files: [
        {
          path: "SKILL.md",
          content_text: "---\nname: code-reviewer\ndescription: Review code changes.\n---\n\n# code-reviewer\n",
        },
      ],
    });
    expect(validateBlankSkillDraft({ slug: "Code Reviewer", description: "Review code changes." }).valid).toBe(false);
    expect(validateBlankSkillDraft({ slug: "code-reviewer", description: "" }).errors.description).toBe("填写 Skill 描述。");
  });

  it("validates required Skill Tag groups without forcing a default value", () => {
    const groups = [
      { id: "team", display_name: "团队", description: "", sort_order: 1, required: false, values: [{ tag_group_id: "team", value: "backend", description: "", sort_order: 0 }] },
      { id: "domain", display_name: "业务领域", description: "", sort_order: 10, required: true, values: [{ tag_group_id: "domain", value: "api", description: "", sort_order: 0 }] },
      { id: "risk", display_name: "风险等级", description: "", sort_order: 2, required: true, values: [{ tag_group_id: "risk", value: "high", description: "", sort_order: 0 }] },
    ] as never;

    expect(sortTagGroupsForPicker(groups).map((group) => group.id)).toEqual(["risk", "domain", "team"]);
    expect(missingRequiredTagGroups([{ group_id: "domain", value: "api" }], groups).map((group) => group.id)).toEqual(["risk"]);
    expect(requiredTagMissingMessage([], groups)).toBe("请为必选 Tag Group 选择 Tag：风险等级、业务领域");
    expect(requiredTagMissingMessage([{ group_id: "domain", value: "api" }, { group_id: "risk", value: "high" }], groups)).toBe("");
  });

  it("activates nested Tag Groups and removes descendants with their parent value", () => {
    const groups = [
      {
        id: "platform",
        display_name: "平台",
        description: "",
        sort_order: 0,
        required: true,
        free_form: false,
        parent: null,
        values: [
          { tag_group_id: "platform", value: "cloud", description: "", sort_order: 0 },
          { tag_group_id: "platform", value: "desktop", description: "", sort_order: 1 },
        ],
      },
      {
        id: "provider",
        display_name: "云厂商",
        description: "",
        sort_order: 0,
        required: true,
        free_form: false,
        parent: { group_id: "platform", value: "cloud" },
        values: [{ tag_group_id: "provider", value: "aws", description: "", sort_order: 0 }],
      },
      {
        id: "region",
        display_name: "区域",
        description: "",
        sort_order: 0,
        required: true,
        free_form: true,
        parent: { group_id: "provider", value: "aws" },
        values: [],
      },
    ] as TagGroup[];
    const selected = [
      { group_id: "platform", value: "cloud" },
      { group_id: "provider", value: "aws" },
      { group_id: "region", value: "cn-north" },
    ];

    expect(activeTagGroups(groups, selected).map((item) => `${item.depth}:${item.group.id}`)).toEqual(["0:platform", "1:provider", "2:region"]);
    expect(missingRequiredTagGroups(selected.slice(0, 2), groups).map((group) => group.id)).toEqual(["region"]);
    expect(pruneInactiveTags(selected.filter((tag) => tag.value !== "cloud"), groups)).toEqual([]);
    expect(orphanedTags([{ group_id: "provider", value: "aws" }], groups)).toEqual([{ group_id: "provider", value: "aws" }]);
  });

  it("builds a cascade tree from flat relations", () => {
    const groups = [
      { id: "root", display_name: "Root", description: "", sort_order: 0, required: false, free_form: false, values: [{ tag_group_id: "root", value: "one", description: "", sort_order: 0 }] },
      { id: "child", display_name: "Child", description: "", sort_order: 0, required: false, free_form: true, values: [] },
    ] as TagGroup[];
    const nested = withCascadeParents(groups, [{ child_group_id: "child", parent_group_id: "root", parent_value: "one" }]);

    expect(buildTagCascadeTreeRows(nested).map((row) => `${row.depth}:${row.kind}:${row.kind === "group" ? row.group.id : row.value.value}`)).toEqual([
      "0:group:root",
      "1:value:one",
      "2:group:child",
    ]);
  });

  it("keeps orphan Tags searchable but excludes them from structured Hub filters", () => {
    const skill = {
      skill: {
        id: "skill-1",
        slug: "writer",
        owner_ref: "alice",
        current_version_id: null,
        lifecycle_status: "active",
        tags: [{ group_id: "child", value: "orphan-value", path_valid: false }],
      },
      summary: { current_version: null, latest_accepted_eval_run: null },
    } as SkillSummary;

    expect(filterSkills([skill], { query: "orphan-value", filter: "all", actor: "", selectedTags: [], tagGroups: [] })).toHaveLength(1);
    expect(filterSkills([skill], {
      query: "",
      filter: "all",
      actor: "",
      selectedTags: [{ group_id: "child", value: "orphan-value" }],
      tagGroups: [],
    })).toHaveLength(0);
    expect(tagUsageCounts([skill])).toEqual({});
  });

  it("validates Skill bundle file paths", () => {
    for (const path of ["../x", "/x", "C:\\x", "a\\ b", "", "safe/../x"]) {
      expect(validateBundlePath(path)).not.toBe("");
    }
    expect(validateBundlePath("prompts/review.md")).toBe("");
    const duplicate = validateBundleDraftFiles([
      { id: "file-1", path: "SKILL.md", binary: false, content_text: "---\nname: a\ndescription: a\n---\n" },
      { id: "file-2", path: "SKILL.md", binary: false, content_text: "" },
    ]);
    expect(duplicate.valid).toBe(false);
    expect(duplicate.errors["file-2"]).toBe("文件路径重复。");
  });

  it("builds editable Skill bundle source from draft files", () => {
    const drafts = bundleFilesToDraftFiles([
      { path: "SKILL.md", content_text: "---\nname: writer\ndescription: Writes docs.\n---\n", binary: false },
      { path: "assets/logo.png", content_base64: "aGVsbG8=", binary: true },
    ]);
    const renamedBinary = drafts.map((file) => (file.path === "assets/logo.png" ? { ...file, path: "assets/icon.png" } : file));
    const source = buildBundleSourceFromDraftFiles([
      ...renamedBinary,
      { id: "new-file", path: "prompts/guide.md", binary: false, content_text: "Write clearly." },
    ], "writer");

    expect(source).toEqual({
      kind: "files",
      name: "writer",
      files: [
        { path: "SKILL.md", content_text: "---\nname: writer\ndescription: Writes docs.\n---\n" },
        { path: "assets/icon.png", content_base64: "aGVsbG8=" },
        { path: "prompts/guide.md", content_text: "Write clearly." },
      ],
    });
    expect(() => buildBundleSourceFromDraftFiles([{ id: "file-1", path: "notes.md", binary: false, content_text: "" }], "writer")).toThrow("必须保留根目录 SKILL.md。");
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

  it("serializes free Tag Group and cascade admin requests", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ relations: [], diagnostics: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await api.adminCreateTagGroup({ id: "keywords", display_name: "关键词", free_form: true, required: true });
    await api.adminCreateTagCascade({ parent_group_id: "platform", parent_value: "cloud", child_group_id: "provider" });

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ id: "keywords", display_name: "关键词", free_form: true, required: true }),
    });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({ parent_group_id: "platform", parent_value: "cloud", child_group_id: "provider" }),
    });
    fetchMock.mockRestore();
  });

  it("sends the confirmation slug as a JSON DELETE body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await api.deleteSkill("skill/one", "example-skill");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/skills/skill%2Fone"),
      expect.objectContaining({
        method: "DELETE",
        body: JSON.stringify({ confirmation_slug: "example-skill" }),
        headers: expect.objectContaining({ "content-type": "application/json" }),
      }),
    );
    fetchMock.mockRestore();
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

  it("builds validation summary for eval case editor", () => {
    const form = {
      title: "",
      steps: [
        {
          id: "",
          title: "步骤 1",
          input: "",
          assertions: [{ id: "assertion-1", assertion_template_id: "missing", assertion_params: {} }],
        },
      ],
      workspace_files: [{ id: "file-1", path: "../x", content: "" }],
      runner_config: {},
      notes: "",
    };
    const stepValidations = form.steps.map((step) => validateStep(step, () => undefined));
    const summary = buildEvalCaseValidationSummary(form, stepValidations);

    expect(summary.map((item) => item.label)).toEqual(["标题", "步骤 1", "工作区"]);
    expect(summary[1].stepIndex).toBe(0);
    expect(summary[2].message).toContain("路径不能包含");
  });

  it("explains disabled actions with user-facing reasons", () => {
    expect(evalRunReason({ canRun: false, caseCount: 1 })).toContain("没有运行测评权限");
    expect(evalRunReason({ canRun: true, caseCount: 0 })).toContain("还没有测试例");
    expect(formalEvalReason({ canRun: true, canRunFormal: false, caseCount: 2 })).toContain("所有测试例");
    expect(publishRequestReason({ canRequest: false, reviewClosed: true })).toContain("发布确认单");
  });

  it("aggregates task center groups from existing frontend data", () => {
    const groups = buildTaskCenterGroups({
      reviews: [
        { id: "review-1", status: "open", skill: { slug: "writer" }, skill_version: { version: "0.0.1" } },
        { id: "review-2", status: "closed", skill: { slug: "closed" }, skill_version: { version: "0.0.1" } },
      ] as never,
      notifications: [
        { id: "notification-1", title: "新通知", body: "请处理", read_at: null },
        { id: "notification-2", title: "已读", body: "", read_at: "2026-01-01" },
      ] as never,
      skill: { skill: { id: "skill-1" }, latest_eval_runs: [{ status: "running", created_at: "2026-01-01" }] } as never,
      publishOverview: { publish_records: [{ status: "pending_confirmation", created_at: "2026-01-02" }] } as never,
    });

    expect(groups.map((group) => group.id)).toEqual(["reviews", "notifications", "skill"]);
    expect(taskCenterBadgeCount(groups)).toBe(4);
  });

  it("diagnoses long waiting eval runs without changing run state", () => {
    const now = new Date("2026-06-28T10:10:00Z").getTime();
    expect(runWaitHint({
      eval_case_run: { status: "queued", created_at: "2026-06-28T10:07:30Z" },
      job: { status: "queued" },
      case_version: { runner_config: {} },
    } as never, now)?.title).toBe("排队时间较长");
    expect(runWaitHint({
      eval_case_run: { status: "running", started_at: "2026-06-28T10:07:00Z" },
      job: { status: "running" },
      case_version: { runner_config: { timeout_seconds: 60 } },
    } as never, now)?.title).toBe("运行时间超过预期");
    expect(runWaitHint({ eval_case_run: { status: "running" }, job: { status: "running" }, case_version: { runner_config: {} } } as never, now)).toBeNull();
  });

  it("builds readonly version flow and skill suggestions", () => {
    const skillFixture = {
      skill: { id: "skill-1", current_version_id: "version-1" },
      versions: [{ id: "version-1", version: "0.0.1", change_summary: "init" }],
      eval_sets: [{ id: "evalset-1" }],
      latest_eval_runs: [{ skill_version_id: "version-1", summary: { passed: 1, total: 1 }, created_at: "2026-01-01" }],
    };
    const skill = skillFixture as never;
    const reviews = [{ id: "review-1", skill_version_id: "version-1", status: "closed", responses: [{ reviewer_actor: "u" }], reviewers: [{ reviewer_actor: "u" }] }] as never;
    const publishRecords = [{ id: "publish-1", skill_version_id: "version-1", status: "pending_confirmation" }] as never;
    const flow = buildVersionFlowItems({ skill, reviews, publishRecords });

    expect(flow[0].stages.map((stage) => `${stage.id}:${stage.status}`)).toEqual(["version:done", "evaluation:done", "review:done", "publish:active"]);
    expect(buildSkillSuggestions({ skill, reviews, publishRecords })).toEqual([]);
    expect(buildSkillSuggestions({ skill: { ...skillFixture, eval_sets: [], latest_eval_runs: [] } as never })).toEqual([
      expect.objectContaining({ id: "create-eval-set" }),
      expect.objectContaining({ id: "run-evaluation" }),
      expect.objectContaining({ id: "start-review" }),
    ]);
  });

  it("selects pending publish records for batch actions", () => {
    const records = [
      { id: "p1", status: "pending_confirmation" },
      { id: "p2", status: "released" },
      { id: "p3", status: "pending_confirmation" },
    ] as never;
    expect(pendingPublishRecords(records).map((record) => record.id)).toEqual(["p1", "p3"]);
    expect(selectedPendingRecords(records, new Set(["p1", "p2"])).map((record) => record.id)).toEqual(["p1"]);
    expect(summarizeBatchResults([{ ok: true }, { ok: false }])).toEqual({ total: 2, succeeded: 1, failed: 1 });
  });

  it("builds copied eval case titles within the API limit", () => {
    expect(copyEvalCaseTitle("A")).toBe("A（副本）");
    const title = copyEvalCaseTitle("测".repeat(200));
    expect(title.endsWith("（副本）")).toBe(true);
    expect(title.length).toBeLessThanOrEqual(160);
  });

  it("builds copied eval case payload without sharing nested step objects", () => {
    const source: EvalSetCase = {
      position: 0,
      case: { id: "case_1", skill_id: "skill_1", title: "生成 README", current_version_id: "casever_1" },
      case_version: {
        id: "casever_1",
        skill_id: "skill_1",
        case_id: "case_1",
        version_number: 1,
        steps: [
          {
            id: "step-1",
            title: "步骤 1",
            input: "创建 README.md",
            assertions: [
              {
                id: "assertion-1",
                assertion_template_id: "file_exists",
                assertion_params: { directory: ".", filename: "README.md" },
              },
            ],
          },
        ],
        runner_config: { timeout_seconds: 60 },
        notes: "需要工作区文件",
        created_by: "tester",
        workspace_artifact: null,
      },
    };

    const payload = buildCopiedEvalCasePayload(source, { evalSetId: "evalset_1" });

    expect(payload.title).toBe("生成 README（副本）");
    expect(payload).not.toHaveProperty("workspace_base64");
    expect(payload.steps).not.toBe(source.case_version.steps);
    expect(payload.steps[0].assertions).not.toBe(source.case_version.steps[0].assertions);
    expect(payload.steps[0].assertions[0].assertion_params).not.toBe(source.case_version.steps[0].assertions[0].assertion_params);
    expect(payload.runner_config).toEqual({ timeout_seconds: 60 });
  });

  it("validates workspace file paths before generating a zip", () => {
    for (const path of ["../x", "/x", "C:\\x", "a\\ b", "", "safe/../x"]) {
      const result = validateWorkspaceFiles([{ id: "file-1", path, content: "" }]);
      expect(result.valid).toBe(false);
    }
    const duplicate = validateWorkspaceFiles([
      { id: "file-1", path: "README.md", content: "" },
      { id: "file-2", path: "README.md", content: "" },
    ]);
    expect(duplicate.valid).toBe(false);
  });

  it("generates workspace zip base64 with the fixed workspace filename", async () => {
    const base64 = await workspaceFilesToBase64([
      { id: "file-1", path: "README.md", content: "hello" },
      { id: "file-2", path: "src/app.ts", content: "export const ok = true;" },
    ]);

    expect(GENERATED_WORKSPACE_NAME).toBe("workspace.generated.zip");
    expect(base64.length).toBeGreaterThan(20);
    expect(() => atob(base64)).not.toThrow();
  });

  it("calculates semantic version bumps", () => {
    expect(bumpVersion("0.0.1", "major")).toBe("1.0.0");
    expect(bumpVersion("0.0.1", "minor")).toBe("0.1.0");
    expect(bumpVersion("0.0.1", "patch")).toBe("0.0.2");
    expect(nextPatchVersion([])).toBe("0.0.1");
  });

  it("keeps SPA route paths under the configured app base", () => {
    expect(appBasePath("/")).toBe("");
    expect(appBasePath("/skillhub/")).toBe("/skillhub");
    expect(withAppBase("/skills", "/")).toBe("/skills");
    expect(withAppBase("skills/admin", "/skillhub/")).toBe("/skillhub/skills/admin");
    expect(stripAppBase("/skillhub/skills/reviews", "/skillhub/")).toBe("/skills/reviews");
    expect(stripAppBase("/skillhub", "/skillhub/")).toBe("/");
    expect(stripAppBase("/skills", "/skillhub/")).toBe("/skills");
  });

  it("keeps the Skill Builder route under the app base", () => {
    expect(withAppBase("/skills/builder", "/skillhub/")).toBe("/skillhub/skills/builder");
    expect(stripAppBase("/skillhub/skills/builder", "/skillhub/")).toBe("/skills/builder");
  });

  it("summarizes worker status labels and queued jobs", () => {
    const overview: WorkerStatusOverview = {
      generated_at: "2026-07-09T10:05:30.000Z",
      online_threshold_seconds: 30,
      active_window_hours: 24,
      summary: {
        total: 2,
        online: 1,
        running: 1,
        idle: 0,
        offline: 1,
        queued_eval_jobs: 3,
        queued_builder_jobs: 2,
        running_jobs: 1,
      },
      workers: [
        {
          worker_id: "worker-1",
          status: "running",
          online: true,
          last_seen_at: "2026-07-09T10:05:20.000Z",
          started_at: "2026-07-09T09:00:00.000Z",
          current_job: {
            id: "job_1",
            type: "eval_case_run",
            attempts: 2,
            started_at: "2026-07-09T10:00:00.000Z",
            run_id: "run_1",
            skill_version_id: "skillver_1",
          },
        },
        {
          worker_id: "worker-2",
          status: "offline",
          online: false,
          last_seen_at: "2026-07-09T09:00:00.000Z",
          started_at: "2026-07-09T08:00:00.000Z",
        },
      ],
    };

    expect(queuedWorkerJobs(overview)).toBe(5);
    expect(workerStatusText(overview.workers[0])).toBe("运行中");
    expect(workerStatusTone(overview.workers[0])).toBe("neutral");
    expect(workerStatusText(overview.workers[1])).toBe("离线");
    expect(workerStatusTone(overview.workers[1])).toBe("negative");
    expect(workerJobTypeText("skill_builder_message")).toBe("AI 创建任务");
    expect(workerCurrentJobText(overview.workers[0])).toBe("Run run_1 · Version skillver_1");
    expect(workerCurrentJobText(overview.workers[1])).toBe("无当前任务");
    expect(durationText("2026-07-09T10:05:00.000Z", overview.generated_at)).toBe("30s");
    expect(durationText("2026-07-09T09:00:00.000Z", overview.generated_at)).toBe("1h 5m");
  });

  it("builds explicit review subjects from groups and typed users", () => {
    const candidates: ReviewerCandidateOverview = {
      skill_id: "skill_1",
      groups: [
        {
          id: "group_1",
          scope_type: "global",
          scope_id: "default",
          name: "backend-reviewers",
          description: "",
          member_count: 2,
          members: [
            { group_id: "group_1", subject_type: "user", subject_id: "alice" },
            { group_id: "group_1", subject_type: "user", subject_id: "bob" },
          ],
        },
      ],
    };

    expect(reviewerUserIds("alice, bob；alice carol")).toEqual(["alice", "bob", "carol"]);
    expect(buildReviewerSources(["group_1", "group_1"], "bob; carol")).toEqual([
      { subject_type: "group", subject_id: "group_1" },
      { subject_type: "user", subject_id: "bob" },
      { subject_type: "user", subject_id: "carol" },
    ]);
    expect(selectedReviewerCount(["group_1"], "bob carol", candidates)).toBe(3);
    expect(reviewerSourceText({ reviewer_actor: "alice", source_subject_type: "group", source_subject_id: "group_1" } as never, candidates)).toBe("alice（backend-reviewers）");
  });
});
