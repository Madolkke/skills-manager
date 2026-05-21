import type { EvalRunRecord, SkillSummary, VariantDetail, VariantVersion } from "../types";

export function variantName(variant?: VariantDetail | null): string {
  if (!variant) return "未选择";
  return variant.tags.length > 0 ? variant.tags.join(" + ") : variant.name;
}

export function versionName(version?: VariantVersion | null): string {
  return version ? `v${version.version_number}` : "-";
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

export function allKnownTags(skills: SkillSummary[]): string[] {
  const tags = new Set<string>();
  for (const item of skills) for (const tag of item.default_variant?.tags ?? []) tags.add(tag);
  return Array.from(tags).sort((left, right) => left.localeCompare(right));
}

export function sameTags(left: string[], right: string[]): boolean {
  const a = [...left].sort();
  const b = [...right].sort();
  return a.length === b.length && a.every((tag, index) => tag === b[index]);
}

export function slugTitle(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}

export function compactText(value?: string | null, fallback = "-"): string {
  const text = value?.trim();
  return text ? text : fallback;
}
