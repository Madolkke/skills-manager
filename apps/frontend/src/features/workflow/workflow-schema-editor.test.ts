// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import WorkflowJsonValueModal from "./components/WorkflowJsonValueModal.vue";
import WorkflowSchemaEditorModal from "./components/WorkflowSchemaEditorModal.vue";
import type { WorkflowJsonSchema } from "../../types";
import { workflowSchemaEditorType, workflowSchemasAssignable } from "./workflowJsonSchema";

afterEach(() => { document.body.innerHTML = ""; });

describe("Workflow Schema editor", () => {
  it("按字段结构区分字符串数组与复杂对象", () => {
    const complexSchemas: WorkflowJsonSchema[] = [
      { type: "object", title: "", description: "", properties: {}, required: [], additionalProperties: false },
      { type: "array", title: "", description: "", items: { type: "number", title: "", description: "" } },
      {
        type: "array", title: "", description: "",
        items: {
          type: "object", title: "", description: "", properties: {}, required: [], additionalProperties: false,
        },
      },
      {
        type: "array", title: "", description: "",
        items: {
          type: "array", title: "", description: "",
          items: { type: "boolean", title: "", description: "" },
        },
      },
      {
        type: "array", title: "", description: "",
        items: { "x-skillhub-legacy-loose": true },
        "x-skillhub-legacy-loose": true,
      },
    ];

    expect(complexSchemas.map(workflowSchemaEditorType)).toEqual([
      "complex", "complex", "complex", "complex", "complex",
    ]);
    expect(workflowSchemaEditorType({
      type: "array", title: "标签", description: "",
      items: { type: "string", title: "", description: "" },
      "x-skillhub-legacy-loose": true,
    })).toBe("string-array");
  });

  it("递归展示对象数组并按 Key 规范化确认结果", async () => {
    const wrapper = mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: {
        open: true,
        fieldKey: "rows",
        readonly: false,
        schema: {
          type: "array", title: "数据行", description: "表格数据",
          items: {
            type: "object", title: "行", description: "", additionalProperties: false,
            required: ["status"],
            properties: {
              status: { type: "string", title: "状态", description: "" },
              name: { type: "string", title: "名称", description: "" },
            },
          },
        },
      },
    });

    expect(document.body.textContent).toContain("数组元素");
    expect(document.body.textContent).toContain("对象属性");
    expect(document.body.querySelector(".modal-card.editor")).not.toBeNull();
    expect(document.body.querySelector('.workflow-schema-property input[type="checkbox"]')).toBeNull();
    const previewButton = [...document.body.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.includes("JSON Schema 预览"))!;
    expect(previewButton.getAttribute("aria-expanded")).toBe("false");
    await clickButton("JSON Schema 预览");
    expect(previewButton.getAttribute("aria-expanded")).toBe("true");
    expect(document.body.querySelector("pre")?.textContent).toContain('"additionalProperties": false');
    expect([...document.body.querySelectorAll(".modal-actions .ui-button")].at(-1)?.classList).toContain("is-primary");
    await clickButton("确认 Schema");

    const confirmed = wrapper.emitted("confirm")?.[0]?.[0] as { items: { properties: Record<string, unknown>; required: string[] } };
    expect(Object.keys(confirmed.items.properties)).toEqual(["name", "status"]);
    expect(confirmed.items.required).toEqual(["name", "status"]);
  });

  it("关闭未保存弹窗时直接丢弃且不触发确认", async () => {
    const wrapper = mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: { open: true, fieldKey: "value", readonly: false, schema: { type: "string", title: "值", description: "" } },
    });

    document.body.querySelector<HTMLButtonElement>('button[aria-label="关闭"]')!.click();
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(1);
    expect(wrapper.emitted("confirm")).toBeUndefined();
  });

  it("顶层只允许复杂类型且名称说明保留在行内编辑", () => {
    mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: {
        open: true, fieldKey: "rows", readonly: false,
        schema: { type: "array", title: "数据行", description: "表格数据", items: { type: "number", title: "数值", description: "" } },
      },
    });

    const basics = document.body.querySelector(".workflow-schema-modal-body > .workflow-schema-node > .workflow-schema-basics")!;
    expect([...basics.querySelectorAll("option")].map((option) => option.textContent)).toEqual(["object", "array"]);
    expect(basics.querySelectorAll("input")).toHaveLength(0);
  });

  it("复杂数组改为 string items 后输出标准字符串数组", async () => {
    const wrapper = mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: {
        open: true, fieldKey: "rows", readonly: false,
        schema: { type: "array", title: "数据行", description: "表格数据", items: { type: "number", title: "数值", description: "" } },
      },
    });

    const itemType = document.body.querySelector<HTMLSelectElement>(".workflow-schema-array-items .workflow-schema-basics select")!;
    itemType.value = "string";
    itemType.dispatchEvent(new Event("change"));
    await nextTick();
    await clickButton("确认 Schema");
    expect(wrapper.emitted("confirm")?.[0]?.[0]).toEqual({
      type: "array", title: "数据行", description: "表格数据",
      items: { type: "string", title: "数值", description: "" },
    });
  });

  it("拒绝重复 Key，并在重命名和删除后同步 required", async () => {
    const wrapper = mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: {
        open: true,
        fieldKey: "row",
        readonly: false,
        schema: {
          type: "object", title: "行", description: "", additionalProperties: false,
          required: ["name", "status"],
          properties: {
            name: { type: "string", title: "名称", description: "" },
            status: { type: "string", title: "状态", description: "" },
          },
        },
      },
    });

    const propertyKeys = [...document.body.querySelectorAll<HTMLInputElement>(".workflow-schema-property-head label:first-child input")];
    propertyKeys[1]!.value = "name";
    propertyKeys[1]!.dispatchEvent(new Event("change"));
    await nextTick();

    expect(propertyKeys[1]!.value).toBe("status");
    propertyKeys[1]!.value = "state";
    propertyKeys[1]!.dispatchEvent(new Event("change"));
    await nextTick();
    document.body.querySelectorAll<HTMLButtonElement>('button[aria-label="删除属性"]')[0]!.click();
    await nextTick();
    await clickButton("确认 Schema");
    expect(wrapper.emitted("confirm")?.[0]?.[0]).toMatchObject({
      properties: { state: expect.any(Object) },
      required: ["state"],
    });
  });

  it("JSON 固定值不匹配时警告但允许确认", async () => {
    const wrapper = mount(WorkflowJsonValueModal, {
      attachTo: document.body,
      props: {
        open: true, value: { count: "2" }, fieldName: "统计", readonly: false,
        schema: { type: "object", title: "统计", description: "", properties: { count: { type: "integer", title: "数量", description: "" } }, required: ["count"], additionalProperties: false },
      },
    });

    expect(document.body.textContent).toContain("与字段 Schema 不匹配");
    await clickButton("确认固定值");
    expect(wrapper.emitted("confirm")?.[0]).toEqual([{ count: "2" }]);
  });

  it("递归兼容规则允许 integer 赋给 number", () => {
    expect(workflowSchemasAssignable(
      { type: "array", title: "", description: "", items: { type: "integer", title: "", description: "" } },
      { type: "array", title: "", description: "", items: { type: "number", title: "", description: "" } },
    )).toBe(true);
  });
});

async function clickButton(label: string): Promise<void> {
  const button = [...document.body.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.includes(label));
  if (!button) throw new Error(`Button not found: ${label}`);
  button.click();
  await nextTick();
}
