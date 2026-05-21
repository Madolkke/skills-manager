import clsx from "clsx";
import { Database, Package, X } from "lucide-react";
import { humanDate, variantName, versionName } from "../lib/format";
import { compactDigest } from "../lib/history";
import type { EvalSetSummary, EvalSetVersion, EvalSetVersionDetail, VariantDetail, VariantVersion } from "../types";

export type ManualVersionDetailFocus = "variant" | "evalset";

type VariantSelection = {
  variant: VariantDetail;
  version: VariantVersion;
};

type EvalSetSelection = {
  set: EvalSetSummary;
  version: EvalSetVersion;
};

type ManualVersionDetailPanelProps = {
  focus: ManualVersionDetailFocus;
  variantVersion?: VariantSelection;
  evalSetVersion?: EvalSetSelection;
  evalSetDetail: EvalSetVersionDetail | null;
  onClose: () => void;
};

/**
 * Shows the exact version bindings used by the current manual evaluation.
 */
export function ManualVersionDetailPanel({ focus, variantVersion, evalSetVersion, evalSetDetail, onClose }: ManualVersionDetailPanelProps) {
  const variant = variantVersion?.variant;
  const version = variantVersion?.version;
  const evalVersion = evalSetVersion?.version;
  const evalSet = evalSetDetail?.eval_set ?? evalSetVersion?.set;
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
        <article className={clsx("version-detail-card", focus === "variant" && "active")}>
          <h3>
            <Package size={17} />
            VariantVersion
          </h3>
          <dl>
            <DetailItem label="变体" value={variantName(variant)} />
            <DetailItem label="版本" value={versionName(version)} />
            <DetailItem label="创建者" value={version?.created_by ?? "-"} />
            <DetailItem label="内容 digest" value={compactDigest(version?.content_digest)} mono />
            <DetailItem label="Bundle 文件" value={`${version?.bundle_files?.length ?? 0} 个文件`} />
          </dl>
        </article>
        <article className={clsx("version-detail-card", focus === "evalset" && "active")}>
          <h3>
            <Database size={17} />
            EvalSetVersion
          </h3>
          <dl>
            <DetailItem label="测评集" value={evalSet?.name ?? "-"} />
            <DetailItem label="版本" value={evalVersion ? `v${evalVersion.version_number}` : "-"} />
            <DetailItem label="创建者" value={evalVersion?.created_by ?? "-"} />
            <DetailItem label="创建时间" value={humanDate(evalVersion?.created_at)} />
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
