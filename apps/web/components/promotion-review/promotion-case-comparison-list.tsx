import { Badge } from "@/components/chrome";
import type { PromotionCaseComparison } from "@/lib/types";

const summaryOrder: Array<PromotionCaseComparison["change"]> = [
  "fixed",
  "regressed",
  "stable_pass",
  "stable_fail",
  "missing_baseline",
  "missing_candidate",
];

const summaryLabels: Record<PromotionCaseComparison["change"], string> = {
  fixed: "修复",
  regressed: "回退",
  stable_pass: "稳定通过",
  stable_fail: "仍未通过",
  missing_baseline: "缺少对照",
  missing_candidate: "候选缺失",
};

export function PromotionCaseComparisonList({
  cases,
  summary,
}: {
  cases: PromotionCaseComparison[];
  summary: Record<PromotionCaseComparison["change"], number>;
}) {
  return (
    <section className="promotionCasePanel">
      <div className="promotionPanelHead">
        <div>
          <span>Case impact</span>
          <strong>{cases.length} 个测试用例</strong>
        </div>
        <div className="promotionSummaryChips" aria-label="Promotion comparison summary">
          {summaryOrder.map((key) => (
            <span className={`promotionSummaryChip promotionSummaryChip-${key}`} key={key}>
              {summaryLabels[key]} <b>{summary[key] ?? 0}</b>
            </span>
          ))}
        </div>
      </div>

      <div className="promotionCaseList">
        {cases.map((item) => (
          <article className={`promotionCaseRow promotionCaseRow-${item.change}`} key={item.case_version_id}>
            <div className="promotionCaseMain">
              <Badge tone={changeTone(item.change)}>{item.change_label}</Badge>
              <strong>{item.case_title}</strong>
              <small>case version {item.case_version_id.slice(0, 10)}</small>
            </div>
            <div className="promotionCaseResultGrid">
              <ResultCell label="Current" value={item.current_passed} />
              <ResultCell label="Candidate" value={item.candidate_passed} />
            </div>
            <details className="promotionCaseDetail">
              <summary>查看 input / expected output</summary>
              <div>
                <span>Input</span>
                <pre>{item.input_text ?? "没有文本快照"}</pre>
              </div>
              <div>
                <span>Expected output</span>
                <pre>{item.expected_output_text ?? "没有文本快照"}</pre>
              </div>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}

function ResultCell({ label, value }: { label: string; value: boolean | null }) {
  return (
    <span className={`promotionResultCell promotionResultCell-${value === null ? "missing" : value ? "pass" : "fail"}`}>
      <small>{label}</small>
      <b>{value === null ? "缺失" : value ? "通过" : "不通过"}</b>
    </span>
  );
}

function changeTone(change: PromotionCaseComparison["change"]) {
  if (change === "fixed" || change === "stable_pass") return "good";
  if (change === "regressed" || change === "stable_fail" || change === "missing_candidate") return "bad";
  return "neutral";
}
