// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import WorkflowCollectionInputRows from "./components/WorkflowCollectionInputRows.vue";
import WorkflowCollectionOutputRows from "./components/WorkflowCollectionOutputRows.vue";

describe("Workflow Collection 字段表格", () => {
  it("为输入参数提供 Schema 摘要和编辑入口", async () => {
    const wrapper = mount(WorkflowCollectionInputRows, {
      props: {
        items: [{ id: "input-interface", key: "", required: true, schema: { type: "string", title: "", description: "" } }],
        readonly: false,
      },
    });

    expect(wrapper.get(".workflow-field-table-head").text()).toContain("字段 Key");
    expect(wrapper.get(".workflow-field-table-head").text()).toContain("Schema");
    expect(wrapper.get('input[aria-label="参数 Key"]').attributes("placeholder")).toBe("interface_name");
    expect(wrapper.text()).toContain("string");

    await wrapper.get('input[aria-label="参数 Key"]').setValue("interface_name");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-interface", { key: "interface_name" }]);
  });

  it("按 Key、名称、Schema、必填顺序展示输出并支持只读态", async () => {
    const wrapper = mount(WorkflowCollectionOutputRows, {
      props: {
        items: [{ id: "output-version", key: "version", required: true, schema: { type: "string", title: "版本", description: "软件版本" } }],
        readonly: false,
      },
    });

    expect(wrapper.findAll(".workflow-field-table-head > span").map((item) => item.text())).toEqual([
      "字段 Key", "显示名称", "Schema", "必填", "",
    ]);
    expect(wrapper.get('input[aria-label="字段名称（Key）"]').classes()).toContain("workflow-key-input");
    expect(wrapper.text()).toContain("软件版本");

    await wrapper.get('input[aria-label="字段名称（Key）"]').setValue("software_version");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["output-version", { key: "software_version" }]);

    await wrapper.setProps({ readonly: true });
    expect(wrapper.findAll("input, select, button").every((item) => item.attributes("disabled") !== undefined)).toBe(true);
  });
});
