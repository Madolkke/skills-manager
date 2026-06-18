import type { EvalCaseFormData } from "../components/EvalCaseModal.vue";
import type { EvalSetCase } from "../../../types";

export type CaseSortKey = "position" | "title" | "version";
export type CaseFilter = "all" | "active";

export function filterCases(items: EvalSetCase[], value: string, filter: CaseFilter): EvalSetCase[] {
  const normalized = value.trim().toLowerCase();
  return items.filter((item) => {
    if (filter === "active" && item.case.lifecycle_status !== "active") return false;
    if (!normalized) return true;
    return [item.case.title, item.case_version.input_artifact.content_text, item.case_version.expected_output_artifact.content_text].join(" ").toLowerCase().includes(normalized);
  });
}

export function sortCases(items: EvalSetCase[], sortKey: CaseSortKey): EvalSetCase[] {
  const copy = [...items];
  if (sortKey === "title") return copy.sort((left, right) => left.case.title.localeCompare(right.case.title) || left.position - right.position);
  if (sortKey === "version") return copy.sort((left, right) => right.case_version.version_number - left.case_version.version_number || left.position - right.position);
  return copy.sort((left, right) => left.position - right.position);
}

export function caseLifecycleLabel(status: string): string {
  if (status === "active") return "活跃";
  if (status === "archived") return "归档";
  return status || "未知";
}

export function cleanCaseForm(form: EvalCaseFormData) {
  return {
    title: form.title,
    input_text: form.input_text,
    expected_output: form.expected_output,
    attachment_name: form.attachment_name,
    attachment_base64: form.attachment_base64,
    prompt_template_id: form.prompt_template_id,
    prompt_text: form.prompt_text,
    model_provider_id: form.model_provider_id,
    model_id: form.model_id,
    notes: form.notes.trim() || undefined,
  };
}

export function attachmentFileName(locator: string): string {
  return locator.split(":").at(-1) || "case-attachment.zip";
}
