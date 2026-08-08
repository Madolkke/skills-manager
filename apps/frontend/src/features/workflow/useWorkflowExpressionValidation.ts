import { computed, getCurrentScope, onScopeDispose, ref, watch, type Ref } from "vue";
import { api } from "../../lib/api";
import type {
  WorkflowBundle,
  WorkflowExpressionDiagnostic,
  WorkflowValidationIssue,
} from "../../types";
import { workflowSteps } from "./domain/utils";
import { workflowExpressionEnvironment } from "./workflowExpressionVariables";

const sampleIndexCodes = new Set([
  "SAMPLE_INDEX_REQUIRED",
  "SAMPLE_INDEX_NOT_ALLOWED",
  "SAMPLE_INDEX_OUT_OF_RANGE",
  "INVALID_SAMPLE_INDEX_TYPE",
]);

export function workflowExpressionValidationKey(stepId: string, transitionId: string): string {
  return `${stepId}:${transitionId}`;
}

export function useWorkflowExpressionValidation(bundle: Ref<WorkflowBundle | null>) {
  const diagnostics = ref<Record<string, WorkflowExpressionDiagnostic[]>>({});
  let timer: number | null = null;
  let controller: AbortController | null = null;
  let generation = 0;

  watch(bundle, schedule, { deep: true, immediate: true });
  if (getCurrentScope()) onScopeDispose(clear);

  const issues = computed<WorkflowValidationIssue[]>(() => {
    const current = bundle.value;
    if (!current) return [];
    const occurrences = new Map<string, number>();
    return workflowSteps(current).flatMap((step) => step.topology.flatMap((transition) => {
      const key = workflowExpressionValidationKey(step.id, transition.id);
      return (diagnostics.value[key] ?? []).filter((item) => sampleIndexCodes.has(item.code)).map((item) => {
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
        return { id: `${base}/${occurrence}`, code: item.code, severity: "warning" as const, message: item.message, selection };
      });
    }));
  });

  function schedule(): void {
    clearRequest();
    if (typeof window === "undefined") return;
    const current = bundle.value;
    if (!current) {
      diagnostics.value = {};
      return;
    }
    const batches = workflowSteps(current).map((step) => ({
      step,
      expressions: step.topology.filter((transition) => transition.conditionExpression.trim()).map((transition) => ({
        id: workflowExpressionValidationKey(step.id, transition.id), source: transition.conditionExpression,
      })),
    })).filter((batch) => batch.expressions.length);
    if (!batches.length) {
      diagnostics.value = {};
      return;
    }
    const requestGeneration = ++generation;
    timer = window.setTimeout(async () => {
      timer = null;
      controller = new AbortController();
      try {
        const results = await Promise.all(batches.map((batch) => api.validateWorkflowExpressions(
          batch.expressions,
          workflowExpressionEnvironment(current, batch.step.id),
          controller!.signal,
        )));
        if (requestGeneration !== generation) return;
        diagnostics.value = Object.fromEntries(results.flatMap((result) => result.validations.map((item) => [item.id, item.diagnostics])));
      } catch (error) {
        if (requestGeneration === generation && !isAbortError(error)) diagnostics.value = {};
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
  }

  return { diagnostics, issues };
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function workflowIssueBase(code: string, selection: { type: string; id: string; section: string; itemId: string; field: string }): string {
  const values = [code.toLowerCase(), selection.type, selection.id, "", selection.section, selection.itemId, selection.field];
  return ["workflow-issue", ...values.map(encodeIssueIdPart)].join("/");
}

function encodeIssueIdPart(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`);
}
