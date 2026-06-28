import type { EvalCaseRunDetail, EvalCaseRunRecord, EvalCaseStep, EvalSetCase, EvalStepAssertion } from "../../../types";
import { humanDate } from "../../../lib/format";

export type RunnerStateKind = "not-run" | "queued" | "running" | "passed" | "failed" | "rejected";

export type RunnerState = {
  kind: RunnerStateKind;
  label: string;
  helper: string;
};

export type RunnerBoardItem = {
  kind: RunnerStateKind;
  label: string;
  count: number;
};

export type RunnerStatusRow = {
  label: string;
  value: string;
};

export type RunnerInsight = {
  label: string;
  value: string;
  help: string;
};

export type OpencodeToolCall = {
  tool: string;
  status: string;
  input: unknown;
  output_preview: string;
  call_id: string;
};

export type OpencodeTrace = {
  reasoning_text: string;
  tool_calls: OpencodeToolCall[];
  text_output: string;
  finish: string;
  model_id: string;
  provider_id: string;
};

export type AssertionRunResult = {
  assertion_id: string;
  assertion_template_id: string;
  status: "passed" | "failed" | "skipped" | string;
  passed?: boolean | null;
  actual?: string;
  reason?: string;
  details?: Record<string, unknown>;
};

export type StepRunResult = {
  step_id: string;
  title: string;
  status: "passed" | "failed" | "skipped" | string;
  passed?: boolean | null;
  actual?: string;
  reason?: string;
  details?: Record<string, unknown>;
  assertions?: AssertionRunResult[];
  opencode_trace?: OpencodeTrace;
};

export type StepTimelineAssertionRow = {
  id: string;
  assertionTemplateId: string;
  status: "pending" | "running" | "asserting" | "passed" | "failed" | "skipped";
  label: string;
  reason: string;
  actual: string;
  details?: Record<string, unknown>;
};

export type StepTimelineRow = {
  id: string;
  title: string;
  input: string;
  status: "pending" | "running" | "asserting" | "passed" | "failed" | "skipped";
  label: string;
  reason: string;
  actual: string;
  assertions: StepTimelineAssertionRow[];
  opencodeTrace?: OpencodeTrace;
};

export type RunnerSummary = {
  confirmed: number;
  passed: number;
  failed: number;
  failedRuns: number;
  queuedRuns: number;
  runningRuns: number;
  pending: number;
  coverage: number;
};

export function runnerState(detail?: EvalCaseRunDetail | null): RunnerState {
  if (!detail) return { kind: "not-run", label: "未运行", helper: "尚未创建任务" };
  const jobStatus = detail.job?.status;
  if (detail.eval_case_run.status === "succeeded") {
    return detail.eval_case_run.passed
      ? { kind: "passed", label: "通过", helper: "输出满足期望" }
      : { kind: "rejected", label: "不通过", helper: "输出未满足期望" };
  }
  if (detail.eval_case_run.status === "failed" || detail.eval_case_run.status === "canceled") {
    return { kind: "failed", label: "执行失败", helper: detail.eval_case_run.error || detail.job?.error || "测评器未完成" };
  }
  if (detail.eval_case_run.status === "running" || jobStatus === "running") return { kind: "running", label: "运行中", helper: "后台进程正在执行" };
  return { kind: "queued", label: "排队中", helper: "等待后台进程领取" };
}

export function summarizeOpencodeRuns(items: EvalSetCase[], runs: Record<string, EvalCaseRunDetail>): RunnerSummary {
  const values = items.map((item) => runs[item.case_version.id]).filter(Boolean);
  const succeeded = values.filter((item) => item.eval_case_run.status === "succeeded");
  return {
    confirmed: succeeded.length,
    passed: succeeded.filter((item) => item.eval_case_run.passed === true).length,
    failed: succeeded.filter((item) => item.eval_case_run.passed === false).length,
    failedRuns: values.filter((item) => item.eval_case_run.status === "failed").length,
    queuedRuns: values.filter((item) => runnerState(item).kind === "queued").length,
    runningRuns: values.filter((item) => runnerState(item).kind === "running").length,
    pending: Math.max(items.length - succeeded.length, 0),
    coverage: items.length === 0 ? 0 : Math.round((succeeded.length / items.length) * 100),
  };
}

