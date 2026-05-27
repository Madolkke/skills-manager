import clsx from "clsx";
import { Copy, FileCheck2, GitCommitHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RunEvidencePanel } from "../components/RunEvidencePanel";
import { api, ApiError } from "../lib/api";
import { evalSetVersionName, humanDate, scoreKind, versionName } from "../lib/format";
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
            <small>{item.eval_set.name} {evalSetVersionName(item.eval_set_version)} · {humanDate(item.eval_run.created_at)}</small>
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
