import clsx from "clsx";
import { CheckCircle2, Clock3, Copy, Link2, Tags, XCircle } from "lucide-react";
import { humanDate, scoreKind, versionName } from "../lib/format";
import { compactDigest, runScoreText } from "../lib/history";
import type { EvalRunDetail, EvalRunHistory } from "../types";

type RunEvidencePanelProps = {
  context: EvalRunHistory["runs"][number];
  run: EvalRunDetail | null;
  onCopy: (label: string, value?: string | null) => void;
};

export function RunEvidencePanel({ context, run, onCopy }: RunEvidencePanelProps) {
  const summary = context.eval_run.summary;
  return (
    <section className="evidence-panel">
      <div className="evidence-hero">
        <div className={clsx("evidence-score", scoreKind(context.eval_run))}>
          <strong>{runScoreText(summary)}</strong>
          <span>{summary.failed ?? 0} 个不通过</span>
        </div>
        <EvidenceCard title="测评 Run" value={context.eval_run.id} meta={`${context.eval_run.strategy} · ${context.eval_run.status}`} onCopy={onCopy} />
        <EvidenceCard
          title="SkillVersion"
          value={versionName(context.skill_version)}
          meta={compactDigest(context.skill_version.content_digest)}
          copyValue={context.skill_version.id}
          onCopy={onCopy}
        />
        <EvidenceCard
          title="测评集"
          value={context.eval_set.name}
          meta={humanDate(context.eval_set.created_at)}
          copyValue={context.eval_set.id}
          onCopy={onCopy}
        />
      </div>
      <div className="evidence-meta-row">
        <span><Clock3 size={15} />{humanDate(context.eval_run.created_at)}</span>
        <span><Link2 size={15} />created by {context.eval_run.created_by}</span>
      </div>
      <RunContextRow tags={context.eval_run.environment_tags} context={context.eval_run.run_context} />
      <div className="case-evidence-list">
        <h2>Case 结果</h2>
        {run ? run.case_results.map((item) => (
          <CaseEvidenceRow item={item} key={item.case_version.id} onCopy={onCopy} />
        )) : <div className="quiet-panel">正在读取 case 证据...</div>}
      </div>
    </section>
  );
}

function CaseEvidenceRow({
  item,
  onCopy,
}: {
  item: EvalRunDetail["case_results"][number];
  onCopy: (label: string, value?: string | null) => void;
}) {
  const actualOutput = item.result_artifact?.content_text ?? "";
  const input = item.case_version.input_artifact.content_text ?? "";
  const expectedOutput = item.case_version.expected_output_artifact.content_text ?? "";
  return (
    <article className={clsx("case-evidence-row", item.result.passed ? "passed" : "failed")}>
      <div className="case-result-head">
        <div className="case-result-title">
          {item.result.passed ? <CheckCircle2 size={19} /> : <XCircle size={19} />}
          <span>#{item.position + 1}</span>
          <strong>{item.case.title}</strong>
        </div>
        <b>{item.result.passed ? "通过" : "不通过"}</b>
      </div>
      <div className="case-evidence-main">
        <span>
          case v{item.case_version.version_number} · input {compactDigest(item.case_version.input_artifact.digest)} · expected {compactDigest(item.case_version.expected_output_artifact.digest)}
        </span>
        <div className="case-result-grid">
          <ResultTextPanel title="Input" value={input} onCopy={onCopy} />
          <ResultTextPanel title="Expected output" value={expectedOutput} onCopy={onCopy} />
          <ResultTextPanel title="Actual output" value={actualOutput || "未填写 actual output。"} muted={!actualOutput} onCopy={onCopy} />
        </div>
      </div>
    </article>
  );
}

function ResultTextPanel({
  title,
  value,
  muted = false,
  onCopy,
}: {
  title: string;
  value: string;
  muted?: boolean;
  onCopy: (label: string, value?: string | null) => void;
}) {
  return (
    <section className={clsx("result-text-panel", muted && "muted")}>
      <header>
        <small>{title}</small>
        <button className="icon-button mini" type="button" aria-label={`复制 ${title}`} onClick={() => onCopy(title, value)}>
          <Copy size={14} />
        </button>
      </header>
      <code>{value || "无内容"}</code>
    </section>
  );
}

function RunContextRow({ tags, context }: { tags: string[]; context: Record<string, unknown> }) {
  const entries = Object.entries(context).filter(([, value]) => value !== null && value !== undefined && String(value).trim().length > 0);
  if (tags.length === 0 && entries.length === 0) return null;
  return (
    <div className="evidence-context-row" aria-label="运行环境">
      <span className="context-row-title"><Tags size={15} />运行环境</span>
      {tags.map((tag) => <span className="tag-chip" key={`tag:${tag}`}>{tag}</span>)}
      {entries.map(([key, value]) => <span className="context-chip" key={key}>{key}: {String(value)}</span>)}
    </div>
  );
}

function EvidenceCard({
  title,
  value,
  meta,
  copyValue,
  onCopy,
}: {
  title: string;
  value: string;
  meta: string;
  copyValue?: string;
  onCopy: (label: string, value?: string | null) => void;
}) {
  return (
    <div className="evidence-card">
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{meta}</small>
      <button className="icon-button mini" type="button" aria-label={`复制 ${title}`} onClick={() => onCopy(title, copyValue ?? value)}>
        <Copy size={15} />
      </button>
    </div>
  );
}
