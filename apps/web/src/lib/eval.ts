import type { EvalSetCase } from "../types";

export type ManualEvalSummary = {
  confirmed: number;
  passed: number;
  failed: number;
  pending: number;
  coverage: number;
};

export type ManualCaseResult = {
  passed?: boolean;
  actualOutput: string;
};

export function summarizeManualEval(total: number, results: Record<string, ManualCaseResult>): ManualEvalSummary {
  const confirmedResults = Object.values(results).filter((result) => result.passed !== undefined);
  const confirmed = confirmedResults.length;
  const passed = confirmedResults.filter((result) => result.passed === true).length;
  const failed = confirmed - passed;
  return {
    confirmed,
    passed,
    failed,
    pending: Math.max(total - confirmed, 0),
    coverage: total === 0 ? 0 : Math.round((confirmed / total) * 100),
  };
}

export function nextPendingCaseVersionId(
  cases: EvalSetCase[],
  results: Record<string, ManualCaseResult>,
  activeCaseVersionId?: string | null,
): string | null {
  if (!activeCaseVersionId) {
    return cases.find((item) => results[item.case_version.id]?.passed === undefined)?.case_version.id ?? null;
  }

  const activeIndex = cases.findIndex((item) => item.case_version.id === activeCaseVersionId);
  if (activeIndex === -1) {
    return cases.find((item) => results[item.case_version.id]?.passed === undefined)?.case_version.id ?? null;
  }

  const ordered = [...cases.slice(activeIndex + 1), ...cases.slice(0, activeIndex + 1)];
  return ordered.find((item) => results[item.case_version.id]?.passed === undefined)?.case_version.id ?? null;
}

export function manualResultLabel(value?: boolean): string {
  if (value === true) return "通过";
  if (value === false) return "不通过";
  return "待评估";
}

export function manualRecordHint(total: number, pending: number): string {
  if (total === 0) return "当前测评集没有 case，无法记录测评结果。";
  if (pending > 0) return `需确认剩余 ${pending} 个 case 后才能记录。`;
  return "全部 case 已确认，可以记录本次测评。";
}
