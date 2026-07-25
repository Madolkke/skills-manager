// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { defineComponent, h, ref } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { ToastState, WorkflowBundle, WorkflowDetail } from "../../types";
import { useWorkflowEditor } from "./useWorkflowEditor";
import { useWorkflowPersistence } from "./useWorkflowPersistence";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("Workflow persistence", () => {
  it("accepts a save without losing selection or editor scroll", async () => {
    vi.useFakeTimers();
    const initial = workflowDetail(1);
    const saved = workflowDetail(2);
    saved.document.workflow.metadata.name = "Updated workflow";
    vi.spyOn(api, "getWorkflow").mockResolvedValue(initial);
    vi.spyOn(api, "listWorkflowCollections").mockResolvedValue({ definitions: [] });
    vi.spyOn(api, "saveWorkflow").mockResolvedValue(saved);
    const harness = mountPersistence();

    await harness.persistence.load();
    harness.editor.selection.value = { type: "step", id: "step-1" };
    harness.editor.updateMetadata({ name: "Updated workflow" });
    harness.editorPane.value!.scrollTop = 184;
    await harness.persistence.save();

    expect(api.saveWorkflow).toHaveBeenCalledWith("skill-1", expect.objectContaining({
      document: expect.objectContaining({ workflow: expect.objectContaining({ metadata: expect.objectContaining({ name: "Updated workflow" }) }) }),
    }));
    expect(harness.detail.value?.revision).toBe(2);
    expect(harness.editor.selection.value).toEqual({ type: "step", id: "step-1" });
    expect(harness.editorPane.value?.scrollTop).toBe(184);
    expect(harness.editor.dirty.value).toBe(false);
    expect(harness.persistence.saveFeedback.value).toBe("success");
    expect(harness.refresh).toHaveBeenCalledOnce();
    expect(harness.toasts.at(-1)).toEqual({ tone: "success", message: "Workflow revision 2 已保存。" });

    await vi.advanceTimersByTimeAsync(900);
    expect(harness.persistence.saveFeedback.value).toBe("idle");
    harness.wrapper.unmount();
  });

  it("keeps sync context and closes the modal only after the request succeeds", async () => {
    const initial = workflowDetail(1);
    const synced = workflowDetail(2);
    vi.spyOn(api, "getWorkflow").mockResolvedValueOnce(initial).mockResolvedValueOnce(synced);
    vi.spyOn(api, "listWorkflowCollections").mockResolvedValue({ definitions: [] });
    vi.spyOn(api, "syncWorkflow").mockResolvedValue({
      mode: "created",
      skill_id: "skill-1",
      skill_version_id: "version-2",
      workflow_revision: 2,
    });
    const harness = mountPersistence();

    await harness.persistence.load();
    harness.editor.selection.value = { type: "step", id: "step-1" };
    await harness.persistence.sync({ version: "0.0.2", change_summary: "Sync workflow." });

    expect(harness.closeSync).toHaveBeenCalledOnce();
    expect(harness.editor.selection.value).toEqual({ type: "step", id: "step-1" });
    expect(harness.refresh).toHaveBeenCalledOnce();
    expect(harness.toasts.at(-1)).toEqual({ tone: "success", message: "已生成新版本" });
    expect(harness.persistence.syncError.value).toBe("");
    harness.wrapper.unmount();
  });

  it("does not close sync UI or discard errors when persistence fails", async () => {
    vi.spyOn(api, "syncWorkflow").mockRejectedValue(new Error("Provider unavailable"));
    const harness = mountPersistence();

    await harness.persistence.sync({ version: "0.0.2", change_summary: "Sync workflow." });

    expect(harness.closeSync).not.toHaveBeenCalled();
    expect(harness.refresh).not.toHaveBeenCalled();
    expect(harness.persistence.syncError.value).toBe("Provider unavailable");
    expect(harness.persistence.syncing.value).toBe(false);
    harness.wrapper.unmount();
  });
});

function mountPersistence() {
  const detail = ref<WorkflowDetail | null>(null);
  const editorPane = ref<HTMLElement | null>(document.createElement("main"));
  const refresh = vi.fn();
  const closeSync = vi.fn();
  const toasts: ToastState[] = [];
  let editor!: ReturnType<typeof useWorkflowEditor>;
  let persistence!: ReturnType<typeof useWorkflowPersistence>;
  const Host = defineComponent({
    setup() {
      editor = useWorkflowEditor(() => false);
      persistence = useWorkflowPersistence({
        skillId: () => "skill-1",
        detail,
        editor,
        editorPane,
        readonly: () => false,
        refresh,
        closeSync,
        toast: (toast) => toasts.push(toast),
      });
      return () => h("div");
    },
  });
  const wrapper = mount(Host);
  return { wrapper, detail, editor, editorPane, persistence, refresh, closeSync, toasts };
}

function workflowDetail(revision: number): WorkflowDetail {
  return {
    id: "workflow-1",
    skill_id: "skill-1",
    revision,
    document_schema_version: 1,
    document: workflowBundle(revision),
    validation: { errors: [], warnings: [] },
    sync: { status: "never_synced", last_synced_revision: null, last_synced_skill_version_id: null, last_synced_at: null },
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    created_by: "owner",
    last_saved_by: "owner",
    capabilities: { actor: "owner", subject_type: "user", groups: [], roles: ["owner"], effective_roles: ["owner"], permissions: { "skill.edit": true }, permission_sources: [] },
  };
}

function workflowBundle(revision: number): WorkflowBundle {
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision,
      metadata: { name: "Workflow", code: "", description: "Test", symptom: "", industry: "", device: "", versions: [] },
      inputs: [],
      deviceRoles: [],
      nodes: [{ id: "step-1", name: "Inspect", description: "", isStart: true, collectionCalls: [], topology: [], stepType: "script" }],
    },
    collectionSnapshots: [],
  };
}
