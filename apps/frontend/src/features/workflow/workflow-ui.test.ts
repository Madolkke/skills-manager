// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick } from "vue";
import { describe, expect, it } from "vitest";
import type { WorkflowBundle, WorkflowParameter } from "../../types";
import WorkflowSettingsEditor from "./components/WorkflowSettingsEditor.vue";
import WorkflowSidebar from "./components/WorkflowSidebar.vue";
import WorkflowToolbar from "./components/WorkflowToolbar.vue";
import { useWorkflowLayout } from "./useWorkflowLayout";

describe("Workflow UI state", () => {
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

    const save = wrapper.get('button[title="保存 Workflow (Ctrl+S)"]');
    expect(wrapper.get("time").attributes("datetime")).toBe("2026-07-12T02:12:12Z");
    expect(wrapper.text()).toContain("修改尚未写入服务端");
    expect(save.attributes("data-state")).toBe("loading");
    expect(save.attributes("aria-busy")).toBe("true");

    await wrapper.setProps({ dirty: false, saveState: "success" });
    expect(save.attributes("data-state")).toBe("success");
    expect(save.attributes("data-disabled")).toBeUndefined();
    expect(wrapper.text()).toContain("内容已写入服务端");
  });

  it("collapses layout tracks without changing the remembered panel widths", () => {
    let layout: ReturnType<typeof useWorkflowLayout> | undefined;
    const Host = defineComponent({
      setup() {
        layout = useWorkflowLayout();
        return () => h("div");
      },
    });
    const wrapper = mount(Host);
    const expanded = layout!.gridStyle.value.gridTemplateColumns;

    layout!.toggle("left");
    expect(layout!.gridStyle.value.gridTemplateColumns).toContain("0px 20px");
    layout!.toggle("left");
    expect(layout!.gridStyle.value.gridTemplateColumns).toBe(expanded);

    wrapper.unmount();
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
    expect(document.activeElement).toBe(wrapper.get('[aria-labelledby="workflow-inputs-heading"]').element);

    await wrapper.findAll("button").find((button) => button.text().includes("添加输入"))!.trigger("click");
    await wrapper.get('input[aria-label="输入名称"]').setValue("接口名称");
    await wrapper.get('button[aria-label="删除输入"]').trigger("click");
    await wrapper.findAll("button").find((button) => button.text().includes("添加设备角色"))!.trigger("click");
    await wrapper.get('input[aria-label="角色名称"]').setValue("主设备");
    await wrapper.get('button[aria-label="删除设备角色"]').trigger("click");
    expect(wrapper.emitted("add-input")).toHaveLength(1);
    expect(wrapper.emitted("update-input")?.[0]).toEqual(["input-1", { name: "接口名称" }]);
    expect(wrapper.emitted("remove-input")?.[0]).toEqual(["input-1"]);
    expect(wrapper.emitted("add-role")).toHaveLength(1);
    expect(wrapper.emitted("update-role")?.[0]).toEqual(["role-1", { name: "主设备" }]);
    expect(wrapper.emitted("remove-role")?.[0]).toEqual(["role-1"]);

    await wrapper.setProps({ target: "roles" });
    await nextTick();
    expect(document.activeElement).toBe(wrapper.get('[aria-labelledby="workflow-roles-heading"]').element);
    wrapper.unmount();
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
});

function workflowInput(id: string, key: string): WorkflowParameter {
  return { id, key, name: key, description: "", dataType: "string", required: true };
}

function workflowBundle(): WorkflowBundle {
  return {
    documentType: "workflow_bundle",
    workflow: {
      id: "workflow-1",
      revision: 1,
      metadata: { name: "Test", code: "", description: "Test", industry: "", device: "", versions: [] },
      inputs: [workflowInput("input-1", "interface"), workflowInput("input-2", "site")],
      deviceRoles: [{ id: "role-1", key: "device", name: "目标设备", description: "", required: true }],
      nodes: [],
    },
    collectionSnapshots: [],
  };
}