export function summarizeRunnerBoard(items: EvalSetCase[], runs: Record<string, EvalCaseRunDetail>): RunnerBoardItem[] {
  const counts: Record<RunnerStateKind, number> = {
    "not-run": 0,
    queued: 0,
    running: 0,
    passed: 0,
    failed: 0,
    rejected: 0,
  };
  for (const item of items) counts[runnerState(runs[item.case_version.id]).kind] += 1;
  return [
    { kind: "not-run", label: "未运行", count: counts["not-run"] },
    { kind: "queued", label: "排队中", count: counts.queued },
    { kind: "running", label: "运行中", count: counts.running },
    { kind: "passed", label: "通过", count: counts.passed },
    { kind: "rejected", label: "不通过", count: counts.rejected },
    { kind: "failed", label: "执行失败", count: counts.failed },
  ];
}

export function modelLabel(item?: EvalSetCase | null, detail?: EvalCaseRunDetail | null): string {
  void item;
  const selection = opencodeSelectionFromRun(detail);
  if (selection?.provider_id && selection.model_id) return `${selection.provider_id}/${selection.model_id}`;
  return "Opencode 外部配置";
}

export function agentLabel(detail?: EvalCaseRunDetail | null): string {
  const snapshot = opencodeAgentSnapshot(detail);
  if (snapshot) return snapshot.name || snapshot.agent_id;
  const selection = opencodeSelectionFromRun(detail);
  if (selection?.agent_id) return selection.agent_id;
  return "Opencode 默认 Agent";
}

export function promptSourceLabel(item: EvalSetCase): string {
  return `${item.case_version.steps.length} 个步骤`;
}

export function runTimeLabel(detail?: EvalCaseRunDetail | null): string {
  const value = detail?.eval_case_run.finished_at ?? detail?.eval_case_run.started_at ?? detail?.eval_case_run.created_at;
  return value ? humanDate(value) : "-";
}

export function runActivityHint(detail?: EvalCaseRunDetail | null): string {
  const state = runnerState(detail);
  if (state.kind === "running") return "正在执行";
  if (state.kind === "queued") return "等待领取";
  return "";
}

export function emptyActualOutputText(state: RunnerState): string {
  if (state.kind === "running") return "仍在等待后台进程或 Opencode 返回步骤结果。";
  if (state.kind === "queued") return "任务已入队，等待后台进程领取。";
  return state.helper;
}

export function actionBarStatusText(summary: RunnerSummary, caseCount: number, pollIntervalSeconds: number): string {
  if (summary.runningRuns > 0) return `正在运行 ${summary.runningRuns} 个测试例，页面每 ${pollIntervalSeconds} 秒自动刷新。`;
  if (summary.queuedRuns > 0) return `${summary.queuedRuns} 个测试例正在排队，等待后台进程领取。`;
  return `${summary.confirmed}/${caseCount} 个 Opencode 测试例已完成，${summary.failedRuns} 个执行失败。`;
}

export function metadataText(detail: EvalCaseRunDetail | null | undefined, key: string): string {
  const value = detail?.eval_case_run.runner_metadata?.[key];
  return typeof value === "string" && value.trim() ? value : "";
}

export function currentStageLabel(detail: EvalCaseRunDetail | null | undefined): string {
  return metadataText(detail, "current_stage_label");
}

export function runError(detail: EvalCaseRunDetail | null | undefined): string {
  return detail?.eval_case_run.error || detail?.job?.error || "";
}

export function opencodeSelectionFromRun(detail?: EvalCaseRunDetail | null): { agent_id?: string; provider_id?: string; model_id?: string } | null {
  const runContext = detail?.eval_case_run.run_context;
  const raw = runContext && typeof runContext === "object" ? runContext.opencode : null;
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const agentId = typeof row.agent_id === "string" ? row.agent_id : "";
  const providerId = typeof row.provider_id === "string" ? row.provider_id : "";
  const modelId = typeof row.model_id === "string" ? row.model_id : "";
  const selection: { agent_id?: string; provider_id?: string; model_id?: string } = {};
  if (agentId) selection.agent_id = agentId;
  if (providerId && modelId) {
    selection.provider_id = providerId;
    selection.model_id = modelId;
  }
  return Object.keys(selection).length ? selection : null;
}

