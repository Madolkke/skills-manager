import type { EvalRunRecord, SkillVersion } from "../types";

export function versionName(version?: SkillVersion | null): string {
  return namedVersion(version);
}

function namedVersion(version?: { version_number: number; version?: string | null; display_name?: string | null } | null): string {
  if (!version) return "-";
  return version.display_name?.trim() || version.version?.trim() || `v${version.version_number}`;
}

export function scoreLabel(run?: EvalRunRecord | null): string {
  const summary = run?.summary;
  if (!summary?.total) return "未测";
  return `${Math.round(((summary.passed ?? 0) / summary.total) * 100)}%`;
}

export function scoreKind(run?: EvalRunRecord | null): "verified" | "warning" | "empty" {
  const summary = run?.summary;
  if (!summary?.total) return "empty";
  return (summary.failed ?? 0) > 0 ? "warning" : "verified";
}

export function humanDate(value?: string): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function compactText(value?: string | null, fallback = "-"): string {
  const text = value?.trim();
  return text ? text : fallback;
}
