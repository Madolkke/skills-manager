import clsx from "clsx";
import { ArrowRight, CheckCircle2, Circle, Copy, ListChecks, Save, XCircle } from "lucide-react";
import { manualResultLabel, type ManualCaseResult, type ManualEvalSummary } from "../lib/eval";
import { versionName } from "../lib/format";
import type { EvalSetCase, VariantVersion } from "../types";
import type { CSSProperties } from "react";

export function ManualCase({
  item,
  version,
  result,
  positionLabel,
  onActualOutputChange,
  onCopy,
}: {
  item: EvalSetCase;
  version?: VariantVersion;
  result?: ManualCaseResult;
  positionLabel: number;
  onActualOutputChange: (caseVersionId: string, actualOutput: string) => void;
  onCopy: (label: string, text?: string | null) => void;
}) {
  const expectedOutput = item.case_version.expected_output_artifact.content_text;
  const actualOutput = result?.actualOutput ?? "";
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
        <div className={clsx("case-result-badge", resultClass(result?.passed))}>
          <ListChecks size={17} />
          {manualResultLabel(result?.passed)}
        </div>
      </header>
      <EvalText title="Input" text={item.case_version.input_artifact.content_text} onCopy={onCopy} />
      <ActualOutputCompare
        expectedOutput={expectedOutput}
        actualOutput={actualOutput}
        onActualOutputChange={(value) => onActualOutputChange(item.case_version.id, value)}
        onCopy={onCopy}
      />
      {item.case_version.notes ? (
        <section className="case-notes">
          <strong>Notes</strong>
          <p>{item.case_version.notes}</p>
        </section>
      ) : null}
    </>
  );
}

export function ManualEvalActionBar({
  activePassed,
  busy,
  canMark,
  canMoveNext,
  canRecord,
  recordHint,
  onPass,
  onFail,
  onNext,
  onRecord,
}: {
  activePassed?: boolean;
  busy: boolean;
  canMark: boolean;
  canMoveNext: boolean;
  canRecord: boolean;
  recordHint: string;
  onPass: () => void;
  onFail: () => void;
  onNext: () => void;
  onRecord: () => void;
}) {
  return (
    <div className="eval-action-bar">
      <div className="action-buttons">
        <button className={clsx("pass-button", activePassed === true && "selected")} type="button" disabled={!canMark || busy} onClick={onPass}>
          <CheckCircle2 size={20} />
          通过
          <kbd className="shortcut-badge">P</kbd>
        </button>
        <button className={clsx("fail-button", activePassed === false && "selected")} type="button" disabled={!canMark || busy} onClick={onFail}>
          <XCircle size={20} />
          不通过
          <kbd className="shortcut-badge">F</kbd>
        </button>
        <button className="secondary-button" type="button" onClick={onNext} disabled={!canMoveNext}>
          下一条
          <ArrowRight size={18} />
          <kbd className="shortcut-badge">N</kbd>
        </button>
        <button className="primary-button" type="button" disabled={!canRecord} onClick={onRecord}>
          <Save size={18} />
          {busy ? "记录中" : "记录本次测评"}
          <kbd className="shortcut-badge">S</kbd>
        </button>
      </div>
      <p>{recordHint}</p>
    </div>
  );
}

function ActualOutputCompare({
  expectedOutput,
  actualOutput,
  onActualOutputChange,
  onCopy,
}: {
  expectedOutput?: string | null;
  actualOutput: string;
  onActualOutputChange: (value: string) => void;
  onCopy: (label: string, text?: string | null) => void;
}) {
  const expected = expectedOutput ?? "";
  return (
    <section className="actual-output-compare" aria-label="Actual output 与 expected output 对比">
      <div className="compare-pane expected">
        <header>
          <h2>Expected output</h2>
          <button className="inline-copy-button" type="button" disabled={!expected.trim()} onClick={() => onCopy("Expected output", expected)}>
            <Copy size={14} />
            复制
          </button>
        </header>
        <pre className={expected ? undefined : "empty"}>{expected || "暂无内容"}</pre>
      </div>
      <label className="compare-pane actual">
        <span>本次运行结果</span>
        <textarea
          value={actualOutput}
          onChange={(event) => onActualOutputChange(event.target.value)}
          placeholder="粘贴本次运行的实际输出、模型回答或 evaluator 返回内容"
        />
      </label>
    </section>
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
