import clsx from "clsx";
import { Copy, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CaseVersionRoadmap } from "../components/CaseVersionRoadmap";
import { EvalCaseModal, type EvalCaseFormData } from "../components/EvalCaseModal";
import { EvalSetVersionNameEditor } from "../components/EvalSetVersionNameEditor";
import { api, ApiError } from "../lib/api";
import { compactText, evalSetVersionName, humanDate } from "../lib/format";
import type { RouteState } from "../lib/navigation";
import type { EvalCaseHistory, EvalSetCase, EvalSetVersionDetail, SkillDetail, ToastState } from "../types";

type EvalSetsPageProps = {
  skill: SkillDetail;
  selectedCaseId: string | null;
  onNavigate: (next: Partial<RouteState>) => void;
  onRefresh: () => Promise<void>;
  onToast: (toast: ToastState) => void;
};

type CaseSortKey = "position" | "title" | "version";

export function EvalSetsPage({ skill, selectedCaseId, onNavigate, onRefresh, onToast }: EvalSetsPageProps) {
  const evalSet = skill.summary.primary_eval_set;
  const [versionId, setVersionId] = useState(evalSet?.current_version_id ?? "");
  const [detail, setDetail] = useState<EvalSetVersionDetail | null>(null);
  const [query, setQuery] = useState("");
  const [caseFilter, setCaseFilter] = useState<"all" | "active">("all");
  const [caseSort, setCaseSort] = useState<CaseSortKey>("position");
  const [editor, setEditor] = useState<EvalSetCase | "new" | null>(null);
  const [history, setHistory] = useState<EvalCaseHistory | null>(null);
  const [detailRevision, setDetailRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const selectedVersion = evalSet?.versions.find((version) => version.id === versionId) ?? evalSet?.current_version ?? null;
  const viewingCurrent = Boolean(versionId && versionId === evalSet?.current_version_id);

  useEffect(() => {
    const currentVersionId = evalSet?.current_version_id ?? "";
    if (!currentVersionId) return;
    if (!versionId || !evalSet?.versions.some((version) => version.id === versionId)) {
      setVersionId(currentVersionId);
    }
  }, [evalSet, versionId]);

  useEffect(() => {
    if (!versionId) {
      setDetail(null);
      return;
    }
    api.getEvalSetVersion(versionId).then(setDetail).catch((error) => onToast({ tone: "danger", message: errorMessage(error) }));
  }, [detailRevision, onToast, versionId]);

  const cases = useMemo(() => sortCases(filterCases(detail?.cases ?? [], query, caseFilter), caseSort), [caseFilter, caseSort, detail, query]);
  const selected = cases.find((item) => item.case.id === selectedCaseId) ?? cases[0] ?? null;

  useEffect(() => {
    if (!selected || selected.case.id === selectedCaseId) return;
    onNavigate({ selectedCaseId: selected.case.id });
  }, [onNavigate, selected, selectedCaseId]);

  useEffect(() => {
    if (!selected) {
      setHistory(null);
      return;
    }
    api.getEvalCaseHistory(selected.case.id).then(setHistory).catch(() => setHistory(null));
  }, [selected]);

  async function saveCase(form: EvalCaseFormData) {
    setBusy(true);
    try {
      const payload = { ...form, eval_set_version_display_name: cleanName(form.eval_set_version_display_name) };
      const saved = editor === "new"
        ? await api.createEvalCase({ skill_id: skill.skill.id, ...payload })
        : editor
          ? await api.updateEvalCase(editor.case.id, { ...payload, make_current: true })
          : null;
      if (saved) {
        setVersionId(saved.eval_set_version_id);
        onNavigate({ selectedCaseId: saved.eval_case_id });
        setDetailRevision((value) => value + 1);
      }
      setEditor(null);
      onToast({ tone: "success", message: "Case 已保存。" });
      await onRefresh();
    } catch (caught) {
      onToast({ tone: "danger", message: errorMessage(caught) });
    } finally {
      setBusy(false);
    }
  }

  async function renameEvalSetVersion(displayName: string | null) {
    if (!selectedVersion) return;
    try {
      await api.updateEvalSetVersionName(selectedVersion.id, displayName);
      onToast({ tone: "success", message: "测评集版本名称已更新。" });
      await onRefresh();
    } catch (caught) {
      onToast({ tone: "danger", message: errorMessage(caught) });
    }
  }

  return (
    <div className="evalset-layout">
      <aside className="case-sidebar">
        <span className="back-link">当前测评集</span>
        <div className="evalset-card">
          <div className="evalset-title-row">
            <span className="green-dot" />
            <span>{viewingCurrent ? "当前 EvalSetVersion" : "历史 EvalSetVersion"}</span>
          </div>
          <EvalSetVersionNameEditor version={selectedVersion} evalSetName={evalSet?.name ?? "Regression Set"} onSave={renameEvalSetVersion} />
          <div className="mini-grid">
            <span>Cases<b>{detail?.cases.length ?? 0}</b></span>
            <span>状态<b>{viewingCurrent ? "当前" : "历史"}</b></span>
            <span>更新时间<b>{humanDate(selectedVersion?.created_at)}</b></span>
          </div>
        </div>
        <div className="evalset-version-list" aria-label="测评集历史版本">
          <strong>版本历史</strong>
          {evalSet?.versions.map((version) => (
            <button
              className={clsx("evalset-version-row", version.id === versionId && "active")}
              type="button"
              key={version.id}
              onClick={() => {
                setVersionId(version.id);
                onNavigate({ selectedCaseId: null });
              }}
            >
              <span>{evalSetVersionName(version)}</span>
              <small>{version.id === evalSet.current_version_id ? "当前" : humanDate(version.created_at)}</small>
            </button>
          ))}
        </div>
        <label className="search-field compact">
          <Search size={18} />
          <input value={query} placeholder="搜索 case" onChange={(event) => setQuery(event.target.value)} />
        </label>
        <div className="case-toolbar">
          <button className={clsx("select-button", caseFilter === "all" && "active")} type="button" onClick={() => setCaseFilter("all")}>
            全部
          </button>
          <button className={clsx("select-button", caseFilter === "active" && "active")} type="button" onClick={() => setCaseFilter("active")}>
            仅活跃
          </button>
          <label className="case-sort-control">
            <select aria-label="Case 排序" value={caseSort} onChange={(event) => setCaseSort(event.target.value as CaseSortKey)}>
              <option value="position">按列表顺序</option>
              <option value="title">按标题排序</option>
              <option value="version">按版本排序</option>
            </select>
          </label>
          {viewingCurrent ? (
          <button className="primary-button" type="button" onClick={() => setEditor("new")}>
            <Plus size={17} />
            添加
          </button>
          ) : (
            <button className="secondary-button" type="button" onClick={() => setVersionId(evalSet?.current_version_id ?? "")}>
              当前版本
            </button>
          )}
        </div>
        <div className="case-list">
          {cases.map((item) => {
            const isCurrentCaseVersion = item.case.current_version_id === item.case_version.id;
            const lifecycleLabel = caseLifecycleLabel(item.case.lifecycle_status);
            return (
              <button
                aria-label={`${item.case.title}，#${item.position + 1}，case v${item.case_version.version_number}，${isCurrentCaseVersion ? "当前版本" : "历史版本"}，${lifecycleLabel}`}
                className={clsx("case-row", selected?.case.id === item.case.id && "active")}
                type="button"
                key={item.case.id}
                onClick={() => onNavigate({ selectedCaseId: item.case.id })}
              >
                <span className="case-position-mark">#{item.position + 1}</span>
                <span className="case-row-copy">
                  <span className="case-row-topline">
                    <strong className="case-row-title">{item.case.title}</strong>
                  </span>
                  <span className="case-row-metadata">
                    <span className="case-version-pill">case v{item.case_version.version_number}</span>
                    <span className={clsx("case-current-chip", !isCurrentCaseVersion && "muted")}>
                      {isCurrentCaseVersion ? "当前" : "历史"}
                    </span>
                    <span className={clsx("case-status-chip", item.case.lifecycle_status !== "active" && "muted")}>
                      <span className="case-status-dot" />
                      {lifecycleLabel}
                    </span>
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <p className="case-count">共 {detail?.cases.length ?? 0} 个 case</p>
      </aside>

      <section className="case-detail">
        {selected ? (
          <>
            <header className="case-detail-head">
              <div>
                <h1>{selected.case.title}</h1>
                <div className="tag-row">
                  <span className="tag-chip">case v{selected.case_version.version_number}</span>
                  <span className="tag-chip">position {selected.position + 1}</span>
                </div>
              </div>
              <div className="button-row">
                <button className="primary-button" type="button" disabled={!viewingCurrent} onClick={() => setEditor(selected)}>
                  编辑 case
                </button>
              </div>
            </header>
            <CaseBlock title="Input" text={selected.case_version.input_artifact.content_text} />
            <CaseBlock title="Expected output" text={selected.case_version.expected_output_artifact.content_text} />
            <CaseBlock title="Notes" text={selected.case_version.notes} />
            <CaseVersionRoadmap history={history} currentVersionId={selected.case_version.id} />
          </>
        ) : (
          <div className="quiet-panel">还没有测试用例。</div>
        )}
      </section>

      {editor ? <EvalCaseModal caseItem={editor === "new" ? null : editor} busy={busy} onClose={() => setEditor(null)} onSubmit={saveCase} /> : null}
    </div>
  );
}

function CaseBlock({ title, text }: { title: string; text?: string | null }) {
  const value = compactText(text, "无内容");
  return (
    <section className="case-block">
      <header>
        <h2>{title}</h2>
        <button className="icon-button mini" type="button" aria-label={`复制 ${title}`} onClick={() => navigator.clipboard.writeText(value)}>
          <Copy size={16} />
        </button>
      </header>
      <pre>{value}</pre>
    </section>
  );
}

function filterCases(cases: EvalSetCase[], query: string, filter: "all" | "active"): EvalSetCase[] {
  const normalized = query.trim().toLowerCase();
  return cases.filter((item) => {
    if (filter === "active" && item.case.lifecycle_status !== "active") return false;
    if (!normalized) return true;
    return [item.case.title, item.case_version.input_artifact.content_text, item.case_version.expected_output_artifact.content_text].join(" ").toLowerCase().includes(normalized);
  });
}

function sortCases(cases: EvalSetCase[], sortKey: CaseSortKey): EvalSetCase[] {
  const copy = [...cases];
  if (sortKey === "title") return copy.sort((left, right) => left.case.title.localeCompare(right.case.title) || left.position - right.position);
  if (sortKey === "version") {
    return copy.sort((left, right) => right.case_version.version_number - left.case_version.version_number || left.position - right.position);
  }
  return copy.sort((left, right) => left.position - right.position);
}

function caseLifecycleLabel(status: string): string {
  if (status === "active") return "活跃";
  if (status === "archived") return "归档";
  return status || "未知";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "操作失败。";
}

function cleanName(value: string): string | undefined {
  const clean = value.trim();
  return clean || undefined;
}
