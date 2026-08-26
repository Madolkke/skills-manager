import { computed, getCurrentScope, onScopeDispose, ref, watch, type Ref } from "vue";
import { api } from "../../lib/api";
import type {
  WorkflowBundle,
  WorkflowExpressionDiagnostic,
  WorkflowValidationIssue,
} from "../../types";
import { workflowSteps } from "./domain/utils";
import { workflowExpressionEnvironment } from "./workflowExpressionVariables";

type ValidationBatch = {
  stepId: string;
  expressions: Array<{ id: string; source: string }>;
};

const sampleIndexCodes = new Set([
  "SAMPLE_INDEX_REQUIRED",
  "SAMPLE_INDEX_NOT_ALLOWED",
  "SAMPLE_INDEX_OUT_OF_RANGE",
  "INVALID_SAMPLE_INDEX_TYPE",
]);
const blockingExpressionCodes = new Set([
  "CONFIG_STRING_SUBSCRIPT_FORBIDDEN",
  "CONFIG_ARRAY_INDEX_INVALID",
]);

export function workflowExpressionValidationKey(stepId: string, transitionId: string): string {
  return `${stepId}:${transitionId}`;
}

export function useWorkflowExpressionValidation(bundle: Ref<WorkflowBundle | null>) {
  const diagnostics = ref<Record<string, WorkflowExpressionDiagnostic[]>>({});
  let timer: number | null = null;
  let controller: AbortController | null = null;
  let generation = 0;
  let validatedSources: Record<string, string> = {};
  let requestedSources: Record<string, string> = {};

  watch(bundle, schedule, { deep: true, immediate: true });
  if (getCurrentScope()) onScopeDispose(clear);

  const issues = computed<WorkflowValidationIssue[]>(() => {
    const current = bundle.value;
    if (!current) return [];
    const occurrences = new Map<string, number>();
    return workflowSteps(current).flatMap((step) => step.topology.flatMap((transition) => {
      const key = workflowExpressionValidationKey(step.id, transition.id);
      return (diagnostics.value[key] ?? []).filter((item) => sampleIndexCodes.has(item.code) || blockingExpressionCodes.has(item.code)).map((item) => {
        const selection = {
          type: "step" as const,
          id: step.id,
          section: "paths" as const,
          itemId: transition.id,
          field: "conditionExpression",
        };
        const base = workflowIssueBase(item.code, selection);
        const occurrence = occurrences.get(base) ?? 0;
        occurrences.set(base, occurrence + 1);
        return {
          id: `${base}/${occurrence}`,
          code: item.code,
          severity: blockingExpressionCodes.has(item.code) ? "error" as const : "warning" as const,
          message: item.message,
          selection,
        };
      });
    }));
  });

  function schedule(): void {
    if (typeof window === "undefined") return;
    const current = bundle.value;
    if (!current) {
      clearRequest();
      diagnostics.value = {};
      validatedSources = {};
      requestedSources = {};
      return;
    }
    const projected = projectValidationBatches(current);
    const activeSources = projected.sources;
    const changedIds = Object.keys(activeSources).filter((id) => requestedSources[id] !== activeSources[id]);
    const removedIds = Object.keys(requestedSources).filter((id) => !Object.hasOwn(activeSources, id));
    if (!changedIds.length) {
      if (removedIds.length) {
        diagnostics.value = Object.fromEntries(Object.entries(diagnostics.value).filter(([id]) => Object.hasOwn(activeSources, id)));
        validatedSources = Object.fromEntries(Object.entries(validatedSources).filter(([id]) => Object.hasOwn(activeSources, id)));
        requestedSources = activeSources;
      }
      return;
    }
    clearRequest();
    requestedSources = activeSources;
    const changed = new Set(changedIds);
    const batches = projected.batches.map((batch) => ({
      ...batch,
      expressions: batch.expressions.filter((item) => changed.has(item.id)),
    })).filter((batch) => batch.expressions.length);
    const requestGeneration = ++generation;
    timer = window.setTimeout(async () => {
      timer = null;
      controller = new AbortController();
      try {
        const results = await Promise.allSettled(batches.map((batch) => api.validateWorkflowExpressions(
          batch.expressions,
          projected.environments.get(batch.stepId)!,
          controller!.signal,
        )));
        if (requestGeneration !== generation) return;
        const nextDiagnostics = Object.fromEntries(
          Object.entries(diagnostics.value).filter(([id]) => activeSources[id] === validatedSources[id]),
        );
        const nextValidatedSources = Object.fromEntries(
          Object.entries(validatedSources).filter(([id, source]) => activeSources[id] === source),
        );
        results.forEach((result) => {
          if (result.status !== "fulfilled") return;
          result.value.validations.forEach((item) => {
            if (requestedSources[item.id] !== activeSources[item.id]) return;
            nextDiagnostics[item.id] = item.diagnostics;
            nextValidatedSources[item.id] = activeSources[item.id] ?? "";
          });
        });
        diagnostics.value = nextDiagnostics;
        validatedSources = nextValidatedSources;
      } catch (error) {
        if (requestGeneration === generation && !isAbortError(error)) {
          diagnostics.value = Object.fromEntries(Object.entries(diagnostics.value).filter(([id]) => activeSources[id] === validatedSources[id]));
          validatedSources = Object.fromEntries(Object.entries(validatedSources).filter(([id, source]) => activeSources[id] === source));
          batches.flatMap((batch) => batch.expressions).forEach((item) => delete requestedSources[item.id]);
        }
      }
    }, 300);
  }

  function clearRequest(): void {
    generation += 1;
    if (timer !== null) window.clearTimeout(timer);
    timer = null;
    controller?.abort();
    controller = null;
  }

  function clear(): void {
    clearRequest();
    diagnostics.value = {};
    validatedSources = {};
    requestedSources = {};
  }

  return { diagnostics, issues };
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function projectValidationBatches(bundle: WorkflowBundle): {
  batches: ValidationBatch[];
  sources: Record<string, string>;
  environments: Map<string, ReturnType<typeof workflowExpressionEnvironment>>;
} {
  const environments = new Map<string, ReturnType<typeof workflowExpressionEnvironment>>();
  const sources: Record<string, string> = {};
  const batches = workflowSteps(bundle).flatMap((step) => {
    const expressions = step.topology
      .filter((transition) => transition.conditionExpression.trim())
      .map((transition) => ({ id: workflowExpressionValidationKey(step.id, transition.id), source: transition.conditionExpression }));
    if (!expressions.length) return [];
    const environment = workflowExpressionEnvironment(bundle, step.id);
    environments.set(step.id, environment);
    const fingerprint = JSON.stringify(environment);
    expressions.forEach((item) => { sources[item.id] = `${item.source}\u0000${fingerprint}`; });
    return [{ stepId: step.id, expressions }];
  });
  return { batches, sources, environments };
}

function workflowIssueBase(code: string, selection: { type: string; id: string; section: string; itemId: string; field: string }): string {
  const values = [code.toLowerCase(), selection.type, selection.id, "", selection.section, selection.itemId, selection.field];
  return ["workflow-issue", ...values.map(encodeIssueIdPart)].join("/");
}

function encodeIssueIdPart(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`);
}
