"use client";

import { passRate } from "@/lib/api";
import { percent } from "@/lib/format";
import type { EvalRunMatrix } from "@/lib/types";

type MatrixImpact = "waiting" | "fixed" | "regressed" | "stable_pass" | "stable_fail" | "missing";

const impactCopy: Record<MatrixImpact, string> = {
  waiting: "选择对照/候选",
  fixed: "修复",
  regressed: "回退",
  stable_pass: "稳定通过",
  stable_fail: "仍未通过",
  missing: "缺失",
};

const impactClass: Record<MatrixImpact, string> = {
  waiting: "runMatrixImpactWaiting",
  fixed: "runMatrixImpactFixed",
  regressed: "runMatrixImpactRegressed",
  stable_pass: "runMatrixImpactStablePass",
  stable_fail: "runMatrixImpactStableFail",
  missing: "runMatrixImpactMissing",
};

export function RunMatrixPanel({
  baselineRunId,
  candidateRunId,
  loading,
  matrix,
}: {
  baselineRunId?: string | null;
  candidateRunId?: string | null;
  loading: boolean;
  matrix: EvalRunMatrix | null;
}) {
  const runs = matrix?.runs ?? [];
  const cases = matrix?.cases ?? [];
  const cells = new Map((matrix?.cells ?? []).map((cell) => [`${cell.run_id}:${cell.case_id}`, cell]));
  const hasImpactPair = Boolean(baselineRunId && candidateRunId && baselineRunId !== candidateRunId);

  return (
    <section className="runMatrixPanel" data-testid="run-matrix-panel">
      <div className="runMatrixHead">
        <div>
          <h3>Run matrix</h3>
          <p>{loading ? "正在加载矩阵..." : `${runs.length} runs · ${cases.length} cases · 当前筛选生效`}</p>
        </div>
        <span>Case x EvalRun</span>
      </div>

      {!loading && runs.length === 0 ? (
        <div className="linearEmpty">还没有可进入矩阵的测评 run。</div>
      ) : (
        <div className="runMatrixScroller">
          <table className="runMatrixTable">
            <thead>
              <tr>
                <th className="runMatrixCaseHeader">Case</th>
                <th className="runMatrixImpactHeader">Impact</th>
                {runs.map((row) => (
                  <th className="runMatrixRunHeader" key={row.eval_run.id}>
                    <strong>{row.variant.label} v{row.variant_version.version_number}</strong>
                    <span>{row.eval_set.name} v{row.eval_set_version.version_number}</span>
                    <small>{percent(passRate(row.eval_run))}</small>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cases.map((row) => {
                const impact = caseImpact(cells, row.case.id, baselineRunId, candidateRunId, hasImpactPair);
                return (
                  <tr key={row.case.id}>
                    <th className="runMatrixCaseTitle" scope="row">
                      <strong>{row.case.title}</strong>
                      <span>{row.versions.map((version) => `v${version.version_number}`).join(", ")}</span>
                    </th>
                    <td className="runMatrixImpactCell">
                      <span className={impactClass[impact]}>{impactCopy[impact]}</span>
                    </td>
                    {runs.map((run) => {
                      const cell = cells.get(`${run.eval_run.id}:${row.case.id}`);
                      return (
                        <td key={run.eval_run.id}>
                          {cell ? (
                            <span className={cell.passed ? "runMatrixCellPass" : "runMatrixCellFail"}>
                              {cell.passed ? "通过" : "不通过"}
                            </span>
                          ) : (
                            <span className="runMatrixCellMissing">-</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function caseImpact(
  cells: Map<string, EvalRunMatrix["cells"][number]>,
  caseId: string,
  baselineRunId?: string | null,
  candidateRunId?: string | null,
  hasImpactPair = false,
): MatrixImpact {
  if (!hasImpactPair || !baselineRunId || !candidateRunId) return "waiting";
  const baseline = cells.get(`${baselineRunId}:${caseId}`);
  const candidate = cells.get(`${candidateRunId}:${caseId}`);
  if (!baseline || !candidate) return "missing";
  if (!baseline.passed && candidate.passed) return "fixed";
  if (baseline.passed && !candidate.passed) return "regressed";
  if (baseline.passed && candidate.passed) return "stable_pass";
  return "stable_fail";
}