export function runnerStatusRows(detail: EvalCaseRunDetail | null | undefined): RunnerStatusRow[] {
  return [
    { label: "运行", value: detail?.eval_case_run.status ?? "未运行" },
    { label: "任务", value: detail?.job?.status ?? "无任务" },
    { label: "次数", value: String(detail?.job?.attempts ?? 0) },
    { label: "阶段", value: currentStageLabel(detail) || "-" },
    { label: "Agent", value: agentLabel(detail) },
    { label: "模型", value: modelLabel(null, detail) },
    { label: "会话", value: metadataText(detail, "session_id") || "-" },
    { label: "工作目录", value: metadataText(detail, "workdir") || "-" },
    { label: "Laminar", value: metadataText(detail, "laminar_datapoint_id") || (detail?.eval_case_run.runner_metadata?.laminar_configured === false ? "未配置" : "-") },
    { label: "更新", value: runTimeLabel(detail) },
  ];
}

export function runnerInsightRows(detail: EvalCaseRunDetail | null | undefined): RunnerInsight[] {
  return [
    {
      label: "当前阶段",
      value: currentStageLabel(detail) || runnerState(detail).label,
      help: currentStepText(detail) || "还没有记录到具体步骤。",
    },
    {
      label: "运行配置",
      value: `${agentLabel(detail)} · ${modelLabel(null, detail)}`,
      help: runConfigHelp(detail),
    },
    {
      label: "Skill 安装",
      value: skillInstallationText(detail),
      help: "每次测评会把被测 Skill 安装到隔离工作区的项目级 Skill 目录。",
    },
  ];
}

function opencodeAgentSnapshot(detail: EvalCaseRunDetail | null | undefined): { agent_id: string; name: string } | null {
  const value = detail?.eval_case_run.runner_metadata?.opencode_agent;
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const agentId = typeof row.agent_id === "string" ? row.agent_id : "";
  const name = typeof row.name === "string" ? row.name : "";
  return agentId || name ? { agent_id: agentId, name } : null;
}

function runConfigHelp(detail: EvalCaseRunDetail | null | undefined): string {
  const selection = opencodeSelectionFromRun(detail);
  const parts = [];
  parts.push(selection?.agent_id ? "本次运行显式指定了 SkillHub Agent。" : "本次运行使用 Opencode 默认 Agent。");
  parts.push(selection?.provider_id && selection.model_id ? "provider/model 显式覆盖 Agent 默认模型。" : "模型使用 Opencode 或 Agent 默认配置。");
  return parts.join("");
}

export function stepRunResults(detail: EvalCaseRunDetail | null | undefined): StepRunResult[] {
  const value = detail?.eval_case_run.runner_metadata?.step_results;
  return Array.isArray(value) ? value as StepRunResult[] : [];
}

export function stepTimelineRows(item: EvalSetCase, detail: EvalCaseRunDetail | null | undefined): StepTimelineRow[] {
  const results = new Map(stepRunResults(detail).map((step) => [step.step_id, step]));
  const current = currentStep(detail);
  return item.case_version.steps.map((step, index) => {
    const result = results.get(step.id);
    if (result) {
      const status = normalizeStepStatus(result.status);
      return {
        id: step.id,
        title: step.title,
        input: step.input,
        status,
        label: stepStatusLabel(status),
        reason: result.reason || "",
        actual: result.actual || "",
        assertions: assertionTimelineRows(step, result.assertions, status),
        opencodeTrace: result.opencode_trace,
      };
    }
    if (current?.id === step.id || current?.index === index + 1) {
      const status = current.stage === "asserting" ? "asserting" : "running";
      return {
        id: step.id,
        title: step.title,
        input: step.input,
        status,
        label: stepStatusLabel(status),
        reason: currentStageLabel(detail),
        actual: "",
        assertions: assertionTimelineRows(step, undefined, status),
      };
    }
    return {
      id: step.id,
      title: step.title,
      input: step.input,
      status: "pending",
      label: "待执行",
      reason: "",
      actual: "",
      assertions: assertionTimelineRows(step, undefined, "pending"),
    };
  });
}

