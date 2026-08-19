// @vitest-environment jsdom

import { CompletionContext, type CompletionResult } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, ref } from "vue";
import { api } from "../../lib/api";
import type { CollectionDefinition, WorkflowBundle, WorkflowStep } from "../../types";
import { validateWorkflow } from "./domain/validation";
import { useWorkflowExpressionValidation } from "./useWorkflowExpressionValidation";
import { createWorkflowExpressionCompletionSource } from "./workflowExpressionCompletion";
import { workflowExpressionEnvironment, workflowExpressionVariables } from "./workflowExpressionVariables";
import { workflowExpressionVisibleSteps } from "./workflowExpressionScope";

afterEach(() => { vi.restoreAllMocks(); });

describe("Workflow graph-scoped expression environment", () => {
  it("projects the current step and transitive predecessors in document order", () => {
    const bundle = graphBundle();
    const visible = workflowExpressionVisibleSteps(bundle, "step-current");
    const references = workflowExpressionVariables(bundle, "step-current").map((item) => item.reference);

    expect(visible.map((step) => step.id)).toEqual(["step-root", "step-previous", "step-current"]);
    expect(references).toEqual([
      "outputs.root.version",
      "outputs.previous.version",
      "outputs.version",
    ]);
    expect(references.some((reference) => reference.includes("future"))).toBe(false);
    expect(references.some((reference) => reference.includes("unrelated"))).toBe(false);
  });

  it("keeps keyed outputs first-wins across visible steps", () => {
    const bundle = graphBundle();
    const later = structuredClone(bundle.collectionSnapshots[0]!);
    later.id = "collection-later";
    later.outputs[0]!.schema = { type: "integer", title: "后续版本", description: "" };
    bundle.collectionSnapshots.push(later);
    const previous = findStep(bundle, "step-previous");
    previous.collectionCalls[0]!.key = "root";
    previous.collectionCalls[0]!.definition = { id: later.id, revision: later.revision };

    const candidates = workflowExpressionVariables(bundle, "step-current")
      .filter((item) => item.reference === "outputs.root.version");

    expect(candidates).toHaveLength(1);
    expect(candidates[0]).toMatchObject({ source: "根步骤 · 根采集" });
    expect(workflowExpressionEnvironment(bundle, "step-current").outputs.root)
      .toMatchObject({ fields: { version: { type: "string" } } });
  });

  it("handles cycles without losing stable document order", () => {
    const bundle = graphBundle();
    findStep(bundle, "step-future").topology = [path("path-cycle", "step-current")];

    expect(workflowExpressionVisibleSteps(bundle, "step-current").map((step) => step.id)).toEqual([
      "step-root",
      "step-previous",
      "step-current",
      "step-future",
    ]);
    expect(workflowExpressionVisibleSteps(bundle).map((step) => step.id)).toEqual([
      "step-root",
      "step-previous",
      "step-current",
      "step-future",
      "step-unrelated",
    ]);
  });

  it("projects object and array fields from an unscoped predecessor", async () => {
    const bundle = graphBundle();
    findStep(bundle, "step-current").collectionCalls[0]!.key = "current";
    findStep(bundle, "step-previous").collectionCalls[0]!.key = "";
    bundle.collectionSnapshots[0]!.outputs.push(
      {
        id: "output-details",
        key: "details",
        required: true,
        schema: {
          type: "object",
          title: "详情",
          description: "",
          properties: { status: { type: "string", title: "状态", description: "" } },
          required: ["status"],
          additionalProperties: false,
        },
      },
      {
        id: "output-items",
        key: "items",
        required: true,
        schema: {
          type: "array",
          title: "项目",
          description: "",
          items: {
            type: "object",
            title: "项目元素",
            description: "",
            properties: { id: { type: "string", title: "ID", description: "" } },
            required: ["id"],
            additionalProperties: false,
          },
        },
      },
    );
    const variables = workflowExpressionVariables(bundle, "step-current");
    const references = variables.map((item) => item.reference);
    const source = createWorkflowExpressionCompletionSource(() => variables);

    expect(references).toEqual(expect.arrayContaining([
      "outputs.details",
      "outputs.details.status",
      "outputs.items",
      "outputs.items[0]",
      "outputs.items[0].id",
    ]));
    expect((await completion(source, "outputs.details.sta"))?.options.map((item) => item.label))
      .toEqual(["outputs.details.status"]);
    expect((await completion(source, "outputs.items[0].i"))?.options.map((item) => item.label))
      .toEqual(["outputs.items[0].id"]);
  });

  it("projects prototype-named output keys without inherited-property collisions", () => {
    const bundle = graphBundle();
    bundle.collectionSnapshots[0]!.outputs[0]!.key = "constructor";
    const environment = workflowExpressionEnvironment(bundle, "step-current");

    expect(environment.outputs.constructor).toBeDefined();
    expect(Object.keys(environment.outputs)).toContain("constructor");
  });

  it("suppresses direct fields that conflict across visible predecessors", () => {
    const bundle = graphBundle();
    bundle.collectionSnapshots[0]!.outputs.push({
      id: "output-details",
      key: "details",
      required: true,
      schema: {
        type: "object",
        title: "详情",
        description: "",
        properties: { status: { type: "string", title: "状态", description: "" } },
        required: ["status"],
        additionalProperties: false,
      },
    }, {
      id: "output-invalid",
      key: "router-status",
      required: true,
      schema: { type: "string", title: "非法字段", description: "" },
    });
    findStep(bundle, "step-previous").collectionCalls[0]!.key = "";

    const references = workflowExpressionVariables(bundle, "step-current").map((item) => item.reference);
    const conflicts = validateWorkflow(bundle)
      .filter((item) => item.code === "UNSCOPED_OUTPUT_CONFLICT")
      .map((item) => ({
        itemId: "itemId" in item.selection ? item.selection.itemId : undefined,
        field: item.message.match(/字段“([^”]+)”/)?.[1],
      }));

    expect(references).not.toContain("outputs.details");
    expect(references).not.toContain("outputs.router-status");
    expect(workflowExpressionEnvironment(bundle, "step-current").outputs.details).toBeUndefined();
    expect(conflicts).toEqual([
      { itemId: "call-previous", field: "version" },
      { itemId: "call-current", field: "version" },
      { itemId: "call-previous", field: "details" },
      { itemId: "call-current", field: "details" },
    ]);
  });

  it("does not project an unscoped multi-sample call", () => {
    const bundle = graphBundle();
    findStep(bundle, "step-current").collectionCalls[0]!.sampleCount = 2;

    expect(workflowExpressionVariables(bundle, "step-current").map((item) => item.reference))
      .not.toContain("outputs.version");
    expect(workflowExpressionEnvironment(bundle, "step-current").outputs.version).toBeUndefined();
    expect(validateWorkflow(bundle).map((item) => item.code)).toContain("MULTI_SAMPLE_CALL_KEY_REQUIRED");
  });

  it("sends the same graph-scoped outputs used by completion", async () => {
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockResolvedValue({ validations: [] });
    const bundle = ref<WorkflowBundle | null>(graphBundle());
    findStep(bundle.value!, "step-current").topology[0]!.conditionExpression = "outputs.root.version == outputs.version";
    const scope = effectScope();
    scope.run(() => useWorkflowExpressionValidation(bundle));

    await expect.poll(() => validation.mock.calls.length, { timeout: 1000 }).toBe(1);
    expect(validation.mock.calls[0]?.[1].outputs).toEqual(expect.objectContaining({
      root: expect.any(Object),
      previous: expect.any(Object),
      version: expect.any(Object),
    }));
    expect(validation.mock.calls[0]?.[1].outputs.future).toBeUndefined();
    expect(validation.mock.calls[0]?.[1].outputs.unrelated).toBeUndefined();
    scope.stop();
  });
});

