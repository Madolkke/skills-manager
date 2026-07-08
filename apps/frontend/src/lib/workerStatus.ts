import type { WorkerStatus, WorkerStatusOverview } from "../types";

export function workerStatusText(worker: WorkerStatus): string {
  if (worker.status === "running") return "运行中";
  if (worker.status === "idle") return "空闲";
  return "离线";
}

export function workerStatusTone(worker: WorkerStatus): string {
  if (worker.status === "running") return "neutral";
  if (worker.status === "idle") return "positive";
  return "negative";
}

export function workerJobTypeText(type?: string | null): string {
  if (type === "eval_case_run") return "测评任务";
  if (type === "skill_builder_message") return "AI 创建任务";
  return type || "-";
}

export function workerCurrentJobText(worker: WorkerStatus): string {
  const job = worker.current_job;
  if (!job) return "无当前任务";
  const refs = [job.run_id && `Run ${job.run_id}`, job.session_id && `Session ${job.session_id}`, job.skill_version_id && `Version ${job.skill_version_id}`].filter(Boolean);
  return refs.length ? refs.join(" · ") : job.id;
}

export function queuedWorkerJobs(overview: WorkerStatusOverview | null): number {
  return (overview?.summary.queued_eval_jobs ?? 0) + (overview?.summary.queued_builder_jobs ?? 0);
}

export function durationText(start?: string | null, end?: string): string {
  if (!start) return "-";
  const startedAt = new Date(start).getTime();
  const endedAt = new Date(end || Date.now()).getTime();
  if (!Number.isFinite(startedAt) || !Number.isFinite(endedAt) || endedAt < startedAt) return "-";
  const totalSeconds = Math.floor((endedAt - startedAt) / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}
