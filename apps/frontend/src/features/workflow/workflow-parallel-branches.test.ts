// @vitest-environment jsdom
import { shallowMount } from "@vue/test-utils";
import { effectScope } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { WorkflowBundle, WorkflowStep } from "../../types";
import WorkflowStepEditor from "./components/WorkflowStepEditor.vue";
import WorkflowTransitionList from "./components/WorkflowTransitionList.vue";
import { parseWorkflowBundle } from "./domain/schema";
import { newStep } from "./editorDefaults";
import { useWorkflowEditor } from "./useWorkflowEditor";

/** Build a minimal normalized document for editor and compatibility checks. */
function bundle(): WorkflowBundle {
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow", revision: 1,
      metadata: { name: "检查", code: "", description: "", symptom: "", industry: "", device: "", versions: [] },
      inputs: [], deviceRoles: [], nodes: [newStep(1)],
    },
    collectionSnapshots: [],
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("Workflow parallel branches", () => {
  it("defaults new and legacy steps to false and rejects non-booleans", () => {
    const document = bundle();
    expect((document.workflow.nodes[0] as WorkflowStep).parallelBranches).toBe(false);
    Reflect.deleteProperty(document.workflow.nodes[0]!, "parallelBranches");
    expect(parseWorkflowBundle(document).workflow.nodes[0]).toMatchObject({ parallelBranches: false });
    for (const value of [true, false]) {
      Object.assign(document.workflow.nodes[0]!, { parallelBranches: value });
      expect(parseWorkflowBundle(document).workflow.nodes[0]).toMatchObject({ parallelBranches: value });
    }
    for (const value of ["true", 0, 1, null]) {
      Object.assign(document.workflow.nodes[0]!, { parallelBranches: value });
      expect(() => parseWorkflowBundle(document)).toThrow();
    }
  });

  it("preserves the mode when updating and duplicating a step", () => {
    const scope = effectScope();
    const editor = scope.run(() => useWorkflowEditor(() => false))!;
    editor.bundle.value = bundle();
    const id = editor.bundle.value.workflow.nodes[0]!.id;
    editor.updateStep(id, { parallelBranches: true });
    editor.duplicateStep(id);
    expect(editor.bundle.value.workflow.nodes).toHaveLength(2);
    expect(editor.bundle.value.workflow.nodes.every((step) => (step as WorkflowStep).parallelBranches)).toBe(true);
    scope.stop();
  });

  it("edits the checkbox, disables it in read-only mode and displays the mode", async () => {
    vi.stubGlobal("IntersectionObserver", class {
      /** No layout observation is needed in jsdom. */
      observe(): void {}
      /** No resources are retained by the test observer. */
      disconnect(): void {}
    });
    const document = bundle();
    const step = document.workflow.nodes[0] as WorkflowStep;
    const wrapper = shallowMount(WorkflowStepEditor, { props: {
      step, bundle: document, catalog: [], currentDefinitionRefs: [], changes: [], issues: [], expressionDiagnostics: {},
      target: { type: "step", id: step.id }, readonly: false,
    } });
    const input = wrapper.findAll("label").find((label) => label.text().includes("非互斥执行"))!.get("input");
    await input.setValue(true);
    expect(wrapper.emitted("change")).toEqual([[{ parallelBranches: true }]]);
    await wrapper.setProps({ readonly: true, step: { ...step, parallelBranches: true } });
    expect(input.attributes("disabled")).toBeDefined();
    expect((input.element as HTMLInputElement).checked).toBe(true);
    const paths = shallowMount(WorkflowTransitionList, { props: {
      step, bundle: document, issues: [], diagnostics: {}, readonly: true, sectionNumber: "03",
    } });
    expect(paths.text()).toContain("分支执行：互斥");
    await paths.setProps({ step: { ...step, parallelBranches: true } });
    expect(paths.text()).toContain("非互斥（执行所有满足条件的分支）");
    paths.unmount();
    wrapper.unmount();
  });
});
