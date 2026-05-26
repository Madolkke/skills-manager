import { Database, Package } from "lucide-react";
import { versionName } from "../lib/format";
import type { EvalSetSummary, EvalSetVersion, SkillVersion } from "../types";
import type { ManualVersionDetailFocus } from "./ManualVersionDetailPanel";

export type EvalSetVersionOption = {
  set: EvalSetSummary;
  version: EvalSetVersion;
};

type EvaluationVersionSelectorsProps = {
  versions: SkillVersion[];
  evalSetVersions: EvalSetVersionOption[];
  skillVersionId: string;
  evalSetVersionId: string;
  versionDetailFocus: ManualVersionDetailFocus | null;
  onSkillVersionChange: (versionId: string) => void;
  onEvalSetVersionChange: (versionId: string) => void;
  onVersionDetailFocusChange: (focus: ManualVersionDetailFocus) => void;
};

/**
 * Keeps exact SkillVersion and EvalSetVersion binding controls together.
 */
export function EvaluationVersionSelectors({
  versions,
  evalSetVersions,
  skillVersionId,
  evalSetVersionId,
  versionDetailFocus,
  onSkillVersionChange,
  onEvalSetVersionChange,
  onVersionDetailFocusChange,
}: EvaluationVersionSelectorsProps) {
  return (
    <>
      <div className="evaluation-selector-card">
        <label className="selector-title" htmlFor="skill-version-select">
          <Package size={18} />
          Skill 版本
        </label>
        <div className="selector-control-row">
          <select id="skill-version-select" value={skillVersionId} onChange={(event) => onSkillVersionChange(event.target.value)} disabled={versions.length === 0}>
            {versions.length === 0 ? <option value="">暂无可选版本</option> : null}
            {versions.map((version) => (
              <option value={version.id} key={version.id}>
                {versionName(version)}
              </option>
            ))}
          </select>
          <button
            className="selector-detail-button"
            type="button"
            aria-label="查看 Skill 版本详情"
            aria-pressed={versionDetailFocus === "skill"}
            onClick={() => onVersionDetailFocusChange("skill")}
          >
            查看详情
          </button>
        </div>
      </div>
      <div className="evaluation-selector-card">
        <label className="selector-title" htmlFor="eval-set-version-select">
          <Database size={18} />
          测评集版本
        </label>
        <div className="selector-control-row">
          <select
            id="eval-set-version-select"
            value={evalSetVersionId}
            onChange={(event) => onEvalSetVersionChange(event.target.value)}
            disabled={evalSetVersions.length === 0}
          >
            {evalSetVersions.length === 0 ? <option value="">暂无测评集版本</option> : null}
            {evalSetVersions.map(({ set, version }) => (
              <option value={version.id} key={version.id}>
                {set.name} v{version.version_number}
              </option>
            ))}
          </select>
          <button
            className="selector-detail-button"
            type="button"
            aria-label="查看测评集版本详情"
            aria-pressed={versionDetailFocus === "evalset"}
            onClick={() => onVersionDetailFocusChange("evalset")}
          >
            查看详情
          </button>
        </div>
      </div>
    </>
  );
}
