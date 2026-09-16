import { computed, getCurrentScope, onScopeDispose, ref, watch, type Ref } from "vue";
import { api } from "../../lib/api";
import type { WorkflowBundle, WorkflowExpressionBatchItem, WorkflowExpressionEnvironment, WorkflowSelection, WorkflowValidationIssue } from "../../types";
import { findCollection, workflowConclusions, workflowSteps } from "./domain/utils";
import { workflowBindingVisibleCalls } from "./workflowExpressionScope";
import { workflowConclusionExpressionEnvironment, workflowExpressionEnvironment, workflowExpressionEnvironmentForSteps } from "./workflowExpressionVariables";
import { workflowTemplateExpressions } from "./workflowTemplate";

type Field = { selection: WorkflowSelection; expression: WorkflowExpressionBatchItem };
type Batch = { environment: WorkflowExpressionEnvironment; fields: Field[] };

/** 绑定与模板复用服务器表达式规则；仅当前请求可以更新诊断。 */
export function useWorkflowFieldValidation(bundle: Ref<WorkflowBundle | null>) {
  const issues = ref<WorkflowValidationIssue[]>([]);
  const batches = computed(() => bundle.value ? fieldBatches(bundle.value) : []);
  const fingerprint = computed(() => JSON.stringify(batches.value));
  let timer: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | undefined;
  let generation = 0;
  watch(fingerprint, () => {
    clearTimeout(timer);
    controller?.abort();
    const current = ++generation;
    issues.value = [];
    const pending = batches.value;
    if (!pending.length) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      const results = await Promise.allSettled(pending.map(batch => api.validateWorkflowExpressions(batch.fields.map(field => field.expression), batch.environment, controller!.signal)));
      if (current !== generation) return;
      issues.value = results.flatMap((result, index) => {
        const batch = pending[index]!;
        if (result.status !== "fulfilled") return batch.fields.map(field => ({ id: `validation-unavailable:${field.expression.id}`, code: "EXPRESSION_VALIDATION_UNAVAILABLE", severity: "warning" as const, message: "表达式校验暂不可用，保存时将由服务端最终校验。", selection: field.selection }));
        return result.value.validations.flatMap(validation => {
          const field = batch.fields.find(item => item.expression.id === validation.id);
          if (!field) return [];
          const diagnostics = [...validation.diagnostics];
          if (validation.assignable === false && !diagnostics.length) diagnostics.push({ code: "INCOMPATIBLE_BINDING_SCHEMA", severity: "error", message: "表达式结果类型与参数 Schema 不兼容。", start: 0, end: field.expression.source.length });
          return diagnostics.map((item, offset) => ({ id: `field-expression:${validation.id}:${item.code}:${offset}`, code: item.code, severity: field.expression.target_schema || item.code.startsWith("FUNCTION_") || item.code === "UNREGISTERED_CALL" ? "error" as const : item.severity, message: item.message, selection: field.selection }));
        });
      });
    }, 300);
  }, { immediate: true });
  if (getCurrentScope()) onScopeDispose(() => { generation++; clearTimeout(timer); controller?.abort(); });
  return { issues };
}

/** 按字段所属作用域批量投影，绑定仅能看见前序采集。 */
function fieldBatches(bundle: WorkflowBundle): Batch[] {
  const batches: Batch[] = [];
  for (const step of workflowSteps(bundle)) {
    const templates: Field[] = [];
    for (const path of step.topology) templates.push(...templateFields(path.conditionText, { type: "step", id: step.id, section: "paths", itemId: path.id, field: "conditionText" }));
    if (templates.length) batches.push({ environment: workflowExpressionEnvironment(bundle, step.id), fields: templates });
    for (const call of step.collectionCalls) {
      const definition = findCollection(bundle.collectionSnapshots, call.definition);
      if (!definition) continue;
      const fields: Field[] = definition.inputs.flatMap(input => {
        const binding = call.inputBindings[input.id];
        if (binding?.kind !== "expression" || !binding.expression.trim()) return [];
        return [{ selection: { type: "step", id: step.id, section: "collections", itemId: call.id, field: `binding.${input.id}` }, expression: { id: `binding:${call.id}:${input.id}`, source: binding.expression, target_schema: input.schema } }];
      });
      if (!fields.length) continue;
      const visible = workflowBindingVisibleCalls(bundle, step.id, call.id);
      const ids = new Set(visible.map(item => item.call.id));
      const steps = [...new Map(visible.map(item => [item.step.id, item.step])).values()].map(item => ({ ...item, collectionCalls: item.collectionCalls.filter(value => ids.has(value.id)) }));
      batches.push({ fields, environment: workflowExpressionEnvironmentForSteps(bundle, steps) });
    }
  }
  for (const conclusion of workflowConclusions(bundle)) {
    const fields = (["rootCause", "repairRecommendation"] as const).flatMap(field => templateFields(conclusion[field], { type: "conclusion", id: conclusion.id, field }));
    if (fields.length) batches.push({ fields, environment: workflowConclusionExpressionEnvironment(bundle, conclusion.id) });
  }
  batches.forEach((batch, batchIndex) => batch.fields.forEach((field, fieldIndex) => { field.expression.id = `field:${batchIndex}:${fieldIndex}`; }));
  return batches;
}

/** 为每个完整模板表达式保留原字段定位。 */
function templateFields(source: string, selection: WorkflowSelection): Field[] {
  return workflowTemplateExpressions(source).filter(item => item.expression.trim()).map((item, index) => ({ selection, expression: { id: `template:${JSON.stringify(selection)}:${index}`, source: item.expression.trim() } }));
}
