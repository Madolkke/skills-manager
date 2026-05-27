import { Info } from "lucide-react";
import { TagInput } from "./TagInput";
import type { EvalRunRecord } from "../types";

type EvaluationContextCardProps = {
  environmentTags: string[];
  latestRuns: EvalRunRecord[];
  onEnvironmentTagsChange: (tags: string[]) => void;
};

/**
 * Captures the runtime facts that belong to an EvalRun, not to a SkillVersion.
 */
export function EvaluationContextCard({
  environmentTags,
  latestRuns,
  onEnvironmentTagsChange,
}: EvaluationContextCardProps) {
  return (
    <div className="evaluation-selector-card evaluation-context-card">
      <label className="selector-title">
        <Info size={18} />
        运行环境
      </label>
      <TagInput
        value={environmentTags}
        suggestions={knownEnvironmentTags(latestRuns)}
        onChange={onEnvironmentTagsChange}
        placeholder="例如 windows、gpt-5、ci"
      />
    </div>
  );
}

function knownEnvironmentTags(runs: EvalRunRecord[]): string[] {
  return Array.from(new Set(runs.flatMap((run) => run.environment_tags ?? []))).sort((left, right) => left.localeCompare(right));
}
