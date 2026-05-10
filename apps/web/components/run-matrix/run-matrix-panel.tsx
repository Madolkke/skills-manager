"use client";

import { passRate } from "@/lib/api";
import { percent } from "@/lib/format";
import type { EvalRunMatrix } from "@/lib/types";

export function RunMatrixPanel({ loading, matrix }: { loading: boolean; matrix: EvalRunMatrix | null }) {
  const runs = matrix?.runs ?? [];
  const cases = matrix?.cases ?? [];
  const cells = new Map((matrix?.cells ?? []).map((cell) => [`${cell.run_id}:${cell.case_id}`, cell]));

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
              {cases.map((row) => (
                <tr key={row.case.id}>
                  <th className="runMatrixCaseTitle" scope="row">
                    <strong>{row.case.title}</strong>
                    <span>{row.versions.map((version) => `v${version.version_number}`).join(", ")}</span>
                  </th>
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
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
