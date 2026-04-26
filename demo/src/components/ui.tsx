import type { EvalCaseSource } from "../domain/types";

export function SourceLabel({ source }: { source: EvalCaseSource }) {
  const labels: Record<EvalCaseSource, string> = {
    manual: "人工",
    bad_case: "来源反馈",
    imported: "导入",
    generated: "生成",
  };
  return <span>{labels[source]}</span>;
}

export function TagPill({ tag }: { tag: string }) {
  return <span className="tag-pill">{tag}</span>;
}

export function ResultDot({ score }: { score: number | null }) {
  const cls = score === null ? "missing" : score > 0 ? "pass" : "fail";
  const text = score === null ? "·" : score > 0 ? "✓" : "×";
  return <span className={`result-dot ${cls}`}>{text}</span>;
}

export function StatePill({ tone, children }: { tone: "pass" | "fail" | "warn"; children: React.ReactNode }) {
  return <span className={`state-pill ${tone}`}>{children}</span>;
}
