import { useState, type Dispatch, type SetStateAction } from "react";
import type { AppData, AppState, EvalSetVersion } from "../domain/types";
import { aggregateScore, casesForVersion, currentVersionForVariant, percent } from "../domain/scoring";
import { createBackendEvalCase } from "../store/backendState";
import { EvalCaseDetailTable, EvalMatrix } from "./EvalMatrix";

export function EvalCorpusPage({
  data,
  version,
  skillRef,
  setState,
}: {
  data: AppData;
  version: EvalSetVersion;
  skillRef: string;
  setState: Dispatch<SetStateAction<AppState>>;
}) {
  const [backendError, setBackendError] = useState("");
  const [caseForm, setCaseForm] = useState({
    title: "发现敏感 token 输出到错误响应",
    input: "输入：一段 diff 把 access_token 放进 error response body。",
    expectedOutput: "输出：必须指出 token 泄露风险，并建议只返回通用错误信息。",
  });
  const cases = casesForVersion(data, version);
  const variants = data.variants.filter((item) => item.skillRef === skillRef);
  const skill = data.skills.find((item) => item.id === skillRef);
  const defaultVariant = skill ? variants.find((item) => item.id === skill.defaultVariantRef) : variants[0];
  const defaultVersion = defaultVariant ? currentVersionForVariant(data, defaultVariant) : undefined;
  const defaultScore = defaultVersion ? aggregateScore(data, defaultVersion.id, version.id) : null;
  const sourceCaseCount = cases.filter((item) => item.sourceType !== "manual").length;
  const evalSetVersions = data.evalSetVersions
    .filter((item) => item.corpusRef === version.corpusRef)
    .sort((a, b) => a.version.localeCompare(b.version, undefined, { numeric: true }));

  const runApiAction = (action: Promise<AppState>) => {
    setBackendError("");
    action.then(setState).catch((error) => {
      setBackendError(error instanceof Error ? error.message : "后端写入失败");
    });
  };

  return (
    <div className="workbench">
      {backendError && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>后端写入失败</h2>
              <p>{backendError}</p>
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>EvalSetVersion</h2>
            <p>每个版本都是一份 case 快照。选择不同版本时，矩阵和 case 明细会按这个快照切换。</p>
          </div>
        </div>
        <div className="corpus-summary">
          <Metric label="当前快照" value={version.version} note={evalSetVersions.map((item) => item.version).join(" / ")} />
          <Metric label="Cases" value={String(cases.length)} note="当前快照" />
          <Metric label="非手工来源" value={String(sourceCaseCount)} note="只作为 case 来源记录" />
          <Metric label="判定方式" value="Pass/Fail" note="MVP 先记录最终结论" />
        </div>
        <div className="version-timeline">
          {evalSetVersions.map((evalSetVersion) => {
            const snapshotCases = casesForVersion(data, evalSetVersion);
            return (
              <button
                className={`history-row evalset-version-card ${evalSetVersion.id === version.id ? "is-active" : ""}`}
                key={evalSetVersion.id}
                type="button"
                onClick={() => setState((prev) => ({ ...prev, evalSetVersionRef: evalSetVersion.id }))}
              >
                <span className="evalset-version-head">
                  <span>
                    <strong>{evalSetVersion.version}</strong>
                    <em>{evalSetVersion.caseRefs.length} 个 cases</em>
                  </span>
                  <span>{evalSetVersion.id === version.id ? "selected" : "snapshot"}</span>
                </span>
                <span className="evalset-case-list">
                  {snapshotCases.length === 0 && <em>空快照，还没有测试用例。</em>}
                  {snapshotCases.map((item) => (
                    <span className="evalset-case-item" key={item.id}>
                      <strong>{item.title}</strong>
                      <em>{item.expectation}</em>
                    </span>
                  ))}
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>当前结果矩阵</h2>
            <p>这里比较所有当前发布变体在所选 EvalSetVersion 上的逐 case 通过情况。</p>
          </div>
        </div>
        <div className="score-summary">
          <Metric label="默认变体" value={defaultVariant?.name ?? "无"} note={percent(defaultScore)} />
          <Metric label="EvalSetVersion" value={version.version} note={`${cases.length} 个 cases`} />
          <Metric label="可比较变体" value={String(variants.length)} note="包含未运行节点" />
        </div>
        <EvalMatrix data={data} variants={variants} version={version} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>测试用例库</h2>
            <p>当前快照包含的完整测试用例。一个 case 是 input、expected output 和最终 pass/fail 判定的最小单位。</p>
          </div>
        </div>
        <EvalCaseDetailTable data={data} cases={cases} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>添加 EvalCase</h2>
            <p>用最简单的 input / expected output 添加测试用例。每次添加都会生成新的 EvalSetVersion。</p>
          </div>
          <button
            className="primary-button"
            type="button"
            onClick={() =>
              runApiAction(
                createBackendEvalCase({
                  skillId: skillRef,
                  title: caseForm.title,
                  input: caseForm.input,
                  expectedOutput: caseForm.expectedOutput,
                  view: "eval",
                }),
              )
            }
          >
            添加并生成新版本
          </button>
        </div>
        <div className="form-grid">
          <label className="field-block">
            <span>标题</span>
            <input value={caseForm.title} onChange={(event) => setCaseForm({ ...caseForm, title: event.target.value })} />
          </label>
          <label className="field-block wide">
            <span>Input</span>
            <textarea value={caseForm.input} onChange={(event) => setCaseForm({ ...caseForm, input: event.target.value })} />
          </label>
          <label className="field-block wide">
            <span>Expected output</span>
            <textarea
              value={caseForm.expectedOutput}
              onChange={(event) => setCaseForm({ ...caseForm, expectedOutput: event.target.value })}
            />
          </label>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note}</div>
    </div>
  );
}
