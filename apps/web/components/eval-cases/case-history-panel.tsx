"use client";

import { formatDate } from "@/lib/format";
import type { EvalCaseHistory } from "@/lib/types";
import { Badge } from "@/components/chrome";

export function CaseHistoryPanel({
  busy,
  currentCaseVersionId,
  history,
  loading,
  onRestoreVersion,
}: {
  busy: boolean;
  currentCaseVersionId: string | null;
  history: EvalCaseHistory | null;
  loading: boolean;
  onRestoreVersion: (caseId: string, caseVersionId: string, versionNumber: number) => void;
}) {
  if (loading) {
    return (
      <div className="evalCaseDetailEmpty">
        <strong>Case version history</strong>
        <span>正在加载这个 case 的历史版本...</span>
      </div>
    );
  }
  if (!history) {
    return (
      <div className="evalCaseDetailEmpty">
        <strong>Case version history</strong>
        <span>暂时没有可展示的历史记录。</span>
      </div>
    );
  }
  return (
    <div className="caseHistoryPanel">
      <div className="evalCaseDetailHead">
        <span>Case version history</span>
        <strong>{history.case.title}</strong>
      </div>
      <div className="caseHistoryTimeline">
        {history.versions.map((item) => {
          const isCurrent = item.case_version.id === currentCaseVersionId;
          return (
            <article className="caseHistoryVersion" key={item.case_version.id}>
              <div className="caseHistoryVersionHead">
                <div>
                  <span>v{item.case_version.version_number}</span>
                  <strong>{item.case_version.notes || "No notes"}</strong>
                </div>
                <div className="caseHistoryVersionActions">
                  <small>{formatDate(item.case_version.created_at)} · {item.case_version.created_by}</small>
                  {isCurrent ? (
                    <Badge tone="good">当前版本</Badge>
                  ) : (
                    <button
                      disabled={busy}
                      onClick={() => onRestoreVersion(history.case.id, item.case_version.id, item.case_version.version_number)}
                      type="button"
                    >
                      恢复此版本
                    </button>
                  )}
                </div>
              </div>
              <div className="caseIOGrid">
                <div>
                  <span>Input</span>
                  <pre>{item.case_version.input_artifact.content_text ?? item.case_version.input_artifact.digest}</pre>
                </div>
                <div>
                  <span>Expected output</span>
                  <pre>{item.case_version.expected_output_artifact.content_text ?? item.case_version.expected_output_artifact.digest}</pre>
                </div>
              </div>
              <div className="caseHistoryMembership">
                {item.included_in_eval_set_versions.length > 0 ? (
                  item.included_in_eval_set_versions.map((membership) => (
                    <Badge key={membership.id}>EvalSet v{membership.version_number} · position {membership.position + 1}</Badge>
                  ))
                ) : (
                  <Badge>未进入 eval set snapshot</Badge>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
