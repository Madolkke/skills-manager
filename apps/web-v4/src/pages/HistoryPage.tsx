import clsx from "clsx";
import { CheckCircle2, Clock3, Copy, FileCheck2, GitCommitHorizontal, Link2, Tags, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { humanDate, scoreKind, versionName } from "../lib/format";
import { compactDigest, resolveSelectedRunId, runScoreText } from "../lib/history";
import type { RouteState } from "../lib/navigation";
import type { EvalRunDetail, EvalRunHistory, SkillDetail, ToastState } from "../types";

type HistoryPageProps = {
  skill: SkillDetail;
  selectedRunId: string | null;
  onNavigate: (next: Partial<RouteState>) => void;
  onToast: (toast: ToastState) => void;
};

export function HistoryPage({ skill, selectedRunId, onNavigate, onToast }: HistoryPageProps) {
  const [history, setHistory] = useState<EvalRunHistory | null>(null);
  const [run, setRun] = useState<EvalRunDetail | null>(null);
  const runs = useMemo(() => history?.runs ?? [], [history]);
  const activeRunId = useMemo(() => resolveSelectedRunId(runs, selectedRunId), [runs, selectedRunId]);
  const activeContext = runs.find((item) => item.eval_run.id === activeRunId) ?? null;

  useEffect(() => {
    let cancelled = false;
    api.getEvalRunHistory(skill.skill.id).then((next) => {
      if (!cancelled) setHistory(next);
    }).catch((caught) => {
      onToast({ tone: "danger", message: errorMessage(caught) });
      if (!cancelled) setHistory({ skill: skill.skill, runs: [] });
    });
    return () => {
      cancelled = true;
    };
  }, [onToast, skill.skill]);

  useEffect(() => {
    if (!activeRunId) {
      setRun(null);
      return;
    }
    let cancelled = false;
    setRun(null);
    api.getEvalRun(activeRunId).then((next) => {
      if (!cancelled) setRun(next);
    }).catch((caught) => {
      onToast({ tone: "danger", message: errorMessage(caught) });
      if (!cancelled) setRun(null);
    });
    return () => {
      cancelled = true;
    };
  }, [activeRunId, onToast]);

  const copyText = useCallback(async (label: string, value?: string | null) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      onToast({ tone: "success", message: `${label} 已复制。` });
    } catch (caught) {
      onToast({ tone: "danger", message: errorMessage(caught) });
    }
  }, [onToast]);

  return (
    <div className="history-layout">
      <section className="history-workspace">
        <header className="section-heading">
          <div>
            <h1>历史与证据链</h1>
            <p>每次测评记录绑定 exact SkillVersion + EvalSetVersion，并保存运行环境、actual output 与人工判定结果。</p>
          </div>
          <button className="secondary-button" type="button" onClick={() => onNavigate({ tab: "evaluate", selectedRunId: null })}>
            进入测评
          </button>
        </header>

        {activeContext ? (
          <RunEvidencePanel context={activeContext} run={run} onCopy={copyText} />
        ) : (
          <div className="history-empty">
            <FileCheck2 size={24} />
            <strong>还没有测评记录</strong>
            <p>先在“测评”页选择 Skill 版本与测评集版本，逐 case 标记后记录结果。</p>
          </div>
        )}

        <VersionHistory skill={skill} onCopy={copyText} />
      </section>

      <aside className="run-history">
        <div className="run-history-head">
          <div>
            <h2>测评记录</h2>
            <p>{runs.length} 次记录</p>
          </div>
        </div>
        {runs.map((item) => (
          <button
            className={clsx("run-row", activeRunId === item.eval_run.id && "active")}
            type="button"
            key={item.eval_run.id}
            onClick={() => onNavigate({ selectedRunId: item.eval_run.id })}
          >
            <span className={clsx("run-score", scoreKind(item.eval_run))}>{runScoreText(item.eval_run.summary)}</span>
            <strong>{versionName(item.skill_version)}</strong>
            <small>{item.eval_set.name} v{item.eval_set_version.version_number} · {humanDate(item.eval_run.created_at)}</small>
          </button>
        ))}
        {runs.length === 0 ? (
          <button className="secondary-button full-width" type="button" onClick={() => onNavigate({ tab: "evaluate" })}>
            去记录第一次测评
          </button>
        ) : null}
      </aside>
    </div>
  );
}

function RunEvidencePanel({
  context,
  run,
  onCopy,
}: {
  context: EvalRunHistory["runs"][number];
  run: EvalRunDetail | null;
  onCopy: (label: string, value?: string | null) => void;
}) {
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
          title="EvalSetVersion"
          value={`${context.eval_set.name} v${context.eval_set_version.version_number}`}
          meta={humanDate(context.eval_set_version.created_at)}
          copyValue={context.eval_set_version.id}
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
        {run ? run.case_results.map((item) => {
          const actualOutput = item.result_artifact?.content_text ?? "";
          const expectedOutput = item.case_version.expected_output_artifact.content_text ?? "";
          return (
            <div className={clsx("case-evidence-row", item.result.passed ? "passed" : "failed")} key={item.case_version.id}>
              {item.result.passed ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
              <div className="case-evidence-main">
                <strong>{item.case.title}</strong>
                <span>
                  case v{item.case_version.version_number} · input {compactDigest(item.case_version.input_artifact.digest)} · expected {compactDigest(item.case_version.expected_output_artifact.digest)}
                </span>
                {actualOutput ? <OutputEvidence expected={expectedOutput} actual={actualOutput} /> : null}
              </div>
              <b>{item.result.passed ? "通过" : "不通过"}</b>
            </div>
          );
        }) : <div className="quiet-panel">正在读取 case 证据...</div>}
      </div>
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

function OutputEvidence({ expected, actual }: { expected: string; actual: string }) {
  return (
    <div className="output-evidence">
      <span>
        <small>Expected</small>
        <code>{expected || "暂无内容"}</code>
      </span>
      <span>
        <small>Actual</small>
        <code>{actual}</code>
      </span>
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

function VersionHistory({ skill, onCopy }: { skill: SkillDetail; onCopy: (label: string, value?: string | null) => void }) {
  return (
    <section className="version-history">
      <header className="history-section-head">
        <h2>Skill 版本链</h2>
        <p>每个 SkillVersion 都是不可变快照；环境差异记录在 EvalRun 上。</p>
      </header>
      <div className="version-group">
        <h3>{skill.skill.slug}</h3>
        <div className="version-stack">
          {skill.versions.map((version) => (
            <div className={clsx("version-row", version.id === skill.skill.current_version_id && "current")} key={version.id}>
              <GitCommitHorizontal size={18} />
              <strong>{versionName(version)}</strong>
              <span>{version.change_summary}</span>
              <small>{compactDigest(version.content_digest)}</small>
              <button className="icon-button mini" type="button" aria-label={`复制 ${versionName(version)} digest`} onClick={() => onCopy("版本 digest", version.content_digest)}>
                <Copy size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "操作失败。";
}
