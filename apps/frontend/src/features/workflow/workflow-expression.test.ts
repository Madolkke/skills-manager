// @vitest-environment jsdom

import { CompletionContext, completionStatus, selectedCompletionIndex, type CompletionResult } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { mount } from "@vue/test-utils";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { api } from "../../lib/api";
import type { CollectionDefinition, WorkflowBundle, WorkflowStep } from "../../types";
import WorkflowExpressionEditor from "./components/WorkflowExpressionEditor.vue";
import { useWorkflowExpressionValidation } from "./useWorkflowExpressionValidation";
import { createWorkflowPathEditing } from "./workflowPathEditing";
import {
  acceptWorkflowExpressionCompletion,
  createWorkflowExpressionCompletionSource,
  normalizeWorkflowExpressionInput,
  shouldOpenWorkflowExpressionCompletion,
} from "./workflowExpressionCompletion";
import {
  filterWorkflowExpressionVariables,
  workflowExpressionEnvironment,
  workflowExpressionVariables,
} from "./workflowExpressionVariables";

beforeAll(() => {
  if (!("ResizeObserver" in globalThis)) {
    Object.defineProperty(globalThis, "ResizeObserver", {
      value: class { observe() {} unobserve() {} disconnect() {} },
    });
  }
  if (!Range.prototype.getClientRects) {
    Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
  }
  if (!Range.prototype.getBoundingClientRect) {
    Range.prototype.getBoundingClientRect = () => new DOMRect();
  }
});

afterEach(() => { document.body.innerHTML = ""; vi.restoreAllMocks(); });

