// @vitest-environment jsdom
/* eslint-disable vue/one-component-per-file */

import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  CollectionDefinition, WorkflowBundle, WorkflowDebugCase, WorkflowDebugRun,
  WorkflowStep,
} from "../../../types";
import type { WorkflowDebugApi } from "./api";
import WorkflowDebugCaseEditor from "./components/WorkflowDebugCaseEditor.vue";
import WorkflowDebugModal from "./components/WorkflowDebugModal.vue";
import WorkflowDebugScalarField from "./components/WorkflowDebugScalarField.vue";
import { newWorkflowDebugCaseDraft } from "./form";
import { useWorkflowStepDebug } from "./useWorkflowStepDebug";

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("Workflow single-step debug", () => {
  it("distinguishes absent, explicit null, false, and zero scalar values", async () => {
    const wrapper = mount(WorkflowDebugScalarField, {
      props: { label: "开关", schema: scalarSchema("boolean"), present: false },
    });

    await wrapper.get('input[type="checkbox"]').setValue(true);
    expect(wrapper.emitted("presence")?.at(-1)).toEqual([true, false]);
    await wrapper.setProps({ present: true, value: false });
    expect(wrapper.text()).toContain("false");
    await wrapper.findAll('input[type="checkbox"]').find((item) => item.element.parentElement?.textContent?.includes("null"))!.setValue(true);
    expect(wrapper.emitted("change")?.at(-1)).toEqual([null]);

    await wrapper.setProps({ schema: scalarSchema("number"), value: 0 });
    expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe("0");
  });

  it("offers only direct topology targets and persists authoring-side IDs", async () => {
    const bundle = debugBundle();
    const step = bundle.workflow.nodes[0] as WorkflowStep;
    const draft = newWorkflowDebugCaseDraft(step, 0);
    const wrapper = mount(WorkflowDebugCaseEditor, { props: { bundle, step, draft } });

    expect(wrapper.findAll('select option').map((item) => item.attributes("value"))).toEqual(["", "step-next", "conclusion-done"]);
    expect(wrapper.text()).not.toContain("Unrelated");
    const provide = wrapper.findAll(".workflow-debug-value-row")[0]!.get('input[type="checkbox"]');
    await provide.setValue(true);
    expect(wrapper.emitted("change")?.at(-1)?.[0]).toMatchObject({ workflow_inputs: { "input-enabled": false } });

    await wrapper.get(".workflow-debug-fixture-head input").setValue(true);
    expect(wrapper.emitted("change")?.at(-1)?.[0]).toMatchObject({
      collection_fixtures: { "call-status": { raw_output: [], outputs: {} } },
    });
  });

  it("allows case management while a dirty workflow blocks run start", async () => {
    const bundle = debugBundle();
    const step = bundle.workflow.nodes[0] as WorkflowStep;
    const item = debugCase();
    const client = fakeClient({ listCases: vi.fn().mockResolvedValue([item]) });
    const wrapper = mount(WorkflowDebugModal, {
      attachTo: document.body,
      props: { open: true, skillId: "skill-1", bundle, revision: 4, step, workflowDirty: true, client },
    });
    await flushPromises();

    expect(document.body.textContent).toContain("Workflow 存在未保存修改");
    const start = [...document.body.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent?.includes("开始调试"))!;
    expect(start.dataset.disabled).toBe("true");
    expect(document.body.querySelector<HTMLButtonElement>('button[aria-label="新建调试例"]')?.disabled).toBe(false);
    expect(document.body.querySelector<HTMLButtonElement>('button[aria-label="删除调试例"]')?.disabled).toBe(false);
    start.click();
    expect(client.startRun).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("deduplicates advance calls, paginates with opaque cursors, and cleans up polling", async () => {
    vi.useFakeTimers();
    const running = debugRun("running");
    const completed = debugRun("completed", true);
    let resolveAdvance!: (run: WorkflowDebugRun) => void;
    const advance = vi.fn().mockReturnValue(new Promise<WorkflowDebugRun>((resolve) => { resolveAdvance = resolve; }));
    const listRuns = vi.fn()
      .mockResolvedValueOnce({ items: [completed], next_cursor: "opaque-next" })
      .mockResolvedValueOnce({ items: [], next_cursor: null });
    const client = fakeClient({ advanceRun: advance, listRuns, startRun: vi.fn().mockResolvedValue({ run: running, reused: false }) });
    let state!: ReturnType<typeof useWorkflowStepDebug>;
    const Host = defineComponent({
      setup() {
        state = useWorkflowStepDebug({ skillId: () => "skill-1", stepId: () => "step-1", client, pollInterval: 500 });
        return () => h("div");
      },
    });
    const wrapper = mount(Host);

    await state.startRun("case-1");
    const first = state.advanceRun();
    const second = state.advanceRun();
    expect(advance).toHaveBeenCalledTimes(1);
    expect(first).toBe(second);
    resolveAdvance(completed);
    await first;

    await state.loadHistory("case-1");
    await state.loadHistory("case-1", false);
    expect(listRuns.mock.calls[1]?.[1]).toBe("opaque-next");
    await state.startRun("case-1");
    const cleanupRequest = state.advanceRun();
    const cleanupSignal = advance.mock.calls[1]?.[1] as AbortSignal;
    wrapper.unmount();
    expect(cleanupSignal.aborted).toBe(true);
    await cleanupRequest;
    await vi.advanceTimersByTimeAsync(1000);
    expect(advance).toHaveBeenCalledTimes(2);
  });

  it("uses the backend-provided polling interval", async () => {
    vi.useFakeTimers();
    const running = { ...debugRun("running"), poll_interval_seconds: 0.75 };
    const advance = vi.fn().mockResolvedValue(debugRun("completed", true));
    const client = fakeClient({
      startRun: vi.fn().mockResolvedValue({ run: running, reused: false }),
      advanceRun: advance,
    });
    let state!: ReturnType<typeof useWorkflowStepDebug>;
    const Host = defineComponent({
      setup() {
        state = useWorkflowStepDebug({ skillId: () => "skill-1", stepId: () => "step-1", client });
        return () => h("div");
      },
    });
    const wrapper = mount(Host);

    await state.startRun("case-1");
    await vi.advanceTimersByTimeAsync(749);
    expect(advance).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(advance).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});

function scalarSchema(type: "string" | "integer" | "number" | "boolean") {
  return { type, title: "", description: "" } as const;
}

function debugBundle(): WorkflowBundle {
  const definition: CollectionDefinition = {
    id: "collection-status", revision: 2, key: "status", metadata: { name: "状态采集", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display status", outputSamples: [] }, inputs: [],
    outputs: [{ id: "output-count", key: "count", required: true, schema: { type: "integer", title: "数量", description: "" } }],
  };
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1", revision: 4,
      metadata: { name: "调试工作流", code: "DEBUG", description: "", symptom: "", industry: "", device: "", versions: [] },
      inputs: [{ id: "input-enabled", key: "enabled", required: true, schema: { type: "boolean", title: "是否启用", description: "" } }],
      deviceRoles: [],
      nodes: [
        { id: "step-1", name: "检查状态", description: "", isStart: true, stepType: "expression", collectionCalls: [{ id: "call-status", key: "status", name: "状态采集", definition: { id: definition.id, revision: 2 }, sampleCount: 1, inputBindings: {} }], topology: [{ id: "path-next", target: { id: "step-next" }, conditionText: "", conditionExpression: "true" }, { id: "path-done", target: { id: "conclusion-done" }, conditionText: "", conditionExpression: "false" }] },
        { id: "step-next", name: "Next", description: "", isStart: false, stepType: "expression", collectionCalls: [], topology: [] },
        { id: "conclusion-done", name: "Done", rootCause: "", repairRecommendation: "", nodeType: "conclusion" },
        { id: "conclusion-unrelated", name: "Unrelated", rootCause: "", repairRecommendation: "", nodeType: "conclusion" },
      ],
    },
    collectionSnapshots: [definition],
  };
}

function debugCase(): WorkflowDebugCase {
  return { id: "case-1", skill_id: "skill-1", step_id: "step-1", name: "正常路径", description: "", expected_target_id: "step-next", workflow_inputs: {}, collection_fixtures: {}, created_at: "2026-08-03T00:00:00Z", updated_at: "2026-08-03T00:00:00Z" };
}

function debugRun(status: WorkflowDebugRun["status"], passed: boolean | null = null): WorkflowDebugRun {
  return { id: "run-1", case_id: "case-1", skill_id: "skill-1", step_id: "step-1", status, passed, task_id: "task-1", executor_run_id: "external-1", workflow_revision: 4, workflow_digest: "digest", expected_target_id: "step-next", latest_executor_status: null, error: null, created_at: "2026-08-03T00:00:00Z", updated_at: "2026-08-03T00:00:00Z", completed_at: status === "completed" ? "2026-08-03T00:00:01Z" : null };
}

function fakeClient(overrides: Partial<WorkflowDebugApi> = {}): WorkflowDebugApi {
  return {
    listCases: vi.fn().mockResolvedValue([]), createCase: vi.fn(), updateCase: vi.fn(), deleteCase: vi.fn(),
    startRun: vi.fn(), getRun: vi.fn(), advanceRun: vi.fn(), listRuns: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
    ...overrides,
  } as WorkflowDebugApi;
}
