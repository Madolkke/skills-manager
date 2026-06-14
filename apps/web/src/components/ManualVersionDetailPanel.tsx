import clsx from "clsx";
import { Database, Package, X } from "lucide-react";
import { humanDate, versionName } from "../lib/format";
import { compactDigest } from "../lib/history";
import type { EvalSetDetail, EvalSetSummary, SkillVersion } from "../types";

export type ManualVersionDetailFocus = "skill" | "evalset";

type SkillVersionSelection = SkillVersion;

type ManualVersionDetailPanelProps = {
  focus: ManualVersionDetailFocus;
  skillVersion?: SkillVersionSelection;
  evalSet?: EvalSetSummary | null;
  evalSetDetail: EvalSetDetail | null;
  onClose: () => void;
};

/**
 * Shows the exact version bindings used by the current manual evaluation.
 */
export function ManualVersionDetailPanel({ focus, skillVersion, evalSet, evalSetDetail, onClose }: ManualVersionDetailPanelProps) {
  const version = skillVersion;
  const currentEvalSet = evalSetDetail?.eval_set ?? evalSet;
  const caseCount = evalSetDetail?.cases.length ?? 0;

  return (
    <section className="manual-version-detail-panel" aria-label="测评版本详情">
      <header>
        <div>
          <span>版本详情</span>
          <h2>本次测评绑定</h2>
        </div>
        <button className="icon-button" type="button" aria-label="关闭版本详情" onClick={onClose}>
          <X size={17} />
        </button>
      </header>
      <div className="manual-version-detail-grid">
        <article className={clsx("version-detail-card", focus === "skill" && "active")}>
          <h3>
            <Package size={17} />
            SkillVersion
          </h3>
          <dl>
            <DetailItem label="版本" value={versionName(version)} />
            <DetailItem label="创建者" value={version?.created_by ?? "-"} />
            <DetailItem label="内容 digest" value={compactDigest(version?.content_digest)} mono />
            <DetailItem label="Bundle 文件" value={`${version?.bundle_files?.length ?? 0} 个文件`} />
          </dl>
        </article>
        <article className={clsx("version-detail-card", focus === "evalset" && "active")}>
          <h3>
            <Database size={17} />
            测评集
          </h3>
          <dl>
            <DetailItem label="名称" value={currentEvalSet?.name ?? "-"} />
            <DetailItem label="状态" value={currentEvalSet?.lifecycle_status ?? "-"} />
            <DetailItem label="创建时间" value={humanDate(currentEvalSet?.created_at)} />
            <DetailItem label="Cases" value={`${caseCount} 个 case`} />
          </dl>
        </article>
      </div>
    </section>
  );
}

function DetailItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="version-detail-item">
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{value}</dd>
    </div>
  );
}
