// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import WorkflowCollectionInputRows from "./components/WorkflowCollectionInputRows.vue";
import WorkflowCollectionOutputRows from "./components/WorkflowCollectionOutputRows.vue";

describe("Workflow Collection 字段表格", () => {
  it("为输入参数提供表头、示例和独立说明列", async () => {
    const wrapper = mount(WorkflowCollectionInputRows, {
      props: {
        items: [{ id: "input-interface", key: "", name: "", description: "", dataType: "string", required: true }],
        readonly: false,
      },
    });

    expect(wrapper.get(".workflow-field-table-head").text()).toContain("参数 Key");
    expect(wrapper.get(".workflow-field-table-head").text()).toContain("参数说明");
    expect(wrapper.get('input[aria-label="参数 Key"]').attributes("placeholder")).toBe("interface_name");
    expect(wrapper.get('input[aria-label="参数名称"]').attributes("placeholder")).toBe("接口名称");
    expect(wrapper.get('input[aria-label="参数说明"]').attributes("placeholder")).toContain("命令中的用途");

    await wrapper.get('input[aria-label="参数说明"]').setValue("待检查的接口名称");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-interface", { description: "待检查的接口名称" }]);
  });

  it("按 Key、类型、描述顺序编辑输出并支持只读态", async () => {
    const wrapper = mount(WorkflowCollectionOutputRows, {
      props: {
        items: [{ id: "output-version", key: "version", description: "软件版本", dataType: "string" }],
        readonly: false,
      },
    });

    expect(wrapper.findAll(".workflow-field-table-head > span").map((item) => item.text())).toEqual([
      "字段名称（Key）", "类型", "字段说明", "",
    ]);
    expect(wrapper.get('input[aria-label="字段名称（Key）"]').classes()).toContain("workflow-key-input");
    expect(wrapper.get('input[aria-label="字段说明"]').attributes("placeholder")).toContain("采集结果");

    await wrapper.get('input[aria-label="字段说明"]').setValue("设备当前软件版本");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["output-version", { description: "设备当前软件版本" }]);

    await wrapper.setProps({ readonly: true });
    expect(wrapper.findAll("input, select, button").every((item) => item.attributes("disabled") !== undefined)).toBe(true);
  });
});
