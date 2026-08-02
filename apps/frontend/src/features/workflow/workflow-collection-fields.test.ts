// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { describe, expect, it } from "vitest";
import type { CollectionDefinition } from "../../types";
import WorkflowCollectionFields from "./components/WorkflowCollectionFields.vue";
import WorkflowCollectionInputRows from "./components/WorkflowCollectionInputRows.vue";
import WorkflowCollectionOutputRows from "./components/WorkflowCollectionOutputRows.vue";
import WorkflowConfirmModal from "./components/WorkflowConfirmModal.vue";
import WorkflowSchemaEditorModal from "./components/WorkflowSchemaEditorModal.vue";
import { newParameter } from "./editorDefaults";

describe("Workflow Collection 字段表格", () => {
  it("为简单输入参数提供行内 Schema 编辑", async () => {
    const wrapper = mount(WorkflowCollectionInputRows, {
      props: {
        items: [{ id: "input-interface", key: "", required: true, schema: { type: "string", title: "接口", description: "接口名称" } }],
        readonly: false,
      },
    });

    expect(wrapper.get(".workflow-field-table-head").text()).toContain("变量名");
    expect(wrapper.get(".workflow-field-table-head").text()).toContain("类型");
    expect(wrapper.get('input[aria-label="参数变量名"]').attributes("placeholder")).toBe("interface_name");
    expect(wrapper.get('select[aria-label="参数类型"]').element).toHaveProperty("value", "string");
    expect(wrapper.findAll("button").some((button) => button.text().includes("Schema"))).toBe(false);
    expect(wrapper.findAll('.workflow-row-actions button')).toHaveLength(1);
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false);

    await wrapper.get('input[aria-label="参数变量名"]').setValue("interface_name");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-interface", { key: "interface_name" }]);
    await wrapper.get('input[aria-label="参数显示名称"]').setValue("端口");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-interface", { schema: { type: "string", title: "端口", description: "接口名称" } }]);
    await wrapper.get('select[aria-label="参数类型"]').setValue("number");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-interface", { schema: { type: "number", title: "接口", description: "接口名称" } }]);
    await wrapper.get('select[aria-label="参数类型"]').setValue("complex");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-interface", {
      schema: {
        type: "object", title: "接口", description: "接口名称",
        properties: {}, required: [], additionalProperties: false,
      },
    }]);
    expect(wrapper.findComponent(WorkflowSchemaEditorModal).exists()).toBe(false);
  });

  it("按变量名、类型、名称和说明展示输出并支持只读态", async () => {
    const wrapper = mount(WorkflowCollectionOutputRows, {
      props: {
        items: [{ id: "output-version", key: "version", required: true, schema: { type: "string", title: "版本", description: "软件版本" } }],
        readonly: false,
      },
    });

    expect(wrapper.findAll(".workflow-field-table-head > span").map((item) => item.text())).toEqual([
      "变量名", "类型", "显示名称", "说明", "",
    ]);
    expect(wrapper.get('input[aria-label="输出变量名"]').classes()).toContain("workflow-key-input");
    expect(wrapper.get('input[aria-label="字段说明"]').element).toHaveProperty("value", "软件版本");
    expect(wrapper.text()).not.toContain("操作");
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false);

    await wrapper.get('input[aria-label="输出变量名"]').setValue("software_version");
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["output-version", { key: "software_version" }]);

    await wrapper.setProps({ readonly: true });
    expect(wrapper.findAll("input, select, button").every((item) => item.attributes("disabled") !== undefined)).toBe(true);
  });

  it("将所有 string items 数组作为简单字符串数组并保留历史可选语义", async () => {
    const wrapper = mount(WorkflowCollectionInputRows, {
      props: {
        items: [{
          id: "input-tags", key: "tags", required: false,
          schema: {
            type: "array", title: "标签", description: "标签列表", items: { type: "string", title: "标签项", description: "" },
            "x-skillhub-legacy-loose": true,
          },
        }],
        readonly: false,
      },
    });

    expect(wrapper.get('select[aria-label="参数类型"]').element).toHaveProperty("value", "string-array");
    expect(wrapper.findAll("button").some((button) => button.text().includes("Schema"))).toBe(false);
    await wrapper.get('input[aria-label="参数说明"]').setValue("设备标签");
    expect(wrapper.emitted("change")?.at(-1)?.[1]).not.toHaveProperty("required");
  });

  it("仅为复杂对象开放弹窗并确认丢弃嵌套结构", async () => {
    const wrapper = mount(WorkflowCollectionInputRows, {
      props: {
        items: [{
          id: "input-filter", key: "filter", required: true,
          schema: {
            type: "object", title: "过滤条件", description: "查询过滤条件", additionalProperties: false,
            required: ["name"], properties: { name: { type: "string", title: "名称", description: "" } },
          },
        }],
        readonly: false,
      },
      global: { stubs: { Teleport: true } },
    });

    expect(wrapper.get('select[aria-label="参数类型"]').element).toHaveProperty("value", "complex");
    expect(wrapper.get('button[aria-label="配置 Schema"]').attributes("aria-label")).toBe("配置 Schema");
    expect(wrapper.findAll('.workflow-row-actions button')).toHaveLength(2);
    await wrapper.get('select[aria-label="参数类型"]').setValue("string-array");
    expect(wrapper.emitted("change")).toBeUndefined();
    expect(wrapper.findComponent(WorkflowConfirmModal).exists()).toBe(true);

    wrapper.findComponent(WorkflowConfirmModal).vm.$emit("close");
    await nextTick();
    expect(wrapper.emitted("change")).toBeUndefined();
    await wrapper.get('select[aria-label="参数类型"]').setValue("string-array");
    wrapper.findComponent(WorkflowConfirmModal).vm.$emit("confirm");
    await nextTick();
    expect(wrapper.emitted("change")?.at(-1)).toEqual(["input-filter", {
      schema: {
        type: "array", title: "过滤条件", description: "查询过滤条件",
        items: { type: "string", title: "", description: "" },
      },
    }]);

    await wrapper.setProps({
      items: [{
        id: "input-filter", key: "filter", required: true,
        schema: {
          type: "object", title: "过滤条件", description: "查询过滤条件", additionalProperties: false,
          required: [], properties: {}, "x-skillhub-legacy-loose": true,
        },
      }],
    });
    expect(wrapper.get('button[aria-label="完善 Schema"]').attributes("aria-label")).toBe("完善 Schema");
  });

  it("新建 Workflow 输入仍默认必填", () => {
    expect(newParameter().required).toBe(true);
  });

  it("Collection 新字段默认必填且回显正文使用代码样式", async () => {
    const definition: CollectionDefinition = {
      id: "collection-memory", revision: 1, key: "memory",
      metadata: { name: "内存", description: "", industry: "", device: "", versions: [], tags: [] },
      spec: {
        collectionType: "cli", commandTemplate: "display memory",
        outputSamples: [{ id: "sample-1", name: "正常回显", stdout: "Memory: 42%", inputValues: {} }],
      },
      inputs: [], outputs: [],
    };
    const wrapper = mount(WorkflowCollectionFields, { props: { definition, readonly: false } });

    expect(wrapper.get(".workflow-sample-output").element.tagName).toBe("TEXTAREA");
    const sections = wrapper.findAll(".workflow-field-section");
    const inputSection = sections.find((section) => section.find("h3").exists() && section.find("h3").text() === "输入参数")!;
    const outputSection = sections.find((section) => section.find("h3").exists() && section.find("h3").text() === "输出字段")!;
    await inputSection.get("button").trigger("click");
    expect((wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition).inputs[0]?.required).toBe(true);
    await outputSection.get("button").trigger("click");
    expect((wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition).outputs[0]?.required).toBe(true);
  });
});