export function isActiveRun(status: string): boolean {
  return ["queued", "running"].includes(status);
}

export function queuedRecordToDetail(record: EvalCaseRunRecord, item: EvalSetCase): EvalCaseRunDetail {
  return {
    eval_case_run: {
      id: record.eval_case_run_id,
      job_id: record.job_id,
      skill_id: record.skill_id,
      skill_version_id: record.skill_version_id,
      eval_set_id: record.eval_set_id,
      case_version_id: record.case_version_id,
      status: record.status,
      passed: record.passed,
      score: record.score,
    },
    job: { id: record.job_id, attempts: 0, status: record.status },
    case_version: item.case_version,
    result_artifact: null,
  };
}

export function resolveRunnerPollInterval(rawValue: unknown): number {
  const value = Number(rawValue);
  if (!Number.isFinite(value) || value < 1000) return 5000;
  return Math.round(value);
}

function currentStep(detail: EvalCaseRunDetail | null | undefined): { id?: string; index?: number; stage?: string } | null {
  const value = detail?.eval_case_run.runner_metadata?.current_step;
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  return {
    id: typeof row.id === "string" ? row.id : undefined,
    index: typeof row.index === "number" ? row.index : undefined,
    stage: typeof row.stage === "string" ? row.stage : undefined,
  };
}

function currentStepText(detail: EvalCaseRunDetail | null | undefined): string {
  const current = currentStep(detail);
  if (!current) return "";
  const parts = [
    typeof current.index === "number" ? `第 ${current.index} 步` : "",
    current.id ? `ID ${current.id}` : "",
    current.stage ? `阶段 ${current.stage}` : "",
  ].filter(Boolean);
  return parts.join(" · ");
}

function skillInstallationText(detail: EvalCaseRunDetail | null | undefined): string {
  const value = detail?.eval_case_run.runner_metadata?.skill_installation;
  if (!value || typeof value !== "object") return "未记录";
  const row = value as Record<string, unknown>;
  const slug = typeof row.skill_slug === "string" ? row.skill_slug : "Skill";
  const version = typeof row.version === "string" ? row.version : "";
  const mode = typeof row.mode === "string" ? row.mode : "";
  return [slug, version, mode].filter(Boolean).join(" · ");
}

function normalizeStepStatus(status: string): StepTimelineRow["status"] {
  if (status === "passed" || status === "failed" || status === "skipped") return status;
  return "pending";
}

function assertionTimelineRows(
  step: EvalCaseStep,
  results: AssertionRunResult[] | undefined,
  fallbackStatus: StepTimelineAssertionRow["status"],
): StepTimelineAssertionRow[] {
  const resultMap = new Map((results ?? []).map((result) => [result.assertion_id, result]));
  return stepAssertions(step).map((assertion) => {
    const result = resultMap.get(assertion.id);
    if (result) {
      const status = normalizeStepStatus(result.status);
      return {
        id: assertion.id,
        assertionTemplateId: assertion.assertion_template_id,
        status,
        label: stepStatusLabel(status),
        reason: result.reason || "",
        actual: result.actual || "",
        details: result.details,
      };
    }
    return {
      id: assertion.id,
      assertionTemplateId: assertion.assertion_template_id,
      status: fallbackStatus,
      label: stepStatusLabel(fallbackStatus),
      reason: "",
      actual: "",
    };
  });
}

function stepAssertions(step: EvalCaseStep): EvalStepAssertion[] {
  if (step.assertions.length) return step.assertions;
  const legacy = step as EvalCaseStep & { assertion_template_id?: string; assertion_params?: Record<string, unknown> };
  return [
    {
      id: "assertion-1",
      assertion_template_id: legacy.assertion_template_id ?? "agent_output_semantic",
      assertion_params: legacy.assertion_params ?? {},
    },
  ];
}

function stepStatusLabel(status: StepTimelineRow["status"]): string {
  if (status === "running") return "运行中";
  if (status === "asserting") return "判定中";
  if (status === "passed") return "通过";
  if (status === "failed") return "不通过";
  if (status === "skipped") return "已跳过";
  return "待执行";
}
