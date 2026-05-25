import clsx from "clsx";
import { Database, Info, Package } from "lucide-react";
import { type CSSProperties, useCallback, useEffect, useMemo, useState } from "react";
import { ManualCase, ManualEvalActionBar, ManualProgressPanel } from "../components/ManualEvaluationPanels";
import { ManualVersionDetailPanel, type ManualVersionDetailFocus } from "../components/ManualVersionDetailPanel";
import { api, ApiError } from "../lib/api";
import { manualRecordHint, manualResultLabel, nextPendingCaseVersionId, summarizeManualEval, type ManualCaseResult } from "../lib/eval";
import { variantName, versionName } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalSetVersionDetail, SkillDetail, ToastState } from "../types";

type EvaluatePageProps = { skill: SkillDetail; onRefresh: () => Promise<void>; onNavigate: (next: Partial<RouteState>) => void; onToast: (toast: ToastState) => void };

export function EvaluatePage({ skill, onRefresh, onNavigate, onToast }: EvaluatePageProps) {
  const versions = useMemo(() => skill.variants.flatMap((variant) => variant.versions.map((version) => ({ variant, version }))), [skill.variants]);
  const evalSetVersions = useMemo(
    () => skill.eval_sets.flatMap((set) => set.versions.map((version) => ({ set, version }))),
    [skill.eval_sets],
  );
  const defaultVersionId = skill.summary.default_variant?.current_version_id ?? versions[0]?.version.id ?? "";
  const defaultEvalSetVersionId = skill.summary.primary_eval_set?.current_version_id ?? "";
  const [variantVersionId, setVariantVersionId] = useState(defaultVersionId);
  const [evalSetVersionId, setEvalSetVersionId] = useState(defaultEvalSetVersionId);
  const [detail, setDetail] = useState<EvalSetVersionDetail | null>(null);
  const [results, setResults] = useState<Record<string, ManualCaseResult>>({});
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [versionDetailFocus, setVersionDetailFocus] = useState<ManualVersionDetailFocus | null>(null);
  const [busy, setBusy] = useState(false);
  const cases = useMemo(() => detail?.cases ?? [], [detail]);
  const summary = summarizeManualEval(cases.length, results);
  const active = cases.find((item) => item.case_version.id === activeCaseId) ?? cases[0] ?? null;
  const activePosition = active ? cases.findIndex((item) => item.case_version.id === active.case_version.id) + 1 : 0;
  const selectedVersion = versions.find((item) => item.version.id === variantVersionId);
  const selectedEvalSetVersion = evalSetVersions.find((item) => item.version.id === evalSetVersionId);
  const activeResult = active ? results[active.case_version.id] : undefined;
  const activePassed = activeResult?.passed;
  const canRecord = !busy && Boolean(variantVersionId && evalSetVersionId) && summary.pending === 0 && cases.length > 0;
  const canMoveNext = !busy && summary.pending > 0 && cases.length > 0;
  const progressStyle = { "--coverage": `${summary.coverage}%` } as CSSProperties;
  const recordHint = manualRecordHint(cases.length, summary.pending);

  useEffect(() => {
    if (!evalSetVersionId) {
      setDetail(null);
      setActiveCaseId(null);
      setResults({});
      return;
    }
    let cancelled = false;
    api.getEvalSetVersion(evalSetVersionId).then((next) => {
      if (cancelled) return;
      setDetail(next);
      setActiveCaseId(next.cases[0]?.case_version.id ?? null);
      setResults({});
    }).catch((error) => onToast({ tone: "danger", message: errorMessage(error) }));
    return () => {
      cancelled = true;
    };
  }, [evalSetVersionId, onToast]);

  const mark = useCallback((caseVersionId: string, passed: boolean) => {
    setResults((current) => ({
      ...current,
      [caseVersionId]: {
        actualOutput: current[caseVersionId]?.actualOutput ?? "",
        passed,
      },
    }));
  }, []);

  const updateActualOutput = useCallback((caseVersionId: string, actualOutput: string) => {
    setResults((current) => ({
      ...current,
      [caseVersionId]: {
        actualOutput,
        passed: current[caseVersionId]?.passed,
      },
    }));
  }, []);

  const goNext = useCallback(() => {
    const nextId = nextPendingCaseVersionId(cases, results, activeCaseId);
    if (nextId) setActiveCaseId(nextId);
  }, [activeCaseId, cases, results]);

  const copyText = useCallback(async (label: string, text?: string | null) => {
    const content = text ?? "";
    if (!content.trim()) return;
    try {
      await navigator.clipboard.writeText(content);
      onToast({ tone: "success", message: `${label} 已复制。` });
    } catch (caught) {
      onToast({ tone: "danger", message: errorMessage(caught) });
    }
  }, [onToast]);

  const recordRun = useCallback(async () => {
    if (!variantVersionId || !evalSetVersionId || summary.pending > 0 || cases.length === 0) return;
    setBusy(true);
    try {
      const recorded = await api.recordEvalRun({
        variant_version_id: variantVersionId,
        eval_set_version_id: evalSetVersionId,
        strategy: "manual_pass_fail",
        results: Object.fromEntries(
          Object.entries(results).map(([caseVersionId, result]) => [
            caseVersionId,
            { passed: result.passed === true, actual_output: result.actualOutput },
          ]),
        ),
      });
      onToast({ tone: "success", message: "测评结果已记录。" });
      await onRefresh();
      onNavigate({ tab: "history", selectedRunId: recorded.eval_run_id });
    } catch (caught) {
      onToast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      setBusy(false);
    }
  }, [cases.length, evalSetVersionId, onNavigate, onRefresh, onToast, results, summary.pending, variantVersionId]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
      const key = event.key.toLowerCase();
      if (/^[1-9]$/.test(key)) {
        const target = cases[Number(key) - 1];
        if (target) {
          event.preventDefault();
          setActiveCaseId(target.case_version.id);
        }
      }
      if (key === "p" && active) {
        event.preventDefault();
        mark(active.case_version.id, true);
      }
      if (key === "f" && active) {
        event.preventDefault();
        mark(active.case_version.id, false);
      }
      if (key === "n" && summary.pending > 0) {
        event.preventDefault();
        goNext();
      }
      if (key === "s" && canRecord) {
        event.preventDefault();
        void recordRun();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [active, canRecord, cases, goNext, mark, recordRun, summary.pending]);

  return (
    <div className="evaluate-page">
      <section className="evaluation-selectors">
        <div className="evaluation-selector-card">
          <label className="selector-title" htmlFor="variant-version-select">
            <Package size={18} />
            变体版本
          </label>
          <div className="selector-control-row">
            <select id="variant-version-select" value={variantVersionId} onChange={(event) => setVariantVersionId(event.target.value)} disabled={versions.length === 0}>
              {versions.length === 0 ? <option value="">暂无可选版本</option> : null}
              {versions.map(({ variant, version }) => (
                <option value={version.id} key={version.id}>
                  {variantName(variant)} {versionName(version)}
                </option>
              ))}
            </select>
            <button className="selector-detail-button" type="button" aria-label="查看变体版本详情" aria-pressed={versionDetailFocus === "variant"} onClick={() => setVersionDetailFocus("variant")}>
              查看详情
            </button>
          </div>
        </div>
        <div className="evaluation-selector-card">
          <label className="selector-title" htmlFor="eval-set-version-select">
            <Database size={18} />
            测评集版本
          </label>
          <div className="selector-control-row">
            <select id="eval-set-version-select" value={evalSetVersionId} onChange={(event) => setEvalSetVersionId(event.target.value)} disabled={evalSetVersions.length === 0}>
              {evalSetVersions.length === 0 ? <option value="">暂无测评集版本</option> : null}
              {evalSetVersions.map(({ set, version }) => (
                <option value={version.id} key={version.id}>
                  {set.name} v{version.version_number}
                </option>
              ))}
            </select>
            <button className="selector-detail-button" type="button" aria-label="查看测评集版本详情" aria-pressed={versionDetailFocus === "evalset"} onClick={() => setVersionDetailFocus("evalset")}>
              查看详情
            </button>
          </div>
        </div>
        <div className="info-box">
          <Info size={18} />
          <div>
            <strong>在此页面执行人工测评</strong>
            <p>选择确切的变体版本与测评集版本，逐条标记通过/不通过后记录本次结果。</p>
          </div>
        </div>
        {versionDetailFocus ? (
          <ManualVersionDetailPanel
            focus={versionDetailFocus}
            variantVersion={selectedVersion}
            evalSetVersion={selectedEvalSetVersion}
            evalSetDetail={detail}
            onClose={() => setVersionDetailFocus(null)}
          />
        ) : null}
      </section>

      <ManualProgressPanel summary={summary} caseCount={cases.length} evalSetName={detail?.eval_set.name} progressStyle={progressStyle} />

      <div className="manual-eval-grid">
        <aside className="manual-case-list">
          <header className="manual-list-head">
            <div>
              <h2>Case 列表</h2>
              <p>{summary.pending} 个待评估</p>
            </div>
            <span>{cases.length}</span>
          </header>
          {cases.map((item, index) => {
            const result = results[item.case_version.id];
            const position = item.position + 1;
            const label = manualResultLabel(result?.passed);
            return (
              <button
                aria-current={active?.case_version.id === item.case_version.id ? "true" : undefined}
                aria-label={`${item.case.title}，#${position}，case v${item.case_version.version_number}，${label}`}
                className={clsx("manual-case-row", active?.case_version.id === item.case_version.id && "active")}
                type="button"
                key={item.case_version.id}
                onClick={() => setActiveCaseId(item.case_version.id)}
              >
                <span className={clsx("manual-status-dot", manualStatusClass(result?.passed))} aria-hidden="true" />
                <span className="manual-case-index">#{position}</span>
                <span className="manual-case-copy">
                  <strong>{item.case.title}</strong>
                  <small>
                    <span>case v{item.case_version.version_number}</span>
                    <span>{label}</span>
                  </small>
                </span>
                {index < 9 ? <kbd className="manual-shortcut-chip">{index + 1}</kbd> : null}
              </button>
            );
          })}
        </aside>
        <section className="manual-case-detail">
          {active ? (
            <ManualCase
              item={active}
              version={selectedVersion?.version}
              result={activeResult}
              positionLabel={activePosition}
              onActualOutputChange={updateActualOutput}
              onCopy={copyText}
            />
          ) : (
            <div className="quiet-panel">没有可测评的 case。</div>
          )}
        </section>
      </div>

      <ManualEvalActionBar
        activePassed={activePassed}
        busy={busy}
        canMark={Boolean(active)}
        canMoveNext={canMoveNext}
        canRecord={canRecord}
        recordHint={recordHint}
        onPass={() => active && mark(active.case_version.id, true)}
        onFail={() => active && mark(active.case_version.id, false)}
        onNext={goNext}
        onRecord={recordRun}
      />
    </div>
  );
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable;
}

function manualStatusClass(value?: boolean): string {
  if (value === true) return "passed";
  if (value === false) return "failed";
  return "pending";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "操作失败。";
}
