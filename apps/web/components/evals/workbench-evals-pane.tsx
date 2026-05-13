"use client";

import { useEffect, useMemo, useState } from "react";

import { CandidateVerificationBanner } from "@/components/eval-cases/candidate-verification-banner";
import { EvalCaseDetailPanel, type EvalCaseUpdateDraft } from "@/components/eval-cases/eval-case-detail-panel";
import { EvalReviewControls, type EvalReviewFilter } from "@/components/eval-cases/eval-review-controls";
import { QuickAddCases, type QuickEvalCaseDraft } from "@/components/eval-cases/quick-add-cases";
import type { InspectorActionMode } from "@/components/inspector/workbench-inspector";
import type { EvalCaseHistory, EvalSetVersionDetail, VariantDetail, VariantVersion } from "@/lib/types";

type EvalTargetOption = { variant: VariantDetail; version: VariantVersion; label: string; isCurrent: boolean };

type WorkbenchEvalsPaneProps = {
  busy: boolean;
  caseHistory: EvalCaseHistory | null;
  caseHistoryCaseId: string | null;
  caseHistoryLoading: boolean;
  caseResults: Record<string, boolean | null>;
  cases: EvalSetVersionDetail["cases"];
  confirmedDraft: number;
  currentEvalSetVersion?: number;
  evalTargetOption: EvalTargetOption | null;
  evalTargetVersionId: string;
  evalTargetVersions: EvalTargetOption[];
  failedDraft: number;
  onAction: (mode: InspectorActionMode) => void;
  onArchiveCase: (caseId: string) => void;
  onClearDraft: () => void;
  onCloseCaseHistory: () => void;
  onCreateCases: (cases: QuickEvalCaseDraft[]) => Promise<boolean>;
  onEditCase: (caseId: string) => void;
  onHistoryCase: (caseId: string) => void;
  onPromotionReview: (variantId: string, candidateVersionId: string) => void;
  onRecord: () => void;
  onRestoreCaseVersion: (caseId: string, caseVersionId: string, versionNumber: number) => void;
  onSelectCase: (caseId: string) => void;
  onSelectEvalTargetVersion: (versionId: string) => void;
  onToggle: (caseVersionId: string, passed: boolean) => void;
  onUpdateCase: (draft: EvalCaseUpdateDraft) => Promise<boolean>;
  passedDraft: number;
  selectedCaseId: string | null;
};

