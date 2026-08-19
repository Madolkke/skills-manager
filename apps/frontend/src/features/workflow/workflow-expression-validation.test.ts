// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";
import { api } from "../../lib/api";
import type { CollectionDefinition, WorkflowBundle, WorkflowStep } from "../../types";
import { useWorkflowExpressionValidation } from "./useWorkflowExpressionValidation";

afterEach(() => { vi.restoreAllMocks(); });

describe("Workflow expression batch validation", () => {
  it("debounces by step, aborts stale requests, and aggregates stable sample warnings", async () => {
    const signals: AbortSignal[] = [];
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockImplementation(async (expressions, _environment, signal) => {
      if (signal) signals.push(signal);
      return { validations: expressions.map((item) => ({
        id: item.id,
        inferredType: { kind: "boolean" },
        diagnostics: [{ severity: "warning", code: "SAMPLE_INDEX_REQUIRED", message: "需要下标", start: 0, end: 10 }],
      })) };
    });
    const bundle = ref<WorkflowBundle | null>(workflowBundle());
    const current = findStep(bundle.value!, "step-current");
    current.collectionCalls[0]!.sampleCount = 2;
    current.topology[0]!.conditionExpression = "outputs.status.version";
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;

    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(1);
    current.topology[0]!.conditionExpression = "outputs.status[0].version";
    await new Promise((resolve) => window.setTimeout(resolve, 50));
    current.topology[0]!.conditionExpression = "outputs.status.version";
    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(2);

    expect(validation.mock.calls[1]?.[0]).toEqual([{ id: "step-current:path-current", source: "outputs.status.version" }]);
    expect(signals[0]?.aborted).toBe(true);
    await expect.poll(() => result.issues.value.map((item) => item.code)).toEqual(["SAMPLE_INDEX_REQUIRED"]);
    expect(result.issues.value[0]?.id).toBe("workflow-issue/sample_index_required/step/step-current//paths/path-current/conditionExpression/0");
    scope.stop();
  });

  it("retains diagnostics for unchanged expressions when one step batch fails", async () => {
    let failOtherStep = false;
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockImplementation(async (expressions) => {
      if (failOtherStep && expressions.some((item) => item.id.startsWith("step-other:"))) throw new Error("network failure");
      return {
        validations: expressions.map((item) => ({
          id: item.id,
          inferredType: { kind: "boolean" },
          diagnostics: [{ severity: "warning", code: "SAMPLE_INDEX_REQUIRED", message: `诊断 ${item.id}`, start: 0, end: 10 }],
        })),
      };
    });
    const bundle = ref<WorkflowBundle | null>(workflowBundle());
    const current = findStep(bundle.value!, "step-current");
    const other = findStep(bundle.value!, "step-other");
    current.collectionCalls[0]!.sampleCount = 2;
    current.topology[0]!.conditionExpression = "outputs.status.version";
    other.collectionCalls[0]!.key = "other";
    other.collectionCalls[0]!.sampleCount = 2;
    other.topology = [{ id: "path-other", target: { id: "step-current" }, conditionText: "", conditionExpression: "outputs.other.version" }];
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;

    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(2);
    await expect.poll(() => Object.keys(result.diagnostics.value).sort()).toEqual(["step-current:path-current", "step-other:path-other"]);
    failOtherStep = true;
    current.topology[0]!.conditionExpression = "outputs.status[0].version";

    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(4);
    await expect.poll(() => result.diagnostics.value["step-current:path-current"]?.[0]?.message).toBe("诊断 step-current:path-current");
    expect(result.diagnostics.value["step-other:path-other"]?.[0]?.message).toBe("诊断 step-other:path-other");
    scope.stop();
  });

  it("promotes blocking config subscript diagnostics to workflow errors", async () => {
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockResolvedValue({
      validations: [{
        id: "step-current:path-current",
        inferredType: { kind: "unknown" },
        diagnostics: [
          { severity: "warning", code: "CONFIG_STRING_SUBSCRIPT_FORBIDDEN", message: "不支持字符串下标", start: 0, end: 10 },
          { severity: "warning", code: "CONFIG_ARRAY_INDEX_INVALID", message: "数组下标必须是整数", start: 0, end: 10 },
        ],
      }],
    });
    const bundle = ref<WorkflowBundle | null>(workflowBundle());
    findStep(bundle.value!, "step-current").topology[0]!.conditionExpression = "config.interface['name']";
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;

    await expect.poll(() => result.issues.value).toHaveLength(2);
    expect(result.issues.value.map((item) => [item.code, item.severity])).toEqual([
      ["CONFIG_STRING_SUBSCRIPT_FORBIDDEN", "error"],
      ["CONFIG_ARRAY_INDEX_INVALID", "error"],
    ]);
    scope.stop();
    expect(validation).toHaveBeenCalledTimes(1);
  });

  it("promotes invalid config array indexes to workflow errors", async () => {
    vi.spyOn(api, "validateWorkflowExpressions").mockResolvedValue({
      validations: [{
        id: "step-current:path-current", inferredType: { kind: "unknown" },
        diagnostics: [{ severity: "warning", code: "CONFIG_ARRAY_INDEX_INVALID", message: "只允许整数下标", start: 0, end: 10 }],
      }],
    });
    const bundle = ref<WorkflowBundle | null>(workflowBundle());
    findStep(bundle.value!, "step-current").topology[0]!.conditionExpression = "config.interfaces[1.5]";
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;

    await expect.poll(() => result.issues.value).toHaveLength(1);
    expect(result.issues.value[0]).toMatchObject({ code: "CONFIG_ARRAY_INDEX_INVALID", severity: "error" });
    scope.stop();
  });

  it("drops stale diagnostics when the environment changes and validation fails", async () => {
    const validation = vi.spyOn(api, "validateWorkflowExpressions")
      .mockResolvedValueOnce({ validations: [{
        id: "step-current:path-current",
        inferredType: { kind: "boolean" },
        diagnostics: [{ severity: "warning", code: "SAMPLE_INDEX_REQUIRED", message: "旧环境诊断", start: 0, end: 10 }],
      }] })
      .mockRejectedValue(new Error("network failure"));
    const bundle = ref<WorkflowBundle | null>(workflowBundle());
    findStep(bundle.value!, "step-current").topology[0]!.conditionExpression = "outputs.status.version";
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;

    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(1);
    await expect.poll(() => result.diagnostics.value["step-current:path-current"]?.[0]?.message).toBe("旧环境诊断");
    bundle.value!.collectionSnapshots[0]!.outputs[0]!.schema = { type: "integer", title: "整数", description: "" };

    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(2);
    await expect.poll(() => Object.keys(result.diagnostics.value)).toHaveLength(0);
    scope.stop();
  });
});

