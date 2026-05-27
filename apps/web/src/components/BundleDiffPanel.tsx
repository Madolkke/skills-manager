import clsx from "clsx";
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { versionName } from "../lib/format";
import type { BundleDiff, BundleDiffFile, BundleDiffLine, BundleDiffStatus, SkillVersion } from "../types";

type BundleDiffPanelProps = {
  current: SkillVersion;
  previous?: SkillVersion | null;
};

export function BundleDiffPanel({ current, previous }: BundleDiffPanelProps) {
  const [diff, setDiff] = useState<BundleDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDiff(null);
    setError(null);
    if (!previous) return;
    let cancelled = false;
    setLoading(true);
    api.getBundleDiff(previous.id, current.id).then((next) => {
      if (!cancelled) setDiff(next);
    }).catch((caught) => {
      if (!cancelled) setError(errorMessage(caught));
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [current.id, previous]);

  const changedFiles = diff?.files.filter((file) => file.status !== "unchanged") ?? [];

  return (
    <section className="commit-diff-panel" aria-label="Bundle diff">
      <header className="commit-diff-head">
        <div>
          <span>Bundle diff</span>
          <h2>{previous ? `${versionName(current)} 对比 ${versionName(previous)}` : "初始版本"}</h2>
        </div>
        {diff ? (
          <div className="commit-diff-stats" aria-label="变更摘要">
            <DiffStat label="变更" value={diff.summary.changed} tone="changed" />
            <DiffStat label="新增" value={diff.summary.added} tone="added" />
            <DiffStat label="移除" value={diff.summary.removed} tone="removed" />
          </div>
        ) : null}
      </header>

      {loading ? <div className="quiet-panel">正在读取后端 Bundle diff...</div> : null}
      {error ? <div className="quiet-panel">Bundle diff 读取失败：{error}</div> : null}
      {!loading && !error && !previous ? <div className="quiet-panel">这是第一个 SkillVersion，没有可比较的上一个版本。</div> : null}
      {!loading && !error && diff ? (
        <div className="commit-file-list">
          {(changedFiles.length > 0 ? changedFiles : diff.files).map((file) => (
            <DiffFile file={file} key={`${file.status}:${file.path}`} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function DiffStat({ label, value, tone }: { label: string; value: number; tone: BundleDiffStatus }) {
  return (
    <span className={clsx("commit-diff-stat", tone)}>
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

function DiffFile({ file }: { file: BundleDiffFile }) {
  return (
    <article className="commit-file">
      <header>
        <span className={clsx("file-status", file.status)}>{statusLabel(file.status)}</span>
        <strong>{file.path}</strong>
        <small>{formatDiffSize(file)}</small>
      </header>
      {file.binary ? <div className="quiet-panel">二进制文件变更，无法展示文本 diff。</div> : null}
      {file.hunks?.length ? (
        <div className="commit-hunks">
          {file.hunks.map((hunk, index) => (
            <pre key={index}>
              {hunk.lines.map((line, lineIndex) => (
                <DiffLine line={line} key={`${line.old_line}:${line.new_line}:${lineIndex}`} />
              ))}
            </pre>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function DiffLine({ line }: { line: BundleDiffLine }) {
  return (
    <span className={line.kind}>
      <b>{linePrefix(line.kind)}</b>
      <code>{line.text || " "}</code>
    </span>
  );
}

function statusLabel(status: BundleDiffStatus): string {
  if (status === "added") return "新增";
  if (status === "changed") return "变更";
  if (status === "removed") return "移除";
  return "未变更";
}

function linePrefix(kind: BundleDiffLine["kind"]): string {
  if (kind === "added") return "+";
  if (kind === "removed") return "-";
  return " ";
}

function formatDiffSize(file: BundleDiffFile): string {
  const size = file.right_size_bytes ?? file.left_size_bytes ?? 0;
  if (!size) return "-";
  if (size < 1024) return `${size} B`;
  return `${Math.round(size / 102.4) / 10} KB`;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "操作失败。";
}
