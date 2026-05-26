import { Info } from "lucide-react";
import { TagInput } from "./TagInput";
import type { EvalRunRecord } from "../types";

export type EvaluationRunContextDraft = {
  os: string;
  runner: string;
  model: string;
};

type EvaluationContextCardProps = {
  environmentTags: string[];
  runContext: EvaluationRunContextDraft;
  latestRuns: EvalRunRecord[];
  onEnvironmentTagsChange: (tags: string[]) => void;
  onRunContextChange: (context: EvaluationRunContextDraft) => void;
};

/**
 * Captures the runtime facts that belong to an EvalRun, not to a SkillVersion.
 */
export function EvaluationContextCard({
  environmentTags,
  runContext,
  latestRuns,
  onEnvironmentTagsChange,
  onRunContextChange,
}: EvaluationContextCardProps) {
  return (
    <div className="evaluation-selector-card evaluation-context-card">
      <label className="selector-title" htmlFor="run-context-os">
        <Info size={18} />
        运行环境
      </label>
      <TagInput
        value={environmentTags}
        suggestions={knownEnvironmentTags(latestRuns)}
        onChange={onEnvironmentTagsChange}
        placeholder="例如 windows、gpt-5、ci"
      />
      <div className="context-field-grid">
        <input
          id="run-context-os"
          value={runContext.os}
          onChange={(event) => onRunContextChange({ ...runContext, os: event.target.value })}
          placeholder="OS"
        />
        <input
          value={runContext.runner}
          onChange={(event) => onRunContextChange({ ...runContext, runner: event.target.value })}
          placeholder="Runner"
        />
        <input
          value={runContext.model}
          onChange={(event) => onRunContextChange({ ...runContext, model: event.target.value })}
          placeholder="Model"
        />
      </div>
    </div>
  );
}

function knownEnvironmentTags(runs: EvalRunRecord[]): string[] {
  return Array.from(new Set(runs.flatMap((run) => run.environment_tags ?? []))).sort((left, right) => left.localeCompare(right));
}