function workflowBundle(): WorkflowBundle {
  const definition = collectionDefinition();
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 1,
      metadata: { name: "Variables", code: "", description: "Variables", symptom: "", industry: "", device: "", versions: [] },
      inputs: [],
      deviceRoles: [],
      nodes: [
        step("step-other", "其他检查", [{ id: "call-other", key: "status", name: "接口状态", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} }]),
        step("step-current", "当前检查", [{ id: "call-current", key: "status", name: "接口状态", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} }]),
      ],
    },
    collectionSnapshots: [definition],
  };
}

function findStep(bundle: WorkflowBundle, id: string): WorkflowStep {
  return bundle.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === id)!;
}

function step(id: string, name: string, collectionCalls: WorkflowStep["collectionCalls"]): WorkflowStep {
  return {
    id,
    name,
    description: "",
    isStart: id === "step-current",
    collectionCalls,
    topology: id === "step-current"
      ? [{ id: "path-current", target: { id: "step-other" }, conditionText: "", conditionExpression: "" }]
      : [],
    stepType: "expression",
  };
}

function collectionDefinition(): CollectionDefinition {
  return {
    id: "collection-status",
    revision: 1,
    key: "status",
    metadata: { name: "接口状态", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display interface", outputSamples: [] },
    inputs: [],
    outputs: [{ id: "output-version", key: "version", required: true, schema: { type: "string", title: "版本", description: "" } }],
  };
}
