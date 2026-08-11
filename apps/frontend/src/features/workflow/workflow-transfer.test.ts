// @vitest-environment jsdom
/* eslint-disable vue/one-component-per-file */

import { mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { ToastState, WorkflowImportBundle, WorkflowImportDetail } from "../../types";
import WorkflowImportModal from "./components/WorkflowImportModal.vue";
import { useWorkflowTransfer } from "./useWorkflowTransfer";
import { downloadWorkflowBundle, parseWorkflowImportFile } from "./workflowTransfer";

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

describe("Workflow transfer", () => {
  it("parses a portable bundle into a safe preview summary", () => {
    const candidate = parseWorkflowImportFile(JSON.stringify(importBundle()), "workflow.json");

    expect(candidate).toMatchObject({
      fileName: "workflow.json",
      workflowName: "Imported workflow",
      stepCount: 1,
      conclusionCount: 1,
      collectionCount: 1,
    });
    expect(() => parseWorkflowImportFile("{", "bad.json")).toThrow("合法的 JSON");
    expect(() => parseWorkflowImportFile('{"documentType":"workflow_bundle"}', "bad.json")).toThrow("可移植导入包");
  });

  it("downloads pretty UTF-8 JSON with the requested filename", async () => {
    let exported: Blob | undefined;
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn((blob: Blob) => { exported = blob; return "blob:workflow"; }),
      revokeObjectURL: vi.fn(),
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadWorkflowBundle(importBundle(), "bgp-workflow.json");

    expect(click).toHaveBeenCalledOnce();
    expect(exported?.type).toBe("application/json;charset=utf-8");
    expect(await readBlob(exported!)).toBe(`${JSON.stringify(importBundle(), null, 2)}\n`);
  });

  it("imports once, refreshes definitions and reports the created count", async () => {
    const detail = importDetail();
    vi.spyOn(api, "importWorkflow").mockResolvedValue(detail);
    vi.spyOn(api, "listWorkflowCollections").mockResolvedValue({ definitions: [] });
    const imported = vi.fn();
    const toasts: ToastState[] = [];
    let transfer!: ReturnType<typeof useWorkflowTransfer>;
    const wrapper = mount(defineComponent({
      setup() {
        transfer = useWorkflowTransfer({
          skillId: () => "skill-1",
          skillSlug: () => "bgp",
          dirty: () => false,
          readonly: () => false,
          imported,
          toast: (toast) => toasts.push(toast),
        });
        return () => h("div");
      },
    }));
    transfer.candidate.value = parseWorkflowImportFile(JSON.stringify(importBundle()), "workflow.json");

    await Promise.all([transfer.confirmImport(), transfer.confirmImport()]);

    expect(api.importWorkflow).toHaveBeenCalledOnce();
    expect(imported).toHaveBeenCalledWith(detail, []);
    expect(transfer.candidate.value).toBeNull();
    expect(toasts.at(-1)?.message).toContain("创建 1 个独立 Collection");
    wrapper.unmount();
  });

  it("accepts a completed import even when the Catalog refresh fails", async () => {
    const detail = importDetail();
    vi.spyOn(api, "importWorkflow").mockResolvedValue(detail);
    vi.spyOn(api, "listWorkflowCollections").mockRejectedValue(new Error("offline"));
    const imported = vi.fn();
    const toasts: ToastState[] = [];
    let transfer!: ReturnType<typeof useWorkflowTransfer>;
    const wrapper = mount(defineComponent({
      setup() {
        transfer = useWorkflowTransfer({
          skillId: () => "skill-1", skillSlug: () => "bgp", dirty: () => false, readonly: () => false,
          imported, toast: (toast) => toasts.push(toast),
        });
        return () => h("div");
      },
    }));
    transfer.candidate.value = parseWorkflowImportFile(JSON.stringify(importBundle()), "workflow.json");

    await transfer.confirmImport();

    expect(imported).toHaveBeenCalledWith(detail, detail.document.collectionSnapshots);
    expect(transfer.candidate.value).toBeNull();
    expect(toasts.at(-1)?.message).toContain("Catalog 刷新失败");
    wrapper.unmount();
  });

  it("shows the import target and counts in the confirmation modal", () => {
    mount(WorkflowImportModal, {
      attachTo: document.body,
      props: {
        candidate: parseWorkflowImportFile(JSON.stringify(importBundle()), "workflow.json"),
        currentWorkflowName: "Current workflow",
        busy: false,
        error: "",
      },
    });

    expect(document.body.textContent).toContain("Imported workflow");
    expect(document.body.textContent).toContain("Current workflow");
    expect(document.body.textContent).toContain("重复导入会再次创建新的 Collection");
  });
});

function importBundle(): WorkflowImportBundle {
  return {
    documentType: "workflow_import_bundle",
    workflow: {
      metadata: { name: "Imported workflow", code: "", description: "Test", symptom: "", industry: "", device: "", versions: [] },
      inputs: [],
      deviceRoles: [],
      nodes: [
        { id: "step-1", name: "Inspect", description: "", isStart: true, collectionCalls: [], topology: [], stepType: "expression" },
        { id: "end-1", name: "Done", rootCause: "", repairRecommendation: "", nodeType: "conclusion" },
      ],
    },
    collections: [{
      localId: "collection_1",
      key: "status",
      metadata: { name: "Status", description: "", industry: "", device: "", versions: [], tags: [] },
      spec: { collectionType: "cli", commandTemplate: "show status", outputSamples: [] },
      inputs: [],
      outputs: [],
    }],
  };
}

function importDetail(): WorkflowImportDetail {
  const source = importBundle();
  return {
    id: "workflow-1", skill_id: "skill-1", revision: 2, document_schema_version: 5,
    document: {
      documentType: "workflow_bundle",
      workflow: {
        id: "workflow-1",
        revision: 2,
        metadata: source.workflow.metadata,
        inputs: source.workflow.inputs,
        deviceRoles: source.workflow.deviceRoles,
        nodes: [
          { id: "step-1", name: "Inspect", description: "", isStart: true, collectionCalls: [], topology: [], stepType: "expression" },
          { id: "end-1", name: "Done", rootCause: "", repairRecommendation: "", nodeType: "conclusion" },
        ],
      },
      collectionSnapshots: [],
    },
    validation: { errors: [], warnings: [] },
    sync: { status: "workflow_changed", last_synced_revision: 1, last_synced_skill_version_id: null, last_synced_at: null },
    created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-12T00:00:00Z", created_by: "owner", last_saved_by: "owner",
    capabilities: { actor: "owner", subject_type: "user", groups: [], roles: ["owner"], effective_roles: ["owner"], permissions: { "skill.edit": true }, permission_sources: [] },
    import_result: { collection_mappings: [{ local_id: "collection_1", definition_id: "collection-new", revision: 1 }] },
  };
}

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = reject;
    reader.readAsText(blob);
  });
}
