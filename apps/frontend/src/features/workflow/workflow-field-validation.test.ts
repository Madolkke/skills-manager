// @vitest-environment jsdom
import { effectScope, nextTick, ref } from "vue";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { WorkflowBundle, WorkflowStep } from "../../types";
import fixture from "./fixtures/complex-schema-workflow.json";
import { useWorkflowFieldValidation } from "./useWorkflowFieldValidation";

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

it("绑定按前序作用域校验目标类型，模板错误定位到原字段", async () => {
  vi.useFakeTimers();
  const bundle = ref(JSON.parse(JSON.stringify(fixture)) as WorkflowBundle);
  const step = bundle.value.workflow.nodes[0] as WorkflowStep;
  const call = step.collectionCalls[2]!;
  const input = Object.keys(call.inputBindings)[0]!;
  call.inputBindings[input] = { kind: "expression", reference: {}, expression: "inputs.index" };
  step.topology[0]!.conditionText = "结果 {{ sum(1) }}";
  const spy = vi.spyOn(api, "validateWorkflowExpressions").mockImplementation(async expressions => ({ validations: expressions.map(item => ({ id: item.id, inferredType: { kind: "integer" }, ...(item.target_schema ? { assignable: false } : {}), diagnostics: item.source === "sum(1)" ? [{ code: "FUNCTION_ARGUMENT_TYPE_MISMATCH", message: "类型错误", severity: "error", start: 4, end: 5 }] : [] })) }));
  const scope = effectScope();
  const result = scope.run(() => useWorkflowFieldValidation(bundle))!;
  await vi.advanceTimersByTimeAsync(300);
  expect(result.issues.value.some(item => item.code === "INCOMPATIBLE_BINDING_SCHEMA" && item.selection.field === `binding.${input}`)).toBe(true);
  expect(result.issues.value.some(item => item.code === "FUNCTION_ARGUMENT_TYPE_MISMATCH" && item.selection.field === "conditionText")).toBe(true);
  const request = spy.mock.calls.find(([expressions]) => expressions.some(item => item.target_schema));
  expect(Object.keys(request![1].outputs).sort()).toEqual(["interfaces", "routes"]);
  call.inputBindings[input] = { kind: "expression", reference: {}, expression: "outputs.routes.routes[0].vrf" };
  await nextTick();
  expect(request![2]?.aborted).toBe(true);
  scope.stop();
});
