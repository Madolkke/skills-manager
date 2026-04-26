import type { AppData, EvalCase, EvalSetVersion, Variant, VariantEvalSummary } from "./types";

export function tagsForVariant(data: AppData, variant: Variant): string[] {
  return data.tagSets.find((tagSet) => tagSet.id === variant.tagSetRef)?.tags ?? [];
}

export function casesForVersion(data: AppData, version: EvalSetVersion): EvalCase[] {
  return version.caseRefs
    .map((caseRef) => data.evalCases.find((item) => item.id === caseRef))
    .filter((item): item is EvalCase => Boolean(item));
}

export function latestVersionForSkill(data: AppData, skillRef: string): EvalSetVersion | undefined {
  const corpus = data.evalCorpora.find((item) => item.skillRef === skillRef);
  if (!corpus) return undefined;
  return data.evalSetVersions
    .filter((item) => item.corpusRef === corpus.id)
    .sort((a, b) => a.version.localeCompare(b.version, undefined, { numeric: true }))
    .at(-1);
}

export function currentVersionForVariant(data: AppData, variant: Variant) {
  return data.variantVersions.find((version) => version.id === variant.currentVersionRef);
}

export function artifactContent(data: AppData, artifactRef: string): string {
  return data.artifacts.find((artifact) => artifact.id === artifactRef)?.content ?? artifactRef;
}

export function runFor(data: AppData, variantVersionRef: string, evalSetVersionRef: string) {
  return data.evalRuns
    .filter((run) => run.variantVersionRef === variantVersionRef && run.evalSetVersionRef === evalSetVersionRef && run.status === "finished")
    .sort((a, b) => a.startedAt.localeCompare(b.startedAt))
    .at(-1);
}

export function caseScore(data: AppData, variantVersionRef: string, evalSetVersionRef: string, caseRef: string): number | null {
  const run = runFor(data, variantVersionRef, evalSetVersionRef);
  if (!run) return null;
  return data.caseResults.find((result) => result.runRef === run.id && result.caseRef === caseRef)?.score ?? null;
}

export function aggregateScore(data: AppData, variantVersionRef: string, evalSetVersionRef: string): number | null {
  const version = data.evalSetVersions.find((item) => item.id === evalSetVersionRef);
  const run = runFor(data, variantVersionRef, evalSetVersionRef);
  if (!version || !run) return null;
  const cases = casesForVersion(data, version);
  if (cases.length === 0) return null;
  return cases.reduce((sum, item) => sum + (caseScore(data, variantVersionRef, evalSetVersionRef, item.id) ?? 0), 0) / cases.length;
}

export function resultCounts(data: AppData, variantVersionRef: string, evalSetVersionRef: string) {
  const version = data.evalSetVersions.find((item) => item.id === evalSetVersionRef);
  if (!version) return { passed: 0, failed: 0, missing: 0, total: 0 };
  const cases = casesForVersion(data, version);
  return cases.reduce(
    (counts, item) => {
      const score = caseScore(data, variantVersionRef, evalSetVersionRef, item.id);
      if (score === null) return { ...counts, missing: counts.missing + 1 };
      if (score > 0) return { ...counts, passed: counts.passed + 1 };
      return { ...counts, failed: counts.failed + 1 };
    },
    { passed: 0, failed: 0, missing: 0, total: cases.length },
  );
}

export function tagMatchScore(data: AppData, variant: Variant, requestedTags: string[]): number {
  if (requestedTags.length === 0) return 0.5;
  const variantTags = new Set(tagsForVariant(data, variant));
  const matches = requestedTags.filter((tag) => variantTags.has(tag)).length;
  const exact = matches === requestedTags.length && variantTags.size === requestedTags.length;
  if (exact) return 1;
  if (matches === requestedTags.length) return 0.86;
  if (matches > 0) return 0.62;
  return 0.2;
}

export function summarizeVariants(
  data: AppData,
  skillRef: string,
  requestedTags: string[],
  evalSetVersionRef: string,
): VariantEvalSummary[] {
  return data.variants
    .filter((variant) => variant.skillRef === skillRef)
    .map((variant) => {
      const version = currentVersionForVariant(data, variant);
      if (!version) return null;
      const evalScore = aggregateScore(data, version.id, evalSetVersionRef);
      const matchScore = tagMatchScore(data, variant, requestedTags);
      return { variant, version, evalScore, tagMatchScore: matchScore };
    })
    .filter((item): item is VariantEvalSummary => Boolean(item));
}

export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "未运行";
  return `${Math.round(value * 100)}%`;
}
