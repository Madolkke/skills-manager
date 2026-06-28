import type { EvalSetCase } from "../../../types";
import { cleanRunnerConfig, type EvalCaseFormData } from "./evalCaseForm";

export type CaseSortKey = "position" | "title" | "version";
export type CleanEvalCaseFormOptions = {
  includePreserveWorkspace?: boolean;
};

export function filterCases(items: EvalSetCase[], value: string): EvalSetCase[] {
  const normalized = value.trim().toLowerCase();
  return items.filter((item) => {
    if (!normalized) return true;
    const stepText = item.case_version.steps.map((step) => [step.title, step.input, JSON.stringify(step.assertions)].join(" ")).join(" ");
    return [item.case.title, stepText].join(" ").toLowerCase().includes(normalized);
  });
}

export function sortCases(items: EvalSetCase[], sortKey: CaseSortKey): EvalSetCase[] {
  const copy = [...items];
  if (sortKey === "title") return copy.sort((left, right) => left.case.title.localeCompare(right.case.title) || left.position - right.position);
  if (sortKey === "version") return copy.sort((left, right) => right.case_version.version_number - left.case_version.version_number || left.position - right.position);
  return copy.sort((left, right) => left.position - right.position);
}

export function cleanCaseForm(form: EvalCaseFormData, options: CleanEvalCaseFormOptions = {}) {
  const payload = {
    title: form.title.trim(),
    steps: form.steps.map((step, index) => ({
      id: step.id || `step-${index + 1}`,
      title: step.title.trim() || `步骤 ${index + 1}`,
      input: step.input.trim(),
      assertions: step.assertions.map((assertion, assertionIndex) => ({
        id: assertion.id || `assertion-${assertionIndex + 1}`,
        assertion_template_id: assertion.assertion_template_id,
        assertion_params: assertion.assertion_params,
      })),
    })),
    workspace_name: form.workspace_name,
    workspace_base64: form.workspace_base64,
    runner_config: cleanRunnerConfig(form.runner_config),
    notes: form.notes.trim() || undefined,
  };
  return options.includePreserveWorkspace ? { ...payload, preserve_workspace: true } : payload;
}

export function workspaceFileName(locator: string): string {
  return locator.split(":").at(-1) || "workspace.zip";
}
