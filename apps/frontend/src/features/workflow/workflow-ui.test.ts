// @vitest-environment jsdom
/* eslint-disable vue/one-component-per-file */

import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkflowBundle, WorkflowParameter } from "../../types";
import WorkflowMetadataEditor from "./components/WorkflowMetadataEditor.vue";
import WorkflowSettingsEditor from "./components/WorkflowSettingsEditor.vue";
import WorkflowPreviewPanel, { type PreviewTab } from "./components/WorkflowPreviewPanel.vue";
import WorkflowSidebar from "./components/WorkflowSidebar.vue";
import WorkflowToolbar from "./components/WorkflowToolbar.vue";

describe("Workflow UI state", () => {
  beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });
  it("keeps save success visible after dirty state clears", async () => {
    const wrapper = mount(WorkflowToolbar, {
      props: {
        title: "Interface workflow",
        lastSavedAt: "2026-07-12T02:12:12Z",
        dirty: true,
        readonly: false,
        saveState: "loading",
        syncing: false,
        issueCount: 1,
        canUndo: true,
        canRedo: false,
        canSync: false,
      },
    });

    const save = wrapper.get(".workflow-toolbar-save-command");
    expect(wrapper.get("time").attributes("datetime")).toBe("2026-07-12T02:12:12Z");
    expect(wrapper.text()).toContain("修改尚未写入服务端");
    expect(save.attributes("data-state")).toBe("loading");
    expect(save.attributes("aria-busy")).toBe("true");

    await wrapper.setProps({ dirty: false, saveState: "success" });
    expect(save.attributes("data-state")).toBe("success");
    expect(save.attributes("data-disabled")).toBeUndefined();
    expect(wrapper.text()).toContain("内容已写入服务端");
  });

  it("keeps destructive and persistence commands inert in read-only mode", async () => {
    const wrapper = mount(WorkflowToolbar, {
      props: {
        title: "Read-only workflow",
        dirty: true,
        readonly: true,
        saveState: "idle",
        syncing: false,
        issueCount: 0,
        canUndo: false,
        canRedo: false,
        canSync: false,
      },
    });

    const save = wrapper.get(".workflow-toolbar-save-command");
    expect(save.attributes("data-disabled")).toBe("true");
    expect(save.attributes("aria-disabled")).toBe("true");
    await save.trigger("click");
    expect(wrapper.emitted("save")).toBeUndefined();
    const importButton = wrapper.get('[aria-label="导入 Workflow"]');
    const exportButton = wrapper.get('[aria-label="导出 Workflow"]');
    expect(importButton.attributes("data-disabled")).toBe("true");
    expect(exportButton.attributes("data-disabled")).toBe("true");
  });

  it("exposes import and export only for a clean editable Workflow", async () => {
    const wrapper = mount(WorkflowToolbar, {
      props: {
        title: "Portable workflow", dirty: false, readonly: false, saveState: "idle", syncing: false,
        issueCount: 0, canUndo: false, canRedo: false, canSync: false,
      },
    });

    await wrapper.get('[aria-label="导出 Workflow"]').trigger("click");
    await wrapper.get('[aria-label="导入 Workflow"]').trigger("click");
    expect(wrapper.emitted("export")).toHaveLength(1);
    expect(wrapper.emitted("import")).toHaveLength(1);

    await wrapper.setProps({ dirty: true });
    expect(wrapper.get('[aria-label="导出 Workflow"]').attributes("data-disabled")).toBe("true");
    expect(wrapper.get('[aria-label="导入 Workflow"]').attributes("data-disabled")).toBe("true");
  });

  it("defaults the graph to horizontal and toggles the in-workbench expanded state", async () => {
    const expanded = ref(false);
    const tab = ref<PreviewTab>("graph");
    const GraphStub = defineComponent({
      name: "WorkflowGraph",
      props: {
        direction: { type: String, default: "RIGHT" },
        compact: { type: Boolean, default: false },
        expanded: { type: Boolean, default: false },
      },
      emits: ["toggle-expand"],
      setup(props, { emit }) {
        return () => h("div", {
          class: "workflow-graph-stub",
          "data-direction": props.direction,
          "data-compact": String(props.compact),
          "data-expanded": String(props.expanded),
        }, [h("button", { type: "button", onClick: () => emit("toggle-expand") }, "切换展开")]);
      },
    });
    const issue = {
      id: "issue-1",
      code: "missing_name",
      severity: "error" as const,
      message: "步骤名称不能为空。",
      selection: { type: "metadata" as const },
    };
    const Host = defineComponent({
      setup() {
        return () => h(WorkflowPreviewPanel, {
          bundle: workflowBundle(),
          catalog: [],
          issues: [issue],
          tab: tab.value,
          expanded: expanded.value,
          "onUpdate:tab": (value) => { tab.value = value; },
          "onUpdate:expanded": (value) => { expanded.value = value; },
        });
      },
    });
    const wrapper = mount(Host, { global: { stubs: { WorkflowGraph: GraphStub } } });

    expect(wrapper.get(".workflow-graph-stub").attributes()).toMatchObject({
      "data-direction": "RIGHT",
      "data-compact": "true",
      "data-expanded": "false",
    });
    await wrapper.get(".workflow-graph-stub button").trigger("click");
    expect(expanded.value).toBe(true);
    expect(wrapper.get(".workflow-graph-stub").attributes("data-compact")).toBe("false");
    await wrapper.get(".workflow-graph-stub button").trigger("click");
    expect(expanded.value).toBe(false);
    await wrapper.get(".workflow-graph-stub button").trigger("click");
    await wrapper.findAll('button[role="tab"]').find((button) => button.text() === "阅读视图")!.trigger("click");
    expect(tab.value).toBe("read");
    expect(expanded.value).toBe(false);
    const validationTab = wrapper.findAll('button[role="tab"]').find((button) => button.text().startsWith("校验"))!;
    expect(validationTab.find("b.has-errors").text()).toBe("1");
    await validationTab.trigger("click");
    expect(tab.value).toBe("validation");
    expect(wrapper.get(".workflow-validation-summary").text()).toContain("1 个错误");
    await wrapper.get(".workflow-validation-list > button").trigger("click");
    expect(wrapper.findComponent(WorkflowPreviewPanel).emitted("navigate")?.at(-1)).toEqual([issue.selection]);

    wrapper.unmount();
  });

  it("does not present a warning-only validation summary as an error", () => {
    const warning = {
      id: "warning-1",
      code: "missing_description",
      severity: "warning" as const,
      message: "建议补充步骤说明。",
      selection: { type: "metadata" as const },
    };
    const wrapper = mount(WorkflowPreviewPanel, {
      props: { bundle: workflowBundle(), catalog: [], issues: [warning], tab: "validation" },
    });

    expect(wrapper.get(".workflow-validation-summary strong").text()).toBe("0 个错误");
    expect(wrapper.get(".workflow-validation-summary strong").classes()).toContain("is-clear");
    expect(wrapper.get(".workflow-validation-summary span").classes()).toContain("has-warnings");
  });

  it("provides a replace tab with live preview and respects read-only mode", async () => {
    Object.defineProperty(window, "matchMedia", { configurable: true, value: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }) });
    const bundle = workflowBundle();
    bundle.workflow.nodes = [
      { id: "step-1", name: "检查状态", description: "", isStart: true, stepType: "expression", collectionCalls: [], topology: [{ id: "path-1", target: { id: "conclusion-1" }, conditionText: "", conditionExpression: "outputs.status == true" }] },
      { id: "conclusion-1", name: "异常结论", severity: "error", rootCause: "outputs.status 异常", repairRecommendation: "检查 outputs.status", nodeType: "conclusion" },
    ];
    const wrapper = mount(WorkflowPreviewPanel, { props: { bundle, catalog: [], issues: [], tab: "graph", readonly: true } });
    const replaceTab = wrapper.findAll('button[role="tab"]').find((button) => button.text() === "替换")!;
    expect(replaceTab.exists()).toBe(true);
    await replaceTab.trigger("click");
    await wrapper.get('input[aria-label="搜索内容"]').setValue("outputs.status");
    expect(wrapper.text()).toContain("3 个表达式");
    expect(wrapper.get(".workflow-replace-actions button").attributes("data-disabled")).toBe("true");
  });

  it("shows variables for the selected step and expands nested paths", async () => {
    const bundle = workflowBundle();
    bundle.workflow.inputs[0]!.schema = { type: "object", title: "接口", description: "", properties: { address: { type: "string", title: "地址", description: "" } }, required: ["address"], additionalProperties: false };
    bundle.workflow.nodes = [{ id: "step-1", name: "检查接口", description: "", isStart: true, stepType: "expression", collectionCalls: [], topology: [] }];
    const wrapper = mount(WorkflowPreviewPanel, { props: { bundle, catalog: [], issues: [], selection: { type: "step", id: "step-1" }, tab: "variables" } });
    expect(wrapper.text()).toContain("检查接口 的表达式环境");
    expect(wrapper.text()).toContain("inputs.interface");
    expect(wrapper.text()).toContain("inputs.site");
    const toggle = wrapper.get('button[aria-label="收起 inputs.interface"]');
    await toggle.trigger("click");
    expect(toggle.attributes("aria-expanded")).toBe("false");
    wrapper.unmount();
  });

  it("按精确定义版本去重展示并复制全部 CLI 命令", async () => {
    const bundle = workflowBundle();
    const first = { id: "collection-status", revision: 1, key: "status", metadata: { name: "状态 r1", description: "", industry: "", device: "", versions: [], tags: [] }, spec: { collectionType: "cli" as const, commandTemplate: "display status", outputSamples: [] }, inputs: [], outputs: [] };
    const second = { ...structuredClone(first), revision: 2, metadata: { ...first.metadata, name: "状态 r2" }, spec: { ...first.spec, commandTemplate: "display status verbose" } };
    bundle.workflow.nodes.push({
      id: "step-1", name: "检查状态", description: "", isStart: true, stepType: "expression", topology: [], collectionCalls: [
      { id: "call-1", key: "", name: "", definition: { id: first.id, revision: 1 }, sampleCount: 1, inputBindings: {} },
      { id: "call-2", key: "", name: "", definition: { id: first.id, revision: 1 }, sampleCount: 1, inputBindings: {} },
      { id: "call-3", key: "", name: "", definition: { id: second.id, revision: 2 }, sampleCount: 1, inputBindings: {} },
      ],
    });
    const wrapper = mount(WorkflowPreviewPanel, { props: { bundle, catalog: [first, second], issues: [], tab: "collections" } });

    expect(wrapper.findAll(".workflow-command-list article")).toHaveLength(2);
    await wrapper.findAll(".workflow-command-preview > header button")[0].trigger("click");
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("display status\ndisplay status verbose");
  });

  it("shows inputs and device roles in one editor and keeps their actions separate", async () => {
    const wrapper = mount(WorkflowSettingsEditor, {
      attachTo: document.body,
      props: {
        inputs: [workflowInput("input-1", "interface")],
        roles: [{ id: "role-1", key: "device", name: "目标设备", description: "", required: true }],
        target: "inputs",
        readonly: false,
      },
    });
    await nextTick();

    expect(wrapper.get("h2").text()).toBe("全局输入");
    expect(wrapper.get("#workflow-inputs-heading").text()).toContain("输入参数 1");
    expect(wrapper.get("#workflow-roles-heading").text()).toContain("设备角色 1");
    expect(wrapper.findAll(".workflow-setting-field > span").map((item) => item.text())).toEqual([
      "角色 Key", "角色名称", "角色说明",
    ]);
    expect(wrapper.get('input[aria-label="参数变量名"]').attributes("placeholder")).toBe("interface_name");
    expect(wrapper.get('input[aria-label="角色 Key"]').attributes("placeholder")).toBe("primary");
    expect(wrapper.find('.workflow-schema-field-grid input[type="checkbox"]').exists()).toBe(false);
    expect(wrapper.find('.workflow-setting-row.is-role input[type="checkbox"]').exists()).toBe(true);
    expect(document.activeElement).toBe(wrapper.get('[aria-labelledby="workflow-inputs-heading"]').element);

    await wrapper.findAll("button").find((button) => button.text().includes("添加输入"))!.trigger("click");
    await wrapper.get('input[aria-label="参数变量名"]').setValue("interface_name");
    await wrapper.get('button[aria-label="删除输入"]').trigger("click");
    await wrapper.findAll("button").find((button) => button.text().includes("添加设备角色"))!.trigger("click");
    await wrapper.get('input[aria-label="角色名称"]').setValue("主设备");
    await wrapper.get('button[aria-label="删除设备角色"]').trigger("click");
    expect(wrapper.emitted("add-input")).toHaveLength(1);
    expect(wrapper.emitted("update-input")?.[0]).toEqual(["input-1", { key: "interface_name" }]);
    expect(wrapper.emitted("remove-input")?.[0]).toEqual(["input-1"]);
    expect(wrapper.emitted("add-role")).toHaveLength(1);
    expect(wrapper.emitted("update-role")?.[0]).toEqual(["role-1", { name: "主设备" }]);
    expect(wrapper.emitted("remove-role")?.[0]).toEqual(["role-1"]);

    await wrapper.setProps({ target: "roles" });
    await nextTick();
    expect(document.activeElement).toBe(wrapper.get('[aria-labelledby="workflow-roles-heading"]').element);
    wrapper.unmount();
  });

  it("edits the optional workflow symptom without exposing it elsewhere", async () => {
    const wrapper = mount(WorkflowMetadataEditor, {
      props: {
        metadata: { name: "接口排障", code: "", description: "检查接口。", symptom: "接口闪断", industry: "网络", device: "交换机", versions: [] },
        readonly: false,
      },
    });

    const symptom = wrapper.get('textarea[aria-label="问题现象"]');
    expect(symptom.element).toHaveProperty("value", "接口闪断");
    await symptom.setValue("接口频繁闪断");
    expect(wrapper.emitted("change")?.at(-1)).toEqual([{ symptom: "接口频繁闪断" }]);

    await wrapper.setProps({ readonly: true });
    expect(symptom.attributes()).toHaveProperty("disabled");
  });

  it("uses one sidebar entry with separate input and role counts", async () => {
    const wrapper = mount(WorkflowSidebar, {
      props: {
        bundle: workflowBundle(),
        selection: { type: "roles" },
        issues: [],
        readonly: false,
      },
    });

    const globalInputs = wrapper.get(".workflow-sidebar-root .workflow-sidebar-item.active");
    expect(globalInputs.text()).toContain("全局输入");
    expect(globalInputs.text()).toContain("输入 2 · 角色 1");
    expect(wrapper.findAll(".workflow-sidebar-root .workflow-sidebar-item").some((item) => item.text() === "设备角色")).toBe(false);

    await globalInputs.trigger("click");
    expect(wrapper.emitted("select")?.at(-1)).toEqual([{ type: "inputs" }]);
    wrapper.unmount();
  });

  it("filters outline nodes while keeping mutation controls disabled in read-only mode", async () => {
    const bundle = workflowBundle();
    bundle.workflow.nodes = [
      {
        id: "step-1",
        name: "检查接口",
        description: "Investigate timeout alarms",
        isStart: true,
        collectionCalls: [],
        topology: [],
        stepType: "script",
      },
      { id: "conclusion-1", name: "链路异常", rootCause: "丢包", repairRecommendation: "切换链路", nodeType: "conclusion" },
    ];
    const wrapper = mount(WorkflowSidebar, {
      props: { bundle, selection: { type: "metadata" }, issues: [], readonly: true },
    });

    expect(wrapper.get('button[aria-label="添加步骤"]').attributes()).toHaveProperty("disabled");
    expect(wrapper.get('button[aria-label="添加结论"]').attributes()).toHaveProperty("disabled");
    expect(wrapper.text()).not.toContain("Investigate timeout alarms");
    expect(wrapper.text()).not.toContain("丢包");
    expect(wrapper.text()).not.toContain("切换链路");
    await wrapper.get('input[aria-label="搜索工作流节点"]').setValue("TIMEOUT");
    expect(wrapper.findAll(".workflow-sidebar-node")).toHaveLength(1);
    expect(wrapper.get(".workflow-sidebar-node").text()).toContain("检查接口");
    expect(wrapper.get(".workflow-drag-handle").attributes()).toHaveProperty("disabled");
    expect(wrapper.text()).toContain("没有匹配的结论");
  });
});

function workflowInput(id: string, key: string): WorkflowParameter {
  return { id, key, required: true, schema: { type: "string", title: key, description: "" } };
}

function workflowBundle(): WorkflowBundle {
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 1,
      metadata: { name: "Test", code: "", description: "Test", symptom: "", industry: "", device: "", versions: [] },
      inputs: [workflowInput("input-1", "interface"), workflowInput("input-2", "site")],
      deviceRoles: [{ id: "role-1", key: "device", name: "目标设备", description: "", required: true }],
      nodes: [],
    },
    collectionSnapshots: [],
  };
}