describe("Workflow expression variables", () => {
  it("projects inputs and only the current step output namespace", () => {
    const variables = workflowExpressionVariables(workflowBundle(), "step-current");

    expect(variables.map((item) => item.reference)).toEqual([
      "inputs.tenant",
      "outputs.status.version",
      "outputs.version",
    ]);
    expect(variables.filter((item) => item.reference === "outputs.status.version").map((item) => item.source)).toEqual([
      "当前检查 · 接口状态",
    ]);
    expect(variables.some((item) => item.reference.includes("other_input"))).toBe(false);
  });

  it("matches full references, call paths, and leaf keys", () => {
    const variables = workflowExpressionVariables(workflowBundle(), "step-current");

    expect(filterWorkflowExpressionVariables(variables, "inputs.ten").map((item) => item.reference)).toEqual(["inputs.tenant"]);
    expect(filterWorkflowExpressionVariables(variables, "status.ver")).toHaveLength(1);
    expect(filterWorkflowExpressionVariables(variables, "ver").map((item) => item.kind)).toEqual(["output", "output"]);
  });

  it("provides explicit completion at an empty cursor and suppresses quoted text", async () => {
    const variables = workflowExpressionVariables(workflowBundle(), "step-current");
    const source = createWorkflowExpressionCompletionSource(() => variables);
    const explicit = await completion(source, "", true);
    const automatic = await completion(source, "status.ver", false);
    const quoted = await completion(source, "\"ver", false);
    const readonlyState = EditorState.create({ extensions: EditorState.readOnly.of(true) });
    const readonlyResult = await source(new CompletionContext(readonlyState, 0, true));

    expect(explicit?.options).toHaveLength(3);
    expect(automatic?.options.map((item) => item.label)).toEqual(["outputs.status.version"]);
    expect(quoted).toBeNull();
    expect(readonlyResult).toBeNull();
    expect(normalizeWorkflowExpressionInput("a\r\n&&\nb")).toBe("a && b");
    expect(shouldOpenWorkflowExpressionCompletion(variables, "inputs.ten")).toBe(true);
    expect(shouldOpenWorkflowExpressionCompletion(variables, "\"inputs.ten")).toBe(false);
    expect(shouldOpenWorkflowExpressionCompletion(variables, "unknown")).toBe(false);
  });

  it("exposes unique unscoped output fields and suppresses conflicts", async () => {
    const bundle = workflowBundle();
    const variables = workflowExpressionVariables(bundle, "step-current");
    const source = createWorkflowExpressionCompletionSource(() => variables);

    expect((await completion(source, "outputs.ver", false))?.options.map((item) => item.label)).toEqual(["outputs.version"]);
    expect(workflowExpressionEnvironment(bundle, "step-current").outputs.version).toMatchObject({
      sampleCount: 1,
      schema: { type: "string" },
    });

    const definition = bundle.collectionSnapshots[0]!;
    definition.outputs.push({
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
    });
    const withObject = workflowExpressionVariables(bundle, "step-current");
    expect(withObject.map((item) => item.reference)).toContain("outputs.details.status");

    bundle.workflow.inputs.push(parameter("global-version", "version"));
    expect(workflowExpressionVariables(bundle, "step-current").map((item) => item.reference)).not.toContain("outputs.version");

    bundle.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-current")!.collectionCalls.push({
      id: "call-unscoped-duplicate",
      key: "",
      name: "重复直接输出",
      definition: { id: definition.id, revision: definition.revision },
      sampleCount: 1,
      inputBindings: {},
    });
    expect(workflowExpressionVariables(bundle, "step-current").map((item) => item.reference)).not.toContain("outputs.details");
  });

  it("completes multi-sample fields only after a supported closed non-slice index", async () => {
    const bundle = workflowBundle();
    const current = bundle.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-current")!;
    current.collectionCalls[0]!.sampleCount = 3;
    const variables = workflowExpressionVariables(bundle, current.id);
    const source = createWorkflowExpressionCompletionSource(() => variables);

    expect(variables.filter((item) => item.reference.startsWith("outputs.status")).map((item) => item.reference)).toEqual(["outputs.status"]);
    expect(await completion(source, "outputs.status[", false)).toBeNull();
    expect((await completion(source, "outputs.status[0].ver", false))?.options.map((item) => item.label)).toEqual(["outputs.status[0].version"]);
    expect((await completion(source, "outputs.status[-1].", false))?.options.map((item) => item.label)).toEqual(["outputs.status[-1].version"]);
    expect((await completion(source, "outputs.status[inputs.index].ver", false))?.options.map((item) => item.label)).toEqual(["outputs.status[inputs.index].version"]);
    expect(await completion(source, "outputs.status['zero'].ver", false)).toBeNull();
    expect(await completion(source, "outputs.status[1.5].ver", false)).toBeNull();
    expect(await completion(source, "outputs.status[true].ver", false)).toBeNull();
    expect(await completion(source, "outputs.status[0][0].ver", false)).toBeNull();
    expect(await completion(source, "outputs.status[0][", false)).toBeNull();
    expect(await completion(source, "outputs.status[1:].", true)).toBeNull();
    expect(workflowExpressionEnvironment(bundle, current.id).outputs.status).toMatchObject({
      sampleCount: 3,
      fields: { version: expect.any(Object) },
    });
  });

  it("keeps continuous expression edits in the same history group", () => {
    const bundle = ref(workflowBundle());
    const groups: string[] = [];
    const editing = createWorkflowPathEditing(bundle, (_recipe, group) => { groups.push(group ?? ""); });

    editing.updatePath("step-current", "path-current", { conditionExpression: "inputs.tenant" });
    editing.updatePath("step-current", "path-current", { conditionExpression: "inputs.tenant == 'acme'" });

    expect(groups).toEqual([
      "path:step-current:path-current:conditionExpression",
      "path:step-current:path-current:conditionExpression",
    ]);
  });
});