async function completion(
  source: ReturnType<typeof createWorkflowExpressionCompletionSource>,
  doc: string,
): Promise<CompletionResult | null> {
  const state = EditorState.create({ doc, selection: { anchor: doc.length } });
  return await source(new CompletionContext(state, doc.length, false)) as CompletionResult | null;
}

function graphBundle(): WorkflowBundle {
  const definition = collectionDefinition();
  const call = (id: string, key: string, name: string) => ({
    id,
    key,
    name,
    definition: { id: definition.id, revision: definition.revision },
    sampleCount: 1,
    inputBindings: {},
  });
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-graph",
      revision: 1,
      metadata: { name: "Graph", code: "", description: "Graph", symptom: "", industry: "", device: "", versions: [] },
      inputs: [],
      deviceRoles: [],
      nodes: [
        { ...step("step-root", "根步骤", [call("call-root", "root", "根采集")]), isStart: true, topology: [path("path-root", "step-previous")] },
        { ...step("step-previous", "前置步骤", [call("call-previous", "previous", "前置采集")]), topology: [path("path-previous", "step-current")] },
        { ...step("step-current", "当前步骤", [call("call-current", "", "当前直接")]), topology: [path("path-future", "step-future")] },
        step("step-future", "未来步骤", [call("call-future", "future", "未来采集")]),
        step("step-unrelated", "无关步骤", [call("call-unrelated", "unrelated", "无关采集")]),
      ],
    },
    collectionSnapshots: [definition],
  };
}

function step(id: string, name: string, collectionCalls: WorkflowStep["collectionCalls"]): WorkflowStep {
  return { id, name, description: "", isStart: false, collectionCalls, topology: [], stepType: "expression" };
}

function path(id: string, targetId: string) {
  return { id, target: { id: targetId }, conditionText: "", conditionExpression: "" };
}

function findStep(bundle: WorkflowBundle, id: string): WorkflowStep {
  return bundle.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === id)!;
}

function collectionDefinition(): CollectionDefinition {
  return {
    id: "collection-status",
    revision: 1,
    key: "status",
    metadata: { name: "接口状态", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display interface", outputSamples: [] },
    inputs: [],
    outputs: [
      { id: "output-version", key: "version", required: true, schema: { type: "string", title: "版本", description: "" } },
    ],
  };
}