export function WorkbenchEvalsPane({
  busy,
  caseHistory,
  caseHistoryCaseId,
  caseHistoryLoading,
  caseResults,
  cases,
  confirmedDraft,
  currentEvalSetVersion,
  evalTargetVersionId,
  evalTargetOption,
  evalTargetVersions,
  failedDraft,
  onAction,
  onArchiveCase,
  onCloseCaseHistory,
  onClearDraft,
  onCreateCases,
  onEditCase,
  onHistoryCase,
  onPromotionReview,
  onRecord,
  onRestoreCaseVersion,
  onSelectCase,
  onSelectEvalTargetVersion,
  onToggle,
  onUpdateCase,
  passedDraft,
  selectedCaseId,
}: WorkbenchEvalsPaneProps) {
  const [reviewFilter, setReviewFilter] = useState<EvalReviewFilter>("all");
  const pendingCases = useMemo(
    () => cases.filter((item) => typeof caseResults[item.case_version.id] !== "boolean"),
    [caseResults, cases],
  );
  const visibleCases = useMemo(
    () => cases.filter((item) => {
      const passed = caseResults[item.case_version.id];
      if (reviewFilter === "pending") return typeof passed !== "boolean";
      if (reviewFilter === "passed") return passed === true;
      if (reviewFilter === "failed") return passed === false;
      return true;
    }),
    [caseResults, cases, reviewFilter],
  );

  function nextPendingCase(afterCaseVersionId?: string) {
    if (pendingCases.length === 0) return null;
    const startIndex = Math.max(0, cases.findIndex((item) => item.case_version.id === afterCaseVersionId));
    for (let offset = 1; offset <= cases.length; offset += 1) {
      const candidate = cases[(startIndex + offset) % cases.length];
      if (candidate.case_version.id !== afterCaseVersionId && typeof caseResults[candidate.case_version.id] !== "boolean") {
        return candidate;
      }
    }
    return null;
  }

  function toggleAndAdvance(item: EvalSetVersionDetail["cases"][number], passed: boolean) {
    onToggle(item.case_version.id, passed);
    const nextCase = nextPendingCase(item.case_version.id);
    onSelectCase(nextCase?.case.id ?? item.case.id);
  }

  function selectCaseByOffset(offset: number) {
    const reviewCases = visibleCases.length > 0 ? visibleCases : cases;
    if (reviewCases.length === 0) return;
    const selectedIndex = reviewCases.findIndex((item) => item.case.id === selectedCaseId);
    const currentIndex = selectedIndex >= 0 ? selectedIndex : 0;
    const nextIndex = (currentIndex + offset + reviewCases.length) % reviewCases.length;
    onSelectCase(reviewCases[nextIndex].case.id);
  }

  function jumpPending() {
    const target = pendingCases[0];
    if (target) onSelectCase(target.case.id);
  }

  function markPendingPassed() {
    for (const item of pendingCases) onToggle(item.case_version.id, true);
    if (pendingCases[0]) onSelectCase(pendingCases[0].case.id);
  }

  const selectedItem = cases.find((item) => item.case.id === selectedCaseId) ?? cases[0] ?? null;
  const historyVisible = Boolean(selectedItem && caseHistoryCaseId === selectedItem.case.id);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTextEntryTarget(event.target)) return;
      const key = event.key.toLowerCase();
      const selected = cases.find((item) => item.case.id === selectedCaseId) ?? cases[0];

      if (key === "j" || event.key === "ArrowDown") {
        event.preventDefault();
        selectCaseByOffset(1);
      } else if (key === "k" || event.key === "ArrowUp") {
        event.preventDefault();
        selectCaseByOffset(-1);
      } else if (key === "p" && selected) {
        event.preventDefault();
        toggleAndAdvance(selected, true);
      } else if (key === "f" && selected) {
        event.preventDefault();
        toggleAndAdvance(selected, false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  return (
    <div className="linearPane evalPane">
      <div className="linearToolbar">
        <div>
          <h2>手工测评</h2>
          <p>EvalSetVersion {currentEvalSetVersion ? `v${currentEvalSetVersion}` : "暂无"} · 已确认 {confirmedDraft}/{cases.length} · 通过 {passedDraft} · 不通过 {failedDraft}</p>
        </div>
        <div>
          <button onClick={() => onAction("new-case")} type="button">添加 case</button>
          <button disabled={cases.length === 0} onClick={() => onAction("edit-case")} type="button">编辑 case</button>
        </div>
      </div>
      <div className="evalTargetBar">
        <label>
          <span>测评目标版本</span>
          <select
            aria-label="测评目标版本"
            disabled={evalTargetVersions.length === 0}
            onChange={(event) => onSelectEvalTargetVersion(event.currentTarget.value)}
            value={evalTargetVersionId}
          >
            {evalTargetVersions.map((item) => (
              <option key={item.version.id} value={item.version.id}>
                {item.label}{item.isCurrent ? " · current" : " · candidate"}
              </option>
            ))}
          </select>
        </label>
        <span>测评结果会绑定到 exact VariantVersion，候选版本也可以先测再上架。</span>
      </div>
      {evalTargetOption && !evalTargetOption.isCurrent ? (
        <CandidateVerificationBanner
          onPromotionReview={onPromotionReview}
          variant={evalTargetOption.variant}
          version={evalTargetOption.version}
        />
      ) : null}
      <QuickAddCases busy={busy} onCreateCases={onCreateCases} />
      <EvalReviewControls
        busy={busy}
        canRecord={cases.length > 0 && confirmedDraft === cases.length}
        confirmedCount={confirmedDraft}
        failedCount={failedDraft}
        filter={reviewFilter}
        onClearDraft={onClearDraft}
        onFilterChange={setReviewFilter}
        onJumpPending={jumpPending}
        onMarkPendingPassed={markPendingPassed}
        onRecord={onRecord}
        passedCount={passedDraft}
        pendingCount={pendingCases.length}
        totalCount={cases.length}
      />
      <div className="evalReviewGrid">
        <section className="evalCaseRail">
          <div className="evalCaseRailHead">
            <strong>Cases</strong>
            <span>{cases.length} snapshots</span>
          </div>
          <div className="caseReviewList">
            {visibleCases.map((item) => {
              const passed = caseResults[item.case_version.id];
              const isSelected = selectedCaseId === item.case.id;
              return (
                <article
                  className={[
                    "caseReviewCard",
                    isSelected ? "caseReviewCardActive" : "",
                    passed === true ? "caseReviewCardDone" : "",
                    passed === false ? "caseReviewCardFailed" : "",
                    typeof passed !== "boolean" ? "caseReviewCardPending" : "",
                  ].filter(Boolean).join(" ")}
                  key={item.case_version.id}
                  onClick={() => onSelectCase(item.case.id)}
                >
                  <div className="caseReviewHeader">
                    <div>
                      <span>case v{item.case_version.version_number}</span>
                      <strong>{item.case.title}</strong>
                    </div>
                    <div className="resultSwitch" aria-label={`${item.case.title} result`}>
                      <button
                        className={passed === true ? "resultOn" : ""}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleAndAdvance(item, true);
                        }}
                        type="button"
                      >通过</button>
                      <button
                        className={passed === false ? "resultOff" : ""}
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleAndAdvance(item, false);
                        }}
                        type="button"
                      >不通过</button>
                    </div>
                  </div>
                  <div className="caseReviewFooter">
                    <small>{item.case_version.notes || "No notes"}</small>
                    <div className="caseRowActions">
                      <button onClick={() => onEditCase(item.case.id)} type="button">编辑</button>
                      <button onClick={() => onHistoryCase(item.case.id)} type="button">历史</button>
                      <button onClick={() => onArchiveCase(item.case.id)} type="button">归档</button>
                    </div>
                  </div>
                </article>
              );
            })}
            {cases.length === 0 ? <div className="linearEmpty">还没有测试用例。先从右侧添加一个 case。</div> : null}
            {cases.length > 0 && visibleCases.length === 0 ? <div className="linearEmpty">当前筛选下没有 case。</div> : null}
          </div>
        </section>

        <section className="evalCaseDetail">
          <EvalCaseDetailPanel
            busy={busy}
            currentHistory={caseHistory}
            historyLoading={caseHistoryLoading}
            historyVisible={historyVisible}
            item={selectedItem}
            onArchiveCase={onArchiveCase}
            onCloseHistory={onCloseCaseHistory}
            onHistoryCase={onHistoryCase}
            onRestoreCaseVersion={onRestoreCaseVersion}
            onUpdateCase={onUpdateCase}
          />
        </section>
      </div>
    </div>
  );
}

function isTextEntryTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select" || target.isContentEditable;
}
