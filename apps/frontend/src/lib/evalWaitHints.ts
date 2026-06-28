import type { EvalCaseRunDetail } from "../types";

export type RunWaitHint = {
  tone: "info" | "warning";
  title: string;
  message: string;
};

const QUEUED_WARNING_MS = 2 * 60 * 1000;
const DEFAULT_RUNNING_WARNING_MS = 10 * 60 * 1000;

export function runWaitHint(detail: EvalCaseRunDetail | null | undefined, now = Date.now()): RunWaitHint | null {
  if (!detail) return null;
  const status = detail.eval_case_run.status;
  const jobStatus = detail.job?.status ?? "";
  if (status === "queued" || jobStatus === "queued") {
    const created = parseTime(detail.eval_case_run.created_at);
    if (created && now - created >= QUEUED_WARNING_MS) {
      return {
        tone: "warning",
        title: "排队时间较长",
        message: "任务已排队超过 2 分钟。请确认 backend worker 正在运行，并能访问同一数据库队列。",
      };
    }
  }
  if (status === "running" || jobStatus === "running") {
    const started = parseTime(detail.eval_case_run.started_at) ?? parseTime(detail.eval_case_run.created_at);
    const timeoutSeconds = Number(detail.case_version.runner_config?.timeout_seconds);
    const threshold = Number.isFinite(timeoutSeconds) && timeoutSeconds > 0
      ? (timeoutSeconds + 60) * 1000
      : DEFAULT_RUNNING_WARNING_MS;
    if (started && now - started >= threshold) {
      return {
        tone: "warning",
        title: "运行时间超过预期",
        message: "Opencode 或 worker 可能仍在等待外部响应。请检查 Opencode 服务、模型 provider、worker 日志和 Laminar trace。",
      };
    }
  }
  return null;
}

function parseTime(value?: string | null): number | null {
  if (!value) return null;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : null;
}
