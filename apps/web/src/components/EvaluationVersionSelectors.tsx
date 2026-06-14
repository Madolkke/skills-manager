import { Database, Package } from "lucide-react";
import { versionName } from "../lib/format";
import type { EvalSetSummary, SkillVersion } from "../types";
import type { ManualVersionDetailFocus } from "./ManualVersionDetailPanel";

type EvaluationVersionSelectorsProps = {
  versions: SkillVersion[];
  evalSet?: EvalSetSummary | null;
  skillVersionId: string;
  versionDetailFocus: ManualVersionDetailFocus | null;
  onSkillVersionChange: (versionId: string) => void;
  onVersionDetailFocusChange: (focus: ManualVersionDetailFocus) => void;
};

/**
 * Keeps exact SkillVersion and eval set binding controls together.
 */
export function EvaluationVersionSelectors({
  versions,
  evalSet,
  skillVersionId,
  versionDetailFocus,
  onSkillVersionChange,
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
        <div className="selector-title">
          <Database size={18} />
          测评集
        </div>
        <div className="selector-control-row">
          <div className="selector-static-value">{evalSet?.name ?? "暂无测评集"}</div>
          <button
            className="selector-detail-button"
            type="button"
            aria-label="查看测评集详情"
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
