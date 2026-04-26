import type { AppData, Variant, VariantEvalSummary } from "../domain/types";
import { aggregateScore, caseScore, casesForVersion, currentVersionForVariant, percent, tagsForVariant } from "../domain/scoring";
import { StatePill, TagPill } from "./ui";

export function VariantMap({
  data,
  summaries,
  evalSetVersionRef,
  selectedVariantRef,
  onSelectVariant,
}: {
  data: AppData;
  summaries: VariantEvalSummary[];
  evalSetVersionRef: string;
  selectedVariantRef: string;
  onSelectVariant: (variantRef: string) => void;
}) {
  const summaryByVariant = new Map(summaries.map((item) => [item.variant.id, item]));
  const variants = summaries.map((item) => item.variant);
  const groups = groupByTagSet(data, variants);
  const version = data.evalSetVersions.find((item) => item.id === evalSetVersionRef);
  const cases = version ? casesForVersion(data, version) : [];

  return (
    <div className="variant-map">
      {groups.map(([tagKey, group]) => (
        <section className="tag-lane" key={tagKey}>
          <div className="tag-start-node">
            <div className="tag-start-label">TagSet</div>
            <div className="tag-start-title">[{tagKey}]</div>
          </div>
          <div className="lane-connector" aria-hidden="true" />
          <div className="variant-node-row">
            {group.map((variant) => {
              const summary = summaryByVariant.get(variant.id);
              const currentVersion = currentVersionForVariant(data, variant);
              const hasFailedCase = cases.some(
                (item) => currentVersion && caseScore(data, currentVersion.id, evalSetVersionRef, item.id) === 0,
              );
              const hasRun = currentVersion ? aggregateScore(data, currentVersion.id, evalSetVersionRef) !== null : false;
              const tone = !hasRun ? "warn" : hasFailedCase ? "fail" : "pass";
              return (
                <button
                  className={`variant-node ${selectedVariantRef === variant.id ? "is-selected" : ""}`}
                  key={variant.id}
                  type="button"
                  onClick={() => onSelectVariant(variant.id)}
                >
                  <span className="variant-node-title">{variant.name}</span>
                  <StatePill tone={tone}>{!hasRun ? "未运行" : hasFailedCase ? "有失败" : "全通过"}</StatePill>
                  <span className="variant-node-score">{percent(summary?.evalScore)}</span>
                  <span className="variant-node-parent">current version: {currentVersion?.version ?? "none"}</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function groupByTagSet(data: AppData, variants: Variant[]): [string, Variant[]][] {
  const groups = new Map<string, Variant[]>();
  variants.forEach((variant) => {
    const key = tagsForVariant(data, variant).join(", ") || "untagged";
    groups.set(key, [...(groups.get(key) ?? []), variant]);
  });
  return Array.from(groups.entries());
}
