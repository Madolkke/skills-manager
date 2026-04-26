import type { AppData, EvalSetVersion, Variant, VariantVersion } from "../domain/types";
import { artifactContent, caseScore, casesForVersion, percent, resultCounts, runFor } from "../domain/scoring";
import { ResultDot, TagPill } from "./ui";

export function ResultPage({
  data,
  variant,
  variantVersion,
  evalSetVersion,
}: {
  data: AppData;
  variant: Variant;
  variantVersion: VariantVersion;
  evalSetVersion: EvalSetVersion;
}) {
  const cases = casesForVersion(data, evalSetVersion);
  const counts = resultCounts(data, variantVersion.id, evalSetVersion.id);
  const run = runFor(data, variantVersion.id, evalSetVersion.id);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>当前测评结果详情</h2>
          <p>
            {variant.name} / {variantVersion.version} 在 {evalSetVersion.version} 上的每条测试用例结果。
          </p>
        </div>
      </div>
      <div className="result-hero">
        <div>
          <div className="variant-titleline">
            <strong>{variant.label}</strong>
            {data.tagSets
              .find((tagSet) => tagSet.id === variant.tagSetRef)
              ?.tags.map((tag) => <TagPill key={tag} tag={tag} />)}
          </div>
          <p>{run ? `EvalRun: ${run.id}` : "当前版本还没有这个测评集的运行记录。"}</p>
        </div>
        <div className="score-number">{percent(counts.total ? counts.passed / counts.total : null)}</div>
      </div>
      <div className="summary-row">
        <Metric label="通过" value={String(counts.passed)} />
        <Metric label="不通过" value={String(counts.failed)} />
        <Metric label="未测" value={String(counts.missing)} />
      </div>
      <div className="data-table">
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Input</th>
              <th>Expected output</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>
                  <pre className="case-artifact">{artifactContent(data, item.inputArtifactRef)}</pre>
                </td>
                <td>
                  <pre className="case-artifact">{artifactContent(data, item.expectationArtifactRef)}</pre>
                </td>
                <td>
                  <ResultDot score={caseScore(data, variantVersion.id, evalSetVersion.id, item.id)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric compact-metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </div>
  );
}