describe("WorkflowExpressionEditor", () => {
  it("accepts an active completion with Tab and leaves Tab free when the menu is closed", async () => {
    const variables = workflowExpressionVariables(workflowBundle(), "step-current");
    const wrapper = mount(WorkflowExpressionEditor, {
      attachTo: document.body,
      props: { value: "", variables, readonly: false },
    });
    await nextTick();
    const view = EditorView.findFromDOM(wrapper.get(".cm-editor").element as HTMLElement)!;
    view.focus();
    view.dispatch({ changes: { from: 0, insert: "ver" }, selection: { anchor: 3 }, userEvent: "input.type" });

    await expect.poll(() => completionStatus(view.state), { timeout: 1000 }).toBe("active");
    await expect.poll(() => document.querySelector(".cm-tooltip-autocomplete"), { timeout: 1000 }).not.toBeNull();
    expect(selectedCompletionIndex(view.state)).toBe(0);
    const completionAccepted = acceptWorkflowExpressionCompletion(view);
    await nextTick();
    expect(view.state.doc.toString()).toBe("outputs.status.version");
    expect(completionAccepted).toBe(true);

    expect(acceptWorkflowExpressionCompletion(view)).toBe(false);
    const nextButton = document.createElement("button");
    document.body.append(nextButton);
    view.focus();
    view.contentDOM.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab", keyCode: 9, bubbles: true, cancelable: true }));
    expect(document.activeElement).toBe(nextButton);
    view.focus();
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: "ver" }, selection: { anchor: 3 }, userEvent: "input.type" });
    await expect.poll(() => completionStatus(view.state), { timeout: 1000 }).toBe("active");
    await wrapper.setProps({ value: "inputs.tenant", readonly: true });
    await nextTick();
    expect(view.state.doc.toString()).toBe("inputs.tenant");
    expect(view.state.readOnly).toBe(true);
    expect(completionStatus(view.state)).toBeNull();
    wrapper.unmount();
  });

  it("renders diagnostics supplied by workflow-level validation", () => {
    const diagnostics = [{ severity: "warning" as const, code: "SAMPLE_INDEX_REQUIRED", message: "需要下标", start: 0, end: 10 }];
    const wrapper = mount(WorkflowExpressionEditor, {
      props: { value: "outputs.status.version", variables: [], diagnostics },
    });
    expect(wrapper.text()).toContain("需要下标");
    wrapper.unmount();
  });
});

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
    const current = bundle.value!.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-current")!;
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
    const validation = vi.spyOn(api, "validateWorkflowExpressions").mockImplementation(async (expressions, environment) => {
      if (failOtherStep && "other" in environment.outputs) throw new Error("network failure");
      return {
        validations: expressions.map((item) => ({
          id: item.id,
          inferredType: { kind: "boolean" },
          diagnostics: [{ severity: "warning", code: "SAMPLE_INDEX_REQUIRED", message: `诊断 ${item.id}`, start: 0, end: 10 }],
        })),
      };
    });
    const bundle = ref<WorkflowBundle | null>(workflowBundle());
    const current = bundle.value!.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-current")!;
    const other = bundle.value!.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-other")!;
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
    const current = bundle.value!.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-current")!;
    current.topology[0]!.conditionExpression = "config.interface['name']";
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
    const current = bundle.value!.workflow.nodes.find((item): item is WorkflowStep => "stepType" in item && item.id === "step-current")!;
    current.topology[0]!.conditionExpression = "config.interfaces[1.5]";
    const scope = effectScope();
    const result = scope.run(() => useWorkflowExpressionValidation(bundle))!;

    await expect.poll(() => result.issues.value).toHaveLength(1);
    expect(result.issues.value[0]).toMatchObject({ code: "CONFIG_ARRAY_INDEX_INVALID", severity: "error" });
    scope.stop();
  });
});

async function completion(
  source: ReturnType<typeof createWorkflowExpressionCompletionSource>,
  doc: string,
  explicit: boolean,
): Promise<CompletionResult | null> {
  const state = EditorState.create({ doc, selection: { anchor: doc.length } });
  return await source(new CompletionContext(state, doc.length, explicit)) as CompletionResult | null;
}

function workflowBundle(): WorkflowBundle {
  const definition = collectionDefinition();
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 1,
      metadata: { name: "Variables", code: "", description: "Variables", symptom: "", industry: "", device: "", versions: [] },
      inputs: [parameter("global-tenant", "tenant"), parameter("global-empty", "")],
      deviceRoles: [],
      nodes: [
        step("step-other", "其他检查", [{ id: "call-other", key: "status", name: "接口状态", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} }]),
        step("step-current", "当前检查", [
          { id: "call-current", key: "status", name: "接口状态", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} },
          { id: "call-unscoped", key: "", name: "直接输出", definition: { id: definition.id, revision: 1 }, sampleCount: 1, inputBindings: {} },
          { id: "call-broken", key: "broken", name: "损坏引用", definition: { id: "missing", revision: 1 }, sampleCount: 1, inputBindings: {} },
        ]),
      ],
    },
    collectionSnapshots: [definition],
  };
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

function parameter(id: string, key: string) {
  return { id, key, required: true, schema: { type: "string" as const, title: key, description: "" } };
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
      { id: "output-empty", key: "", required: true, schema: { type: "string", title: "空字段", description: "" } },
    ],
  };
}
