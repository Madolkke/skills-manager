// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { CollectionDefinition } from "../../types";
import WorkflowCommandInstanceModal from "./components/WorkflowCommandInstanceModal.vue";
import WorkflowCollectionFields from "./components/WorkflowCollectionFields.vue";
import WorkflowCommandSourceNotice from "./components/WorkflowCommandSourceNotice.vue";

const definition: CollectionDefinition = {
  id: "preview", revision: 1, key: "routes", sourceSystemCommandId: "system", sourceBindingMode: "concrete-command",
  metadata: { name: "路由", description: "来源说明", industry: "", device: "", versions: [], tags: [] },
  spec: { collectionType: "cli", commandTemplate: "show routes", commandParameterSyntax: "angle-v1", outputSamples: [] },
  inputs: [], outputs: [],
};

describe("具体命令确认", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("区分动态提示、不匹配提醒和请求失败，更新命令后清除旧提示", async () => {
    vi.useFakeTimers();
    vi.spyOn(api, "previewCommandInstance")
      .mockResolvedValueOnce({ definition, warnings: [{ code: "COMMAND_MATCH_DYNAMIC", message: "无法确认运行时匹配" }] })
      .mockResolvedValueOnce({ definition, warnings: [{ code: "COMMAND_SOURCE_MISMATCH", message: "与来源不匹配" }] })
      .mockRejectedValueOnce(new Error("网络不可用"));
    const wrapper = mount(WorkflowCommandSourceNotice, { props: { sourceId: "system", command: "show <vrf>" } });
    await vi.advanceTimersByTimeAsync(310);
    expect(wrapper.get('[role="status"]').text()).toContain("动态参数");
    await wrapper.setProps({ command: "other" });
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
    await vi.advanceTimersByTimeAsync(310);
    expect(wrapper.get('[role="status"]').text()).toContain("匹配提醒");
    await wrapper.setProps({ command: "show routes" });
    await vi.advanceTimersByTimeAsync(310);
    expect(wrapper.get('[role="alert"]').text()).toContain("检查失败网络不可用");
    wrapper.unmount();
  });

  it("只接受当前预览，非法命令保留文本且禁止添加", async () => {
    vi.useFakeTimers();
    const requests: Array<(value: { definition: CollectionDefinition; warnings: [] }) => void> = [];
    vi.spyOn(api, "previewCommandInstance").mockImplementation(() => new Promise((resolve) => requests.push(resolve)));
    const wrapper = mount(WorkflowCommandInstanceModal, { props: { commandId: "system" }, global: { stubs: { Modal: { template: "<div><slot /></div>" } } } });
    const input = wrapper.get("input");
    const confirm = () => wrapper.findAll("button").find((button) => button.text().includes("确认命令"))!;
    await input.setValue("show routes");
    await vi.advanceTimersByTimeAsync(260);
    await input.setValue("show routes detail");
    requests[0]!({ definition, warnings: [] });
    await flushPromises();
    expect(confirm().attributes("disabled")).toBeDefined();
    await vi.advanceTimersByTimeAsync(260);
    const current = structuredClone(definition);
    if (current.spec.collectionType === "cli") current.spec.commandTemplate = "show routes detail";
    requests[1]!({ definition: current, warnings: [] });
    await flushPromises();
    await confirm().trigger("click");
    expect(wrapper.emitted("confirm")?.[0]?.[0]).toEqual(current);
    await input.setValue("show <broken");
    expect(input.element.value).toBe("show <broken");
    expect(confirm().attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });

  it("来源字段只读、实例命令可编辑，全局只读禁止编辑", async () => {
    const wrapper = mount(WorkflowCollectionFields, { props: { definition, readonly: false } });
    expect(wrapper.get('[data-workflow-field="metadata.name"] input').attributes("disabled")).toBeDefined();
    expect(wrapper.get(".workflow-command-input").attributes("disabled")).toBeUndefined();
    await wrapper.setProps({ readonly: true });
    expect(wrapper.get(".workflow-command-input").attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });
});
