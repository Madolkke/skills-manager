import type { AppData } from "../domain/types";

export function StatusRail({ data }: { data: AppData }) {
  const hasSkill = data.skills.length > 0;
  const hasVariant = data.variants.length > 0;
  const hasVersion = data.variantVersions.length > 0;
  const hasRun = data.evalRuns.length > 0;
  return (
    <section className="status-rail" aria-label="闭环状态">
      <StatusStep done={hasSkill} label="Skill 入口" />
      <StatusStep done={hasVariant} label="Variant" />
      <StatusStep done={hasVersion} label="Version" />
      <StatusStep done={hasRun} label="EvalRun" />
    </section>
  );
}

function StatusStep({ done, label }: { done: boolean; label: string }) {
  return (
    <div className={`status-step ${done ? "is-done" : ""}`}>
      <span className="status-dot" />
      <span>{label}</span>
    </div>
  );
}
