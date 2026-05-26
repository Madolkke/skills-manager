import clsx from "clsx";
import { ArrowLeftRight, ExternalLink, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { humanDate, scoreKind, scoreLabel, versionName } from "../lib/format";
import { compactDigest } from "../lib/history";
import type { BundleDiff, BundleDiffFile, BundleDiffStatus, BundleFile, EvalRunRecord, SkillDetail, SkillVersion } from "../types";
import { SkillVersionTrack } from "./SkillVersionTrack";

type VersionInspectorProps = {
  skill: SkillDetail;
  version: SkillVersion;
  evalSetName: string;
  latestRun: EvalRunRecord | null;
};

type ActionPanel = "diff" | "detail";

export function VersionInspector({ skill, version, evalSetName, latestRun }: VersionInspectorProps) {
  const [activePanel, setActivePanel] = useState<ActionPanel | null>(null);
  const [diff, setDiff] = useState<BundleDiff | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const files = version.bundle_files ?? [];
  const previousVersion = previousSkillVersion(skill, version);

  useEffect(() => {
    setActivePanel(null);
    setDiff(null);
    setDiffError(null);
  }, [version.id]);

  useEffect(() => {
    if (activePanel !== "diff" || !previousVersion) return;
    let cancelled = false;
    setDiffLoading(true);
    setDiffError(null);
    api.getBundleDiff(previousVersion.id, version.id).then((next) => {
      if (!cancelled) setDiff(next);
    }).catch((caught) => {
      if (cancelled) return;
      setDiff(null);
      setDiffError(errorMessage(caught));
    }).finally(() => {
      if (!cancelled) setDiffLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [activePanel, previousVersion, version.id]);

  return (
    <div className="inspector-card">
      <div className="version-inspector-head">
        <div>
          <h2>{versionName(version)}</h2>
          <span className="version-pill">{version.id === skill.skill.current_version_id ? "当前版本" : "历史版本"}</span>
        </div>
      </div>
      <p>{version.change_summary}</p>

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
        <SkillVersionTrack skill={skill} />
      </section>

      <section className="inspector-section">
        <h3>Bundle 内容</h3>
        {files.length > 0 ? <BundleFileList files={files} /> : <div className="quiet-panel">当前版本没有可预览文件。</div>}
      </section>

      <div className="inspector-actions" role="group" aria-label="SkillVersion 操作">
        <button className="secondary-button" type="button" aria-pressed={activePanel === "diff"} onClick={() => setActivePanel(togglePanel(activePanel, "diff"))}>
          <ArrowLeftRight size={16} />
          Bundle diff
        </button>
        <button className="secondary-button" type="button" aria-pressed={activePanel === "detail"} onClick={() => setActivePanel(togglePanel(activePanel, "detail"))}>
          查看该版本详情
          <ExternalLink size={16} />
        </button>
      </div>

      {activePanel === "diff" ? <VersionBundleDiffPanel diff={diff} loading={diffLoading} error={diffError} current={version} previous={previousVersion} /> : null}
      {activePanel === "detail" ? <VersionDetailPanel version={version} /> : null}
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

function VersionBundleDiffPanel({
  diff,
  loading,
  error,
  current,
  previous,
}: {
  diff: BundleDiff | null;
  loading: boolean;
  error: string | null;
  current: SkillVersion;
  previous?: SkillVersion | null;
}) {
  const changedFiles = diff?.files.filter((file) => file.status !== "unchanged") ?? [];
  return (
    <section className="version-inspector-detail-panel" aria-label="Bundle diff">
      <header>
        <span>Bundle diff</span>
        <strong>{previous ? `${versionName(current)} 对比 ${versionName(previous)}` : "当前版本没有上一个版本"}</strong>
      </header>
      {loading ? <div className="quiet-panel">正在读取后端 Bundle diff...</div> : null}
      {error ? <div className="quiet-panel">Bundle diff 读取失败：{error}</div> : null}
      {!loading && !error && !previous ? <div className="quiet-panel">当前版本没有上一个版本，无法生成版本间 diff。</div> : null}
      {!loading && !error && diff ? (
        <>
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
        </>
      ) : null}
    </section>
  );
}

function VersionDetailPanel({ version }: { version: SkillVersion }) {
  return (
    <section className="version-inspector-detail-panel" aria-label="SkillVersion 详情">
      <header>
        <span>SkillVersion 详情</span>
        <strong>{versionName(version)}</strong>
      </header>
      <dl className="version-detail-list">
        <DetailItem label="创建者" value={version.created_by} />
        <DetailItem label="创建时间" value={humanDate(version.created_at)} />
        <DetailItem label="内容 digest" value={compactDigest(version.content_digest)} mono />
        <DetailItem label="Bundle 文件" value={`${version.bundle_files?.length ?? 0} 个文件`} />
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
  const hunk = file.hunks?.[0];
  return (
    <div className="diff-file-row">
      <b className={file.status}>{statusLabel(file.status)}</b>
      <em>{file.path}</em>
      <small>{formatDiffSize(file)}</small>
      {hunk ? <pre>{hunk.lines.slice(0, 6).map((line) => `${linePrefix(line.kind)} ${line.text}`).join("\n")}</pre> : null}
    </div>
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

function previousSkillVersion(skill: SkillDetail, current: SkillVersion): SkillVersion | null {
  return [...skill.versions]
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

function formatDiffSize(file: BundleDiffFile): string {
  const size = file.right_size_bytes ?? file.left_size_bytes ?? 0;
  if (!size) return "-";
  if (size < 1024) return `${size} B`;
  return `${Math.round(size / 102.4) / 10} KB`;
}

function linePrefix(kind: string): string {
  if (kind === "added") return "+";
  if (kind === "removed") return "-";
  return " ";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "操作失败。";
}
