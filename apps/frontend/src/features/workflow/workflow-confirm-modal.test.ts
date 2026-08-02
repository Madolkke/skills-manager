// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import WorkflowConfirmModal from "./components/WorkflowConfirmModal.vue";

describe("WorkflowConfirmModal", () => {
  it("uses a compact consequence layout and keeps both actions available", async () => {
    const wrapper = mount(WorkflowConfirmModal, {
      props: {
        title: "离开 Workflow 编辑器",
        description: "当前 Workflow 的修改尚未保存。离开后将无法恢复这些内容。",
        confirmLabel: "放弃并离开",
        tone: "danger",
      },
      global: { stubs: { Teleport: true } },
    });

    expect(wrapper.get(".modal-card").classes()).toContain("compact");
    expect(wrapper.get(".workflow-confirm-message").text()).toContain("离开后将无法恢复");
    expect(wrapper.get(".workflow-confirm-icon").classes()).toContain("danger");
    const actions = wrapper.get(".workflow-confirm-actions").findAll("button");
    expect(actions).toHaveLength(2);

    await actions[0].trigger("click");
    await actions[1].trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
    expect(wrapper.emitted("confirm")).toHaveLength(1);
  });
});
