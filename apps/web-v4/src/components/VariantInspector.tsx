import clsx from "clsx";
import { ArrowLeftRight, ExternalLink, FileText } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { humanDate, scoreKind, scoreLabel, variantName, versionName } from "../lib/format";
import { compactDigest } from "../lib/history";
import { summarizeBundleDiff, type BundleDiffFile, type BundleDiffResult, type BundleDiffStatus } from "../lib/variant-diff";
import type { BundleFile, EvalRunRecord, VariantDetail, VariantVersion } from "../types";
import { VariantVersionTrack } from "./VariantVersionTrack";

type VariantInspectorProps = {
  variant: VariantDetail;
  evalSetName: string;
  latestRun: EvalRunRecord | null;
};

type ActionPanel = "diff" | "detail";

export function VariantInspector({ variant, evalSetName, latestRun }: VariantInspectorProps) {
  const [activePanel, setActivePanel] = useState<ActionPanel | null>(null);
  const files = variant.current_version?.bundle_files ?? [];
  const previousVersion = previousVariantVersion(variant);
  const diff = useMemo(
    () => summarizeBundleDiff(variant.current_version?.bundle_files ?? [], previousVersion?.bundle_files ?? []),
    [previousVersion?.bundle_files, variant.current_version?.bundle_files],
  );

  useEffect(() => setActivePanel(null), [variant.id, variant.current_version_id]);

  return (
    <div className="inspector-card">
      <div className="variant-inspector-head">
        <div>
          <h2>{variantName(variant)}</h2>
          <span className="version-pill">当前 {versionName(variant.current_version)}</span>
        </div>
      </div>
      <p>{variant.summary}</p>
      <div className="tag-row">
        {variant.tags.map((tag) => (
          <span className="tag-chip" key={tag}>
            {tag}
          </span>
        ))}
      </div>

      <div className="inspector-metrics">
        <span>
          <small>最新得分</small>
          <strong className={scoreKind(latestRun)}>{scoreLabel(latestRun)}</strong>
        </span>
        <span>
          <small>绑定测评集</small>
          <strong>{evalSetName}</strong>
        </span>
      </div>

      <section className="inspector-section">
        <h3>版本历史</h3>
        <VariantVersionTrack variant={variant} />
      </section>

      <section className="inspector-section">
        <h3>Bundle 内容</h3>
        {files.length > 0 ? <BundleFileList files={files} /> : <div className="quiet-panel">当前版本没有可预览文件。</div>}
      </section>

      <div className="inspector-actions" role="group" aria-label="变体版本操作">
        <button className="secondary-button" type="button" aria-pressed={activePanel === "diff"} onClick={() => setActivePanel(togglePanel(activePanel, "diff"))}>
          <ArrowLeftRight size={16} />
          Bundle diff
        </button>
        <button className="secondary-button" type="button" aria-pressed={activePanel === "detail"} onClick={() => setActivePanel(togglePanel(activePanel, "detail"))}>
          查看该版本详情
          <ExternalLink size={16} />
        </button>
      </div>

      {activePanel === "diff" ? <VariantBundleDiffPanel diff={diff} current={variant.current_version} previous={previousVersion} /> : null}
      {activePanel === "detail" ? <VariantVersionDetailPanel version={variant.current_version} /> : null}
    </div>
  );
}

function BundleFileList({ files }: { files: BundleFile[] }) {
  return (
    <div className="bundle-file-list">
      {files.slice(0, 7).map((file) => (
        <span key={file.path}>
          <FileText size={15} />
          <b>{file.path}</b>
          <small>{formatSize(file)}</small>
        </span>
      ))}
    </div>
  );
}

function VariantBundleDiffPanel({ diff, current, previous }: { diff: BundleDiffResult; current: VariantVersion | null; previous?: VariantVersion | null }) {
  const changedFiles = diff.files.filter((file) => file.status !== "unchanged");
  return (
    <section className="variant-inspector-detail-panel" aria-label="Bundle diff">
      <header>
        <span>Bundle diff</span>
        <strong>{current && previous ? `${versionName(current)} 对比 ${versionName(previous)}` : "当前版本没有上一个版本"}</strong>
      </header>
      <div className="diff-summary-grid">
        <DiffMetric label="变更文件" value={diff.summary.changed} tone="changed" />
        <DiffMetric label="新增" value={diff.summary.added} tone="added" />
        <DiffMetric label="移除" value={diff.summary.removed} tone="removed" />
        <DiffMetric label="未变更" value={diff.summary.unchanged} tone="unchanged" />
      </div>
      <div className="diff-file-list">
        {(changedFiles.length > 0 ? changedFiles : diff.files.slice(0, 4)).map((file) => (
          <DiffFileRow file={file} key={`${file.status}:${file.path}`} />
        ))}
      </div>
    </section>
  );
}

function VariantVersionDetailPanel({ version }: { version: VariantVersion | null }) {
  return (
    <section className="variant-inspector-detail-panel" aria-label="VariantVersion 详情">
      <header>
        <span>VariantVersion 详情</span>
        <strong>{versionName(version)}</strong>
      </header>
      <dl className="version-detail-list">
        <DetailItem label="创建者" value={version?.created_by ?? "-"} />
        <DetailItem label="创建时间" value={humanDate(version?.created_at)} />
        <DetailItem label="内容 digest" value={compactDigest(version?.content_digest)} mono />
        <DetailItem label="Bundle 文件" value={`${version?.bundle_files?.length ?? 0} 个文件`} />
      </dl>
    </section>
  );
}

function DiffMetric({ label, value, tone }: { label: string; value: number; tone: BundleDiffStatus }) {
  return (
    <span className={clsx("diff-metric", tone)}>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function DiffFileRow({ file }: { file: BundleDiffFile }) {
  return (
    <span className="diff-file-row">
      <b className={file.status}>{statusLabel(file.status)}</b>
      <em>{file.path}</em>
      <small>{formatSize(file.current ?? file.previous)}</small>
    </span>
  );
}

function DetailItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{value}</dd>
    </div>
  );
}

function previousVariantVersion(variant: VariantDetail): VariantVersion | null {
  const current = variant.current_version;
  if (!current) return null;
  return [...variant.versions]
    .filter((version) => version.version_number < current.version_number)
    .sort((left, right) => right.version_number - left.version_number)[0] ?? null;
}

function togglePanel(current: ActionPanel | null, next: ActionPanel): ActionPanel | null {
  return current === next ? null : next;
}

function statusLabel(status: BundleDiffStatus): string {
  if (status === "added") return "新增";
  if (status === "changed") return "变更";
  if (status === "removed") return "移除";
  return "未变更";
}

function formatSize(file?: BundleFile): string {
  const size = file?.size_bytes ?? 0;
  if (!size) return "-";
  if (size < 1024) return `${size} B`;
  return `${Math.round(size / 102.4) / 10} KB`;
}
