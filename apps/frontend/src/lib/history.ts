import type { EvalRunHistory, EvalRunRecord } from "../types";

type RunSummary = EvalRunRecord["summary"];

export function runScoreText(summary?: RunSummary): string {
  const total = summary?.total ?? 0;
  if (total <= 0) return "未测";
  return `${summary?.passed ?? 0}/${total} 通过`;
}

export function compactDigest(value?: string | null): string {
  if (!value) return "-";
  const [prefix, digest] = value.includes(":") ? value.split(":", 2) : ["", value];
  const short = digest.slice(0, 12);
  return prefix ? `${prefix}:${short}` : short;
}

export function resolveSelectedRunId(runs: EvalRunHistory["runs"], selectedRunId: string | null): string | null {
  if (runs.some((item) => item.eval_run.id === selectedRunId)) return selectedRunId;
  return runs[0]?.eval_run.id ?? null;
}
