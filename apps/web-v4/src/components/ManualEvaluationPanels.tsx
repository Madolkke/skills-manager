import clsx from "clsx";
import { CheckCircle2, Circle, Copy, ListChecks, XCircle } from "lucide-react";
import { manualResultLabel, type ManualEvalSummary } from "../lib/eval";
import { versionName } from "../lib/format";
import type { EvalSetCase, VariantVersion } from "../types";
import type { CSSProperties } from "react";

export function ManualCase({
  item,
  version,
  result,
  positionLabel,
  onCopy,
}: {
  item: EvalSetCase;
  version?: VariantVersion;
  result?: boolean;
  positionLabel: number;
  onCopy: (label: string, text?: string | null) => void;
}) {
  return (
    <>
      <header className="case-detail-head">
        <div>
          <span className="eyebrow">当前 Case</span>
          <h1>{item.case.title}</h1>
          <div className="tag-row">
            <span className="tag-chip">case v{item.case_version.version_number}</span>
            <span className="tag-chip">position {positionLabel}</span>
            <span className="tag-chip">target {versionName(version)}</span>
          </div>
        </div>
        <div className={clsx("case-result-badge", resultClass(result))}>
          <ListChecks size={17} />
          {manualResultLabel(result)}
        </div>
      </header>
      <EvalText title="Input" text={item.case_version.input_artifact.content_text} onCopy={onCopy} />
      <EvalText title="Expected output" text={item.case_version.expected_output_artifact.content_text} onCopy={onCopy} />
      {item.case_version.notes ? (
        <section className="case-notes">
          <strong>Notes</strong>
          <p>{item.case_version.notes}</p>
        </section>
      ) : null}
    </>
  );
}

export function ProgressMetric({ tone, label, value }: { tone: "passed" | "failed" | "pending"; label: string; value: number }) {
  return (
    <span className={clsx("progress-metric", tone)}>
      <i />
      <strong>{value}</strong>
      <small>{label}</small>
    </span>
  );
}

export function ManualProgressPanel({
  summary,
  caseCount,
  evalSetName,
  progressStyle,
}: {
  summary: ManualEvalSummary;
  caseCount: number;
  evalSetName?: string;
  progressStyle: CSSProperties;
}) {
  return (
    <section className="eval-progress-panel">
      <div className="progress-summary-card">
        <div className="progress-ring" style={progressStyle}>
          <span>{summary.coverage}%</span>
        </div>
        <div className="progress-copy">
          <span>本次测评进度</span>
          <h1>
            {summary.confirmed}/{caseCount} 已确认
          </h1>
          <p className="progress-total-label">共 {caseCount} 个 case</p>
          <small>{evalSetName ?? "尚未选择测评集"}</small>
        </div>
      </div>
      <div className="progress-metrics" aria-label="测评结果统计">
        <ProgressMetric tone="passed" label="通过" value={summary.passed} />
        <ProgressMetric tone="failed" label="不通过" value={summary.failed} />
        <ProgressMetric tone="pending" label="待评估" value={summary.pending} />
      </div>
      <div className="progress-track-card">
        <div className="progress-track-head">
          <span>结果分布</span>
          <strong>{summary.coverage}%</strong>
        </div>
        <div className="progress-track">
          <div className="stacked-bar">
            <span style={{ flex: summary.passed || 0 }} className="passed" />
            <span style={{ flex: summary.failed || 0 }} className="failed" />
            <span style={{ flex: summary.pending || 0 }} className="pending" />
          </div>
          <div className="track-labels">
            <span>0</span>
            <span>{caseCount}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

export function StatusIcon({ value }: { value?: boolean }) {
  if (value === true) return <CheckCircle2 className="passed-icon" size={17} />;
  if (value === false) return <XCircle className="failed-icon" size={17} />;
  return <Circle className="pending-icon" size={15} />;
}

function EvalText({ title, text, onCopy }: { title: string; text?: string | null; onCopy: (label: string, text?: string | null) => void }) {
  const content = text ?? "";
  return (
    <section className="case-block dark">
      <header>
        <h2>{title}</h2>
        <button className="inline-copy-button" type="button" disabled={!content.trim()} onClick={() => onCopy(title, content)}>
          <Copy size={14} />
          复制
        </button>
      </header>
      <pre className={content ? undefined : "empty"}>{content || "暂无内容"}</pre>
    </section>
  );
}

function resultClass(value?: boolean): string {
  if (value === true) return "passed";
  if (value === false) return "failed";
  return "pending";
}
