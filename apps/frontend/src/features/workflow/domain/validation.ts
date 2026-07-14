import type { CollectionDefinition, WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import { projectWorkflowGraph, reachableNodeIds } from "./graph";
import { findCollection, workflowConclusions, workflowSteps } from "./utils";

export function validateWorkflow(bundle: WorkflowBundle, catalog: CollectionDefinition[] = bundle.collectionSnapshots): WorkflowValidationIssue[] {
  const issues: WorkflowValidationIssue[] = [];
  const steps = workflowSteps(bundle);
  const nodes = new Map(bundle.workflow.nodes.map((item) => [item.id, item]));
  if (!bundle.workflow.metadata.name.trim()) add(issues, "MISSING_WORKFLOW_NAME", "error", "工作流名称不能为空。", { type: "metadata" });
  if (!bundle.workflow.metadata.description.trim()) add(issues, "MISSING_WORKFLOW_DESCRIPTION", "error", "工作流说明不能为空。", { type: "metadata" });
  if (!steps.some((step) => step.isStart)) add(issues, "NO_START_STEP", "error", "工作流至少需要一个起始步骤。", { type: "metadata" });
  duplicates(bundle.workflow.nodes, "id", "DUPLICATE_NODE_ID", "节点 ID", issues, { type: "metadata" });
  duplicates(bundle.workflow.inputs, "id", "DUPLICATE_INPUT_ID", "全局输入 ID", issues, { type: "inputs" });
  duplicates(bundle.workflow.inputs, "key", "DUPLICATE_INPUT_KEY", "全局输入 key", issues, { type: "inputs" });
  missingNames(bundle.workflow.inputs, "全局输入名称", issues, { type: "inputs" });
  duplicates(bundle.workflow.deviceRoles, "id", "DUPLICATE_ROLE_ID", "设备角色 ID", issues, { type: "roles" });
  duplicates(bundle.workflow.deviceRoles, "key", "DUPLICATE_ROLE_KEY", "设备角色 key", issues, { type: "roles" });
  duplicates(bundle.collectionSnapshots.map((item) => ({ reference: `${item.id}@${item.revision}` })), "reference", "DUPLICATE_COLLECTION_REFERENCE", "Collection 引用", issues, { type: "collections" });
  for (const definition of bundle.collectionSnapshots) {
    const selection: WorkflowSelection = { type: "collection", id: definition.id, revision: definition.revision };
    if (!definition.metadata.name.trim()) add(issues, "MISSING_COLLECTION_NAME", "error", "采集名称不能为空。", { ...selection, field: "metadata.name" });
    if (!definition.spec.commandTemplate.trim()) add(issues, "MISSING_COLLECTION_COMMAND", "error", `采集“${definition.metadata.name || definition.key}”的采集命令不能为空。`, { ...selection, field: "spec.commandTemplate" });
    else if (/\r|\n/.test(definition.spec.commandTemplate)) add(issues, "MULTILINE_COLLECTION_COMMAND", "error", `采集“${definition.metadata.name || definition.key}”的采集命令必须为单行。`, { ...selection, field: "spec.commandTemplate" });
    duplicates(definition.inputs, "id", "DUPLICATE_COLLECTION_INPUT_ID", "Collection 输入 ID", issues, selection);
    duplicates(definition.inputs, "key", "DUPLICATE_COLLECTION_INPUT_KEY", "Collection 输入 key", issues, selection);
    missingNames(definition.inputs, "Collection 输入名称", issues, selection);
    duplicates(definition.outputs, "id", "DUPLICATE_COLLECTION_OUTPUT_ID", "Collection 输出 ID", issues, selection);
    duplicates(definition.outputs, "key", "DUPLICATE_COLLECTION_OUTPUT_KEY", "Collection 输出 key", issues, selection);
    duplicates(definition.spec.outputSamples, "id", "DUPLICATE_COLLECTION_SAMPLE_ID", "回显示例 ID", issues, selection);
  }

  const roleIds = new Set(bundle.workflow.deviceRoles.map((item) => item.id));
  const workflowInputIds = new Set(bundle.workflow.inputs.map((item) => item.id));
  const workflowInputKeys = new Set(bundle.workflow.inputs.map((item) => item.key.trim()).filter(Boolean));
  for (const step of steps) {
    const selection: WorkflowSelection = { type: "step", id: step.id };
    duplicates(step.collectionCalls, "id", "DUPLICATE_CALL_ID", "采集调用 ID", issues, selection);
    optionalDuplicates(step.collectionCalls, "key", "DUPLICATE_CALL_KEY", "采集调用 key", issues, selection);
    duplicates(step.topology, "id", "DUPLICATE_TRANSITION_ID", "跳转 ID", issues, selection);
    const calls = new Map(step.collectionCalls.map((item) => [item.id, item]));
    const unscopedOutputKeys = new Set<string>();
    for (const call of step.collectionCalls) {
      const definition = findCollection(catalog, call.definition);
      const callSelection: WorkflowSelection = { ...selection, section: "collections", itemId: call.id };
      const callName = call.name || definition?.metadata.name || "未命名采集";
      if (call.sampleCount < 1) add(issues, "INVALID_SAMPLE_COUNT", "error", `采集“${callName}”的采集次数必须大于零。`, { ...callSelection, field: "sampleCount" });
      if (!definition) add(issues, "BROKEN_REFERENCE", "error", `采集“${callName}”引用的定义版本不存在。`, callSelection);
      if (call.deviceRoleId && !roleIds.has(call.deviceRoleId)) add(issues, "BROKEN_REFERENCE", "error", `采集“${call.name}”引用的设备角色不存在。`, { ...callSelection, field: "deviceRoleId" });
      definition?.inputs.forEach((input) => {
        const binding = call.inputBindings[input.id];
        if (input.required && (!binding || (binding.kind === "literal" && (binding.value === undefined || binding.value === "")))) {
          add(issues, "MISSING_REQUIRED_BINDING", "error", `采集“${callName}”尚未绑定必填参数“${input.name}”。`, { ...callSelection, field: `binding.${input.id}` });
        }
        if (binding && !validBinding(binding, workflowInputIds, calls, catalog)) add(issues, "BROKEN_REFERENCE", "error", `采集“${callName}”的参数“${input.name}”引用无效。`, { ...callSelection, field: `binding.${input.id}` });
      });
      if (definition && !call.key.trim()) {
        definition.outputs.forEach((output) => {
          const key = output.key.trim();
          if (!key) return;
          if (workflowInputKeys.has(key) || unscopedOutputKeys.has(key)) {
            add(issues, "UNSCOPED_OUTPUT_CONFLICT", "error", `采集“${callName}”直接暴露的输出字段“${key}”与 Workflow 全局输入或其他直接输出重名，请填写调用 Key 作为命名空间。`, callSelection);
          }
          unscopedOutputKeys.add(key);
        });
      }
    }
    step.topology.forEach((item) => {
      const target = nodes.get(item.target.id);
      if (!target) add(issues, "BROKEN_REFERENCE", "error", `步骤“${step.name}”存在无效跳转目标。`, selection);
    });
  }

  const reachable = reachableNodeIds(bundle);
  [...steps.filter((item) => !item.isStart), ...workflowConclusions(bundle)].forEach((node) => {
    if (!reachable.has(node.id)) add(issues, "UNREACHABLE_NODE", "warning", `节点“${node.name}”无法从任何起始步骤到达。`, "stepType" in node ? { type: "step", id: node.id } : { type: "conclusion", id: node.id });
  });
  const cyclicSteps = new Set(projectWorkflowGraph(bundle).edges.filter((item) => item.loop).flatMap((item) => [item.source, item.target]));
  if (cyclicSteps.size) {
    const first = steps.find((item) => cyclicSteps.has(item.id));
    const names = steps.filter((item) => cyclicSteps.has(item.id)).map((item) => item.name).join(" -> ");
    if (first) add(issues, "POTENTIAL_CYCLE", "warning", `检测到可能的循环路径：${names}。`, { type: "step", id: first.id });
  }
  return issues;
}

function validBinding(
  binding: { kind: string; reference: Record<string, string> },
  workflowInputs: Set<string>,
  calls: Map<string, { definition: { id: string; revision: number } }>,
  definitions: CollectionDefinition[],
): boolean {
  if (binding.kind === "literal") return true;
  if (binding.kind === "workflow_input") return workflowInputs.has(binding.reference.input_id ?? "");
  if (binding.kind !== "collection_output") return false;
  const call = calls.get(binding.reference.call_id ?? "");
  const definition = call && findCollection(definitions, call.definition);
  return Boolean(definition?.outputs.some((item) => item.id === binding.reference.output_id));
}

function duplicates(items: Array<Record<string, unknown>>, field: string, code: string, label: string, issues: WorkflowValidationIssue[], selection: WorkflowSelection): void {
  const counts = new Map<string, number>();
  items.forEach((item) => counts.set(String(item[field] ?? "").trim(), (counts.get(String(item[field] ?? "").trim()) ?? 0) + 1));
  counts.forEach((count, value) => {
    if (!value || count > 1) add(issues, code, "error", value ? `${label}“${value}”重复。` : `${label}不能为空。`, selection);
  });
}

function optionalDuplicates(items: Array<Record<string, unknown>>, field: string, code: string, label: string, issues: WorkflowValidationIssue[], selection: WorkflowSelection): void {
  const counts = new Map<string, number>();
  items.forEach((item) => {
    const value = String(item[field] ?? "").trim();
    if (value) counts.set(value, (counts.get(value) ?? 0) + 1);
  });
  counts.forEach((count, value) => {
    if (count > 1) add(issues, code, "error", `${label}“${value}”重复。`, selection);
  });
}

function missingNames(items: Array<{ name: string }>, label: string, issues: WorkflowValidationIssue[], selection: WorkflowSelection): void {
  items.forEach((item) => {
    if (!item.name.trim()) add(issues, "MISSING_PARAMETER_NAME", "error", `${label}不能为空。`, selection);
  });
}

function add(issues: WorkflowValidationIssue[], code: string, severity: "error" | "warning", message: string, selection: WorkflowSelection): void {
  issues.push({ id: `${code.toLowerCase()}-${"id" in selection ? selection.id : selection.type}-${issues.length}`, code, severity, message, selection });
}
