import type { AppData, EvalCase, EvalSetVersion, Variant } from "../domain/types";
import { artifactContent, caseScore, casesForVersion, currentVersionForVariant } from "../domain/scoring";
import { ResultDot, SourceLabel } from "./ui";

export function EvalMatrix({
  data,
  variants,
  version,
}: {
  data: AppData;
  variants: Variant[];
  version: EvalSetVersion;
}) {
  const cases = casesForVersion(data, version);
  return (
    <div className="case-matrix">
      <table>
        <thead>
          <tr>
            <th>EvalCase</th>
            <th>来源</th>
            {variants.map((variant) => (
              <th key={variant.id}>{variant.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.id}>
              <td>{item.title}</td>
              <td>
                <SourceLabel source={item.sourceType} />
              </td>
              {variants.map((variant) => (
                <td key={variant.id}>
                  <ResultDot score={caseScore(data, currentVersionForVariant(data, variant)?.id ?? "", version.id, item.id)} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvalCaseTable({ cases }: { cases: EvalCase[] }) {
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>来源</th>
            <th>期望行为</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.id}>
              <td>{item.title}</td>
              <td>
                <SourceLabel source={item.sourceType} />
              </td>
              <td>{item.expectation}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvalCaseDetailTable({ data, cases }: { data: AppData; cases: EvalCase[] }) {
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Input</th>
            <th>Expected output</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
